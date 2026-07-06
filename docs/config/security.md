# 安全配置

```yaml
security:
  super_admins:
    - "123456789"
    - "987654321"
  rate_limit:
    enabled: true
    messages_per_second: 5
    burst: 10
```

## super_admins

- **类型**：string[]
- **默认**：`[]`
- **说明**：超级管理员的 QQ 号列表

::: warning
生产环境**必须**配置至少一个管理员，否则无法执行管理类命令。
:::

### 配置示例

```yaml
security:
  super_admins:
    - "123456789"      # 管理员1
    - "987654321"      # 管理员2
```

::: tip
QQ 号用字符串形式（带引号），避免被解析成数字。
:::

## rate_limit

频率限制配置，详见 [频率限制](/guide/rate-limit)。

### enabled

- **类型**：bool
- **默认**：`false`
- **说明**：是否启用频率限制

### messages_per_second

- **类型**：int
- **默认**：`5`
- **说明**：每秒补充的令牌数（长期平均速率）

### burst

- **类型**：int
- **默认**：`10`
- **说明**：令牌桶容量（瞬时突发上限）

## 黑名单

黑名单不通过配置文件管理，而是通过命令动态维护：

```
/ban <QQ号> [原因]     # 添加
/unban <QQ号>          # 移除
/blacklist             # 查看
```

黑名单存储在 `data/qtine.db`，重启不丢失。

## Token 鉴权

WebUI 和 API 的访问 Token 在启动时自动生成，保存在 `data/token.txt`。

::: tip
通过 WebUI 设置页可以查看、复制 Token。如果泄露，删除 `data/token.txt` 后重启即可生成新 Token。
:::

## 安全建议

### 生产环境清单

- [ ] 配置 `super_admins`
- [ ] 启用频率限制
- [ ] 设置 OneBot V11 `access_token`
- [ ] 修改 `webui.session_secret`
- [ ] 通过反向代理限制 WebUI 访问
- [ ] 启用 HTTPS

### session_secret

```yaml
webui:
  session_secret: "你的随机字符串"
```

::: warning
默认的 `qtine-secret-key-change-me` 仅用于开发，生产环境必须修改。
:::

生成随机字符串：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### access_token

```yaml
adapters:
  onebot_v11:
    access_token: "你的随机字符串"
```

避免未授权的客户端连接 Qtine。

## 权限等级

| 等级 | 说明 | 可执行的命令 |
|------|------|--------------|
| `user` | 普通用户 | `#help`、`#qtine`、`/echo` 等 |
| `admin` | 管理员 | 上述 + `qtine list/enable/disable/...`、`/ban`、`/unban` |

命令的权限级别由插件声明，参考 [插件开发](/develop/plugin)。
