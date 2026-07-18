# Docker 部署

## 1. 配置密钥

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

生成三次随机值，分别写入 `.env` 的 `QTINE_ADMIN_TOKEN`、`QTINE_SESSION_SECRET` 和 `QTINE_ONEBOT_ACCESS_TOKEN`。

## 2. 准备目录

```bash
mkdir -p data plugins adapters
chown 10001:10001 config.yml
chown -R 10001:10001 data plugins adapters
```

## 3. 启动

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f qtine
```

服务在容器内监听 `0.0.0.0:4990`。

- WebUI：`http://localhost:4990/webui`
- 健康检查：`http://localhost:4990/health`
- OneBot WebSocket：`ws://localhost:4990/onebot/v11`

## 持久化

- `./data:/app/data`：数据库、日志和上传文件
- `./plugins:/app/plugins`：外部插件
- `./adapters:/app/adapters`：外部适配器
- `./config.yml:/app/config.yml`：主配置，WebUI 修改设置时需要写权限

## HTTPS

公网部署应在 Qtine 前使用 Caddy、Nginx 或其他支持 WebSocket 的 TLS 反向代理。启用 HTTPS 后设置：

```yaml
webui:
  secure_cookie: true
  allowed_origins:
    - "https://bot.example.com"
```

反向代理必须转发 `Upgrade` 和 `Connection` 请求头，并将外部流量代理到 `qtine:4990`。

## NapCat

NapCat 在宿主机时使用 `ws://宿主机地址:4990/onebot/v11`。NapCat 在同一 Compose 网络时使用 `ws://qtine:4990/onebot/v11`。两端配置相同的 OneBot `access_token`。

## 运维

```bash
docker compose pull
docker compose up -d --build
docker compose down
```

生产模式由 Gunicorn 管理进程，WebUI 关机和重启接口默认禁用。容器包含健康检查、日志轮转、非 root 用户、能力删除和 `no-new-privileges`。
