# -*- coding: utf-8 -*-
"""内置复读插件 - 简单的复读测试功能。"""

from qtine.plugins.base import BasePlugin


class EchoPlugin(BasePlugin):
    name = "echo"
    package = "qtine-builtin-echo"
    version = "1.0.0"
    description = "复读你发送的消息"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/echo", self.handle_echo,
                              aliases=["/e", "/复读"])

    def handle_echo(self, event, args):
        if not args:
            return "用法: /echo <内容>"
        return " ".join(args)
