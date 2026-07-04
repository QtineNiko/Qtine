# -*- coding: utf-8 -*-
"""Configuration management for Qtine."""

import os
from typing import Any, Dict, Optional

import yaml


class Config:
    _instance: Optional["Config"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config.yml"):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._config_path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self._config_path):
            self._data = self._defaults()
            return
        with open(self._config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}
        defaults = self._defaults()
        self._merge_defaults(self._data, defaults)

    def _defaults(self) -> Dict[str, Any]:
        return {
            "server": {"host": "0.0.0.0", "port": 4990, "debug": False},
            "adapters": {
                "onebot_v11": {
                    "enabled": True,
                    "ws_path": "/onebot/v11",
                    "access_token": "",
                    "heartbeat_interval": 30,
                    "forward_ws_enabled": False,
                    "forward_ws_url": "ws://127.0.0.1:3001",
                    "reconnect_interval": 5,
                },
                "discord": {"enabled": False, "token": ""},
                "telegram": {"enabled": False, "bot_token": ""},
            },
            "plugins": {
                "dir": "./plugins",
                "autoload": [],
                "marketplace_url": "",
                "marketplace_mirrors": [],
            },
            "webui": {
                "enabled": True,
                "username": "admin",
                "password": "qtine123",
                "session_secret": "",
            },
            "storage": {
                "backend": "sqlite",
                "sqlite_path": "./data/qtine.db",
                "backup_interval_hours": 24,
                "backup_keep_count": 7,
            },
            "security": {
                "super_admins": [],
                "rate_limit": {
                    "enabled": True,
                    "messages_per_second": 5,
                    "burst": 10,
                },
                "sensitive_words": {"enabled": False, "word_file": ""},
                "blacklist": {
                    "enabled": True,
                    "users": [],
                    "groups": [],
                },
            },
            "ai": {
                "enabled": False,
                "provider": "openai",
                "api_key": "",
                "base_url": "",
                "model": "gpt-3.5-turbo",
                "max_tokens": 2048,
                "temperature": 0.7,
            },
            "logging": {
                "level": "INFO",
                "file": "./data/logs/qtine.log",
                "max_size_mb": 10,
                "backup_count": 5,
            },
        }

    def _merge_defaults(self, data: dict, defaults: dict) -> None:
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
            elif isinstance(value, dict) and isinstance(data[key], dict):
                self._merge_defaults(data[key], value)

    def save(self) -> None:
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._data, f, allow_unicode=True, default_flow_style=False
            )

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    @property
    def data(self) -> Dict[str, Any]:
        return self._data
