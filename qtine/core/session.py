# -*- coding: utf-8 -*-
"""Session management for Qtine."""

from typing import Dict, Optional
import time
import threading
from qtine.utils.models import Session
from qtine.utils.logger import get_logger


class SessionManager:
    _instance: "SessionManager" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self.logger = get_logger()
        self._gc_interval = 300
        self._last_gc = time.time()

    def create(self, user_id: str, adapter: str,
               ttl: float = 3600.0) -> Session:
        session = Session(
            user_id=user_id,
            adapter=adapter,
            expires_at=time.time() + ttl
        )
        key = self._make_key(user_id, adapter)
        with self._lock:
            self._sessions[key] = session
        return session

    def get(self, user_id: str, adapter: str) -> Optional[Session]:
        self._maybe_gc()
        key = self._make_key(user_id, adapter)
        with self._lock:
            session = self._sessions.get(key)
            if session and session.is_expired():
                del self._sessions[key]
                return None
            if session:
                session.expires_at = time.time() + 3600
            return session

    def get_or_create(self, user_id: str, adapter: str,
                      ttl: float = 3600.0) -> Session:
        session = self.get(user_id, adapter)
        if session is None:
            session = self.create(user_id, adapter, ttl)
        return session

    def delete(self, user_id: str, adapter: str):
        key = self._make_key(user_id, adapter)
        with self._lock:
            self._sessions.pop(key, None)

    def set_context(self, user_id: str, adapter: str,
                    key: str, value):
        session = self.get_or_create(user_id, adapter)
        session.context_data[key] = value

    def get_context(self, user_id: str, adapter: str,
                    key: str, default=None):
        session = self.get(user_id, adapter)
        if session is None:
            return default
        return session.context_data.get(key, default)

    def _make_key(self, user_id: str, adapter: str) -> str:
        return f"{adapter}:{user_id}"

    def _maybe_gc(self):
        now = time.time()
        if now - self._last_gc < self._gc_interval:
            return
        self._last_gc = now
        with self._lock:
            expired = [
                k for k, v in self._sessions.items()
                if v.is_expired()
            ]
            for k in expired:
                del self._sessions[k]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._sessions)
