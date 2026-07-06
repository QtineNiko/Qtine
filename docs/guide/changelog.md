# 更新日志

## v1.0.0 (2025-07)

🎉 首个正式版本发布！

### 新增

- **核心框架**：基于 Flask + WebSocket 的模块化架构
- **OneBot V11 适配器**：支持反向 WS、正向 WS、HTTP API
- **消息管道**：PRE → HANDLER → POST 三阶段中间件链
- **插件系统**：命令/正则/关键词三种匹配，热加载
- **WebUI 管理面板**：Material Design 3 风格
  - 仪表盘（运行状态、消息统计）
  - 插件管理（启用/禁用/重载/导入）
  - 适配器管理（状态查看/重连/导入）
  - 日志查看（实时滚动、分级过滤）
  - 系统设置（Token 管理）
- **6 个内置插件**：
  - `help` - 状态查询与帮助
  - `admin` - 聊天式管理命令
  - `echo` - 复读测试
  - `welcome` - 入群欢迎语
  - `repeat` - 复读检测
  - `ban` - 黑名单管理
- **存储后端**：SQLite 持久化 + 内存模式
- **权限系统**：管理员/普通用户两级权限
- **频率限制**：令牌桶算法防刷屏
- **事件总线**：发布/订阅模式解耦模块
- **Docker 部署**：完整 Docker Compose 支持
- **中文文档站**：VitePress 构建的文档网站

### 技术栈

- Python 3.9+
- Flask + Flask-SocketIO
- simple-websocket
- SQLite
- Material Design 3 (WebUI)
- VitePress (文档)

### 已知限制

- 仅支持 OneBot V11 协议（QQ）
- 不支持多 Bot 实例
- 无集群支持

## 未来计划

- v1.1: Discord 适配器
- v1.2: Telegram 适配器
- v1.3: 插件市场
- v2.0: 多 Bot 实例、集群支持

---

*本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)*
