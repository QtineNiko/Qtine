# -*- coding: utf-8 -*-
"""Base plugin class and decorators for Qtine."""

import inspect
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
        self._message_listeners: List[Callable] = []
        self._event_subscriptions: List[str] = []
        self._config_schema: List[dict] = []
        self._config_cache: Dict[str, Any] = {}
        self._loaded_at = time.time()
        self._collect_decorated_handlers()

    def _collect_decorated_handlers(self) -> None:
        for _, method in inspect.getmembers(self, predicate=callable):
            command = getattr(method, "_qtine_command", None)
            if command is not None:
                self.register_command(
                    command,
                    method,
                    aliases=list(getattr(method, "_qtine_aliases", [])),
                    permission=getattr(method, "_qtine_permission", "user"),
                )
            pattern = getattr(method, "_qtine_regex", None)
            if pattern is not None:
                self._regex_handlers.append((pattern, method))
                self._notify_handler_change()
            keywords = getattr(method, "_qtine_keywords", None)
            if keywords:
                self._keyword_handlers.append((list(keywords), method))
                self._notify_handler_change()
            event = getattr(method, "_qtine_event", None)
            if event is not None:
                self.subscribe_event(event, method)

    def on_enable(self):
        pass

    def on_disable(self):
        pass

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def add_config(self, key: str, label: str, default: Any = None,
                   config_type: str = "text", description: str = "",
                   options: List[dict] = None):
        """声明一个插件配置项。

        Args:
            key: 配置键名
            label: 显示名称
            default: 默认值
            config_type: 类型（text/number/boolean/select/textarea/password）
            description: 描述说明
            options: 下拉选项（config_type=select 时用，[{"label":..., "value":...}]）
        """
        self._config_schema.append({
            "key": key,
            "label": label,
            "default": default,
            "type": config_type,
            "description": description,
            "options": options or [],
        })

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取插件配置，带缓存。"""
        if not self.bot or not self.bot.storage:
            return default
        storage_key = f"plugin_config.{self.name}.{key}"
        if key in self._config_cache:
            return self._config_cache[key]
        # 找 schema 里的 default
        schema_default = default
        for item in self._config_schema:
            if item["key"] == key:
                schema_default = item["default"] if default is None else default
                break
        value = self.bot.storage.get(storage_key, schema_default)
        self._config_cache[key] = value
        return value

    def set_config(self, key: str, value: Any) -> None:
        """设置插件配置并写回存储。"""
        if not self.bot or not self.bot.storage:
            return
        storage_key = f"plugin_config.{self.name}.{key}"
        self.bot.storage.set(storage_key, value)
        self._config_cache[key] = value

    def get_config_schema(self) -> List[dict]:
        """返回配置 schema。"""
        return list(self._config_schema)

    def get_all_config_values(self) -> Dict[str, Any]:
        """返回所有配置的当前值。"""
        result = {}
        for item in self._config_schema:
            result[item["key"]] = self.get_config(item["key"], item["default"])
        return result

    def get_group_config(self, group_id: str, key: str, default: Any = None) -> Any:
        """读取群级别的插件配置，带缓存。"""
        if not self.bot or not self.bot.storage or not group_id:
            return self.get_config(key, default)
        storage_key = f"plugin_config.{self.name}.group.{group_id}.{key}"
        cache_key = f"__group__{group_id}__{key}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        # 如果存储里没有这个群的配置，fallback 到全局配置
        value = self.bot.storage.get(storage_key, None)
        if value is None:
            value = self.get_config(key, default)
        self._config_cache[cache_key] = value
        return value

    def set_group_config(self, group_id: str, key: str, value: Any) -> None:
        """设置群级别的插件配置。"""
        if not self.bot or not self.bot.storage or not group_id:
            return
        storage_key = f"plugin_config.{self.name}.group.{group_id}.{key}"
        cache_key = f"__group__{group_id}__{key}"
        self.bot.storage.set(storage_key, value)
        self._config_cache[cache_key] = value

    def reset_group_config(self, group_id: str) -> int:
        """重置某个群的所有配置（回归全局默认）。返回删除的配置数。"""
        if not self.bot or not self.bot.storage or not group_id:
            return 0
        prefix = f"plugin_config.{self.name}.group.{group_id}."
        keys = self.bot.storage.keys(prefix)
        count = 0
        for k in keys:
            self.bot.storage.delete(k)
            count += 1
        # 清缓存里该群的
        to_del = [k for k in self._config_cache if k.startswith(f"__group__{group_id}__")]
        for k in to_del:
            del self._config_cache[k]
        return count

    def get_group_config_values(self, group_id: str) -> Dict[str, Any]:
        """返回某个群的所有配置值（没有配置的项用全局值）。"""
        result = {}
        for item in self._config_schema:
            result[item["key"]] = self.get_group_config(group_id, item["key"], item["default"])
        return result

    def get_group_list(self) -> List[str]:
        """返回有独立配置的群列表。"""
        if not self.bot or not self.bot.storage:
            return []
        prefix = f"plugin_config.{self.name}.group."
        keys = self.bot.storage.keys(prefix)
        groups = set()
        for k in keys:
            rest = k[len(prefix):]
            parts = rest.split(".", 1)
            if parts:
                groups.add(parts[0])
        return sorted(groups)

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
        if self._message_listeners:
            hooks.append("listener")
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
        self._notify_handler_change()

    def register_regex(self, pattern: str, handler: Callable):
        self._regex_handlers.append((re.compile(pattern), handler))
        self._notify_handler_change()

    def register_keyword(self, keywords: List[str], handler: Callable):
        self._keyword_handlers.append((keywords, handler))
        self._notify_handler_change()

    def register_listener(self, handler: Callable) -> None:
        """注册一个通用消息监听器，收到的每条消息都会调用。"""
        self._message_listeners.append(handler)
        self._notify_handler_change()

    def subscribe_event(self, event: str, handler: Callable,
                        priority: int = 0) -> Optional[str]:
        """订阅事件总线事件，订阅 ID 会在卸载时自动清理。"""
        if not self.bot or not getattr(self.bot, "event_bus", None):
            return None

        def managed_handler(data):
            if not self.enabled:
                return None
            return handler(data)

        sub_id = self.bot.event_bus.subscribe(
            event, managed_handler, priority=priority
        )
        self._event_subscriptions.append(sub_id)
        self._event_handlers.append((event, handler))
        return sub_id

    def cleanup(self) -> None:
        """卸载/禁用时释放插件占用的事件订阅与监听器。"""
        bus = getattr(self.bot, "event_bus", None) if self.bot else None
        if bus is not None:
            for sub_id in self._event_subscriptions:
                try:
                    bus.unsubscribe(sub_id)
                except Exception as e:
                    self.logger.error(
                        f"[{self.name}] unsubscribe error: {e}"
                    )
        self._event_subscriptions.clear()
        self._event_handlers.clear()
        self._message_listeners.clear()
        self._notify_handler_change()

    def dispatch_listeners(self, message) -> None:
        """把一条消息广播给所有已注册的通用监听器。"""
        if not self._message_listeners:
            return
        for listener in tuple(self._message_listeners):
            try:
                listener(message)
            except Exception as e:
                self.logger.error(f"[{self.name}] listener error: {e}")

    def has_listeners(self) -> bool:
        return bool(self._message_listeners)

    def _notify_handler_change(self) -> None:
        manager = getattr(self.bot, "plugin_manager", None) if self.bot else None
        mark_dirty = getattr(manager, "_mark_indexes_dirty", None)
        if mark_dirty is not None:
            mark_dirty()

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
        self._notify_handler_change()


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
