# 适配器管理

适配器（Adapter）是 Qtine 与外部平台通信的桥梁。每个适配器负责一个平台的消息收发。

## 内置适配器

目前 Qtine 内置一个适配器：

| 适配器名 | 协议 | 说明 |
|----------|------|------|
| `onebot_v11` | OneBot V11 | 对接 NapCat / LLOneBot 等 QQ 协议端 |

## 适配器状态

每个适配器有以下状态：

| 状态 | 说明 |
|------|------|
| `DISCONNECTED` | 已断开 |
| `CONNECTING` | 连接中（等待客户端连接或正在重连） |
| `CONNECTED` | 已连接 |
| `ERROR` | 错误 |

## 通过 WebUI 管理

1. 访问 WebUI → **适配器管理**
2. 可以看到所有适配器的：
   - 名称、协议
   - 当前状态
   - 连接的 Bot 账号
   - 消息计数、错误计数
   - 连接时间
3. 点击 **重连** 让适配器重新建立连接
4. 点击 **导入适配器** 上传 .zip 包

## 通过聊天命令管理

```
qtine adapter                        # 查看所有适配器状态
qtine adapter reconnect <适配器名>    # 重连指定适配器
```

例如：

```
qtine adapter
qtine adapter reconnect onebot_v11
```

## 外部适配器导入

适配器以 .zip 包分发，结构如下：

```
my-adapter.zip
├── adapter.json          # 清单文件（必需）
├── adapter.py            # 入口文件（必需）
└── ...其他依赖文件
```

### adapter.json 示例

```json
{
  "name": "discord",
  "protocol": "Discord",
  "version": "1.0.0",
  "author": "你的名字",
  "entry": "adapter.py",
  "config": {
    "ws_endpoint": "/discord/ws",
    "port_requirement": null
  }
}
```

详细的适配器开发指南请参考 [适配器开发](/develop/adapter)。

## OneBot V11 适配器详解

OneBot V11 适配器支持三种工作模式，可同时启用：

### 反向 WebSocket

NapCat 主动连接 Qtine：

```yaml
adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""
```

### 正向 WebSocket

Qtine 主动连接 NapCat：

```yaml
adapters:
  onebot_v11:
    forward_ws_enabled: true
    forward_ws_url: "ws://127.0.0.1:3001"
    reconnect_interval: 5
```

### HTTP API

Qtine 暴露 REST 接口供外部调用：

```
POST http://localhost:4990/onebot/v11/api/<action>
```

例如调用 `send_msg`：

```bash
curl -X POST http://localhost:4990/onebot/v11/api/send_msg \
  -H "Content-Type: application/json" \
  -d '{"message_type":"private","user_id":123456,"message":"hello"}'
```

## 故障排查

### 适配器一直显示"连接中"

- 反向 WS 模式：等待 NapCat 连接，检查 NapCat 配置
- 正向 WS 模式：检查 NapCat 是否开启了 WS 服务端

### Bot 账号显示为空

Qtine 连接成功后会调用 `get_login_info` 获取 Bot 信息。如果失败：
- 检查 NapCat 是否正常登录 QQ
- 查看日志中是否有 API 调用错误

### 消息计数不增长

- 确认 NapCat 已经登录 QQ
- 在 QQ 里发消息，观察 Qtine 日志是否出现 `<< message from`
- 如果没有，说明消息没到达 Qtine，检查网络连接
