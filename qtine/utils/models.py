# -*- coding: utf-8 -*-
"""Unified data models for Qtine."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import time
import uuid


class MessageType(Enum):
    PRIVATE = "private"
    GROUP = "group"


class AdapterStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class PluginType(Enum):
    BUILTIN = "builtin"
    EXTERNAL = "external"


@dataclass
class Sender:
    user_id: str
    nickname: str = ""
    role: str = "user"
    card: str = ""


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    adapter: str = ""
    type: str = MessageType.PRIVATE.value
    content: str = ""
    sender: Optional[Sender] = None
    group_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None

    def is_group(self) -> bool:
        return self.type == MessageType.GROUP.value

    def is_private(self) -> bool:
        return self.type == MessageType.PRIVATE.value


@dataclass
class PluginInfo:
    name: str
    package: str
    version: str
    enabled: bool = True
    plugin_type: PluginType = PluginType.EXTERNAL
    description: str = ""
    author: str = ""
    loaded_at: float = 0.0
    hooks: List[str] = field(default_factory=list)
    entry: str = ""
    qtine_version: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)
    icon: str = ""


@dataclass
class AdapterInfo:
    name: str
    protocol: str
    status: AdapterStatus = AdapterStatus.DISCONNECTED
    connected_at: float = 0.0
    message_count: int = 0
    received_count: int = 0
    sent_count: int = 0
    error_count: int = 0
    account_id: str = ""


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    adapter: str = ""
    context_data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at
