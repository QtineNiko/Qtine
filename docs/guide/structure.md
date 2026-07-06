# 目录结构

```
Qtine/
├── main.py                     # 启动入口
├── config.yml                  # 主配置文件
├── requirements.txt            # Python 依赖
├── LICENSE                     # MIT 许可证
├── README.md                   # 项目说明
│
├── qtine/                      # 核心代码
│   ├── __init__.py
│   ├── core/                   # 核心模块
│   │   ├── app.py              # QtineApp 主应用
│   │   ├── bot.py              # QtineBot 机器人核心
│   │   ├── config.py           # 配置加载
│   │   ├── bus.py              # 事件总线
│   │   ├── pipeline.py         # 消息管道
│   │   ├── session.py          # 会话管理
│   │   ├── plugin_manager.py   # 插件管理器
│   │   └── adapter_manager.py  # 适配器管理器
│   ├── adapters/               # 适配器
│   │   ├── base.py             # 适配器基类
│   │   └── onebot_v11.py       # OneBot V11 适配器
│   ├── plugins/                # 插件
│   │   ├── base.py             # 插件基类
│   │   └── builtin/            # 内置插件
│   │       ├── help.py         # 帮助
│   │       ├── echo.py         # 复读
│   │       ├── admin.py        # 管理
│   │       ├── welcome.py      # 欢迎
│   │       ├── repeat.py       # 复读检测
│   │       └── ban.py          # 黑名单
│   ├── web/                    # WebUI
│   │   └── static/             # 静态资源
│   ├── utils/                  # 工具
│   │   ├── logger.py           # 日志
│   │   └── models.py           # 数据模型
│   └── storage/                # 存储
│       └── backend.py          # 存储后端
│
├── data/                       # 运行时数据（自动生成）
│   ├── qtine.db                # SQLite 数据库
│   ├── token.txt               # WebUI Token
│   ├── logs/                   # 日志文件
│   └── uploads/                # 上传文件
│
├── plugins/                    # 外部插件目录
├── adapters/                   # 外部适配器目录
└── docs/                       # 文档源码（本站）
```

## 关键目录说明

### `qtine/core/`

核心逻辑层，定义了框架的骨架：

- [app.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/app.py) - Flask 应用、WebSocket 端点、WebUI 路由
- [pipeline.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/pipeline.py) - 消息处理管道
- [plugin_manager.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/plugin_manager.py) - 插件加载与管理
- [adapter_manager.py](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/adapter_manager.py) - 适配器加载与管理

### `qtine/adapters/`

协议适配层，将不同平台的消息协议转换为 Qtine 内部统一格式。

### `qtine/plugins/builtin/`

6 个开箱即用的内置插件，也是学习插件开发的优秀示例。

### `data/`

运行时自动生成，存放数据库、日志、Token 等运行数据。**不要手动修改**。

### `plugins/` 和 `adapters/`

外部扩展目录，通过 WebUI 导入的 .zip 包会解压到这里。
