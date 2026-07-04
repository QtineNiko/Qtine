# Qtine — 模块化聊天机器人框架

一个基于 Flask + WebSocket 的模块化聊天机器人框架，灵感源自 AstrBot，支持 OneBot V11 协议，插件化扩展，开箱即用。

> **项目状态**：活跃开发中 ✅ 已可正常收发 QQ 消息

---

## ✨ 功能特性

- **插件化架构**：支持热加载、热启用/禁用，插件以 .zip 包导入
- **消息管道**：PRE（预处理） → HANDLER（命令处理） → POST（后处理）三阶段中间件链
- **事件总线**：发布/订阅模式，模块间解耦
- **多平台适配器**：目前支持 OneBot V11（NapCat / LLOneBot），预留 Discord / Telegram 扩展能力
- **反向 & 正向 WebSocket**：同时支持 NapCat 主动连接和 Qtine 主动连接两种模式
- **WebUI 管理面板**：Material Design 3 风格，仪表盘、插件管理、适配器管理、日志查看、系统设置
- **聊天式命令管理**：在 QQ 群里直接用命令管理机器人
- **权限系统**：管理员 / 普通用户两级权限
- **存储后端**：支持 SQLite 持久化或内存存储
- **会话管理**：用户会话状态跟踪
- **频率限制**：令牌桶算法防刷屏
- **Docker 支持**：一键部署

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- pip
- NapCat 或其他 OneBot V11 实现（用于对接 QQ）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

编辑 `config.yml` 自定义配置：

```yaml
server:
  host: "0.0.0.0"
  port: 4990

adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""

security:
  super_admins:
    - "你的QQ号"
```

### 启动

```bash
python main.py
```

启动后访问 WebUI：`http://localhost:4990/webui`

---

## 🔌 对接 NapCat

### 方式一：反向 WebSocket（推荐）

NapCat 作为客户端连接到 Qtine。在 NapCat 配置中添加 WebSocket 客户端：

```json
{
  "network": {
    "websocketClients": [
      {
        "name": "Qtine",
        "enable": true,
        "url": "ws://127.0.0.1:4990/onebot/v11",
        "reconnectInterval": 5000
      }
    ]
  }
}
```

### 方式二：正向 WebSocket

Qtine 作为客户端连接到 NapCat。修改 `config.yml`：

```yaml
adapters:
  onebot_v11:
    enabled: true
    access_token: ""
    forward_ws_enabled: true
    forward_ws_url: "ws://127.0.0.1:3001"
    reconnect_interval: 5
```

> 💡 两种连接方式可以同时启用。

---

## 📋 命令列表

### 用户命令（前缀 `#`）

| 命令 | 描述 |
|------|------|
| `#qtine` | 查看机器人运行状态 |
| `#help` / `#帮助` | 列出所有可用命令 |

### 管理员命令（前缀 `qtine`）

| 命令 | 描述 |
|------|------|
| `qtine` | 查看详细状态（含插件、适配器信息） |
| `qtine list` | 列出所有插件 |
| `qtine enable <名称>` | 启用插件 |
| `qtine disable <名称>` | 禁用插件 |
| `qtine reload <名称>` | 重载插件 |
| `qtine adapter` | 查看适配器状态 |
| `qtine adapter reconnect <名称>` | 重连适配器 |
| `qtine log [行数]` | 查看最近日志 |

### 其他命令

| 命令 | 别名 | 权限 | 描述 |
|------|------|------|------|
| `/echo <内容>` | `/复读` | 用户 | 复读消息（测试用） |
| `/ban <QQ号> [原因]` | `/封禁` | 管理员 | 封禁用户 |
| `/unban <QQ号>` | `/解封` | 管理员 | 解封用户 |
| `/blacklist` | `/黑名单` | 管理员 | 查看黑名单 |
| `/welcome <消息>` | `/欢迎` | 管理员 | 设置入群欢迎语 |

---

## 🔧 内置插件

| 插件 | 描述 |
|------|------|
| **help** | 状态查询与帮助命令 |
| **admin** | 插件与适配器管理 |
| **echo** | 复读测试命令 |
| **welcome** | 入群欢迎语配置 |
| **repeat** | 复读检测（群聊刷屏自动+1） |
| **ban** | 用户黑名单管理 |

---

## 🧩 插件开发

### 快速示例

```python
from qtine.plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    name = "my_plugin"
    package = "qtine-plugin-my-plugin"
    version = "1.0.0"
    description = "我的第一个插件"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/hello", self.handle_hello)

    def handle_hello(self, event, args):
        return f"你好，{event.message.sender.nickname}！"
```

### 插件部署

将插件文件放入 `plugins/` 目录，或在 WebUI 中通过 .zip 包导入。

### 支持的钩子类型

- **命令匹配**：`register_command()` — 精确匹配命令前缀
- **正则匹配**：`register_regex()` — 正则表达式匹配消息
- **关键词匹配**：`register_keyword()` — 关键词触发
- **事件监听**：事件总线订阅

---

## 🖥️ WebUI 功能

- **仪表盘**：运行状态、消息统计、适配器状态概览
- **插件管理**：查看、启用/禁用、导入（.zip）、删除插件
- **适配器管理**：查看连接状态、重连、导入适配器
- **日志查看**：实时滚动日志，支持分级过滤
- **系统设置**：Token 管理（显示/隐藏/复制）、配置项修改

访问地址：`http://localhost:4990/webui`

---

## 🌐 API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/token` | 获取管理员 Token |
| GET | `/api/status` | 系统状态 |
| GET | `/api/plugins` | 插件列表 |
| POST | `/api/plugins/{name}/enable` | 启用插件 |
| POST | `/api/plugins/{name}/disable` | 禁用插件 |
| POST | `/api/plugins/{name}/reload` | 重载插件 |
| POST | `/api/plugins/import` | 导入插件（.zip） |
| GET | `/api/adapters` | 适配器状态 |
| POST | `/api/adapters/{name}/reconnect` | 重连适配器 |
| POST | `/api/adapters/import` | 导入适配器（.zip） |
| GET | `/api/logs` | 获取日志 |
| GET | `/webui` | WebUI 面板 |

---

## 🏗️ 架构设计

```
NapCat / LLOneBot
      │
      ▼
WebSocket (OneBot V11 协议)
      │
      ▼
  Qtine Core
      │
      ├── Event Bus（事件总线）
      ├── Message Pipeline（消息管道：PRE → HANDLER → POST）
      ├── Plugin Manager（插件管理器）
      │     └── Plugins（内置 + 外部）
      ├── Adapter Manager（适配器管理器）
      │     └── OneBot V11 Adapter
      ├── Storage（存储后端）
      └── WebUI（Flask + SocketIO）
```

---

## 🐳 Docker 部署

```bash
docker compose up -d
```

---

## 📄 版权声明

**版权所有 © 2026 Qtine 开发团队**

本项目采用 **MIT 许可证** 开源，详见 [LICENSE](LICENSE) 文件。

Qtine 是一个开源项目，欢迎贡献代码、提交 Issue 和 PR。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## ⭐ 致谢

- 灵感源自 [AstrBot](https://github.com/Soulter/AstrBot)
- OneBot V11 协议参考：[onebot.dev](https://11.onebot.dev)
