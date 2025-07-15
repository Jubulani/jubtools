import os
import tempfile
from contextlib import contextmanager

import pytest


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
