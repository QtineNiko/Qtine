# -*- coding: utf-8 -*-
"""Storage backend for Qtine."""

from typing import Dict, Any, List, Optional
import json
import os
import sqlite3
import threading
import time
from collections import deque
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
    def add_message(self, message_id: str, group_id: Optional[str], user_id: str,
                    nickname: str, content: str, message_type: str = "text",
                    adapter: str = "") -> None: ...
    @abstractmethod
    def get_messages(self, group_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0,
                     user_id: Optional[str] = None,
                     keyword: Optional[str] = None) -> List[dict]: ...
    @abstractmethod
    def clear_messages(self, group_id: Optional[str] = None) -> int: ...
    @abstractmethod
    def get_message_groups(self) -> List[dict]: ...
    @abstractmethod
    def close(self) -> None: ...


class MemoryStorage(StorageBackend):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._messages: deque = deque(maxlen=2000)

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

    def add_message(self, message_id: str, group_id: Optional[str], user_id: str,
                    nickname: str, content: str, message_type: str = "text",
                    adapter: str = "") -> None:
        with self._lock:
            self._messages.append({
                "message_id": message_id,
                "group_id": group_id or "",
                "user_id": user_id,
                "nickname": nickname,
                "content": content,
                "message_type": message_type,
                "adapter": adapter,
                "timestamp": time.time(),
            })

    def get_messages(self, group_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0,
                     user_id: Optional[str] = None,
                     keyword: Optional[str] = None) -> List[dict]:
        with self._lock:
            results = list(self._messages)
        if group_id is not None:
            results = [m for m in results if m["group_id"] == group_id]
        if user_id:
            results = [m for m in results if m["user_id"] == user_id]
        if keyword:
            results = [m for m in results if keyword.lower() in m["content"].lower()]
        results.reverse()
        return results[offset:offset + limit]

    def clear_messages(self, group_id: Optional[str] = None) -> int:
        with self._lock:
            if group_id is None:
                count = len(self._messages)
                self._messages.clear()
                return count
            before = len(self._messages)
            self._messages = deque(
                [m for m in self._messages if m["group_id"] != group_id],
                maxlen=2000
            )
            return before - len(self._messages)

    def get_message_groups(self) -> List[dict]:
        groups = {}
        with self._lock:
            for m in self._messages:
                gid = m["group_id"] or "私聊"
                if gid not in groups:
                    groups[gid] = {"group_id": gid, "count": 0,
                                   "last_time": m["timestamp"]}
                groups[gid]["count"] += 1
                groups[gid]["last_time"] = m["timestamp"]
        result = list(groups.values())
        result.sort(key=lambda x: x["last_time"], reverse=True)
        return result

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                group_id TEXT,
                user_id TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                adapter TEXT DEFAULT '',
                timestamp REAL DEFAULT (strftime('%s','now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_msg_group
            ON message_history(group_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_msg_user
            ON message_history(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_msg_time
            ON message_history(timestamp DESC)
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

    def add_message(self, message_id: str, group_id: Optional[str], user_id: str,
                    nickname: str, content: str, message_type: str = "text",
                    adapter: str = "") -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO message_history
                   (message_id, group_id, user_id, nickname, content,
                    message_type, adapter, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (message_id, group_id, user_id, nickname, content,
                 message_type, adapter, time.time())
            )
            conn.commit()

    def get_messages(self, group_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0,
                     user_id: Optional[str] = None,
                     keyword: Optional[str] = None) -> List[dict]:
        conn = self._get_conn()
        query = "SELECT * FROM message_history WHERE 1=1"
        params: list = []
        if group_id is not None:
            query += " AND group_id = ?"
            params.append(group_id)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if keyword:
            query += " AND content LIKE ?"
            params.append(f"%{keyword}%")
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def clear_messages(self, group_id: Optional[str] = None) -> int:
        with self._lock:
            conn = self._get_conn()
            if group_id is None:
                cursor = conn.execute("SELECT COUNT(*) FROM message_history")
                count = cursor.fetchone()[0]
                conn.execute("DELETE FROM message_history")
            else:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM message_history WHERE group_id = ?",
                    (group_id,)
                )
                count = cursor.fetchone()[0]
                conn.execute(
                    "DELETE FROM message_history WHERE group_id = ?",
                    (group_id,)
                )
            conn.commit()
            return count

    def get_message_groups(self) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT group_id, COUNT(*) as count, MAX(timestamp) as last_time
            FROM message_history
            GROUP BY group_id
            ORDER BY last_time DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

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

    def add_message(self, message_id: str, group_id: Optional[str], user_id: str,
                    nickname: str, content: str, message_type: str = "text",
                    adapter: str = "") -> None:
        self._backend.add_message(message_id, group_id, user_id, nickname,
                                  content, message_type, adapter)

    def get_messages(self, group_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0,
                     user_id: Optional[str] = None,
                     keyword: Optional[str] = None) -> List[dict]:
        return self._backend.get_messages(group_id, limit, offset, user_id, keyword)

    def clear_messages(self, group_id: Optional[str] = None) -> int:
        return self._backend.clear_messages(group_id)

    def get_message_groups(self) -> List[dict]:
        return self._backend.get_message_groups()

    def close(self) -> None:
        self._backend.close()
