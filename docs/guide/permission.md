# 权限系统

Qtine 提供两级权限控制，保护敏感操作。

## 权限等级

| 等级 | 说明 |
|------|------|
| `user` | 普通用户，所有 QQ 用户默认 |
| `admin` | 管理员，可以执行管理类命令 |

## 配置管理员

在 `config.yml` 中配置：

```yaml
security:
  super_admins:
    - "123456789"     # QQ 号 1
    - "987654321"     # QQ 号 2
```

::: tip
QQ 号用字符串形式，带引号。
:::

## 权限检查

命令处理函数声明权限级别：

```python
# 在插件中注册命令时声明
self.register_command(
    "/admin-cmd",
    self.handle_admin,
    permission="admin"  # 仅管理员可用
)
```

管道在执行命令前会检查权限：

- 命令要求 `admin` 但用户不是管理员 → 拒绝执行，回复 "Permission denied"
- 命令要求 `user` 或未声明 → 所有人可用

## 黑名单

黑名单是一种特殊的权限控制，被加入黑名单的用户**所有消息都会被忽略**。

### 添加黑名单

```
/ban <QQ号> [原因]
```

例如：

```
/ban 123456789 发广告
```

### 移除黑名单

```
/unban <QQ号>
```

### 查看黑名单

```
/blacklist
```

### 通过 API 操作

```bash
# 添加黑名单
curl -X POST http://localhost:4990/api/blacklist \
  -H "Authorization: Bearer <token>" \
  -d '{"user_id":"123456789"}'

# 查看黑名单
curl http://localhost:4990/api/blacklist \
  -H "Authorization: Bearer <token>"
```

## 权限判断内部实现

```python
def _is_admin(self, message: Message) -> bool:
    if not message.sender:
        return False
    admins = self.config.get("security.super_admins", [])
    return message.sender.user_id in admins
```

## 在插件中检查权限

```python
def handle_my_command(self, event, args):
    # 手动检查权限
    if not self.bot._is_admin(event.message):
        return "仅管理员可用"
    # 管理员逻辑
    return "管理员操作成功"
```

## 最佳实践

- **管理类命令**：声明 `permission="admin"`
- **用户类命令**：默认 `permission="user"` 或不声明
- **敏感操作**：在处理函数内部再次检查权限，双重保险
- **黑名单管理**：仅管理员可执行 `/ban` `/unban`

## 安全建议

1. **生产环境必填 `super_admins`**：避免默认无管理员
2. **设置复杂 Token**：WebUI Token 不要用简单字符串
3. **限制 WebUI 访问**：通过反向代理限制 IP 或加防火墙
4. **定期审计黑名单**：避免误封正常用户
