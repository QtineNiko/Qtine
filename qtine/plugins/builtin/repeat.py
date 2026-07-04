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
        self._repeat_threshold = 3

    def handle_message(self, event):
        content = event.message.content.strip()
        if not content:
            return None
        group_id = event.message.group_id or "private"
        key = f"{group_id}:{content}"
        now = time.time()
        self._recent_messages[key] = [
            t for t in self._recent_messages[key]
            if now - t < 30
        ]
        self._recent_messages[key].append(now)
        if len(self._recent_messages[key]) == self._repeat_threshold:
            return content
        return None
