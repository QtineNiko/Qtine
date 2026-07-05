# Qtine 插件 SDK

一个受 AstrBot 启发的极简插件开发 SDK。目标：
**你只需要 `from sdk import ...`，就能开发 Qtine 插件。**

底层完全复用 Qtine 原生插件系统（`qtine.plugins.base.BasePlugin`、
命令/正则/关键词管道、事件总线、适配器），不改动任何现有代码，
兼容现有 `plugin_manager` 加载流程。

---

## 1. 最小示例

```python
# my_plugin/main.py
from sdk import Plugin, filter

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "我的第一个插件"

    @filter.command("hello", aliases=["hi"])
    def hello(self, ctx):
        ctx.reply(f"你好，{ctx.sender_name}！")
```

放到 `plugins/` 目录（zip 或 dir 格式），Qtine 就会自动加载。

---

## 2. 支持的能力

### 2.1 命令

```python
@filter.command("/echo", aliases=["/e", "/复读"])
def echo(self, ctx, args):
    # args: List[str] 是命令后的分词参数
    ctx.reply(" ".join(args))

@filter.command("qtine reload", permission="admin")
def reload(self, ctx, args):
    ctx.reply("only admin can reach here")
```

- 会自动注册到底层 `register_command`，走 Qtine 原生权限校验、频率限制、黑名单等。
- 处理器签名支持 `(ctx)` 或 `(ctx, args)`。

### 2.2 正则

```python
@filter.regex(r"^echo (.+)$")
def echo(self, ctx, match):
    ctx.reply(match.group(1))
```

### 2.3 关键词

```python
@filter.keyword(["ping", "PING"])
def ping(self, ctx):
    ctx.reply("pong")
```

### 2.4 通用消息监听

```python
@filter.on_message()
def any_message(self, ctx):
    self.logger.info(f"收到：{ctx.text}")
```

### 2.5 事件总线

订阅 Qtine 内部/适配器事件：

```python
@filter.on_event("adapter.onebot_v11.notice")
def on_notice(self, data):
    self.logger.info(f"OneBot notice: {data}")

@filter.on_event("message.processed")
def after_process(self, data):
    # data = {"message": ..., "response": ...}
    pass
```

---

## 3. `ctx` 上下文

所有回调都会收到一个 `Context`（`sdk.Context`）：

| 属性 / 方法 | 说明 |
|---|---|
| `ctx.text` | 消息纯文本 |
| `ctx.sender` | `Sender` 对象 |
| `ctx.sender_id` | 用户 QQ 号 |
| `ctx.sender_name` | 昵称 / 群名片 |
| `ctx.group_id` | 群号，私聊为 `None` |
| `ctx.adapter` | 适配器名，例如 `"onebot_v11"` |
| `ctx.is_group` / `ctx.is_private` | 会话类型 |
| `ctx.message_id` | OneBot 消息 ID |
| `ctx.reply(payload)` | 回复当前会话（走管道 response） |
| `ctx.send(payload)` | 直接推送到当前会话 |
| `ctx.send_to(target, payload, message_type, adapter)` | 跨会话发送 |
| `ctx.send_image(url_or_path)` | 便捷发图片 |
| `ctx.send_chain(chain)` | 发送 `MessageChain` |

`payload` 可以是：

- `str`：纯文本，会做 CQ 码转义
- `MessageSegment`：`Plain / Image / At / Face / Reply`
- `MessageChain`：消息链
- `list[MessageSegment | str]`：会被自动包成 `MessageChain`

---

## 4. 发送富媒体消息

```python
from sdk import Plugin, filter, MessageChain, Plain, Image, At

class RichPlugin(Plugin):
    name = "rich"

    @filter.command("/pic")
    def pic(self, ctx):
        ctx.send_image("https://example.com/cat.jpg")

    @filter.command("/mix")
    def mix(self, ctx):
        chain = MessageChain([
            At(ctx.sender_id),
            Plain(" 看看这张图："),
            Image.from_url("https://example.com/a.jpg"),
        ])
        ctx.reply(chain)

    @filter.command("/local")
    def local(self, ctx):
        ctx.send(Image.from_file("/data/imgs/hi.png"))
```

内部会自动序列化为 OneBot V11 CQ 码，例如：

```
[CQ:at,qq=123456] 看看这张图：[CQ:image,file=https://example.com/a.jpg]
```

---

## 5. 主动推送消息

在事件回调、后台任务里可以直接用：

```python
class Notifier(Plugin):
    name = "notifier"

    @filter.on_event("message.processed")
    def after(self, data):
        # 主动私聊某个用户
        self.send(target="123456", payload="有新消息处理完成", message_type="private")

        # 或者在 ctx 里：
        # ctx.send_to("123456", "hi", "private")
```

---

## 6. 生命周期钩子

沿用底层 `BasePlugin`：

```python
class MyPlugin(Plugin):
    def on_load(self):    # 加载时
        ...
    def on_enable(self):  # 启用时
        ...
    def on_disable(self): # 禁用时
        ...
    def on_unload(self):  # 卸载时
        ...
```

---

## 7. 打包结构

Qtine 的插件加载器支持 zip 或目录格式：

```
my_plugin/
├── data.json         # 元数据
├── main.py           # 必须包含唯一一个 Plugin 子类
├── icon.png          # 可选
└── command/          # 可选，供 main.py 内部 import
    ├── __init__.py
    └── xxx.py
```

`data.json` 示例：

```json
{
  "name": "my_plugin",
  "package": "qtine-plugin-my-plugin",
  "version": "1.0.0",
  "description": "示例插件",
  "author": "you",
  "entry": "main",
  "requires": []
}
```

---

## 8. 与旧接口互操作

- SDK 的 `Plugin` **就是** `qtine.plugins.base.BasePlugin` 的子类，两种写法可以在同一项目中共存。
- 旧插件（继承 `BasePlugin` + `self.register_command`）不需要改。
- 新插件写起来更短，等价于旧接口 + 自动注册。
