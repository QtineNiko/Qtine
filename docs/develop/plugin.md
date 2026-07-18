# 插件开发

Qtine 插件运行在机器人进程内，可以注册命令、正则、关键词、事件监听和配置项。插件代码拥有当前进程权限，只安装可信插件。

## 选择开发方式

Qtine 提供两套接口：

- 原生接口：继承 `qtine.plugins.base.BasePlugin`，手动调用 `register_command()` 等方法。
- SDK 接口：继承 `sdk.Plugin`，使用 `sdk.filter` 装饰器，适合新插件。

两套接口可以共存。SDK 最终仍注册到底层 `BasePlugin`。

## 原生插件

### 最小插件

```python
from qtine.plugins.base import BasePlugin


class HelloPlugin(BasePlugin):
    name = "hello"
    package = "qtine-plugin-hello"
    version = "1.0.0"
    description = "问候命令"
    author = "your-name"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command(
            "/hello",
            self.handle_hello,
            aliases=["/hi"],
        )

    def handle_hello(self, event, args):
        sender = event.message.sender
        name = sender.nickname if sender else "world"
        return f"你好，{name}！"
```

处理器的第一个参数是 `PipelineContext`，不是 `PluginEvent`。常用属性：

- `event.message`：内部 `Message` 对象
- `event.message.content`：消息文本
- `event.message.sender`：发送者，可能为 `None`
- `event.message.group_id`：群号，私聊为 `None`
- `event.reply(text)`：写入当前管道响应
- `event.get(key, default)` / `event.set(key, value)`：管道上下文数据

返回字符串会自动作为当前会话的回复。没有返回值时，可以调用 `event.reply()`：

```python
def handle_status(self, event, args):
    event.reply("处理中")
    return None
```

### 命令

```python
self.register_command(
    "/weather",
    self.handle_weather,
    aliases=["/天气"],
    permission="user",
)

self.register_command(
    "/admin-task",
    self.handle_admin_task,
    permission="admin",
)
```

命令处理器签名：`handler(event, args)`。

- `args` 是命令后的参数列表，例如 `/echo hello world` 对应 `["hello", "world"]`。
- `permission` 支持 `user` 和 `admin`。
- 管理员命令由核心根据 `security.super_admins` 校验，插件不应自行信任用户输入。
- 命令匹配优先于正则和关键词匹配；命中后会停止继续匹配。

### 正则

```python
import re


class WeatherPlugin(BasePlugin):
    name = "weather"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_regex(r"^天气\\s+(.+)$", self.handle_weather)

    def handle_weather(self, event, match):
        city = match.group(1).strip()
        return f"查询城市：{city}"
```

正则处理器签名：`handler(event, match)`。Qtine 使用 `re.match()`，需要完整匹配时请在表达式中使用 `^` 和 `$`。

### 关键词

```python
class PingPlugin(BasePlugin):
    name = "ping"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_keyword(["ping", "PING"], self.handle_ping)

    def handle_ping(self, event):
        return "pong"
```

关键词处理器签名：`handler(event)`。消息包含任意关键词时触发，关键词匹配位于命令和正则之后。

## SDK 插件

### 最小示例

```python
from sdk import Plugin, filter


class HelloPlugin(Plugin):
    name = "hello_sdk"
    package = "qtine-plugin-hello-sdk"
    version = "1.0.0"
    description = "SDK 问候命令"
    author = "your-name"

    @filter.command("/hello", aliases=["/hi"])
    def hello(self, ctx):
        ctx.reply(f"你好，{ctx.sender_name or ctx.sender_id}！")
```

`Plugin.__init__()` 会扫描装饰器并自动注册。

### SDK 装饰器

```python
from sdk import Plugin, filter


class ExamplePlugin(Plugin):
    name = "sdk_example"

    @filter.command("/echo", aliases=["/复读"], permission="user")
    def echo(self, ctx, args):
        ctx.reply(" ".join(args) if args else "用法：/echo <内容>")

    @filter.regex(r"^echo\\s+(.+)$")
    def echo_regex(self, ctx, match):
        ctx.reply(match.group(1))

    @filter.keyword(["ping", "PING"])
    def ping(self, ctx):
        ctx.reply("pong")

    @filter.on_event("message.processed")
    def after_message(self, data):
        message = data.get("message")
        response = data.get("response")
        self.logger.info("processed: %s", bool(message and response))
```

