from contextlib import contextmanager
import os
import tempfile

from async_asgi_testclient import TestClient
import pytest
import pytest_asyncio

from jubtools import config
from jubtools.systemtools import create_fastapi_app


@pytest.fixture
def write_config():
    @contextmanager
    def _write_config(base: str, **kwargs):
        with tempfile.TemporaryDirectory() as config_dir:
            config_file = os.path.join(config_dir, "base.toml")
            with open(config_file, "w") as f:
                f.write(base)

            for env, config in kwargs.items():
                env_dir = os.path.join(config_dir, "env")
                os.makedirs(env_dir, exist_ok=True)
                env_file = os.path.join(env_dir, f"{env}.toml")
                with open(env_file, "w") as f:
                    f.write(config)

            yield config_dir

    return _write_config


@pytest_asyncio.fixture(scope="session")
async def client():
    env='UnitTest'
    version='0.1.0'
    config.CONFIG = {
        'app_name': 'TestApp',
        'fastapi': {'disable_docs': False}
    }
    async with TestClient(application=create_fastapi_app(env=env, version=version)) as client:
        yield client