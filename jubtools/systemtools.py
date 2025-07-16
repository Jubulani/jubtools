import datetime as dt
import logging
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jubtools import config, db, misctools
from jubtools.errors import ClientError, JubError

logger = logging.getLogger(__name__)

APP_START_TIME: dt.datetime
APP_VERSION: str
APP_ENV: str


def create_fastapi_app(env: str, version: str, db_module: db.DBModule | None = None) -> FastAPI:
    global APP_ENV
    global APP_VERSION
    global APP_START_TIME

    APP_ENV = env
    APP_VERSION = version

    fastapi_args: dict[str, Any] = {
        "title": config.get("app_name"),
        "version": version,
    }
    if "root_path" in config.get("fastapi"):
        fastapi_args["root_path"] = config.get("fastapi.root_path")
    if config.get("fastapi.disable_docs"):
        fastapi_args["openapi_url"] = None
    app = FastAPI(**fastapi_args)

    if "cors_allow_origin" in config.get("fastapi"):
        origins = config.get("fastapi.cors_allow_origin")
        logger.info(f"Enabling CORS for origins: {origins}")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    APP_START_TIME = dt.datetime.now()
    app.add_api_route("/health", health_handler, methods=["GET"])

    if db_module is not None:
        init_db_module(db_module, app)
    app.add_exception_handler(JubError, custom_exception_handler)

    # Add last, so it wraps everything
    app.add_middleware(TimerMiddleware)

    return app


def init_db_module(db_module: db.DBModule, app: FastAPI):
    """Use dynamic imports here, so we don't need to install all db drivers"""

    db.init(db_module)

    match db_module:
        case db.DBModule.SQLITE:
            from jubtools import sqlt

            app.add_event_handler("startup", sqlt.init)
            app.add_middleware(sqlt.ConnMiddleware)

        case db.DBModule.POSTGRES:
            from jubtools import psql

            app.add_event_handler("startup", psql.init)
            app.add_event_handler("shutdown", psql.shutdown)
            app.add_middleware(psql.ConnMiddleware)

        case _:
            raise ValueError(f"Unknown db_module: {db_module}")


class HealthResponse(BaseModel):
    request_ts: dt.datetime
    status: str
    uptime: str
    version: str
    env: str


async def health_handler(response: Response):
    global APP_START_TIME

    response.headers.update({"Cache-Control": "no-store"})
    return HealthResponse(
        request_ts=dt.datetime.now(),
        status="UP",
        uptime=str(dt.datetime.now() - APP_START_TIME),
        version=APP_VERSION,
        env=APP_ENV,
    )


def custom_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ClientError):
        logger.warning(exc)
    else:
        logger.exception(exc)

    http_status = 500
    if isinstance(exc, JubError):
        http_status = exc.http_status
    return JSONResponse(status_code=http_status, content={"error": {"message": str(exc)}})


# Provide logging of all requests, and the time taken to process them
class TimerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Ignore calls that are not http requests (eg. startup)
        # Ignore health requests - we don't want to log these
        if scope["type"] != "http" or scope["path"] == "/health":
            return await self.app(scope, receive, send)

        status_code = "???"

        def send_wrapper(response):
            nonlocal status_code
            if response["type"] == "http.response.start":
                status_code = response["status"]
            return send(response)

        path = scope["path"]
        if scope["query_string"] != b"":
            path += "?" + scope["query_string"].decode("utf-8")
        if len(path) > 200:
            path = path[:200] + "..."
        logger.info(f"START - {scope['method']} {path}")
        try:
            with misctools.Timer() as timer:
                result = await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            raise
        finally:
            logger.info(f"END - {scope['method']} {path} {status_code} ({timer.elapsed:.2f}ms)")
        return result
