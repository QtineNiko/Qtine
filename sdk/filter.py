# -*- coding: utf-8 -*-
"""AstrBot 风格的过滤器装饰器。

用法：

    from sdk import Plugin, filter

    class MyPlugin(Plugin):
        @filter.command("hello", aliases=["hi"])
        def hello(self, ctx):
            ctx.reply("hi")

        @filter.regex(r"^echo (.+)$")
        def echo(self, ctx, match):
            ctx.reply(match.group(1))

        @filter.keyword(["ping"])
        def ping(self, ctx):
            ctx.reply("pong")

        @filter.on_message()
        def listener(self, ctx):
            # 每条消息都会走这里
            pass

        @filter.on_event("adapter.onebot_v11.notice")
        def on_notice(self, data):
            pass

`Plugin.__init__` 会扫描这些装饰器，把它们注册到底层的
`qtine.plugins.base.BasePlugin` 命令/正则/关键词/事件系统，无需手写 register_xxx。
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional


# 标记属性名，Plugin 基类会读取这些属性做自动注册
ATTR_COMMAND = "_sdk_command"
ATTR_COMMAND_ALIASES = "_sdk_command_aliases"
ATTR_COMMAND_PERMISSION = "_sdk_command_permission"
ATTR_REGEX = "_sdk_regex"
ATTR_KEYWORDS = "_sdk_keywords"
ATTR_LISTENER = "_sdk_listener"
ATTR_EVENT = "_sdk_event"


def command(
    name: str,
    aliases: Optional[List[str]] = None,
    permission: str = "user",
) -> Callable:
    """命令装饰器：精确匹配消息第一段（例如 `/hello`、`hi`）。

    Args:
        name: 命令名，例如 `"/hello"` 或 `"hello"`。
        aliases: 别名列表。
        permission: `"user"` 或 `"admin"`。
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, ATTR_COMMAND, name)
        setattr(func, ATTR_COMMAND_ALIASES, list(aliases) if aliases else [])
        setattr(func, ATTR_COMMAND_PERMISSION, permission)
        return func

    return decorator


def regex(pattern: str) -> Callable:
    """正则装饰器：以 `re.match` 匹配消息全文，回调签名 `(self, ctx, match)`。"""

    compiled = re.compile(pattern)

    def decorator(func: Callable) -> Callable:
        setattr(func, ATTR_REGEX, compiled)
        return func

    return decorator


def keyword(keywords: List[str]) -> Callable:
    """关键词装饰器：消息内容包含任意关键词即触发。"""

    def decorator(func: Callable) -> Callable:
        setattr(func, ATTR_KEYWORDS, list(keywords))
        return func

    return decorator


def on_message() -> Callable:
    """通用消息监听装饰器：每一条消息都会调用。

    回调签名：`(self, ctx)`。
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, ATTR_LISTENER, True)
        return func

    return decorator


def on_event(event: str) -> Callable:
    """事件总线监听装饰器。

    Args:
        event: 事件名，例如 `"message.processed"`、
               `"adapter.onebot_v11.notice"` 等。

    回调签名：`(self, data)`。
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, ATTR_EVENT, event)
        return func

    return decorator
