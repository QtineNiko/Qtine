# -*- coding: utf-8 -*-
"""内置封禁插件 - 管理用户黑名单。"""

from qtine.plugins.base import BasePlugin


class BanPlugin(BasePlugin):
    name = "ban"
    package = "qtine-builtin-ban"
    version = "1.0.0"
    description = "封禁和解封用户"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/ban", self.handle_ban,
                              aliases=["/封禁"],
                              permission="admin")
        self.register_command("/unban", self.handle_unban,
                              aliases=["/解封"],
                              permission="admin")
        self.register_command("/blacklist", self.handle_blacklist,
                              aliases=["/黑名单"],
                              permission="admin")

    def handle_ban(self, event, args):
        if not args:
            return "用法: /ban <用户QQ号> [原因]"
        user_id = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "无原因"
        blacklist = self.bot.storage.get("blacklist_users", [])
        if user_id not in blacklist:
            blacklist.append(user_id)
            self.bot.storage.set("blacklist_users", blacklist)
        return f"用户 {user_id} 已封禁。原因: {reason}"

    def handle_unban(self, event, args):
        if not args:
            return "用法: /unban <用户QQ号>"
        user_id = args[0]
        blacklist = self.bot.storage.get("blacklist_users", [])
        if user_id in blacklist:
            blacklist.remove(user_id)
            self.bot.storage.set("blacklist_users", blacklist)
            return f"用户 {user_id} 已解封。"
        return f"用户 {user_id} 不在黑名单中。"

    def handle_blacklist(self, event, args):
        blacklist = self.bot.storage.get("blacklist_users", [])
        if not blacklist:
            return "暂无封禁用户。"
        return f"封禁用户列表 ({len(blacklist)}):\n" + "\n".join(f"  - {u}" for u in blacklist)
