# -*- coding: utf-8 -*-
"""Storage backend for Qtine."""

from typing import Dict, Any, List, Optional
import json
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from qtine.utils.logger import get_logger


class StorageBackend(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...
    @abstractmethod
    def set(self, key: str, value: Any) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def keys(self, prefix: str = "") -> List[str]: ...
    @abstractmethod
    def close(self) -> None: ...


class MemoryStorage(StorageBackend):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def keys(self, prefix: str = "") -> List[str]:
        if prefix:
            return [k for k in self._data if k.startswith(prefix)]
        return list(self._data.keys())

    def close(self) -> None:
        self._data.clear()


class SQLiteStorage(StorageBackend):
    def __init__(self, db_path: str = "./data/qtine.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path, check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL DEFAULT (strftime('%s','now'))
            )
        """)
        conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT value FROM kv_store WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return row[0]

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            conn = self._get_conn()
            value_str = json.dumps(value, ensure_ascii=False)
            conn.execute(
                """INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                   VALUES (?, ?, ?)""",
                (key, value_str, time.time())
            )
            conn.commit()

    def delete(self, key: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            conn.commit()

    def keys(self, prefix: str = "") -> List[str]:
        conn = self._get_conn()
        if prefix:
            cursor = conn.execute(
                "SELECT key FROM kv_store WHERE key LIKE ?",
                (f"{prefix}%",)
            )
        else:
            cursor = conn.execute("SELECT key FROM kv_store")
        return [row[0] for row in cursor.fetchall()]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class Storage:
    _instance: "Storage" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._backend: StorageBackend = MemoryStorage()
        self.logger = get_logger()

    def init_backend(self, backend: str, **kwargs):
        if backend == "sqlite":
            self._backend = SQLiteStorage(
                db_path=kwargs.get("sqlite_path", "./data/qtine.db")
            )
        elif backend == "memory":
            self._backend = MemoryStorage()
        else:
            self.logger.warning(f"Unknown backend {backend}, using memory")
            self._backend = MemoryStorage()

    def get(self, key: str, default: Any = None) -> Any:
        return self._backend.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._backend.set(key, value)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def keys(self, prefix: str = "") -> List[str]:
        return self._backend.keys(prefix)

    def close(self) -> None:
        self._backend.close()
