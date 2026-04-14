from dotenv import dotenv_values
from typing import Any
import os


class ConfigService:
    def __init__(self):
        # First try to get from environment variables (Docker)
        self._config = {}
        for key, value in os.environ.items():
            self._config[key] = value

        # Then try dotenv files for local development
        dotenv_config = dotenv_values()
        self._config.update(dotenv_config)

        # Debug: Print what we actually read
        print(f"DEBUG: GATEWAY_WS_URL = {self._config.get('GATEWAY_WS_URL')}")
        print(f"DEBUG: All env vars: {dict(os.environ)}")

        # Define default values for configuration keys
        self._defaults = {
            "REDIS_HOST": "localhost",
            "REDIS_PORT": 6379,
            "PUSH_INTERVAL": 5,
            "RECONNECT_DELAY": 5,
            "NODE_TYPE": "slave",
            "GATEWAY_WS_URL": None,
        }
        # Define keys that should be cast to integers
        self._int_keys = {"REDIS_PORT", "PUSH_INTERVAL", "RECONNECT_DELAY"}

    def get(self, key: str) -> Any:
        # 1. Try environment/dotenv (Docker env vars take precedence)
        val = self._config.get(key)

        # 2. Fallback to defaults
        if val is None:
            val = self._defaults.get(key)

        # 3. Cast to int if needed
        if key in self._int_keys and val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                # Fallback to default if cast fails
                return self._defaults.get(key)

        return val

    def __getattr__(self, name: str) -> Any:
        return self.get(name)
