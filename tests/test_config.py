import datetime as dt

from jubtools import config


def init_config(config_dir: str, env: str | None = None):
    config.CONFIG_DIR = config_dir
    config.CONFIG = {}

    config.init(env=env)


HAPPYPATH = """
[section_1]
key_1 = "value_1"
int_key = 123
datetime_key = 2023-01-01T14:00:00Z

[section_2]
bool_key = true
"""


def test_config_base_only(write_config):
    with write_config(base=HAPPYPATH) as config_dir:
        init_config(config_dir)

        assert config.get("section_1.key_1") == "value_1"
        assert config.get("section_1.int_key") == 123
        assert config.get("section_1.datetime_key") == dt.datetime(
            2023, 1, 1, 14, 0, 0, tzinfo=dt.timezone.utc
        )

        assert config.get("section_2.bool_key") is True


OVERWRITE_BASE = """
[section_1]
key_1 = "base_value_1"
key_2 = "base_value_2"
"""

OVERWRITE_ENV_1 = """
[section_1]
key_2 = "env_1_value_2"
"""


def test_env_config_overwrites_base(write_config):
    with write_config(base=OVERWRITE_BASE, env_1=OVERWRITE_ENV_1) as config_dir:
        init_config(config_dir, env="env_1")

        assert config.get("section_1.key_1") == "base_value_1"
        assert config.get("section_1.key_2") == "env_1_value_2"
