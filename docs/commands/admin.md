# 管理员命令

仅超级管理员可用的命令。在 `config.yml` 的 `security.super_admins` 中配置管理员 QQ 号。

## 前缀

管理命令以 `qtine` 开头（无 `#` 或 `/` 前缀）。

```
qtine <子命令> [参数]
```

## 状态查看

### `qtine` - 详细状态

查看包含插件、适配器的详细状态。

```
qtine
```

示例输出：

```
Qtine: [Running]
QQ: 123456789
Version: 1.0.0
Device: Windows
Uptime: 0d 1h 23m 45s
Plugins: 6 (6 enabled)
Adapter onebot_v11: [connected] msgs:42 errs:0
```

## 插件管理

### `qtine list` - 列出所有插件

```
qtine list
```

示例输出：

```
插件列表 (6 loaded, 6 enabled):
[on] help        - 状态查询与帮助命令
[on] admin       - 插件与适配器管理
[on] echo        - 复读测试命令
[on] welcome     - 入群欢迎语
[on] repeat      - 复读检测
[on] ban         - 用户黑名单管理
```

### `qtine enable <名称>` - 启用插件

```
qtine enable echo
```

示例输出：

```
插件 echo 已启用
```

### `qtine disable <名称>` - 禁用插件

```
qtine disable repeat
```

示例输出：

```
插件 repeat 已禁用
```

### `qtine reload <名称>` - 重载插件

重新加载插件代码和配置。

```
qtine reload welcome
```

示例输出：

```
插件 welcome 已重载
```

::: tip
修改插件配置后需要 `reload` 才能生效。
:::

## 适配器管理

### `qtine adapter` - 查看适配器状态

```
qtine adapter
```

示例输出：

```
适配器列表:
[connected] onebot_v11 - OneBot v11
  Bot: 123456789 (机器人昵称)
  消息: 42  错误: 0
  连接时间: 2026-07-05 12:34:56
```

### `qtine adapter reconnect <名称>` - 重连适配器

```
qtine adapter reconnect onebot_v11
```

示例输出：

```
适配器 onebot_v11 正在重连...
```

## 日志查看

### `qtine log [行数]` - 查看最近日志

```
qtine log          # 默认 20 行
qtine log 50       # 50 行
qtine log 100      # 100 行
```

示例输出：

```
最近 20 行日志:
[12:34:56] [INFO] [onebot_v11] << message from 张三: #help
[12:34:56] [INFO] Command matched: '#help' -> [help] handle_help
[12:34:57] [INFO] Command reply: 可用命令列表...
...
```

## 权限说明

### 谁是管理员

在 `config.yml` 中配置：

```yaml
security:
  super_admins:
    - "123456789"   # 你的 QQ 号
```

### 权限检查

执行管理命令时，Qtine 会检查发送者的 QQ 号是否在 `super_admins` 列表中：

- **是管理员**：执行命令
- **不是管理员**：回复 `Permission denied. Admin only.`

## 命令速查表

| 命令 | 说明 |
|------|------|
| `qtine` | 查看详细状态 |
| `qtine list` | 列出所有插件 |
| `qtine enable <名称>` | 启用插件 |
| `qtine disable <名称>` | 禁用插件 |
| `qtine reload <名称>` | 重载插件 |
| `qtine adapter` | 查看适配器状态 |
| `qtine adapter reconnect <名称>` | 重连适配器 |
| `qtine log [行数]` | 查看最近日志 |

## 常见问题

### Q: 提示 "Permission denied"

1. 检查 `config.yml` 中 `security.super_admins` 是否配置了你的 QQ 号
2. QQ 号必须是字符串形式：`- "123456789"`
3. 修改后重启 Qtine
4. 确认发消息的 QQ 号与配置一致

### Q: `qtine enable` 提示 "Plugin not found"

1. 用 `qtine list` 确认插件名拼写
2. 插件名区分大小写

### Q: `qtine reload` 报错

1. 查看日志中的错误信息
2. 检查插件代码是否有语法错误
3. 修复后再次 reload
