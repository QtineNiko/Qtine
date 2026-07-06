# -*- coding: utf-8 -*-
"""内置复读检测插件 - 检测重复消息。"""

from collections import defaultdict
import time
from qtine.plugins.base import BasePlugin


class RepeatPlugin(BasePlugin):
    name = "repeat"
    package = "qtine-builtin-repeat"
    version = "1.0.0"
    description = "检测并触发复读消息"

    def __init__(self, bot=None):
        super().__init__(bot)
        self._recent_messages = defaultdict(list)
        self.add_config("threshold", "复读触发次数", default=3,
                        config_type="number",
                        description="相同消息出现多少次后触发复读")
        self.add_config("window_seconds", "检测窗口(秒)", default=30,
                        config_type="number",
                        description="多长时间内的重复消息计入统计")
        self.add_config("enabled", "启用复读", default=True,
                        config_type="boolean",
                        description="是否启用复读功能")
        self.register_command("/repeat", self.handle_set_threshold,
                              aliases=["/复读"],
                              permission="admin")

    def handle_message(self, event):
        if not self.get_config("enabled", True):
            return None
        content = event.message.content.strip()
        if not content:
            return None
        group_id = event.message.group_id or "private"
        key = f"{group_id}:{content}"
        now = time.time()
        window = self.get_config("window_seconds", 30)
        threshold = self.get_config("threshold", 3)
        self._recent_messages[key] = [
            t for t in self._recent_messages[key]
            if now - t < window
        ]
        self._recent_messages[key].append(now)
        if len(self._recent_messages[key]) == threshold:
            return content
        return None

    def handle_set_threshold(self, event, args):
        if not args:
            return f"当前复读触发次数: {self.get_config('threshold', 3)} (检测窗口 {self.get_config('window_seconds', 30)} 秒)\n用法: /repeat <次数> [窗口秒数]"
        try:
            threshold = int(args[0])
            if threshold < 2:
                return "触发次数至少为 2"
            self.set_config("threshold", threshold)
            if len(args) > 1:
                window = int(args[1])
                if window < 5:
                    return "窗口时间至少为 5 秒"
                self.set_config("window_seconds", window)
            return f"复读设置已更新：触发 {threshold} 次，窗口 {self.get_config('window_seconds', 30)} 秒"
        except ValueError:
            return "参数必须是数字"