- `@filter.command(name, aliases=None, permission="user")`：命令。
- `@filter.regex(pattern)`：正则，回调接收 `ctx, match`。
- `@filter.keyword(keywords)`：关键词，回调接收 `ctx`。
- `@filter.on_event(event)`：事件总线监听，回调接收 `data`。
- `@filter.on_message()`：当前 SDK 保留了该声明接口，但核心消息管道尚未自动调用监听器；当前版本不要依赖它实现业务逻辑。

### SDK Context

常用属性和方法：

- `ctx.message`：底层 `Message`
- `ctx.pipeline_ctx`：当前管道上下文，事件回调中通常为 `None`
- `ctx.bot`：`QtineBot`
- `ctx.text`：消息文本
- `ctx.sender`：`Sender`
- `ctx.sender_id`、`ctx.sender_name`
- `ctx.group_id`、`ctx.adapter`、`ctx.message_id`
- `ctx.is_group`、`ctx.is_private`
- `ctx.reply(payload)`：管道回复；非管道场景自动发送
- `ctx.send(payload)`：直接回复当前会话
- `ctx.send_to(target, payload, message_type="private", adapter=None)`：发送到指定会话
- `ctx.send_image(file)`：发送图片
- `ctx.send_chain(chain)`：发送消息链
- `ctx.get(key, default)`、`ctx.set(key, value)`：上下文数据

### 消息链

```python
from sdk import At, Image, MessageChain, Plain, Plugin, filter


class RichPlugin(Plugin):
    name = "rich"

    @filter.command("/mix")
    def mix(self, ctx):
        chain = MessageChain([
            At(ctx.sender_id),
            Plain(" 图片："),
            Image.from_url("https://example.com/image.jpg"),
        ])
        ctx.reply(chain)
```

可用消息段：`Plain`、`Image`、`At`、`Face`、`Reply`。`Image` 支持 URL、本地文件和 Base64。SDK 会将消息链序列化为 OneBot V11 CQ 码。

## 存储

`bot.storage` 提供 SQLite 或内存存储，值必须能够被 JSON 序列化：

```python
class CounterPlugin(BasePlugin):
    name = "counter"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/count", self.handle_count)

    def handle_count(self, event, args):
        user_id = event.message.sender.user_id
        key = f"counter.{user_id}"
        count = self.bot.storage.get(key, 0) + 1
        self.bot.storage.set(key, count)
        return f"调用次数：{count}"
```

不要把密码、Token 或其他敏感信息写入消息日志或插件源码。

## 插件配置

### 配置声明

使用 `add_config()` 声明配置项，WebUI 会根据 schema 显示配置表单：

```python
class RepeatPlugin(BasePlugin):
    name = "repeat"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.add_config(
            "threshold",
            "触发次数",
            default=3,
            config_type="number",
            description="相同消息出现多少次后触发",
        )
        self.add_config(
            "enabled",
            "启用复读",
            default=True,
            config_type="boolean",
        )
```

支持的 `config_type`：`text`、`number`、`boolean`、`select`、`textarea`、`password`。下拉选项格式为：

```python
options=[
    {"label": "快速", "value": "fast"},
    {"label": "准确", "value": "accurate"},
]
```

### 读取和写入

```python
threshold = self.get_config("threshold", 3)
self.set_config("threshold", max(2, int(threshold)))

if event.message.group_id:
    group_threshold = self.get_group_config(
        event.message.group_id,
        "threshold",
        3,
    )
    self.set_group_config(
        event.message.group_id,
        "threshold",
        group_threshold,
    )
```

群配置不存在时会回退到全局配置。配置数据存储在 Qtine 的存储后端，不直接写入 `config.yml`。

## 事件总线

原生插件可直接订阅事件：

```python
class AuditPlugin(BasePlugin):
    name = "audit"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.subscription_id = bot.event_bus.subscribe(
            "message.processed",
            self.on_processed,
            priority=0,
        )

    def on_processed(self, data):
        message = data.get("message")
        self.logger.info("处理消息：%s", message.message_id)

    def on_unload(self):
        if self.subscription_id:
            self.bot.event_bus.unsubscribe(self.subscription_id)
```

`subscribe()` 返回订阅 ID，取消订阅必须传入这个 ID，而不是事件名和回调函数。

常见事件：

- `message.processed`：消息处理完成，数据为 `{ "message": Message, "response": str | None }`。
- `adapter.onebot_v11.notice`：OneBot notice 事件。
- `adapter.onebot_v11.request`：OneBot request 事件。
- `adapter.onebot_v11.meta_event`：OneBot meta event 事件。
- `bot.started`、`bot.stopped`：机器人生命周期事件。

