# 适配器开发

本指南介绍如何开发 Qtine 适配器，对接新的聊天平台。

## 核心概念

适配器（Adapter）负责：

1. **接收消息**：从平台接收原始消息，转换为 Qtine 内部 `Message` 对象
2. **发送消息**：将 Qtine 的回复转换为平台格式并发送
3. **生命周期管理**：连接、断开、重连

## BaseAdapter

所有适配器继承 `BaseAdapter`：

```python
from qtine.adapters.base import BaseAdapter
from qtine.utils.models import AdapterStatus, Message, Sender


class MyAdapter(BaseAdapter):
    def __init__(self, name="my-adapter"):
        super().__init__(name, "MyProtocol")
        # 自定义初始化
```

## 必须实现的方法

### start()

启动适配器。

```python
def start(self) -> None:
    self.logger.info(f"[{self.name}] 启动中...")
    self._update_status(AdapterStatus.CONNECTING)
    self._running = True
    # 建立连接、启动接收循环等
```

### stop()

停止适配器，释放资源。

```python
def stop(self) -> None:
    self._running = False
    # 关闭连接、清理资源
    self._update_status(AdapterStatus.DISCONNECTED)
```

### serve(ws, environ)

处理反向 WebSocket 连接（如果支持）。

```python
def serve(self, ws, environ) -> None:
    """处理客户端连接"""
    sid = uuid.uuid4().hex
    self._register_client(sid, ws)
    try:
        while self._running:
            raw = ws.receive()
            if raw is None:
                continue
            data = json.loads(raw)
            self._handle_data(sid, data)
    finally:
        self._deregister_client(sid)
```

### send_message(target, message, message_type)

发送消息到平台。

```python
def send_message(
    self,
    target: str,
    message: str,
    message_type: str = "group"
) -> bool:
    """发送消息"""
    try:
        # 转换为平台格式并发送
        payload = self._build_send_payload(target, message, message_type)
        self._ws.send(json.dumps(payload))
        self._adapter_info.message_count += 1
        return True
    except Exception as e:
        self.logger.error(f"发送失败: {e}")
        self._adapter_info.error_count += 1
        return False
```

## 消息转换

将平台原始消息转换为 Qtine `Message` 对象：

```python
from qtine.utils.models import Message, Sender


def _convert_message(self, raw: dict) -> Message:
    """平台原始消息 → Qtine Message"""
    return Message(
        adapter=self.name,
        message_id=str(raw["id"]),
        content=raw["text"],
        message_type="group" if raw.get("group_id") else "private",
        group_id=str(raw.get("group_id", "")),
        sender=Sender(
            user_id=str(raw["user_id"]),
            nickname=raw.get("nickname", ""),
            card=raw.get("card", "")
        ),
        raw_message=raw.get("raw", ""),
        timestamp=raw.get("time", 0)
    )
```

### Message 对象

```python
class Message:
    adapter: str          # 适配器名
    message_id: str       # 消息 ID
    content: str          # 文本内容
    message_type: str     # group / private
    group_id: str         # 群 ID（私聊为空）
    sender: Sender        # 发送者
    raw_message: str      # 原始消息（含 CQ 码等）
    timestamp: int        # 时间戳
```

### Sender 对象

```python
class Sender:
    user_id: str          # 用户 ID
    nickname: str         # 昵称
    card: str             # 群名片
    role: str             # 角色（owner/admin/member）
    level: str            # 等级
    title: str            # 头衔
```

## 触发消息事件

收到消息后，调用 `_emit_message` 触发回调链：

```python
def _handle_data(self, sid: str, data: dict):
    """处理收到的数据"""
    if data.get("type") == "message":
        message = self._convert_message(data)
        self._adapter_info.message_count += 1
        # 触发消息事件，最终调用 QtineBot.handle_message
        self._emit_message(message)
```

## 适配器信息

通过 `_adapter_info` 维护状态：

```python
class AdapterInfo:
    name: str             # 适配器名
    protocol: str         # 协议名
    status: AdapterStatus # 状态
    account_id: str       # Bot 账号
    connected_at: float   # 连接时间戳
    message_count: int    # 消息计数
    error_count: int      # 错误计数
```

### 状态更新

```python
# 连接中
self._update_status(AdapterStatus.CONNECTING)

# 已连接
self._update_status(AdapterStatus.CONNECTED, account_id="123")

# 断开
self._update_status(AdapterStatus.DISCONNECTED)

# 错误
self._update_status(AdapterStatus.ERROR)
```

## 完整示例：Discord 适配器

