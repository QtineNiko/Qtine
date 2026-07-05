# -*- coding: utf-8 -*-
"""Context 对象：插件回调的统一入口。

从底层 `qtine.core.pipeline.PipelineContext` 或 `qtine.utils.models.Message`
封装出一个开发者友好的对象，屏蔽内部实现细节，
让插件作者能用最少的代码完成常见操作：

    def hello(self, ctx):
        ctx.sender_name        # 昵称
        ctx.sender_id          # 用户ID
        ctx.text               # 纯文本消息
        ctx.is_group           # 是否群聊
        ctx.reply("你好")       # 回复文本（走管道 response）
        ctx.send("直接推送")    # 直接调用适配器推送（不走管道）
        ctx.send_image(url)    # 发送图片
        ctx.send_chain(chain)  # 发送消息链
"""

from __future__ import annotations

from typing import Any, Optional, Union

from sdk.message import Image, MessageChain, MessageSegment, to_cq_string


class Context:
    """插件回调统一上下文对象。"""

    __slots__ = ("_pipeline_ctx", "_message", "_bot", "extras")

    def __init__(self, pipeline_ctx=None, message=None, bot=None):
        # pipeline_ctx: qtine.core.pipeline.PipelineContext | None
        # message: qtine.utils.models.Message
        # bot: qtine.core.app.QtineBot
        self._pipeline_ctx = pipeline_ctx
        self._message = message if message is not None else (
            getattr(pipeline_ctx, "message", None)
        )
        self._bot = bot if bot is not None else (
            getattr(pipeline_ctx, "bot", None)
        )
        self.extras: dict = {}

    # ── 原始对象访问 ────────────────────────────────────────────
    @property
    def message(self):
        """底层 `qtine.utils.models.Message` 对象。"""
        return self._message

    @property
    def pipeline_ctx(self):
        """底层 `PipelineContext`，若不是在管道回调中触发则为 None。"""
        return self._pipeline_ctx

    @property
    def bot(self):
        """底层 `QtineBot` 实例。"""
        return self._bot

    # ── 常用属性 ────────────────────────────────────────────────
    @property
    def text(self) -> str:
        """消息的文本内容（原始 content）。"""
        return getattr(self._message, "content", "") or ""

    @property
    def sender(self):
        """`Sender` 对象。"""
        return getattr(self._message, "sender", None) if self._message else None

    @property
    def sender_id(self) -> str:
        s = self.sender
        return getattr(s, "user_id", "") if s else ""

    @property
    def sender_name(self) -> str:
        s = self.sender
        if not s:
            return ""
        return getattr(s, "card", "") or getattr(s, "nickname", "") or ""

    @property
    def group_id(self) -> Optional[str]:
        return getattr(self._message, "group_id", None) if self._message else None

    @property
    def adapter(self) -> str:
        return getattr(self._message, "adapter", "") if self._message else ""

    @property
    def is_group(self) -> bool:
        return bool(self._message and self._message.is_group())

    @property
    def is_private(self) -> bool:
        return bool(self._message and self._message.is_private())

    @property
    def message_id(self):
        return getattr(self._message, "message_id", None) if self._message else None

    # ── 回复 / 发送 ────────────────────────────────────────────
    def reply(self, payload: Union[str, MessageSegment, MessageChain, list, tuple]) -> None:
        """回复消息。

        - 在命令/正则/关键词管道回调里，会把响应写回 `PipelineContext`，
          由核心统一发送（可以正确参与后处理阶段）。
        - 在管道之外（例如通用监听或事件回调）自动改走 `send()`。
        """
        text = to_cq_string(payload)
        if self._pipeline_ctx is not None and hasattr(self._pipeline_ctx, "reply"):
            self._pipeline_ctx.reply(text)
            return
        self.send(text)

    def send(self, payload: Union[str, MessageSegment, MessageChain, list, tuple]) -> bool:
        """直接通过适配器推送消息到当前会话。"""
        text = to_cq_string(payload)
        if self._bot is None or self._message is None:
            return False
        try:
            return bool(self._bot.send(self._message, text))
        except Exception:
            return False

    def send_to(
        self,
        target: Union[str, int],
        payload: Union[str, MessageSegment, MessageChain, list, tuple],
        message_type: str = "private",
        adapter: Optional[str] = None,
    ) -> bool:
        """向指定目标发送消息（跨会话）。

        Args:
            target: user_id 或 group_id
            payload: 文本/消息段/消息链
            message_type: "private" 或 "group"
            adapter: 指定适配器名，默认使用当前消息的适配器
        """
        if self._bot is None:
            return False
        text = to_cq_string(payload)
        adapter_name = adapter or self.adapter or "onebot_v11"
        try:
            return bool(
                self._bot.adapter_manager.send_message(
                    adapter_name, str(target), text, message_type
                )
            )
        except Exception:
            return False

    def send_image(self, file: str) -> bool:
        """便捷发送单张图片。

        `file` 可以是：
            - `http(s)://...` URL
            - 本地路径（会自动加 `file://` 前缀）
            - `base64://...`
        """
        if file.startswith(("http://", "https://", "file://", "base64://")):
            img = Image(file)
        else:
            img = Image.from_file(file)
        return self.send(img)

    def send_chain(self, chain: MessageChain) -> bool:
        """发送消息链。"""
        return self.send(chain)

    # ── 上下文数据 ────────────────────────────────────────────
    def get(self, key: str, default: Any = None) -> Any:
        if self._pipeline_ctx is not None and hasattr(self._pipeline_ctx, "get"):
            return self._pipeline_ctx.get(key, default)
        return self.extras.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self._pipeline_ctx is not None and hasattr(self._pipeline_ctx, "set"):
            self._pipeline_ctx.set(key, value)
        else:
            self.extras[key] = value