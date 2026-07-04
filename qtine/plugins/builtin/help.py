# -*- coding: utf-8 -*-
"""内置帮助插件 - 显示帮助信息。"""

from qtine.plugins.base import BasePlugin


class HelpPlugin(BasePlugin):
    name = "help"
    package = "qtine-builtin-help"
    version = "1.0.0"
    description = "显示 Qtine 和插件的帮助信息"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("#qtine", self.handle_qtine_status)
        self.register_command("#help", self.handle_help,
                              aliases=["#帮助", "help"])

    def handle_qtine_status(self, event, args):
        return self.bot.format_status(public=True)

    def handle_help(self, event, args):
        plugins = self.bot.plugin_manager.get_enabled()
        lines = ["可用命令:"]
        for plugin in plugins:
            for cmd, aliases, perm, _ in plugin.get_all_command_handlers():
                alias_str = f" (别名: {', '.join(aliases)})" if aliases else ""
                perm_str = f" [管理员]" if perm == "admin" else ""
                lines.append(f"  {cmd}{alias_str}{perm_str} - {plugin.description}")
        return "\n".join(lines)
