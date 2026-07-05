# -*- coding: utf-8 -*-
"""SDK Plugin 基类。

`sdk.Plugin` 继承 `qtine.plugins.base.BasePlugin`，会在 `__init__` 时
自动扫描类里所有被 `sdk.filter.*` 装饰的方法，并注册到底层插件系统。

因此插件作者只需要：

    from sdk import Plugin, filter

    class MyPlugin(Plugin):
        name = "my_plugin"

        @filter.command("hello")
        def hello(self, ctx):
            ctx.reply("hi")

即可，无需再手写 `register_command`。
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, List, Optional

from qtine.plugins.base import BasePlugin

from sdk import filter as _filter
from sdk.context import Context


class Plugin(BasePlugin):
    """AstrBot 风格的 Qtine 插件基类。"""

    # 让子类只需要覆盖必要字段
    name: str = ""
    package: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    def __init__(self, bot=None):
        super().__init__(bot)
        # 保存 SDK 层监听器与事件处理器
        self._sdk_listeners: List[Callable] = []
        self._sdk_event_handlers: List[tuple] = []  # [(event_name, bound_method)]
        self._collect_handlers()
        self._subscribe_events()

    # ── 装饰器扫描 ────────────────────────────────────────────
    def _collect_handlers(self) -> None:
        """扫描类里被 filter.* 装饰过的方法，注册到底层系统。"""
        for _, method in inspect.getmembers(self, predicate=callable):
            # 命令
            command = getattr(method, _filter.ATTR_COMMAND, None)
            if command is not None:
                aliases = getattr(method, _filter.ATTR_COMMAND_ALIASES, [])
                permission = getattr(
                    method, _filter.ATTR_COMMAND_PERMISSION, "user"
                )
                self.register_command(
                    command,
                    self._wrap_command_handler(method),
                    aliases=list(aliases),
                    permission=permission,
                )

            # 正则
            pattern = getattr(method, _filter.ATTR_REGEX, None)
            if pattern is not None:
                # BasePlugin.register_regex 接收字符串，直接传 pattern.pattern
                self.register_regex(
                    pattern.pattern,
                    self._wrap_regex_handler(method),
                )

            # 关键词
            keywords = getattr(method, _filter.ATTR_KEYWORDS, None)
            if keywords:
                self.register_keyword(
                    list(keywords),
                    self._wrap_keyword_handler(method),
                )

            # 通用消息监听
            if getattr(method, _filter.ATTR_LISTENER, False):
                self._sdk_listeners.append(method)

            # 事件监听
            event_name = getattr(method, _filter.ATTR_EVENT, None)
            if event_name is not None:
                self._sdk_event_handlers.append((event_name, method))

    def _subscribe_events(self) -> None:
        """把 @filter.on_event 声明的方法订阅到 QtineBot.event_bus。"""
        if not self._sdk_event_handlers:
            return
        bot = self.bot
        bus = getattr(bot, "event_bus", None) if bot else None
        if bus is None:
            return
        subscribe = getattr(bus, "subscribe", None) or getattr(bus, "on", None)
        if subscribe is None:
            return
        for event_name, handler in self._sdk_event_handlers:
            try:
                subscribe(event_name, self._wrap_event_handler(handler))
            except Exception as e:
                self.logger.error(
                    f"[SDK] Failed to subscribe event {event_name}: {e}"
                )

    # ── 包装 handler，把底层参数转成 SDK Context ─────────────
    def _build_ctx(self, raw) -> Context:
        """从底层管道对象或 Message 构造 SDK Context。"""
        # 底层 handler 收到的通常是 PipelineContext；也可能直接是 Message
        if hasattr(raw, "message") and hasattr(raw, "reply"):
            return Context(pipeline_ctx=raw, bot=self.bot)
        return Context(message=raw, bot=self.bot)

    def _wrap_command_handler(self, method: Callable) -> Callable:
        def _handler(pipeline_ctx, args):
            ctx = self._build_ctx(pipeline_ctx)
            try:
                result = method(ctx, args)
            except TypeError:
                # 允许开发者省略 args 参数
                result = method(ctx)
            return result

        _handler.__name__ = getattr(method, "__name__", "command_handler")
        return _handler

    def _wrap_regex_handler(self, method: Callable) -> Callable:
        def _handler(pipeline_ctx, match):
            ctx = self._build_ctx(pipeline_ctx)
            try:
                return method(ctx, match)
            except TypeError:
                return method(ctx)

        _handler.__name__ = getattr(method, "__name__", "regex_handler")
        return _handler

    def _wrap_keyword_handler(self, method: Callable) -> Callable:
        def _handler(pipeline_ctx):
            ctx = self._build_ctx(pipeline_ctx)
            return method(ctx)

        _handler.__name__ = getattr(method, "__name__", "keyword_handler")
        return _handler

    def _wrap_event_handler(self, method: Callable) -> Callable:
        def _handler(data: Any):
            try:
                return method(data)
            except Exception as e:
                self.logger.error(
                    f"[{self.name}] event handler error: {e}"
                )

        _handler.__name__ = getattr(method, "__name__", "event_handler")
        return _handler

    # ── 供开发者使用的便捷方法 ─────────────────────────────────
    def send(
        self,
        target,
        payload,
        message_type: str = "private",
        adapter: Optional[str] = None,
    ) -> bool:
        """主动向指定会话发送消息，不依赖当前上下文。"""
        if self.bot is None:
            return False
        from sdk.message import to_cq_string
        text = to_cq_string(payload)
        adapter_name = adapter or "onebot_v11"
        try:
            return bool(
                self.bot.adapter_manager.send_message(
                    adapter_name, str(target), text, message_type
                )
            )
        except Exception:
            return False

    def dispatch_listeners(self, message) -> None:
        """内部：把每条消息广播给 `@filter.on_message` 监听器。

        由核心在 handler 阶段前后择机调用；未接入时不影响命令注册。
        """
        if not self._sdk_listeners:
            return
        ctx = Context(message=message, bot=self.bot)
        for listener in self._sdk_listeners:
            try:
                listener(ctx)
            except Exception as e:
                self.logger.error(
                    f"[{self.name}] listener error: {e}"
                )