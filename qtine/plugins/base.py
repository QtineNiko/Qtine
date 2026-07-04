# -*- coding: utf-8 -*-
"""Base plugin class and decorators for Qtine."""

import re
import time
from typing import Optional, Callable, Dict, Any, List, Pattern
from abc import ABC
from qtine.utils.models import Message, PluginInfo, PluginType
from qtine.utils.logger import get_logger


class PluginEvent:
    def __init__(self, message: Message, bot):
        self.message = message
        self.bot = bot
        self._prevent_default = False

    def prevent_default(self):
        self._prevent_default = True

    @property
    def content(self) -> str:
        return self.message.content

    @property
    def sender(self):
        return self.message.sender

    @property
    def group_id(self) -> Optional[str]:
        return self.message.group_id

    async def reply(self, text: str):
        await self.bot.send(self.message, text)


class BasePlugin(ABC):
    name: str = ""
    package: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.EXTERNAL
    requires: List[str] = []
    icon: str = ""

    def __init__(self, bot=None):
        self.bot = bot
        self.logger = get_logger()
        self._enabled = True
        self._command_handlers: List[tuple] = []
        self._regex_handlers: List[tuple] = []
        self._keyword_handlers: List[tuple] = []
        self._event_handlers: List[tuple] = []
        self._loaded_at = time.time()

    def on_enable(self):
        pass

    def on_disable(self):
        pass

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def get_info(self) -> PluginInfo:
        hooks = []
        if self._command_handlers:
            hooks.append("command")
        if self._regex_handlers:
            hooks.append("regex")
        if self._keyword_handlers:
            hooks.append("keyword")
        if self._event_handlers:
            hooks.append("event")
        return PluginInfo(
            name=self.name,
            package=self.package,
            version=self.version,
            enabled=self._enabled,
            plugin_type=self.plugin_type,
            description=self.description,
            author=self.author,
            loaded_at=self._loaded_at,
            hooks=hooks,
            requires=list(self.requires) if self.requires else [],
            icon=self.icon,
        )

    def register_command(self, command: str, handler: Callable,
                         aliases: List[str] = None, permission: str = "user"):
        self._command_handlers.append((command, aliases or [], permission, handler))

    def register_regex(self, pattern: str, handler: Callable):
        self._regex_handlers.append((re.compile(pattern), handler))

    def register_keyword(self, keywords: List[str], handler: Callable):
        self._keyword_handlers.append((keywords, handler))

    def get_all_command_handlers(self) -> List[tuple]:
        return self._command_handlers

    def get_all_regex_handlers(self) -> List[tuple]:
        return self._regex_handlers

    def get_all_keyword_handlers(self) -> List[tuple]:
        return self._keyword_handlers

    def get_all_event_handlers(self) -> List[tuple]:
        return self._event_handlers

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value


def on_command(command: str, aliases: List[str] = None,
               permission: str = "user"):
    def decorator(func: Callable):
        func._qtine_command = command
        func._qtine_aliases = aliases or []
        func._qtine_permission = permission
        func._qtine_is_handler = True
        return func
    return decorator


def on_regex(pattern: str):
    def decorator(func: Callable):
        func._qtine_regex = re.compile(pattern)
        func._qtine_is_handler = True
        return func
    return decorator


def on_keyword(keywords: List[str]):
    def decorator(func: Callable):
        func._qtine_keywords = keywords
        func._qtine_is_handler = True
        return func
    return decorator


def on_event(event: str):
    def decorator(func: Callable):
        func._qtine_event = event
        func._qtine_is_handler = True
        return func
    return decorator
