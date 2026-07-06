# 适配器配置

## OneBot V11 适配器

```yaml
adapters:
  onebot_v11:
    enabled: true                # 是否启用
    ws_path: "/onebot/v11"       # 反向 WS 路径
    access_token: ""             # 鉴权 Token
    forward_ws_enabled: false    # 是否启用正向 WS
    forward_ws_url: ""           # 正向 WS 地址
    reconnect_interval: 5        # 正向 WS 重连间隔（秒）
    heartbeat_interval: 30       # 心跳间隔（秒）
```

### 字段详解

#### enabled

- **类型**：bool
- **默认**：`true`
- **说明**：是否启用 OneBot V11 适配器

#### ws_path

- **类型**：string
- **默认**：`"/onebot/v11"`
- **说明**：反向 WebSocket 的路径
- **示例**：NapCat 连接地址为 `ws://host:4990/onebot/v11`

::: warning
修改 `ws_path` 后，NapCat 的连接地址也要相应修改。
:::

#### access_token

- **类型**：string
- **默认**：`""`（空，不鉴权）
- **说明**：WebSocket 和 HTTP API 的鉴权 Token
- **规则**：客户端必须在 `Authorization: Bearer <token>` 头或 `?access_token=<token>` 查询参数中携带

#### forward_ws_enabled

- **类型**：bool
- **默认**：`false`
- **说明**：是否启用正向 WebSocket（Qtine 主动连接 NapCat）

#### forward_ws_url

- **类型**：string
- **默认**：`""`
- **说明**：NapCat 的 WebSocket 服务端地址
- **示例**：`ws://127.0.0.1:3001`

#### reconnect_interval

- **类型**：int
- **默认**：`5`
- **说明**：正向 WS 断线后重连的间隔（秒）

#### heartbeat_interval

- **类型**：int
- **默认**：`30`
- **说明**：心跳包发送间隔（秒）

## 工作模式

### 仅反向 WS（推荐）

```yaml
adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""
```

NapCat 配置 WebSocket 客户端连接 `ws://qtine:4990/onebot/v11`。

### 仅正向 WS

```yaml
adapters:
  onebot_v11:
    enabled: true
    access_token: ""
    forward_ws_enabled: true
    forward_ws_url: "ws://127.0.0.1:3001"
    reconnect_interval: 5
```

NapCat 配置 WebSocket 服务端监听 3001 端口。

### 双向同时启用

```yaml
adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""
    forward_ws_enabled: true
    forward_ws_url: "ws://127.0.0.1:3001"
```

两种模式同时工作，消息会通过两个通道接收，但发送时优先使用反向 WS 客户端。

## 鉴权

### 配置 Token

```yaml
adapters:
  onebot_v11:
    access_token: "my-secret-token"
```

### NapCat 端配置

```json
{
  "url": "ws://127.0.0.1:4990/onebot/v11",
  "token": "my-secret-token"
}
```

或通过查询参数：

```
ws://127.0.0.1:4990/onebot/v11?access_token=my-secret-token
```

## HTTP API

启用适配器后，HTTP API 自动可用：

```
POST http://host:4990/onebot/v11/api/<action>
```

调用示例：

```bash
curl -X POST http://localhost:4990/onebot/v11/api/send_msg \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret-token" \
  -d '{
    "message_type": "private",
    "user_id": 123456789,
    "message": "hello"
  }'
```

支持的 action 参考 [OneBot V11 API 标准](https://12.onebot.dev/connect/api/)。
