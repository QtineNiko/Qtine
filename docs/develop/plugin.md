# 插件开发

本指南介绍如何开发 Qtine 插件。

## 快速开始

### 1. 创建插件文件

在 `plugins/` 目录下创建 `my-plugin.py`：

```python
from qtine.plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    name = "my-plugin"
    description = "我的第一个插件"
    version = "1.0.0"
    author = "你的名字"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/hello", self.handle_hello)

    def handle_hello(self, event, args):
        return f"你好，{event.message.sender.nickname}！"
```

### 2. 重载插件

在 QQ 里发送：

```
qtine reload my-plugin
```

或重启 Qtine。

### 3. 测试

发送命令：

```
/hello
```

机器人回复：

```
你好，张三！
```

## 插件结构

### 基本属性

```python
class MyPlugin(BasePlugin):
    name = "my-plugin"           # 插件标识（唯一）
    description = "插件描述"      # 显示在插件列表
    version = "1.0.0"            # 版本号
    author = "作者"              # 作者
    enabled = True               # 是否默认启用
```

### 初始化

```python
def __init__(self, bot=None):
    super().__init__(bot)
    # 注册命令、初始化状态等
    self.register_command("/my", self.handle_my)
    self.counter = 0
```

::: tip
`bot` 参数是 `QtineBot` 实例，可以通过它访问 storage、event_bus、adapter_manager 等。
:::

## 注册命令

### 命令匹配

精确匹配命令前缀：

```python
def __init__(self, bot=None):
    super().__init__(bot)
    # 注册命令：/my <args>
    self.register_command(
        "/my",                   # 命令前缀
        self.handle_my,          # 处理函数
        aliases=["/m"],          # 别名（可选）
        permission="user",       # 权限：user / admin
        help_text="我的命令"     # 帮助文本
    )
```

### 处理函数签名

```python
def handle_my(self, event, args):
    """
    event: PipelineContext，包含消息、回复方法等
    args: 命令后面的参数字符串
    """
    message = event.message
    sender = message.sender

    if not args:
        return "请提供参数"

    return f"你输入了: {args}"
```

### 示例：带参数的命令

```python
def __init__(self, bot=None):
    super().__init__(bot)
    self.register_command("/calc", self.handle_calc)

def handle_calc(self, event, args):
    """简单计算器：/calc 1 + 2"""
    parts = args.split()
    if len(parts) != 3:
        return "用法：/calc <数字> <运算符> <数字>"

    a, op, b = parts
    try:
        a, b = float(a), float(b)
    except ValueError:
        return "参数必须是数字"

    ops = {
        "+": lambda: a + b,
        "-": lambda: a - b,
        "*": lambda: a * b,
        "/": lambda: a / b if b != 0 else None,
    }

    if op not in ops:
        return f"不支持的运算符: {op}"

    result = ops[op]()
    if result is None:
        return "错误：除以零"

    return f"{a} {op} {b} = {result}"
```

## 注册正则匹配

```python
import re

def __init__(self, bot=None):
    super().__init__(bot)
    # 匹配 "天气 北京" "天气 上海" 等
    self.register_regex(r"天气\s+(\S+)", self.handle_weather)

def handle_weather(self, event, match):
    """正则匹配处理函数，第二个参数是 Match 对象"""
    city = match.group(1)
    # 调用天气 API
    return f"{city} 的天气：晴 25°C"
```

## 注册关键词匹配

```python
def __init__(self, bot=None):
    super().__init__(bot)
    self.register_keyword("早安", self.handle_morning)
    self.register_keyword("晚安", self.handle_night)

def handle_morning(self, event):
    """关键词匹配处理函数"""
    sender = event.message.sender
    return f"{sender.nickname} 早安！"

def handle_night(self, event):
    return "晚安好梦~"
```

## 回复消息

### 方式一：返回字符串

处理函数返回的字符串会自动作为回复发送。

```python
def handle_hello(self, event, args):
    return "Hello!"  # 自动回复
```

### 方式二：调用 ctx.reply()

```python
def handle_long(self, event, args):
    # 多次回复
    event.reply("第一段")
    event.reply("第二段")
    # 返回 None，不再自动回复
    return None
```

## 使用存储

```python
class CounterPlugin(BasePlugin):
    name = "counter"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/count", self.handle_count)

    def handle_count(self, event, args):
        user_id = event.message.sender.user_id
        key = f"counter:{user_id}"

        count = self.bot.storage.get(key, 0)
        count += 1
        self.bot.storage.set(key, count)

        return f"你调用了 {count} 次"
```

## 订阅事件

