import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar

import aiosqlite

from jubtools import config, misctools

logger = logging.getLogger(__name__)

_SAVED_SQL = {}
DB_PATH: str
CONN = ContextVar("conn")


def init():
    global DB_PATH

    DB_PATH = config.get("db.sqlite.path")
    logger.info(f"Using sqlite db {DB_PATH}")


class SQLError(Exception):
    pass


# Add ability to use 'row.value' syntax, which is shorter and easier than 'row["value"]'
class Row(aiosqlite.Row):
    def __getattr__(self, name):
        return self[name]


def store(name: str, query: str) -> None:
    logger.info(f"Store sql {name}")
    if name in _SAVED_SQL:
        raise SQLError(f"Duplicate sql: {name}")
    _SAVED_SQL[name] = query


async def execute(name: str, args={}, log_args=True) -> list[Row]:
    conn = CONN.get()
    return await execute_with_conn(conn, name, args, log_args)


async def execute_with_conn(conn, name, args={}, log_args=True) -> list[Row]:
    if log_args:
        logger.info(f"Execute sql {name} with args: {args}")
    else:
        logger.info(f"Execute sql {name}")
    sql, params = _get_sql(name, args)
    with misctools.Timer() as timer:
        conn.row_factory = Row
        cursor = await conn.execute(sql, params)
        rs = await cursor.fetchall()
    logger.info(f"{len(rs)} row{'s' if len(rs) != 1 else ''} ({timer.elapsed:.2f}ms)")
    return rs


async def execute_sql(sql: str, args={}) -> list[Row]:
    conn = CONN.get()
    return await execute_sql_with_conn(conn, sql, args)


async def execute_sql_with_conn(conn, sql: str, args={}) -> list[Row]:
    logger.info(f"Execute custom sql with args: {args}")
    sql, params = _format_sql(sql, args)
    with misctools.Timer() as timer:
        conn.row_factory = Row
        cursor = await conn.execute(sql, params)
        rs = await cursor.fetchall()
    logger.info(f"{len(rs)} row{'s' if len(rs) != 1 else ''} ({timer.elapsed:.2f}ms)")
    return rs


def _get_sql(name, args) -> tuple[str, dict]:
    if name not in _SAVED_SQL:
        raise SQLError(f"Unknown sql: {name}")
    return _format_sql(_SAVED_SQL[name], args)


def _format_sql(sql: str, args: dict) -> tuple[str, dict]:
    # SQLite supports named parameters natively, so we can use them directly
    # Convert {param} format to :param format that SQLite expects
    formatted_sql = sql
    for key in args:
        formatted_sql = formatted_sql.replace(f"{{{key}}}", f":{key}")
    return (formatted_sql, args)


@asynccontextmanager
async def connect():
    global CONN
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = Row
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
