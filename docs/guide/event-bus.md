# 事件总线

事件总线（Event Bus）是 Qtine 内部模块间解耦通信的机制，采用发布/订阅模式。

## 基本概念

- **发布者**：产生事件的模块
- **订阅者**：关注某类事件并响应的模块
- **事件**：包含类型和数据的通知

## 内置事件

Qtine 内置以下事件：

| 事件名 | 触发时机 | 数据 |
|--------|----------|------|
| `bot.started` | 机器人启动 | `{"time": timestamp}` |
| `bot.stopped` | 机器人停止 | `{"time": timestamp}` |
| `message.received` | 收到新消息 | `{"message": Message}` |
| `message.processed` | 消息处理完成 | `{"message": Message, "response": str}` |
| `adapter.connected` | 适配器连接成功 | `{"adapter": name, "self_id": str}` |
| `adapter.disconnected` | 适配器断开 | `{"adapter": name}` |
| `plugin.loaded` | 插件加载 | `{"plugin": name}` |
| `plugin.enabled` | 插件启用 | `{"plugin": name}` |
| `plugin.disabled` | 插件禁用 | `{"plugin": name}` |

## 订阅事件

```python
from qtine.core.bus import EventBus


def on_message_received(data):
    message = data["message"]
    print(f"新消息: {message.content}")


# 订阅
event_bus = EventBus()
event_bus.subscribe("message.received", on_message_received)
```

## 发布事件

```python
event_bus.publish("my.custom.event", {"key": "value"})
```

## 在插件中使用

插件可以通过 `self.bot.event_bus` 访问事件总线：

```python
from qtine.plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    name = "my-plugin"

    def __init__(self, bot=None):
        super().__init__(bot)
        # 订阅消息事件
        self.bot.event_bus.subscribe(
            "message.received", self.on_message
        )

    def on_message(self, data):
        message = data["message"]
        # 自定义逻辑
        pass

    def on_unload(self):
        # 卸载时取消订阅，避免内存泄漏
        self.bot.event_bus.unsubscribe(
            "message.received", self.on_message
        )
```

::: warning
插件卸载时务必取消订阅，否则会导致回调引用旧插件实例，引发内存泄漏和错误。
:::

## 异步处理

事件订阅者的执行是同步的，在发布者线程中执行。如果需要异步处理耗时操作：

```python
import threading


def on_message_received(data):
    # 启动新线程处理
    threading.Thread(
        target=process_in_background,
        args=(data,),
        daemon=True,
    ).start()


def process_in_background(data):
    # 耗时操作
    pass
```

## 使用场景

- **日志统计**：订阅 `message.processed` 统计回复率
- **自动回复**：订阅 `message.received` 实现关键词自动回复
- **状态同步**：订阅 `adapter.connected` 同步 Bot 信息到外部系统
- **插件联动**：一个插件发布事件，另一个插件订阅

## 与消息管道的区别

| 机制 | 触发时机 | 能否回复 | 用途 |
|------|----------|----------|------|
| 消息管道 | 消息进入时 | 能 | 命令处理、消息转换 |
| 事件总线 | 各种事件 | 不能（直接） | 旁路监听、统计、联动 |

事件总线是**旁路**机制，不影响主流程，适合解耦的模块间通信。