```python
class LogPlugin(BasePlugin):
    name = "logger"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.bot.event_bus.subscribe(
            "message.received", self.on_message
        )

    def on_message(self, data):
        message = data["message"]
        self.logger.info(f"收到消息: {message.content}")

    def on_unload(self):
        # 卸载时取消订阅，避免内存泄漏
        self.bot.event_bus.unsubscribe(
            "message.received", self.on_message
        )
```

::: warning
插件卸载时**必须**取消事件订阅，否则会导致内存泄漏。
:::

## 发送主动消息

不依赖回复，主动发消息：

```python
def handle_broadcast(self, event, args):
    """给指定群发送消息"""
    group_id = "123456789"
    self.bot.adapter_manager.send_message(
        "onebot_v11",        # 适配器名
        group_id,            # 目标 ID
        "这是主动消息",       # 消息内容
        "group"              # 消息类型：group / private
    )
    return "已发送"
```

## 插件配置

### 读取配置

插件可以通过 `self.config` 读取配置：

```yaml
# config.yml
plugins:
  my-plugin:
    threshold: 5
    prefix: "[MyPlugin]"
```

```python
class MyPlugin(BasePlugin):
    name = "my-plugin"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.threshold = self.bot.config.get(
            f"plugins.{self.name}.threshold", 5
        )
        self.prefix = self.bot.config.get(
            f"plugins.{self.name}.prefix", ""
        )
```

## 日志

```python
class MyPlugin(BasePlugin):
    name = "my-plugin"

    def handle_command(self, event, args):
        self.logger.info(f"收到命令: {args}")
        self.logger.debug(f"发送者: {event.message.sender}")
        try:
            result = self.do_something()
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            return "处理失败"
        self.logger.info(f"处理完成: {result}")
        return result
```

## 打包分发

### .zip 包结构

```
my-plugin.zip
├── plugin.json          # 清单（必需）
├── main.py              # 入口（必需）
└── ...其他文件
```

### plugin.json

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "我的插件",
  "author": "你的名字",
  "entry": "main.py"
}
```

### main.py

主文件必须包含一个继承 `BasePlugin` 的类，Qtine 会自动实例化。

## 生命周期钩子

```python
class MyPlugin(BasePlugin):
    name = "my-plugin"

    def on_load(self):
        """插件加载时调用"""
        self.logger.info("插件已加载")
        # 初始化资源、连接数据库等

    def on_enable(self):
        """插件启用时调用"""
        self.logger.info("插件已启用")

    def on_disable(self):
        """插件禁用时调用"""
        self.logger.info("插件已禁用")

    def on_unload(self):
        """插件卸载时调用"""
        self.logger.info("插件已卸载")
        # 释放资源、取消事件订阅等
```

## 最佳实践

1. **错误处理**：处理函数内部 try/except，避免异常导致管道崩溃
2. **幂等性**：命令重复执行不应产生副作用
3. **性能**：避免在处理函数中执行耗时操作，必要时用线程
4. **日志**：关键操作记录日志，便于排查
5. **配置**：可配置项通过 `config.yml` 管理，避免硬编码
6. **权限**：敏感命令声明 `permission="admin"`
7. **卸载清理**：`on_unload` 中释放资源、取消订阅

## 示例：完整插件

```python
"""投票插件 - 群内发起投票"""
from qtine.plugins.base import BasePlugin


class VotePlugin(BasePlugin):
    name = "vote"
    description = "群内投票"
    version = "1.0.0"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command(
            "/vote",
            self.handle_vote,
            permission="user",
            help_text="发起投票: /vote <主题>"
        )
        self.register_command(
            "/voteresult",
            self.handle_result,
            permission="user",
            help_text="查看投票结果"
        )

    def handle_vote(self, event, args):
        if not args:
            return "用法：/vote <主题>"

        group_id = event.message.group_id
        if not group_id:
            return "仅在群聊中可用"

        key = f"vote:{group_id}"
        vote_data = self.bot.storage.get(key, None)

        if vote_data:
            return f"已有进行中的投票: {vote_data['topic']}"

        self.bot.storage.set(key, {
            "topic": args,
            "yes": 0,
            "no": 0,
            "voters": []
        })
        return f"投票已发起: {args}\n回复 'yes' 或 'no' 投票"

    def handle_result(self, event, args):
        group_id = event.message.group_id
        key = f"vote:{group_id}"
        vote_data = self.bot.storage.get(key, None)

        if not vote_data:
            return "当前没有进行中的投票"

        return (
            f"投票主题: {vote_data['topic']}\n"
            f"赞成: {vote_data['yes']}\n"
            f"反对: {vote_data['no']}"
        )
```
