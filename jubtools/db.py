"""
Unified database interface that provides a common API for both PostgreSQL and SQLite.
Automatically detects the configured database type and delegates to the appropriate module.
"""

import logging
from enum import Enum
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


class DBModule(Enum):
    SQLITE = 1
    POSTGRES = 2


# Global variables to track the active database module
_db_module: DBModule | None = None
_psql = None
_sqlt = None


class DatabaseError(Exception):
    """Generic database error for unified interface"""

    pass


class Row:
    """
    Unified row interface that wraps the underlying database row implementation.
    Provides attribute-style access for both PostgreSQL and SQLite rows.
    """

    def __init__(self, row):
        self._row = row

    def __getattr__(self, name):
        return getattr(self._row, name)

    def __getitem__(self, key):
        return self._row[key]

    def __contains__(self, key):
        return key in self._row

    def keys(self):
        return self._row.keys()

    def values(self):
        return self._row.values()

    def items(self):
        return self._row.items()


def init_for_fastapi(db_module: DBModule, app: FastAPI):
    """
    Initialize the database module based on configuration.

    Args:
        db_module: The database module to use (DBModule.POSTGRES or DBModule.SQLITE)
    """
    global _db_module, _psql, _sqlt

    _db_module = db_module
    logger.info(f"Initializing database interface for {db_module.name}")

    if db_module == DBModule.POSTGRES:
        from jubtools import psql

        _psql = psql
        app.add_event_handler("startup", psql.init)
        app.add_event_handler("shutdown", psql.shutdown)
        app.add_middleware(psql.ConnMiddleware)
    elif db_module == DBModule.SQLITE:
        from jubtools import sqlt

        _sqlt = sqlt
        app.add_event_handler("startup", sqlt.init)
        app.add_middleware(sqlt.ConnMiddleware)
    else:
        raise DatabaseError(f"Unsupported database module: {db_module}")


def store(name: str, sql: str):
    """
    Store a named SQL query for later execution.

    Args:
        name: Name identifier for the SQL query
        sql: The SQL query string
    """
    if _db_module == DBModule.POSTGRES and _psql:
        _psql.store(name, sql)
    elif _db_module == DBModule.SQLITE and _sqlt:
        _sqlt.store(name, sql)
    else:
        raise DatabaseError("Database module not initialized")


async def execute(
    name: str, args: dict[str, Any] | None = None, log_args: bool = True
) -> list[Row]:
    """
    Execute a stored SQL query by name.

    Args:
        name: Name of the stored SQL query
        args: Parameters to pass to the query
        log_args: Whether to log the arguments

    Returns:
        List of Row objects
    """
    if args is None:
        args = {}

    if _db_module == DBModule.POSTGRES and _psql:
        rows = await _psql.execute(name, args, log_args)
        return [Row(row) for row in rows]
    elif _db_module == DBModule.SQLITE and _sqlt:
        rows = await _sqlt.execute(name, args, log_args)
        return [Row(row) for row in rows]
    else:
        raise DatabaseError("Database module not initialized")


async def execute_sql(sql: str, args: dict[str, Any] | None = None) -> list[Row]:
    """
    Execute raw SQL directly.

    Args:
        sql: The SQL query string
        args: Parameters to pass to the query

    Returns:
        List of Row objects
    """
    if args is None:
        args = {}

    if _db_module == DBModule.POSTGRES and _psql:
        rows = await _psql.exec ute_sql(sql, args)
        return [Row(row) for row in rows]
    elif _db_module == DBModule.SQLITE and _sqlt:
        rows = await _sqlt.execute_sql(sql, args)
        return [Row(row) for row in rows]
    else:
        raise DatabaseError("Database module not initialized")
