# 存储配置

```yaml
storage:
  backend: "sqlite"
  sqlite_path: "./data/qtine.db"
```

## backend

- **类型**：string
- **可选值**：`"sqlite"` / `"memory"`
- **默认**：`"sqlite"`
- **说明**：存储后端类型

### sqlite

SQLite 持久化存储，重启不丢失数据。适合生产环境。

### memory

内存存储，重启清空。仅适合临时测试。

::: warning
`memory` 模式下，黑名单、欢迎语、插件配置等都会在重启后丢失。
:::

## sqlite_path

- **类型**：string
- **默认**：`"./data/qtine.db"`
- **说明**：SQLite 数据库文件路径
- **仅在 `backend: sqlite` 时生效**

::: tip
路径相对于项目根目录。可以改为绝对路径，如 `/var/lib/qtine/qtine.db`。
:::

## 后端对比

| 特性 | sqlite | memory |
|------|--------|--------|
| 持久化 | ✅ | ❌ |
| 性能 | 中等 | 最快 |
| 容量 | 受磁盘限制 | 受内存限制 |
| 并发 | 支持读写锁 | 单线程 |
| 适用场景 | 生产环境 | 临时测试 |

## 数据存储

所有数据以键值对形式存储，详见 [存储后端](/guide/storage)。

## 备份

SQLite 数据库是单文件，备份简单：

```bash
# 备份
cp data/qtine.db data/qtine.db.backup

# 恢复
cp data/qtine.db.backup data/qtine.db
```

::: tip
建议设置定时任务自动备份：

```bash
# 每天 3 点备份
0 3 * * * cp /path/to/data/qtine.db /backup/qtine-$(date +\%Y\%m\%d).db
```
:::

## 性能优化

### 数据库过大

如果数据库超过 100MB，可以清理：

```sql
-- 清理旧日志（VACUUM 回收空间）
VACUUM;
```

### 并发写入

SQLite 默认使用 WAL 模式，支持并发读 + 单写。如果写入频繁出现锁错误，可以：

1. 减少插件写入频率
2. 使用批量写入
3. 考虑改用 PostgreSQL（需要自行实现后端）

## 迁移

### 从 memory 迁移到 sqlite

1. 修改配置：`backend: sqlite`
2. 重启 Qtine
3. 重新配置黑名单、欢迎语等

::: warning
`memory` 模式的数据无法直接迁移，需要手动重新配置。
:::
