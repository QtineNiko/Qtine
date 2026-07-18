# 插件管理

Qtine 支持通过 WebUI、聊天命令和插件目录管理扩展。

## 内置插件

当前默认加载 5 个内置插件：

| 插件 | 作用 | 默认状态 |
|---|---|---|
| `help` | 状态和帮助命令 | 启用 |
| `admin` | 插件、适配器和日志管理 | 启用 |
| `echo` | `/echo` 复读命令 | 启用 |
| `repeat` | 群消息复读检测 | 启用 |
| `ban` | 用户黑名单管理 | 启用 |

内置插件可以禁用，但不能卸载或重载。

## WebUI 管理

1. 访问 `/webui` 并使用管理令牌登录。
2. 打开“插件”页面。
3. 使用启用、禁用、重载或卸载操作。
4. 上传插件时选择 `.zip` 文件。

所有管理 API 都需要 Cookie 或 Bearer Token。上传包会执行 ZIP 安全校验。

## 聊天命令

管理员可以发送：

```text
qtine list
qtine enable <插件名>
qtine disable <插件名>
qtine reload <插件名>
```

插件名称必须与 `data.json` 中的 `name` 一致。

## 插件目录

启动时会扫描 `config.yml` 中 `plugins.dir` 指定的目录，默认是 `./plugins`。支持：

- 标准插件目录：包含 `data.json` 和 `main.py`。
- 标准 ZIP：包含 `data.json` 和 `main.py`。
- 旧式 `.py` 文件和包含 `__init__.py` 的目录。

推荐使用标准格式，详见 [插件开发](/develop/plugin)。

## 依赖

插件清单中的 `requires` 是 pip 依赖。生产配置默认关闭运行时依赖安装：

```yaml
plugins:
  allow_dependency_install: false
```

请在 Docker 镜像构建阶段或受控环境中预装依赖，不要让 WebUI 上传流程直接执行不可信依赖安装。

## 状态

- 已加载：插件实例已创建并注册。
- 已启用：插件参与消息匹配。
- 已禁用：插件保留在内存中，但不参与消息匹配。
- 加载失败：日志中会记录入口、清单或依赖错误。

## 卸载和重载

- 外部插件可以卸载。
- 外部插件可以重载，重载前调用 `on_disable()` 和 `on_unload()`。
- 内置插件不能卸载或重载。
- 插件在 `on_unload()` 中应取消事件订阅并释放资源。
