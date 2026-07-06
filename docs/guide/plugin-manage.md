# 插件管理

Qtine 的插件系统支持运行时动态管理，可以通过 WebUI 或聊天命令完成。

## 内置插件

Qtine 自带 6 个开箱即用的插件：

| 插件名 | 描述 | 默认状态 |
|--------|------|----------|
| `help` | 状态查询与帮助命令 | 启用 |
| `admin` | 插件与适配器管理 | 启用 |
| `echo` | 复读测试命令 | 启用 |
| `welcome` | 入群欢迎语 | 启用 |
| `repeat` | 复读检测 | 启用 |
| `ban` | 用户黑名单管理 | 启用 |

## 通过 WebUI 管理

1. 访问 `http://localhost:4990/webui`
2. 进入 **插件管理** 页面
3. 可以看到所有插件的列表，包括名称、版本、描述、状态
4. 点击 **启用/禁用** 切换插件状态
5. 点击 **重载** 重新加载插件配置
6. 点击 **导入插件** 上传 .zip 包

## 通过聊天命令管理

在 QQ 群里发送命令（需要管理员权限）：

```
qtine list                 # 列出所有插件
qtine enable <插件名>       # 启用插件
qtine disable <插件名>      # 禁用插件
qtine reload <插件名>       # 重载插件
```

例如：

```
qtine list
qtine enable echo
qtine disable repeat
qtine reload welcome
```

## 插件 .zip 包格式

外部插件以 .zip 包分发，结构如下：

```
my-plugin.zip
├── plugin.json          # 清单文件（必需）
├── main.py              # 入口文件（必需）
└── ...其他资源文件
```

### plugin.json 示例

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "我的自定义插件",
  "author": "你的名字",
  "entry": "main.py",
  "config": {
    "default_value": "hello"
  }
}
```

### main.py 示例

```python
from qtine.plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    name = "my-plugin"
    description = "我的自定义插件"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/my", self.handle_my)

    def handle_my(self, event, args):
        return "这是我的插件！"
```

详细的插件开发指南请参考 [插件开发](/develop/plugin)。

## 插件状态

每个插件有以下状态：

- **已加载**：插件代码已加载到内存
- **已启用**：插件正在运行，会响应消息
- **已禁用**：插件已加载但不响应消息
- **错误**：插件加载或运行时出错

## 卸载插件

- **内置插件**：无法卸载，但可以禁用
- **外部插件**：在 WebUI 的插件管理页面点击 **删除** 按钮
