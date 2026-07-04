# -*- coding: utf-8 -*-
"""Logging utility for Qtine."""

import logging
import os
import sys
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import Optional


class _MemoryLogHandler(logging.Handler):
    """Keep recent log entries in memory for WebUI / API access."""

    def __init__(self, capacity: int = 500):
        super().__init__()
        self._buf: deque = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(record.created),
                ),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name,
            }
            with self._lock:
                self._buf.append(entry)
        except Exception:
            pass

    def get_entries(
        self, level: str = "ALL", limit: int = 200
    ) -> list:
        with self._lock:
            items = list(self._buf)
        if level != "ALL":
            items = [e for e in items if e["level"] == level]
        if limit > 0:
            items = items[-limit:]
        return items

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


class QtineLogger:
    _instance: Optional["QtineLogger"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, level: str = "INFO", log_file: Optional[str] = None,
                 max_size_mb: int = 10, backup_count: int = 5):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.logger = logging.getLogger("Qtine")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.propagate = False

        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        console_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(console_handler)

        # In-memory buffer for WebUI / API
        self.memory_handler = _MemoryLogHandler(capacity=500)
        self.memory_handler.setFormatter(fmt)
        self.memory_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.memory_handler)

        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setFormatter(fmt)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def critical(self, msg: str):
        self.logger.critical(msg)

    def get_recent_logs(
        self, level: str = "ALL", limit: int = 200
    ) -> list:
        return self.memory_handler.get_entries(level, limit)

    def clear_logs(self) -> None:
        self.memory_handler.clear()


def get_logger() -> QtineLogger:
    return QtineLogger()
