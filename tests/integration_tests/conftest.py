import pytest
from async_asgi_testclient import TestClient

from jubtools import config
from jubtools.systemtools import create_fastapi_app


@pytest.fixture
async def client():
    env = "UnitTest"
    version = "0.1.0"
    config.CONFIG = {"app_name": "TestApp", "fastapi": {"disable_docs": False}}
    async with TestClient(application=create_fastapi_app(env=env, version=version)) as client:
        yield client