SDK 的 `@filter.on_event()` 会自动完成订阅。事件回调不在消息处理管道中，不能使用当前消息的 `ctx.reply()`；需要发送时使用插件的 `send()` 或保存目标后调用适配器。

## 主动发送

原生接口：

```python
self.bot.adapter_manager.send_message(
    "onebot_v11",
    "123456789",
    "主动消息",
    "private",
)
```

SDK 接口：

```python
self.send(
    target="123456789",
    payload="主动消息",
    message_type="private",
    adapter="onebot_v11",
)
```

发送目标来自用户输入时，应先校验目标类型和权限，避免被滥用为消息转发接口。

## 生命周期

```python
class MyPlugin(BasePlugin):
    name = "my-plugin"

    def on_load(self):
        self.logger.info("资源初始化")

    def on_enable(self):
        self.logger.info("插件启用")

    def on_disable(self):
        self.logger.info("插件禁用")

    def on_unload(self):
        self.logger.info("释放资源")
```

- `on_load()`：插件实例注册时调用。
- `on_enable()`：加载后以及通过管理接口启用时调用。
- `on_disable()`：通过管理接口禁用时调用。
- `on_unload()`：卸载或重载前调用。

在 `on_unload()` 中关闭线程、定时器、文件、网络连接并取消事件订阅。

## 打包格式

Qtine 当前自动扫描 `plugins/` 目录中的以下格式：

1. 标准目录插件：目录内包含 `data.json` 和 `main.py`。
2. 标准 ZIP 插件：ZIP 内包含 `data.json` 和 `main.py`，可以直接放在根目录，也可以放在唯一的外层目录中。
3. 旧式单文件插件：`plugins/example.py`，文件中包含 `BasePlugin` 子类。
4. 旧式目录插件：目录内包含 `__init__.py`。

推荐使用标准目录或 ZIP 格式。

### data.json

```json
{
  "name": "hello_sdk",
  "package": "qtine-plugin-hello-sdk",
  "version": "1.0.0",
  "description": "SDK 示例插件",
  "author": "your-name",
  "entry": "main",
  "requires": [],
  "depends_on": []
}
```

字段说明：

- `name`：插件唯一名称，只允许字母、数字、点、下划线和连字符。
- `package`：发布包名称，可选。
- `version`、`description`、`author`：展示信息。
- `entry`：入口模块，默认 `main`；`main.py` 可省略扩展名。
- `requires`：pip 依赖列表。生产环境默认禁止运行时安装依赖。
- `depends_on`：其他 Qtine 插件名称列表，加载时按依赖顺序处理。

入口文件必须包含一个 `BasePlugin` 或 `sdk.Plugin` 子类。可选文件包括 `icon.png` 和其他 Python 模块。

### 打包命令

```bash
cd my-plugin
zip -r ../my-plugin.zip data.json main.py icon.png command/
```

不要把 `.venv`、Token、数据库、日志或密钥打入插件包。

## 安装和管理

- 将目录或 ZIP 放入 `plugins/` 后重启，或通过 WebUI 的插件上传功能导入。
- 管理命令：`qtine list`、`qtine enable <name>`、`qtine disable <name>`、`qtine reload <name>`。
- 内置插件不能卸载或重载，但可以禁用。
- 外部插件可以通过 WebUI 卸载。

WebUI 上传接口：`POST /api/plugins/upload`，字段名为 `file`，只接受 ZIP。

## 安全与兼容性

- 插件代码等同于本地 Python 代码，使用可信来源。
- 上传 ZIP 会检查路径穿越、符号链接、文件数量和解压大小。
- 生产环境默认禁止插件安装 pip 依赖；请在镜像构建阶段固定安装依赖。
- 管理命令使用 `permission="admin"`，不要只在插件内部判断昵称或群名片。
- 处理器不要执行长时间阻塞操作；需要外部请求时设置超时并处理异常。
- 不要在插件中修改全局单例状态，除非明确了解其生命周期。
- 代码兼容 Python 3.9+，优先使用标准库和项目已有依赖。

## 测试插件

建议在独立测试环境中运行：

```bash
python -m compileall -q main.py qtine sdk tests
python -m unittest discover -s tests -v
```

可参考：

- `examples/example_plugin/`：原生插件结构示例。
- `examples/sdk_plugin/`：SDK 装饰器、消息链和事件示例。
