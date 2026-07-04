# -*- coding: utf-8 -*-
"""内置欢迎插件 - 向新成员发送欢迎消息。"""

from qtine.plugins.base import BasePlugin


class WelcomePlugin(BasePlugin):
    name = "welcome"
    package = "qtine-builtin-welcome"
    version = "1.0.0"
    description = "欢迎新入群成员"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/welcome", self.handle_set_welcome,
                              aliases=["/欢迎"],
                              permission="admin")
        self.bot = bot

    def handle_set_welcome(self, event, args):
        if not args:
            return "用法: /welcome <消息内容> (用 {user} 表示用户名)"
        msg = " ".join(args)
        self.bot.storage.set("welcome.message", msg)
        return f"欢迎语已设置: {msg}"
