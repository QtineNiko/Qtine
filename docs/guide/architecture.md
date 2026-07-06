# 架构设计

了解 Qtine 的整体架构，便于深入使用和二次开发。

## 整体架构

```
┌─────────────────────────────────────────────────┐
│              NapCat / LLOneBot                  │
│              (QQ 协议端实现)                     │
└───────────────────┬─────────────────────────────┘
                    │ WebSocket (OneBot V11)
                    ▼
┌─────────────────────────────────────────────────┐
│                 Qtine Core                       │
│ ┌─────────────────────────────────────────────┐ │
│ │            Adapter Manager                  │ │
│ │  ┌─────────────────────────────────────┐    │ │
│ │  │       OneBot V11 Adapter            │    │ │
│ │  │  (反向WS / 正向WS / HTTP API)        │    │ │
│ │  └─────────────────────────────────────┘    │ │
│ └─────────────────────────────────────────────┘ │
│                       │                         │
│                       ▼                         │
│ ┌─────────────────────────────────────────────┐ │
│ │           Message Pipeline                  │ │
│ │  PRE ──→ HANDLER ──→ POST                   │ │
│ │  (黑名单/限流)  (命令匹配)  (复读检测等)     │ │
│ └─────────────────────────────────────────────┘ │
│                       │                         │
│        ┌──────────────┼──────────────┐          │
│        ▼              ▼              ▼          │
│ ┌──────────┐  ┌──────────────┐  ┌─────────┐    │
│ │  Event   │  │    Plugin    │  │ Storage │    │
│ │   Bus    │  │   Manager    │  │ (SQLite)│    │
│ └──────────┘  └──────────────┘  └─────────┘    │
│                       │                         │
│                       ▼                         │
│ ┌─────────────────────────────────────────────┐ │
│ │                 WebUI                       │ │
│ │  (Flask + Flask-SocketIO + 静态资源)         │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 核心组件

### QtineApp

[qtine/core/app.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/app.py) — 主应用，负责：

- 创建 Flask 应用和 SocketIO
- 注册 WebSocket 端点
- 注册 WebUI 路由和 API
- 初始化 Bot、AdapterManager、PluginManager
- 启动 HTTP 服务

### QtineBot

[qtine/core/bot.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/bot.py) — 机器人核心，负责：

- 装配消息管道（PRE/HANDLER/POST）
- 接收适配器消息并送入管道
- 将管道回复交给适配器发送
- 维护运行状态

### MessagePipeline

[qtine/core/pipeline.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/pipeline.py) — 消息处理管道，详见 [消息管道](/guide/pipeline)。

### PluginManager

[qtine/core/plugin_manager.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/plugin_manager.py) — 插件管理器，负责：

- 加载内置插件
- 从 `plugins/` 目录扫描外部插件
- 提供 `find_command_handler` / `find_regex_handler` / `find_keyword_handler` 给管道调用
- 管理插件启用/禁用/重载

### AdapterManager

[qtine/core/adapter_manager.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/adapter_manager.py) — 适配器管理器，负责：

- 注册适配器
- 启动/停止所有适配器
- 统一发送消息接口

### EventBus

[qtine/core/bus.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/bus.py) — 事件总线，详见 [事件总线](/guide/event-bus)。

### Storage

[qtine/storage/backend.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/storage/backend.py) — 存储后端，详见 [存储后端](/guide/storage)。

## 消息流转

完整的一条消息处理流程：

```
1. QQ 用户发消息
2. NapCat 接收，通过 WebSocket 推送给 Qtine
3. OneBotV11Adapter.serve() 接收帧，解析 JSON
4. 调用 _dispatch()，根据 post_type 分发
5. post_type=message 时，转换为内部 Message 对象
6. 调用 BaseAdapter._emit_message() 触发回调链
7. 回调最终调用 QtineBot.handle_message()
8. handle_message 将 Message 送入 MessagePipeline.process()
9. PRE 阶段：黑名单过滤、频率限制
10. HANDLER 阶段：命令/正则/关键词匹配，调用插件
11. POST 阶段：复读检测等后处理
12. 管道返回回复字符串
13. handle_message 调用 AdapterManager.send_message()
14. OneBotV11Adapter.send_message() 通过 WS 发送 API 调用
15. NapCat 收到调用，发送消息给 QQ 用户
```

## 设计原则

### 解耦

适配器、管道、插件、存储各司其职，通过明确接口通信。

### 可扩展

- 新平台：实现 BaseAdapter
- 新功能：编写插件
- 新中间件：注册到管道

### 可观测

- 全链路日志
- WebUI 实时状态
- 事件总线便于订阅

## 时序图：命令处理

```
NapCat          Adapter         Bot          Pipeline        Plugin
  │                │              │              │              │
  │── message ────▶│              │              │              │
  │                │── Message ──▶│              │              │
  │                │              │── process ──▶│              │
  │                │              │              │── PRE ──▶    │
  │                │              │              │              │
  │                │              │              │── HANDLER ──▶│
  │                │              │              │              │── 匹配命令
  │                │              │              │              │── 执行处理函数
  │                │              │              │◀── reply ────│
  │                │              │◀── response ─│              │
  │                │              │── send ─────▶│              │
  │                │◀── api call ─│              │              │
  │◀── send_msg ───│              │              │              │
```
