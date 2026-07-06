# 日志配置

```yaml
logging:
  level: "INFO"
  file: "./data/logs/qtine.log"
  max_size_mb: 10
  backup_count: 5
```

## level

- **类型**：string
- **可选值**：`"DEBUG"` / `"INFO"` / `"WARNING"` / `"ERROR"`
- **默认**：`"INFO"`
- **说明**：日志级别

### 级别说明

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| `DEBUG` | 详细调试信息 | 开发调试 |
| `INFO` | 一般信息 | 生产环境（默认） |
| `WARNING` | 警告 | 排查问题 |
| `ERROR` | 错误 | 仅关注错误 |

::: tip
排查问题时改为 `DEBUG` 可以看到详细的消息流转、命令匹配等日志。
:::

## file

- **类型**：string
- **默认**：`"./data/logs/qtine.log"`
- **说明**：日志文件路径

## max_size_mb

- **类型**：int
- **默认**：`10`
- **说明**：单个日志文件最大大小（MB）

超过此大小会自动轮转，创建新文件。

## backup_count

- **类型**：int
- **默认**：`5`
- **说明**：保留的备份文件数量

日志文件轮转后，最多保留 `backup_count` 个历史文件，超出的自动删除。

## 日志输出

Qtine 的日志同时输出到：

1. **控制台**：启动时实时显示
2. **文件**：按配置写入日志文件
3. **内存缓冲**：最近 500 条，供 WebUI 实时查看

## 日志格式

```
[2026-07-05 12:34:56] [INFO] [onebot_v11] << message from 用户名: 消息内容
[2026-07-05 12:34:57] [INFO] Command matched: '#help' -> [help] handle_help
[2026-07-05 12:34:57] [INFO] Command reply: 帮助信息...
```

格式：`[时间] [级别] [模块] 消息内容`

## 通过 WebUI 查看

访问 `http://localhost:4990/webui` → **日志查看**：

- 实时滚动显示
- 按级别过滤
- 自动刷新

## 通过命令查看

```
qtine log          # 查看最近 20 行
qtine log 50       # 查看最近 50 行
```

## 日志轮转示例

配置 `max_size_mb: 10`，`backup_count: 5` 时：

```
data/logs/
├── qtine.log          # 当前日志
├── qtine.log.1        # 上一个轮转
├── qtine.log.2
├── qtine.log.3
├── qtine.log.4
└── qtine.log.5        # 最老的备份（再轮转会被删除）
```

总占用约 60MB（6 × 10MB）。

## 性能考虑

- `DEBUG` 级别会产生大量日志，影响性能，**生产环境不要用**
- 日志写入是同步操作，频繁写入会影响吞吐量
- 内存缓冲固定 500 条，不会无限增长

## 自定义日志

插件可以直接使用 `self.logger`：

```python
class MyPlugin(BasePlugin):
    def handle_command(self, event, args):
        self.logger.info(f"用户 {event.message.sender.user_id} 调用了命令")
        self.logger.debug(f"参数: {args}")
        try:
            # 业务逻辑
            pass
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
```