```python
"""Discord 适配器示例"""
import json
import threading
import websocket
from qtine.adapters.base import BaseAdapter
from qtine.utils.models import AdapterStatus, Message, Sender


class DiscordAdapter(BaseAdapter):
    def __init__(self, name="discord", token="", ws_path="/discord/ws"):
        super().__init__(name, "Discord")
        self.token = token
        self.ws_path = ws_path
        self._clients = {}

    def start(self) -> None:
        self.logger.info(f"[{self.name}] 启动")
        self._update_status(AdapterStatus.CONNECTING)
        self._running = True

    def stop(self) -> None:
        self._running = False
        for ws in self._clients.values():
            try:
                ws.close()
            except Exception:
                pass
        self._clients.clear()
        self._update_status(AdapterStatus.DISCONNECTED)

    def serve(self, ws, environ) -> None:
        sid = f"discord-{id(ws)}"
        self._clients[sid] = ws
        self._update_status(AdapterStatus.CONNECTED)
        self.logger.info(f"[{self.name}] 客户端连接: {sid}")

        try:
            while self._running:
                raw = ws.receive()
                if raw is None:
                    continue
                data = json.loads(raw)
                if data.get("type") == "MESSAGE_CREATE":
                    message = self._convert_message(data["data"])
                    self._emit_message(message)
        except Exception as e:
            self.logger.error(f"[{self.name}] 连接错误: {e}")
        finally:
            self._clients.pop(sid, None)

    def _convert_message(self, raw: dict) -> Message:
        return Message(
            adapter=self.name,
            message_id=raw["id"],
            content=raw["content"],
            message_type="group" if raw.get("guild_id") else "private",
            group_id=str(raw.get("guild_id", "")),
            sender=Sender(
                user_id=raw["author"]["id"],
                nickname=raw["author"]["username"],
                card=""
            ),
            raw_message=raw["content"],
            timestamp=int(raw.get("timestamp", 0))
        )

    def send_message(self, target, message, message_type="group") -> bool:
        if not self._clients:
            return False
        payload = {
            "action": "send_message",
            "target": target,
            "message": message,
            "message_type": message_type
        }
        try:
            for ws in self._clients.values():
                ws.send(json.dumps(payload))
            self._adapter_info.message_count += 1
            return True
        except Exception as e:
            self.logger.error(f"发送失败: {e}")
            self._adapter_info.error_count += 1
            return False
```

## 打包分发

### .zip 包结构

```
my-adapter.zip
├── adapter.json          # 清单
├── adapter.py            # 入口
└── ...其他文件
```

### adapter.json

```json
{
  "name": "discord",
  "protocol": "Discord",
  "version": "1.0.0",
  "author": "你的名字",
  "entry": "adapter.py",
  "config": {
    "ws_endpoint": "/discord/ws"
  }
}
```

### adapter.py

```python
from qtine.adapters.base import BaseAdapter


class DiscordAdapter(BaseAdapter):
    def __init__(self, name="discord"):
        super().__init__(name, "Discord")
    # ...
```

Qtine 会自动扫描 .zip 中的 `BaseAdapter` 子类并实例化。

## 注册到 AdapterManager

### 内置适配器

在 `qtine/core/adapter_manager.py` 的 `create_onebot_adapter` 旁边添加：

```python
def create_discord_adapter(self, config: dict, bot=None):
    from qtine.adapters.discord import DiscordAdapter
    adapter = DiscordAdapter(
        name="discord",
        token=config.get("token", "")
    )
    adapter.bot = bot
    self.register(adapter)
    return adapter
```

### 外部适配器

通过 WebUI 上传 .zip 包导入，或放到 `adapters/` 目录。

## 测试

### 单元测试

```python
def test_message_conversion():
    adapter = DiscordAdapter()
    raw = {
        "id": "123",
        "content": "hello",
        "author": {"id": "456", "username": "test"}
    }
    msg = adapter._convert_message(raw)
    assert msg.content == "hello"
    assert msg.sender.nickname == "test"
```

### 集成测试

1. 启动 Qtine
2. 导入适配器
3. 模拟客户端连接
4. 发送测试消息
5. 验证消息处理和回复

## 最佳实践

1. **错误处理**：网络异常要捕获并重连
2. **日志**：连接、断开、消息收发都要记录
3. **线程安全**：WebSocket 操作加锁
4. **资源释放**：`stop()` 中关闭所有连接
5. **消息计数**：维护 `message_count` 和 `error_count`
6. **状态同步**：及时更新 `AdapterStatus`
