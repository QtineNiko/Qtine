# 对接 NapCat

NapCat 是一个基于 NTQQ 的现代 Bot 协议端实现，Qtine 通过 OneBot V11 协议与 NapCat 通信。

支持两种连接方式，可以同时启用：

## 方式一：反向 WebSocket（推荐）

NapCat 作为客户端主动连接 Qtine。

### Qtine 配置

`config.yml` 默认即可：

```yaml
adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""
```

### NapCat 配置

在 NapCat 的网络配置中添加 **WebSocket 客户端**：

```json
{
  "network": {
    "websocketClients": [
      {
        "name": "Qtine",
        "enable": true,
        "url": "ws://127.0.0.1:4990/onebot/v11",
        "reconnectInterval": 5000,
        "messagePostFormat": "array",
        "token": ""
      }
    ]
  }
}
```

::: tip
如果 Qtine 和 NapCat 不在同一台机器，把 `127.0.0.1` 换成 Qtine 服务器的 IP。
:::

### 验证连接

NapCat 连接成功后，Qtine 日志会显示：

```
[INFO] [onebot_v11] WS upgrade from 127.0.0.1
[INFO] [onebot_v11] Reverse client connected: xxxxxxxx
[INFO] [onebot_v11] Reverse WS serving: xxxxxxxx
[INFO] [onebot_v11] Bot info: 123456789 (机器人昵称)
```

## 方式二：正向 WebSocket

Qtine 作为客户端主动连接 NapCat。

### NapCat 配置

在 NapCat 中开启 **WebSocket 服务端**：

```json
{
  "network": {
    "websocketServers": [
      {
        "name": "NapCat WS Server",
        "enable": true,
        "host": "127.0.0.1",
        "port": 3001,
        "messagePostFormat": "array",
        "token": ""
      }
    ]
  }
}
```

### Qtine 配置

修改 `config.yml`：

```yaml
adapters:
  onebot_v11:
    enabled: true
    access_token: ""
    forward_ws_enabled: true
    forward_ws_url: "ws://127.0.0.1:3001"
    reconnect_interval: 5
    heartbeat_interval: 30
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `forward_ws_enabled` | 是否启用正向 WS |
| `forward_ws_url` | NapCat 的 WS 服务端地址 |
| `reconnect_interval` | 断线重连间隔（秒） |
| `heartbeat_interval` | 心跳间隔（秒） |

## 鉴权配置（可选）

如果 NapCat 配置了 `token`，需要在 Qtine 的 `config.yml` 中填入相同的 token：

```yaml
adapters:
  onebot_v11:
    access_token: "你的token"
```

## 排查连接问题

### 1. NapCat 连接后 Qtine 无反应

检查 Qtine 日志是否出现 `WS upgrade`：

- **没有**：网络层不通，检查防火墙、端口、IP
- **有但马上断开**：Token 不匹配，检查双方 `access_token`

### 2. 收到消息但不回复

- 检查 `super_admins` 是否正确配置你的 QQ 号
- 检查消息是否被黑名单或频率限制拦截
- 查看日志中是否有 `Command matched` 字样

### 3. Bot 信息显示为空

Qtine 启动后会自动调用 `get_login_info` 获取 Bot 信息并缓存。如果获取失败，检查 NapCat 是否正常登录了 QQ。

## 消息流向

```
QQ 用户发消息
    ↓
腾讯服务器
    ↓
NapCat (QQ 协议端)
    ↓ WebSocket
Qtine (适配器接收)
    ↓
消息管道 (PRE → HANDLER → POST)
    ↓
插件处理 / 命令匹配
    ↓
回复消息
    ↓
Qtine (适配器发送)
    ↓
NapCat
    ↓
QQ 用户收到回复
```
