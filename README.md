# Qtine — 模块化聊天机器人框架

一个基于 Flask + WebSocket 的模块化聊天机器人框架，支持 OneBot V11 协议、插件化扩展和 WebUI 管理。

[官方文档](https://qtineniko.github.io/) · [快速开始](https://qtineniko.github.io/#/guide/quick-start) · [GitHub](https://github.com/QtineNiko/Qtine)

> **项目状态**：持续开发中。当前内置 OneBot V11 适配器，可通过 NapCat、LLOneBot 等实现接入 QQ。

## ✨ 核心能力

- **OneBot V11 接入**：支持反向和正向 WebSocket 模式，可对接 NapCat、LLOneBot 等实现。
- **插件化架构**：内置插件管理、热启用/禁用与 ZIP 导入能力；可通过插件扩展命令、消息处理和事件响应。
- **消息处理管道**：PRE → HANDLER → POST 三阶段中间件链，配合事件总线实现模块解耦。
- **WebUI 管理**：提供仪表盘、插件/适配器管理、消息、任务、日志和系统设置等功能。
- **存储与安全**：支持 SQLite 或内存存储，提供管理员权限、黑名单、频率限制和会话管理。
- **易于部署**：支持直接运行和 Docker Compose 部署。

当前内置 OneBot V11 适配器；其他平台可通过适配器机制扩展。

## 🚀 快速开始

### 环境要求

- Python 3.9+
- pip
- NapCat 或其他 OneBot V11 实现（仅在需要接入 QQ 时使用）

### 安装与启动

```bash
git clone https://github.com/QtineNiko/Qtine.git
cd Qtine
pip install -r requirements.txt
python main.py
```

启动后访问 WebUI：<http://localhost:4990/webui>

### 最小配置

编辑 `config.yml`，至少设置你的超级管理员 QQ 号：

```yaml
security:
  super_admins:
    - "你的QQ号"
```

默认服务监听地址为 `0.0.0.0:4990`，OneBot V11 反向 WebSocket 路径为 `/onebot/v11`。

> [!WARNING]
> 生产环境请修改 `config.yml` 中默认的 WebUI 用户名、密码和 `session_secret`，并妥善保管管理员 Token。详细说明见 [WebUI 配置](https://qtineniko.github.io/#/config/webui) 和 [安全配置](https://qtineniko.github.io/#/config/security)。

需要接入 QQ？请继续阅读 [对接 NapCat](https://qtineniko.github.io/#/guide/connect-napcat)。

## 📚 官方文档

完整的使用说明、配置参考和开发文档请访问 [Qtine 官方文档](https://qtineniko.github.io/)。

| 使用与部署 | 管理与配置 | 开发与支持 |
| --- | --- | --- |
| [快速开始](https://qtineniko.github.io/#/guide/quick-start) | [基础配置](https://qtineniko.github.io/#/config/basic) | [插件开发](https://qtineniko.github.io/#/develop/plugin) |
| [对接 NapCat](https://qtineniko.github.io/#/guide/connect-napcat) | [WebUI 使用](https://qtineniko.github.io/#/guide/webui) | [适配器开发](https://qtineniko.github.io/#/develop/adapter) |
| [Docker 部署](https://qtineniko.github.io/#/guide/docker) | [命令参考](https://qtineniko.github.io/#/commands/plugin) | [API 参考](https://qtineniko.github.io/#/develop/api) |
| [反向代理](https://qtineniko.github.io/#/guide/reverse-proxy) | [插件管理](https://qtineniko.github.io/#/guide/plugin-manage) | [FAQ](https://qtineniko.github.io/#/guide/faq) |
|  | [适配器管理](https://qtineniko.github.io/#/guide/adapter-manage) | [更新日志](https://qtineniko.github.io/#/guide/changelog) |

## 🐳 Docker 部署
```bash
cp .env.example .env
# 为 .env 中的三个 Token 填入互不相同的随机值
mkdir -p data plugins adapters
chown 10001:10001 config.yml
chown -R 10001:10001 data plugins adapters
docker compose up -d --build
```
容器内继续监听 `0.0.0.0:4990`。公网部署需要 HTTPS 反向代理，并配置独立的 OneBot `access_token`。

更多部署选项请参阅 [Docker 部署文档](https://qtineniko.github.io/#/guide/docker) 和 [反向代理文档](https://qtineniko.github.io/#/guide/reverse-proxy)。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。请先阅读 [官方文档](https://qtineniko.github.io/) 了解项目结构、配置和开发方式。

## 📄 许可证

版权所有 © 2025–2026 Qtine 开发团队。

本项目采用 [MIT 许可证](LICENSE) 开源。

## ⭐ 致谢

- 灵感源自 [AstrBot](https://github.com/Soulter/AstrBot)
- OneBot V11 协议参考：[onebot.dev](https://11.onebot.dev)
