# 插件命令

各个插件提供的命令汇总。

## help 插件

状态查询与帮助。

| 命令 | 别名 | 权限 | 说明 |
|------|------|------|------|
| `#qtine` | - | user | 查看机器人运行状态 |
| `#help` | `#帮助` | user | 列出所有可用命令 |

## echo 插件

复读测试。

| 命令 | 别名 | 权限 | 说明 |
|------|------|------|------|
| `/echo <内容>` | `/复读 <内容>` | user | 复读消息内容 |

### 示例

```
/echo 你好世界
/复读 你好世界
```

输出：

```
你好世界
```

## admin 插件

插件与适配器管理。

| 命令 | 权限 | 说明 |
|------|------|------|
| `qtine` | admin | 查看详细状态 |
| `qtine list` | admin | 列出所有插件 |
| `qtine enable <名称>` | admin | 启用插件 |
| `qtine disable <名称>` | admin | 禁用插件 |
| `qtine reload <名称>` | admin | 重载插件 |
| `qtine adapter` | admin | 查看适配器状态 |
| `qtine adapter reconnect <名称>` | admin | 重连适配器 |
| `qtine log [行数]` | admin | 查看最近日志 |

详见 [管理员命令](/commands/admin)。

## welcome 插件

入群欢迎语配置。

| 命令 | 别名 | 权限 | 说明 |
|------|------|------|------|
| `/welcome <消息>` | `/欢迎 <消息>` | admin | 设置入群欢迎语 |
| `/welcome` | `/欢迎` | admin | 查看当前欢迎语 |

### 示例

```
/welcome 欢迎加入本群！
/欢迎 欢迎加入本群！
```

输出：

```
入群欢迎语已设置
```

### 占位符

欢迎语支持以下占位符：

| 占位符 | 说明 |
|--------|------|
| `{nickname}` | 新成员昵称 |
| `{user_id}` | 新成员 QQ 号 |
| `{group_name}` | 群名称 |

示例：

```
/welcome 欢迎 {nickname} 加入 {group_name}！
```

新成员入群时，机器人会发送：

```
欢迎 张三 加入 测试群！
```

## repeat 插件

复读检测，无需命令触发。

群聊中如果有人连发 3 条相同消息（可配置），机器人会自动 +1 复读。

### 配置

通过 `config.yml` 或存储配置：

```yaml
plugins:
  repeat:
    threshold: 3          # 触发阈值
    cooldown: 30          # 冷却时间（秒）
```

### 工作流程

```
群成员 A: 哈哈哈
群成员 A: 哈哈哈
群成员 A: 哈哈哈
机器人: 哈哈哈    ← 自动复读
```

## ban 插件

用户黑名单管理。

| 命令 | 别名 | 权限 | 说明 |
|------|------|------|------|
| `/ban <QQ号> [原因]` | `/封禁 <QQ号> [原因]` | admin | 封禁用户 |
| `/unban <QQ号>` | `/解封 <QQ号>` | admin | 解封用户 |
| `/blacklist` | `/黑名单` | admin | 查看黑名单 |

### 示例

```
/ban 123456789 发广告
/封禁 123456789 发广告
```

输出：

```
用户 123456789 已被封禁
原因: 发广告
```

```
/unban 123456789
/解封 123456789
```

输出：

```
用户 123456789 已解封
```

```
/blacklist
/黑名单
```

输出：

```
黑名单 (2):
- 123456789 (发广告)
- 987654321 (恶意刷屏)
```

### 被封禁用户的行为

被封禁的用户：

- **所有消息被忽略**：不进入命令处理
- **日志记录**：`Blocked blacklisted user: <user_id>`
- **不回复**：避免给封禁用户反馈

## 命令汇总表

| 命令 | 别名 | 权限 | 来源插件 |
|------|------|------|----------|
| `#qtine` | - | user | help |
| `#help` | `#帮助` | user | help |
| `/echo <内容>` | `/复读 <内容>` | user | echo |
| `qtine` | - | admin | admin |
| `qtine list` | - | admin | admin |
| `qtine enable <名称>` | - | admin | admin |
| `qtine disable <名称>` | - | admin | admin |
| `qtine reload <名称>` | - | admin | admin |
| `qtine adapter` | - | admin | admin |
| `qtine adapter reconnect <名称>` | - | admin | admin |
| `qtine log [行数]` | - | admin | admin |
| `/welcome <消息>` | `/欢迎 <消息>` | admin | welcome |
| `/ban <QQ号> [原因]` | `/封禁 <QQ号> [原因]` | admin | ban |
| `/unban <QQ号>` | `/解封 <QQ号>` | admin | ban |
| `/blacklist` | `/黑名单` | admin | ban |
