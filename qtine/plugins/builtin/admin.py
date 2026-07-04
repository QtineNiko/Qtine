# -*- coding: utf-8 -*-
"""内置管理插件 - 通过聊天命令管理插件和适配器。"""

from qtine.plugins.base import BasePlugin


class AdminPlugin(BasePlugin):
    name = "admin"
    package = "qtine-builtin-admin"
    version = "1.0.0"
    description = "通过聊天命令管理插件和适配器"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("qtine", self.handle_status, permission="admin")
        self.register_command(
            "qtine list", self.handle_list, permission="admin"
        )
        self.register_command(
            "qtine enable", self.handle_enable, permission="admin"
        )
        self.register_command(
            "qtine disable", self.handle_disable, permission="admin"
        )
        self.register_command(
            "qtine reload", self.handle_reload, permission="admin"
        )
        self.register_command(
            "qtine adapter", self.handle_adapter, permission="admin"
        )
        self.register_command(
            "qtine adapter reconnect",
            self.handle_adapter_reconnect,
            permission="admin",
        )
        self.register_command(
            "qtine log", self.handle_log, permission="admin"
        )

    # ── 状态 ────────────────────────────────────────────────────────

    def handle_status(self, event, args):
        return self.bot.format_status(public=False)

    # ── 插件列表 ────────────────────────────────────────────────────

    def handle_list(self, event, args):
        plugins = self.bot.plugin_manager.get_all()
        if not plugins:
            return "暂无已加载的插件。"

        lines = ["插件列表:"]
        for p in plugins:
            status = "✓" if p.enabled else "✗"
            name = p.name if p.name else "(未命名)"
            lines.append(
                f"  [{status}] {name} v{p.version} — {p.description}"
            )
        return "\n".join(lines)

    # ── 插件启用/禁用/重载 ──────────────────────────────────────────

    def handle_enable(self, event, args):
        if not args:
            return "用法: qtine enable <插件名称>"
        name = args[0]
        ok = self.bot.plugin_manager.enable(name)
        if ok:
            return f"插件 '{name}' 已启用。"
        return f"插件 '{name}' 未找到或已启用。"

    def handle_disable(self, event, args):
        if not args:
            return "用法: qtine disable <插件名称>"
        name = args[0]
        ok = self.bot.plugin_manager.disable(name)
        if ok:
            return f"插件 '{name}' 已禁用。"
        return f"插件 '{name}' 未找到或已禁用。"

    def handle_reload(self, event, args):
        if not args:
            return "用法: qtine reload <插件名称>"
        name = args[0]
        ok = self.bot.plugin_manager.reload(name)
        if ok:
            return f"插件 '{name}' 已重载。"
        return f"插件 '{name}' 未找到或为内置插件（不可重载）。"

    # ── 适配器 ──────────────────────────────────────────────────────

    def handle_adapter(self, event, args):
        adapters = self.bot.adapter_manager.get_all_info()
        if not adapters:
            return "暂无已注册的适配器。"

        lines = ["适配器列表:"]
        for a in adapters:
            status_cn = {
                "disconnected": "未连接",
                "connecting": "连接中",
                "connected": "已连接",
                "error": "错误",
            }.get(a.status.value, a.status.value)
            lines.append(
                f"  {a.name} ({a.protocol}): [{status_cn}] "
                f"消息:{a.message_count} 错误:{a.error_count} "
                f"账号:{a.account_id or '无'}"
            )
        return "\n".join(lines)

    def handle_adapter_reconnect(self, event, args):
        if not args:
            return "用法: qtine adapter reconnect <适配器名称>"
        name = args[0]
        adapter = self.bot.adapter_manager.get(name)
        if adapter is None:
            return f"适配器 '{name}' 未找到。"
        adapter.stop()
        adapter.start()
        return f"适配器 '{name}' 已重新连接。"

    # ── 日志 ────────────────────────────────────────────────────────

    def handle_log(self, event, args):
        lines = 20
        if args:
            try:
                lines = min(int(args[0]), 100)
            except ValueError:
                pass

        log_file = self.bot.config.get(
            "logging.file", "./data/logs/qtine.log"
        )
        import os

        if not os.path.isfile(log_file):
            return "日志文件不存在。"

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            recent = all_lines[-lines:]
            return "最近日志:\n" + "".join(recent).rstrip()
        except Exception as e:
            return f"读取日志失败: {e}"
