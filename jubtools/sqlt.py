import logging
import aiosqlite

log = logging.getLogger(__name__)

_SAVED_SQL = {}
DB_NAME = "db.sqlite"


class SQLError(Exception):
    pass


# Add ability to use 'row.value' syntax, which is shorter and easier than 'row["value"]'
class Row(aiosqlite.Row):
    def __getattr__(self, name):
        return self[name]


def store(name: str, query: str) -> None:
    log.info(f"Store sql {name}")
    if name in _SAVED_SQL:
        raise SQLError(f"Duplicate sql: {name}")
    _SAVED_SQL[name] = query


# Starlette middleware that acquires a db connection before the request, and releases it afterwards
class ConnMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Ignore calls that are not http requests (eg. startup)
        # Ignore /health requests - we don't need a db connection for these
        if scope["type"] != "http" or scope["path"] == "/health":
            return await self.app(scope, receive, send)

        async with aiosqlite.connect(DB_NAME) as conn:
            scope["db_conn"] = conn

            return await self.app(scope, receive, send)
