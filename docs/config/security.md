# 安全配置

```yaml
security:
  super_admins:
    - "123456789"
  login_attempts: 5
  login_window_seconds: 300
  rate_limit:
    enabled: true
    messages_per_second: 5
    burst: 10
```

## 管理员与限流

`super_admins` 填写有管理权限的 QQ 号。生产环境至少配置一个管理员。

`login_attempts` 和 `login_window_seconds` 限制管理令牌登录失败次数。消息限流由 `rate_limit` 控制。

## 管理 API

WebUI 使用 HttpOnly Cookie。外部 API 客户端使用 Bearer Token：

```http
Authorization: Bearer <QTINE_ADMIN_TOKEN>
```

未设置 `QTINE_ADMIN_TOKEN` 时，首次启动会生成 64 位十六进制令牌并写入 `data/token.txt`，文件权限为 `0600`。

Docker 生产部署必须通过 `.env` 设置：

```dotenv
QTINE_ADMIN_TOKEN=<至少32字符的随机值>
QTINE_SESSION_SECRET=<至少32字符的随机值>
QTINE_ONEBOT_ACCESS_TOKEN=<独立的随机值>
```

## OneBot Token

```yaml
adapters:
  onebot_v11:
    access_token: "独立的随机字符串"
```

NapCat 的反向 WebSocket 和 OneBot HTTP API 都必须携带该 Token。不要与管理令牌复用。

## WebUI

```yaml
webui:
  secure_cookie: true
  allowed_origins:
    - "https://bot.example.com"
  allow_process_control: false
```

HTTPS 反向代理后应启用 `secure_cookie`。生产 WSGI 模式固定禁用 WebUI 关机和重启，由 Docker 或 systemd 管理进程。

## 扩展安全

```yaml
plugins:
  allow_dependency_install: false
```

插件和适配器是可执行代码，只安装可信来源。默认禁止插件运行时调用 pip 安装依赖。上传 ZIP 会校验路径、符号链接、文件数和解压大小。

## 生产清单

- 配置 `super_admins` 和 OneBot `access_token`
- 设置 `QTINE_ADMIN_TOKEN`、`QTINE_SESSION_SECRET`
- 保持 `server.debug: false`
- 使用 HTTPS 反向代理并设置 `secure_cookie: true`
- 限制 4990 端口的防火墙访问范围
- 定期备份 `data/`，并监控 `/health` 和容器日志
