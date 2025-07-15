import json
import logging
import logging.config
import os
from typing import Any

import toml

logger = logging.getLogger(__name__)

CONFIG: dict = {}
CONFIG_DIR = "config/"
ENV_DIR = "env/"
BASE_CONFIG_FILE = "base.toml"


def init(env: str | None = None):
    # First, load from base config file
    base_filename = os.path.join(CONFIG_DIR, BASE_CONFIG_FILE)
    _load_from_file(base_filename)

    # Then, load from env file, overwriting if necessary
    if env is not None:
        env_filename = os.path.join(CONFIG_DIR, ENV_DIR, env) + ".toml"
        _load_from_file(env_filename)


def init_logging(log_config_file: str = "log_config.json"):
    filename = os.path.join(CONFIG_DIR, log_config_file)
    with open(filename) as f:
        log_config = json.load(f)
        logging.config.dictConfig(log_config)


# Get a value from config. Will handle nested key names separated by dots eg. 'db.port'
def get(full_key: str) -> Any:
    keys = full_key.split(".")
    vals = CONFIG
    for key in keys:
        if key not in vals:
            raise Exception(f"Config key not present: {full_key}")
        vals = vals[key.casefold()]
    return vals


def _load_from_file(filename: str):
    global CONFIG
    logger.info(f"Load config file: {filename}")
    config_dict = toml.load(filename)
    _merge_into(config_dict, CONFIG)


# Merge dicts recursively, overwriting values in dest with new values from src if present
def _merge_into(src: dict, dest: dict) -> None:
    for key, value in src.items():
        if isinstance(value, dict):
            # get node or create one
            node = dest.setdefault(key, {})
            _merge_into(value, node)
        else:
            dest[key.casefold()] = value
