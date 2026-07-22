# -*- coding: utf-8 -*-
"""Base adapter class for Qtine."""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Dict
from qtine.utils.models import Message, AdapterInfo, AdapterStatus
from qtine.utils.logger import get_logger


class BaseAdapter(ABC):
    def __init__(self, name: str = "", protocol: str = "", config: Dict[str, Any] = None):
        self.name = name
        self.protocol = protocol
        self.config = config or {}
        self.logger = get_logger()
        self._on_message_callback: Optional[Callable] = None
        self._on_event_callback: Optional[Callable] = None
        self._adapter_info = AdapterInfo(
            name=name,
            protocol=protocol,
            config=self.config,
            builtin=getattr(self, "_builtin", False),
        )
        self._running = False
        self.bot = None

    @property
    def info(self) -> AdapterInfo:
        return self._adapter_info

    @property
    def running(self) -> bool:
        return self._running

    @property
    def enabled(self) -> bool:
        return self._adapter_info.enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._adapter_info.enabled = value

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def send_message(self, target: str, message: str,
                     message_type: str = "group") -> bool: ...

    def on_message(self, callback: Callable[[Message], Any]):
        self._on_message_callback = callback

    def on_event(self, callback: Callable[[str, Any], Any]):
        self._on_event_callback = callback

    def _emit_message(self, message: Message):
        if self._on_message_callback:
            try:
                self._on_message_callback(message)
            except Exception as e:
                self.logger.error(f"Message callback error: {e}")

    def _emit_event(self, event_type: str, data: Any):
        if self._on_event_callback:
            try:
                self._on_event_callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Adapter event callback error: {e}")

    def _update_status(self, status: AdapterStatus, account_id: str = "", nickname: str = ""):
        previous = self._adapter_info.status
        self._adapter_info.status = status
        if account_id:
            self._adapter_info.account_id = account_id
        if nickname:
            self._adapter_info.nickname = nickname
        if previous == status or self.bot is None:
            return
        bus = getattr(self.bot, "event_bus", None)
        if bus is None:
            return
        if status == AdapterStatus.CONNECTED:
            bus.publish(
                "adapter.connected",
                {
                    "adapter": self.name,
                    "self_id": self._adapter_info.account_id,
                },
            )
        elif status == AdapterStatus.DISCONNECTED:
            bus.publish(
                "adapter.disconnected",
                {"adapter": self.name},
            )
