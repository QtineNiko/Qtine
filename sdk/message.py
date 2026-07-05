# -*- coding: utf-8 -*-
"""消息链与消息段。

Qtine 底层适配器（OneBot V11）默认按 CQ 码字符串收发消息。
SDK 提供 AstrBot 风格的消息段封装，并统一序列化为 CQ 码字符串，
方便插件开发者构造富媒体消息，而不需要关心 CQ 码语法。

使用方式：

    from sdk import MessageChain, Plain, Image, At

    chain = MessageChain([
        At(user_id="123456"),
        Plain("看看这张图："),
        Image.from_url("https://example.com/a.jpg"),
    ])
    ctx.reply(chain)
"""

from __future__ import annotations

from typing import Iterable, List, Union


def cq_escape(text: str, comma: bool = False) -> str:
    """按 OneBot CQ 码规范转义文本。"""
    if text is None:
        return ""
    s = str(text).replace("&", "&"+"amp;").replace("[", "&#91;").replace("]", "&#93;")
    if comma:
        s = s.replace(",", "&#44;")
    return s


class MessageSegment:
    """消息段基类。"""

    __slots__ = ()

    def to_cq(self) -> str:  # pragma: no cover - 抽象接口
        raise NotImplementedError

    def __str__(self) -> str:
        return self.to_cq()


class Plain(MessageSegment):
    """纯文本消息段。"""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = str(text) if text is not None else ""

    def to_cq(self) -> str:
        return cq_escape(self.text)


class Image(MessageSegment):
    """图片消息段。

    支持 URL、本地文件路径或 base64。适配 OneBot V11 的 `[CQ:image,file=...]`。
    """

    __slots__ = ("file",)

    def __init__(self, file: str):
        self.file = str(file)

    @classmethod
    def from_url(cls, url: str) -> "Image":
        return cls(url)

    @classmethod
    def from_file(cls, path: str) -> "Image":
        if not path.startswith(("http://", "https://", "file://", "base64://")):
            return cls(f"file://{path}")
        return cls(path)

    @classmethod
    def from_base64(cls, data: str) -> "Image":
        if data.startswith("base64://"):
            return cls(data)
        return cls(f"base64://{data}")

    def to_cq(self) -> str:
        return f"[CQ:image,file={cq_escape(self.file, comma=True)}]"


class At(MessageSegment):
    """@某人消息段。"""

    __slots__ = ("user_id",)

    def __init__(self, user_id: Union[str, int]):
        self.user_id = str(user_id)

    def to_cq(self) -> str:
        return f"[CQ:at,qq={cq_escape(self.user_id, comma=True)}]"


class Face(MessageSegment):
    """QQ 表情消息段。"""

    __slots__ = ("id",)

    def __init__(self, id: Union[str, int]):
        self.id = str(id)

    def to_cq(self) -> str:
        return f"[CQ:face,id={cq_escape(self.id, comma=True)}]"


class Reply(MessageSegment):
    """回复某条消息。"""

    __slots__ = ("message_id",)

    def __init__(self, message_id: Union[str, int]):
        self.message_id = str(message_id)

    def to_cq(self) -> str:
        return f"[CQ:reply,id={cq_escape(self.message_id, comma=True)}]"


SegmentLike = Union[MessageSegment, str]


class MessageChain:
    """消息链：一组消息段的有序集合。

    可用 `+` 拼接，可用 `str()` 直接转换为 CQ 码字符串发送。
    """

    __slots__ = ("segments",)

    def __init__(self, segments: Iterable[SegmentLike] = ()):
        self.segments: List[MessageSegment] = []
        for seg in segments:
            self.append(seg)

    def append(self, seg: SegmentLike) -> "MessageChain":
        if isinstance(seg, MessageSegment):
            self.segments.append(seg)
        elif seg is None:
            return self
        else:
            self.segments.append(Plain(str(seg)))
        return self

    def extend(self, segs: Iterable[SegmentLike]) -> "MessageChain":
        for s in segs:
            self.append(s)
        return self

    def to_cq(self) -> str:
        return "".join(s.to_cq() for s in self.segments)

    def __str__(self) -> str:
        return self.to_cq()

    def __add__(self, other) -> "MessageChain":
        new = MessageChain(self.segments)
        if isinstance(other, MessageChain):
            new.extend(other.segments)
        else:
            new.append(other)
        return new

    def __iadd__(self, other) -> "MessageChain":
        if isinstance(other, MessageChain):
            self.extend(other.segments)
        else:
            self.append(other)
        return self


def to_cq_string(payload) -> str:
    """把任意常见类型统一转换为 CQ 码字符串。"""
    if payload is None:
        return ""
    if isinstance(payload, MessageChain):
        return payload.to_cq()
    if isinstance(payload, MessageSegment):
        return payload.to_cq()
    if isinstance(payload, (list, tuple)):
        return MessageChain(payload).to_cq()
    return str(payload)
