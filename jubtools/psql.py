import json
import logging
import os
import time
from collections.abc import Iterable
from contextlib import asynccontextmanager
from contextvars import ContextVar

import asyncpg

from jubtools import config, misctools

logger = logging.getLogger(__name__)

_POOL = None
_SQL = {}
CONN = ContextVar("conn")


# Add ability to use 'row.value' syntax, which is shorter and easier than 'row["value"]'
class Row(asyncpg.Record):
    def __getattr__(self, name):
        return self[name]


async def init() -> None:
    global _POOL

    host = config.get("postgres.host")
    port = config.get("postgres.port")
    database = config.get("postgres.database")
    user = config.get("postgres.user")
    password = os.environ["PG_PASSWORD"]
    logger.info(f"Connecting to db {host}/{database}:{port} as {user}")

    _POOL = await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=2,
        record_class=Row,
        init=init_conn,
    )
    logger.info("DB connection pool created")


async def init_conn(conn):
    logger.info(f"Initialising connection: {conn}")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def shutdown():
    global _POOL

    if _POOL is not None:
        await _POOL.close()


def store(name, sql):
    global _SQL
    logger.info(f"Store sql: {name}")
    if name in _SQL:
        raise ValueError(f"Duplicate sql: {name}")
    _SQL[name] = sql


async def execute(name: str, args={}, log_args=True) -> list[Row]:
    conn = CONN.get()
    return await execute_with_conn(conn, name, args, log_args)


async def execute_with_conn(con, name, args={}, log_args=True) -> list[Row]:
    if log_args:
        logger.info(f"Execute sql {name} with args: {args}")
    else:
        logger.info(f"Execute sql {name}")
    sql, params = _get_sql(name, args)
    with misctools.Timer() as timer:
        rs = await con.fetch(sql, *params)
    logger.info(f"{len(rs)} row{'s' if len(rs) != 1 else ''} ({timer.elapsed:.2f}ms)")
    return rs


async def execute_sql(sql: str, args={}) -> list[Row]:
    conn = CONN.get()
    return await execute_sql_with_conn(conn, sql, args)


async def execute_sql_with_conn(conn, sql: str, args={}) -> list[Row]:
    logger.info(f"Execute custom sql with args: {args}")
    sql, params = _format_sql(sql, args)
    with misctools.Timer() as timer:
        rs = await conn.fetch(sql, *params)
    logger.info(f"{len(rs)} row{'s' if len(rs) != 1 else ''} ({timer.elapsed:.2f}ms)")
    return rs


def transaction(req):
    return Transaction(req.scope["db_conn"])


class Serial(dict):
    def __getitem__(self, key):
        return f"${list(self.keys()).index(key) + 1}"


# Get the sql from our saved list and process it with _format_sql
def _get_sql(name, args) -> tuple[str, Iterable]:
    global _SQL
    if name not in _SQL:
        raise Exception(f"Unknown sql: {name}")
    return _format_sql(_SQL[name], args)


# Convert named ("{name}") params in the sql into positional
# arguments ("$1"), as named arguments are not supported by asyncpg
def _format_sql(sql: str, args: dict) -> tuple[str, Iterable]:
    params = Serial(args)
    sql = sql.format_map(params)
    return (sql, params.values())


@asynccontextmanager
async def connect():
    global CONN
    async with _POOL.acquire() as conn:
        token = CONN.set(conn)
        try:
            yield
        finally:
            CONN.reset(token)


# Starlette middleware that acquires a db connection before the request, and releases it afterwards
class ConnMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Ignore calls that are not http requests (eg. startup)
        # Ignore /health requests - we don't need a db connection for these
        if scope["type"] != "http" or scope["path"] == "/health":
            return await self.app(scope, receive, send)

        async with connect():
            return await self.app(scope, receive, send)


# Basic transaction wrapper which adds timing and logging
class Transaction(asyncpg.transaction.Transaction):
    def __init__(self, conn):
        self.transaction = conn.transaction()

    async def __aenter__(self):
        logger.info("Start transaction")
        self._start = time.time()
        await self.transaction.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.time() - self._start) * 1000
        if exc_type is None:
            await self.transaction.commit()
            logger.info(f"Commit transaction (total {elapsed:.2f}ms)")
        else:
            await self.transaction.rollback()
            logger.info(f"Rollback transaction (total {elapsed:.2f}ms)")
