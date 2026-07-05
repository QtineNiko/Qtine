# -*- coding: utf-8 -*-
"""Qtine Plugin SDK

一个借鉴 AstrBot 风格的极简插件开发 SDK。
用户只需 `from sdk import ...` 就能开发插件，底层完全复用 Qtine 原生插件系统。

最小示例：

    from sdk import Plugin, filter, MessageChain, Image, Plain

    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0"

        @filter.command("hello", aliases=["hi"])
        def hello(self, ctx):
            ctx.reply(f"你好，{ctx.sender_name}！")

        @filter.command("pic")
        def pic(self, ctx):
            ctx.send_image("https://example.com/a.jpg")

        @filter.keyword(["ping"])
        def ping(self, ctx):
            ctx.reply("pong")

        @filter.regex(r"^echo (.+)$")
        def echo(self, ctx, match):
            ctx.reply(match.group(1))
"""

from sdk.plugin import Plugin
from sdk.context import Context
from sdk import filter
from sdk.message import MessageChain, Plain, Image, At, Face, Reply, cq_escape

__all__ = [
    "Plugin",
    "Context",
    "filter",
    "MessageChain",
    "Plain",
    "Image",
    "At",
    "Face",
    "Reply",
    "cq_escape",
]
