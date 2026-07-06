# API 接口

Qtine 提供 REST API，方便外部系统集成。

## 认证

所有 API 需要 Token 认证：

```
Authorization: Bearer <token>
```

Token 在启动时生成，保存在 `data/token.txt`，可在 WebUI 设置页查看。

## 健康检查

### `GET /health`

无需认证。

**响应**：

```
ok
```

## Token

### `GET /api/token`

获取当前 Token（需认证）。

**响应**：

```json
{
  "token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

## 状态

### `GET /api/status`

获取系统状态。

**响应**：

```json
{
  "status": "running",
  "version": "1.0.0",
  "uptime": 3600,
  "bot_qq": "123456789",
  "plugins": {
    "total": 6,
    "enabled": 6
  },
  "adapters": [
    {
      "name": "onebot_v11",
      "protocol": "OneBot v11",
      "status": "connected",
      "message_count": 42,
      "error_count": 0
    }
  ]
}
```

## 插件

### `GET /api/plugins`

获取所有插件列表。

**响应**：

```json
{
  "plugins": [
    {
      "name": "help",
      "description": "状态查询与帮助命令",
      "version": "1.0.0",
      "enabled": true,
      "loaded": true,
      "builtin": true
    }
  ]
}
```

### `POST /api/plugins/{name}/enable`

启用指定插件。

**响应**：

```json
{
  "success": true,
  "message": "Plugin help enabled"
}
```

### `POST /api/plugins/{name}/disable`

禁用指定插件。

### `POST /api/plugins/{name}/reload`

重载指定插件。

### `POST /api/plugins/import`

导入插件（.zip 包）。

**请求**：`multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `file` | file | .zip 文件 |

**响应**：

```json
{
  "success": true,
  "message": "Plugin imported",
  "name": "my-plugin"
}
```

### `DELETE /api/plugins/{name}`

删除外部插件（内置插件不可删除）。

## 适配器

### `GET /api/adapters`

获取所有适配器状态。

**响应**：

```json
{
  "adapters": [
    {
      "name": "onebot_v11",
      "protocol": "OneBot v11",
      "status": "connected",
      "account_id": "123456789",
      "connected_at": 1700000000,
      "message_count": 42,
      "error_count": 0
    }
  ]
}
```

### `POST /api/adapters/{name}/reconnect`

重连指定适配器。

### `POST /api/adapters/import`

导入适配器（.zip 包）。

## 日志

### `GET /api/logs`

获取最近日志。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `limit` | int | 100 | 返回条数 |
| `level` | string | - | 级别过滤（DEBUG/INFO/WARNING/ERROR） |

**响应**：

```json
{
  "logs": [
    {
      "time": "2026-07-05 12:34:56",
      "level": "INFO",
      "module": "onebot_v11",
      "message": "<< message from 张三: #help"
    }
  ]
}
```

## WebSocket 事件

WebUI 使用 SocketIO 实时更新，可以订阅事件：

### 连接

```javascript
const socket = io("http://localhost:4990", {
  auth: { token: "your-token" }
});
```

### 事件

| 事件 | 数据 | 说明 |
|------|------|------|
| `log.new` | LogEntry | 新日志 |
| `message.received` | Message | 收到新消息 |
| `message.processed` | {message, response} | 消息处理完成 |
| `adapter.status` | AdapterInfo | 适配器状态变化 |
| `plugin.status` | PluginInfo | 插件状态变化 |

### JavaScript 示例

```javascript
const socket = io("http://localhost:4990", {
  auth: { token: "your-token" }
});

socket.on("log.new", (log) => {
  console.log(`[${log.level}] ${log.message}`);
});

socket.on("message.received", (msg) => {
  console.log(`新消息: ${msg.content}`);
});
```

## OneBot V11 API

启用 OneBot V11 适配器后，标准 OneBot API 也可用：

```
POST http://host:4990/onebot/v11/api/<action>
```

### 发送消息

```bash
curl -X POST http://localhost:4990/onebot/v11/api/send_msg \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "message_type": "private",
    "user_id": 123456789,
    "message": "hello"
  }'
```

### 获取登录信息

```bash
curl -X POST http://localhost:4990/onebot/v11/api/get_login_info \
  -H "Authorization: Bearer <token>"
```

**响应**：

```json
{
  "status": "ok",
  "retcode": 0,
  "data": {
    "user_id": 123456789,
    "nickname": "机器人昵称"
  }
}
```

完整的 action 列表参考 [OneBot V11 API 标准](https://12.onebot.dev/connect/api/)。

## 错误响应

所有 API 在出错时返回统一格式：

```json
{
  "success": false,
  "error": "错误描述",
  "code": "ERROR_CODE"
}
```

### 常见错误码

| HTTP 状态 | 说明 |
|-----------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或 Token 错误 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 速率限制

API 默认无速率限制，但建议在生产环境通过反向代理配置限流。

## SDK 示例

### Python

```python
import requests

BASE = "http://localhost:4990"
TOKEN = "your-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 获取状态
resp = requests.get(f"{BASE}/api/status", headers=HEADERS)
print(resp.json())

# 发送消息
requests.post(
    f"{BASE}/onebot/v11/api/send_msg",
    headers=HEADERS,
    json={
        "message_type": "private",
        "user_id": 123456789,
        "message": "hello from API"
    }
)
```

### JavaScript

```javascript
const BASE = "http://localhost:4990";
const TOKEN = "your-token";

async function getStatus() {
  const resp = await fetch(`${BASE}/api/status`, {
    headers: { Authorization: `Bearer ${TOKEN}` }
  });
  return await resp.json();
}

async function sendMessage(userId, message) {
  await fetch(`${BASE}/onebot/v11/api/send_msg`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message_type: "private",
      user_id: userId,
      message: message
    })
  });
}
```
