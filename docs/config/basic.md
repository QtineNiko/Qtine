# 基础配置

`config.yml` 是 Qtine 的主配置文件，启动时加载。

## 完整示例

```yaml
# 服务器配置
server:
  host: "0.0.0.0"
  port: 4990

# 适配器配置
adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""
    forward_ws_enabled: false
    forward_ws_url: ""
    reconnect_interval: 5
    heartbeat_interval: 30

# 安全配置
security:
  super_admins:
    - "123456789"
  rate_limit:
    enabled: true
    messages_per_second: 5
    burst: 10

# 存储配置
storage:
  backend: "sqlite"
  sqlite_path: "./data/qtine.db"

# 日志配置
logging:
  level: "INFO"
  file: "./data/logs/qtine.log"
  max_size_mb: 10
  backup_count: 5

# WebUI 配置
webui:
  enabled: true
  session_secret: "qtine-secret-key-change-me"

# 插件配置
plugins:
  dir: "./plugins"
```

## 字段详解

### server

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | `"0.0.0.0"` | 监听地址 |
| `port` | int | `4990` | 监听端口 |

::: tip
`0.0.0.0` 表示监听所有网卡，可以从外部访问。仅在本地测试时可改为 `127.0.0.1`。
:::

### adapters

详见 [适配器配置](/config/adapter)。

### security

详见 [安全配置](/config/security)。

### storage

详见 [存储配置](/config/storage)。

### logging

详见 [日志配置](/config/logging)。

### webui

详见 [WebUI 配置](/config/webui)。

### plugins

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dir` | string | `"./plugins"` | 外部插件目录 |

## 环境变量覆盖

部分配置支持环境变量覆盖（优先级高于配置文件）：

| 环境变量 | 对应配置 |
|----------|----------|
| `QTINE_HOST` | `server.host` |
| `QTINE_PORT` | `server.port` |
| `QTINE_LOG_LEVEL` | `logging.level` |

示例：

```bash
QTINE_PORT=8080 python main.py
```

## 配置校验

启动时 Qtine 会校验配置：

- 必填字段缺失 → 启动失败，提示具体字段
- 类型错误 → 启动失败，提示期望类型
- 未知字段 → 警告但继续启动

## 热重载

目前配置文件**不支持热重载**，修改配置后需要重启 Qtine。

::: tip
通过 WebUI 修改的部分配置（如插件启用状态）会实时生效，无需重启。
:::
