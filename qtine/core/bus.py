# -*- coding: utf-8 -*-
"""Event bus for Qtine - publish/subscribe pattern."""

from typing import Callable, Dict, List, Any
import threading
import time
from qtine.utils.logger import get_logger


class EventBus:
    _instance: "EventBus" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._subscribers: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.logger = get_logger()

    def subscribe(self, event: str, callback: Callable,
                  priority: int = 0, once: bool = False) -> str:
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            sub_id = f"{event}_{len(self._subscribers[event])}_{time.time()}"
            self._subscribers[event].append({
                "id": sub_id,
                "callback": callback,
                "priority": priority,
                "once": once,
            })
            self._subscribers[event].sort(key=lambda x: -x["priority"])
            return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            for event, subs in list(self._subscribers.items()):
                for i, sub in enumerate(subs):
                    if sub["id"] == subscription_id:
                        subs.pop(i)
                        if not subs:
                            del self._subscribers[event]
                        return True
        return False

    def publish(self, event: str, data: Any = None) -> None:
        subs = []
        with self._lock:
            if event in self._subscribers:
                subs = [s.copy() for s in self._subscribers[event]]
        once_ids = []
        for sub in subs:
            try:
                sub["callback"](data)
            except Exception as e:
                self.logger.error(f"Event handler error [{event}]: {e}")
            if sub["once"]:
                once_ids.append(sub["id"])
        for sid in once_ids:
            self.unsubscribe(sid)

    def publish_and_wait(self, event: str, data: Any = None,
                         timeout: float = 30.0) -> List[Any]:
        results = []
        subs = []
        with self._lock:
            if event in self._subscribers:
                subs = [s.copy() for s in self._subscribers[event]]
        once_ids = []
        for sub in subs:
            try:
                result = sub["callback"](data)
                if result is not None:
                    results.append(result)
            except Exception as e:
                self.logger.error(f"Event handler error [{event}]: {e}")
            if sub["once"]:
                once_ids.append(sub["id"])
        for sid in once_ids:
            self.unsubscribe(sid)
        return results

    def on(self, event: str, priority: int = 0):
        """Decorator for subscribing to events."""
        def decorator(func: Callable):
            self.subscribe(event, func, priority=priority)
            return func
        return decorator

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()

    @property
    def events(self) -> List[str]:
        with self._lock:
            return list(self._subscribers.keys())
