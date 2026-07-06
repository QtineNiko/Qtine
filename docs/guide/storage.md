# 存储后端

Qtine 通过 Storage 模块统一管理持久化数据，支持 SQLite 和内存两种后端。

## 配置

在 `config.yml` 中配置：

```yaml
storage:
  backend: "sqlite"                # sqlite 或 memory
  sqlite_path: "./data/qtine.db"   # SQLite 数据库文件路径
```

## 使用场景

Storage 用于存储：

- **黑名单用户**：`blacklist_users`
- **入群欢迎语**：`welcome_messages`
- **Bot 信息缓存**：`onebot_bot_info`
- **插件配置**：`plugin_config:<plugin_name>`
- **用户会话**：`session:<user_id>`
- **自定义数据**：插件可以存储任意键值对

## API

### 读取数据

```python
value = self.bot.storage.get("key", default_value)
```

### 写入数据

```python
self.bot.storage.set("key", value)
```

### 删除数据

```python
self.bot.storage.delete("key")
```

### 检查键是否存在

```python
if self.bot.storage.exists("key"):
    # ...
```

## 在插件中使用

```python
from qtine.plugins.base import BasePlugin


class CounterPlugin(BasePlugin):
    name = "counter"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/count", self.handle_count)

    def handle_count(self, event, args):
        # 读取当前计数
        count = self.bot.storage.get("counter:total", 0)
        count += 1
        # 保存
        self.bot.storage.set("counter:total", count)
        return f"这是第 {count} 次调用"
```

## 数据类型

Storage 支持以下 Python 数据类型（基于 JSON 序列化）：

- 字符串、整数、浮点数、布尔值
- 字典、列表
- None
- 嵌套结构

::: warning
不支持自定义类对象。如需存储复杂对象，请先转换为字典。
:::

## 后端对比

| 特性 | SQLite | 内存 |
|------|--------|------|
| 持久化 | ✅ 重启不丢失 | ❌ 重启清空 |
| 性能 | 中等 | 最快 |
| 容量 | 受磁盘限制 | 受内存限制 |
| 适用场景 | 生产环境 | 临时测试 |

## 数据库表结构

SQLite 后端使用一张通用表 `kv_store`：

```sql
CREATE TABLE kv_store (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

所有数据以 JSON 字符串形式存储在 `value` 字段中。

## 命名约定

为避免键冲突，建议使用命名空间前缀：

| 用途 | 前缀 | 示例 |
|------|------|------|
| 插件数据 | `plugin:<name>:` | `plugin:counter:total` |
| 用户数据 | `user:<id>:` | `user:123456:score` |
| 群数据 | `group:<id>:` | `group:789:config` |
| 系统数据 | 无前缀 | `blacklist_users` |

## 备份

SQLite 数据库是一个独立文件 `data/qtine.db`，备份只需复制此文件。

```bash
cp data/qtine.db data/qtine.db.backup
```

::: tip
建议定期备份，特别是在升级 Qtine 版本前。
:::
