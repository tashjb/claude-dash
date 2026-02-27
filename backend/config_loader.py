import yaml
import os
from typing import Any, Dict

CONFIG_PATH = os.getenv("CONFIG_PATH", "./config.yaml")

_config_cache: Dict[str, Any] = {}

def load_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache:
        return _config_cache

    if not os.path.exists(CONFIG_PATH):
        print(f"Warning: Config file not found at {CONFIG_PATH}. Using defaults.")
        return {}

    with open(CONFIG_PATH, "r") as f:
        _config_cache = yaml.safe_load(f) or {}

    return _config_cache

def get_connector_config(connector_name: str) -> Dict[str, Any]:
    config = load_config()
    return config.get("connectors", {}).get(connector_name, {})

def reload_config():
    global _config_cache
    _config_cache = {}
    return load_config()
