# -*- coding: utf-8 -*-
"""基于 sdk 的示例插件。

演示：命令 / 别名 / 参数、正则、关键词、通用监听、事件订阅、
纯文本与图片、@某人、消息链的所有常见用法。
"""

from sdk import Plugin, filter, MessageChain, Plain, Image, At


class SdkExamplePlugin(Plugin):
    name = "sdk_example"
    package = "qtine-plugin-sdk-example"
    version = "1.0.0"
    description = "SDK 示例插件"
    author = "you"

    # ── 命令 ───────────────────────────────────────────────
    @filter.command("/hello", aliases=["/hi", "/你好"])
    def hello(self, ctx):
        ctx.reply(f"你好，{ctx.sender_name or ctx.sender_id}！")

    @filter.command("/echo", aliases=["/复读"])
    def echo(self, ctx, args):
        text = " ".join(args) if args else "(empty)"
        ctx.reply(text)

    @filter.command("/pic")
    def pic(self, ctx):
        ctx.send_image("https://http.cat/200")

    @filter.command("/mix")
    def mix(self, ctx):
        chain = MessageChain([
            At(ctx.sender_id),
            Plain(" 看看这张图："),
            Image.from_url("https://http.cat/201"),
        ])
        ctx.reply(chain)

    # ── 正则 ───────────────────────────────────────────────
    @filter.regex(r"^echo (.+)$")
    def echo_regex(self, ctx, match):
        ctx.reply(match.group(1))

    # ── 关键词 ─────────────────────────────────────────────
    @filter.keyword(["ping", "PING"])
    def ping(self, ctx):
        ctx.reply("pong")

    # ── 通用消息监听 ────────────────────────────────────────
    @filter.on_message()
    def any_message(self, ctx):
        self.logger.info(
            f"[sdk_example] {ctx.adapter} {ctx.sender_id}: {ctx.text[:80]}"
        )

    # ── 事件监听 ───────────────────────────────────────────
    @filter.on_event("message.processed")
    def after_process(self, data):
        message = data.get("message")
        response = data.get("response")
        if response and message:
            self.logger.info(
                f"[sdk_example] processed -> {str(response)[:80]}"
            )
