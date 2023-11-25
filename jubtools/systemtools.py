import datetime as dt
import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel

# from errors import AuthError, FSError

from jubtools import config, misctools, sqlt

logger = logging.getLogger(__name__)

APP_NAME = "GreekServer"
APP_START_TIME: dt.datetime


def create_fastapi_app():
    global APP_START_TIME

    fastapi_args = {"title": APP_NAME}
    if config.get("fastapi.disable_docs"):
        fastapi_args["openapi_url"] = None
    app = FastAPI(**fastapi_args)

    APP_START_TIME = dt.datetime.now()
    app.add_api_route("/health", health_handler, methods=["GET"])

    # app.add_exception_handler(FSError, custom_exception_handler)

    # app.add_event_handler("startup", psql.init)
    # app.add_event_handler("shutdown", psql.shutdown)
    app.add_middleware(sqlt.ConnMiddleware)

    # Add last, so it wraps everything
    app.add_middleware(TimerMiddleware)

    return app


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
        version=os.environ["FS_VERSION"],
        env=os.environ["FS_ENV"],
    )


# def custom_exception_handler(request: Request, exc: FSError):
#     logger.warning(f"Exception: {exc}")
#     if isinstance(exc, AuthError):
#         return RedirectResponse(url="/", status_code=303)
#     else:
#         return PlainTextResponse(status_code=exc.status_code, content=str(exc))


# Provide logging of all requests, and the time taken to process them
class TimerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Ignore calls that are not http requests (eg. startup)
        # Ignore health requests - we don't want to log these
        if scope["type"] != "http" or scope["path"] == "/api/health":
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
