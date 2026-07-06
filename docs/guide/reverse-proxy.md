# 反向代理

通过 Nginx 反向代理 Qtine，实现 HTTPS、域名访问、IP 限制等。

## 基础配置

```nginx
server {
    listen 80;
    server_name qtine.example.com;

    location / {
        proxy_pass http://127.0.0.1:4990;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 支持
    location /onebot/v11 {
        proxy_pass http://127.0.0.1:4990;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # SocketIO 支持（WebUI 实时日志）
    location /socket.io/ {
        proxy_pass http://127.0.0.1:4990;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## HTTPS 配置

使用 Let's Encrypt 申请免费证书：

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d qtine.example.com
```

完整 HTTPS 配置：

```nginx
server {
    listen 80;
    server_name qtine.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name qtine.example.com;

    ssl_certificate /etc/letsencrypt/live/qtine.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/qtine.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:4990;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /onebot/v11 {
        proxy_pass http://127.0.0.1:4990;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:4990;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## IP 限制

仅允许特定 IP 访问 WebUI：

```nginx
location /webui {
    allow 192.168.1.0/24;    # 允许内网
    allow 1.2.3.4;           # 允许特定 IP
    deny all;

    proxy_pass http://127.0.0.1:4990;
    # ... 其他 proxy_set_header
}
```

## Caddy 配置（更简单）

Caddy 自动申请 HTTPS 证书：

```caddyfile
qtine.example.com {
    reverse_proxy 127.0.0.1:4990

    # WebSocket
    @websocket {
        header Connection *Upgrade*
        header Upgrade websocket
    }
    reverse_proxy @websocket 127.0.0.1:4990
}
```

## NapCat 连接配置

使用反向代理后，NapCat 连接地址改为域名：

```json
{
  "url": "wss://qtine.example.com/onebot/v11"
}
```

::: tip
`wss://` 是 WebSocket over TLS，对应 HTTPS。
:::

## 安全建议

1. **生产环境必须 HTTPS**：避免 Token 明文传输
2. **限制 WebUI 访问**：通过 IP 白名单或额外的 Basic Auth
3. **设置复杂 Token**：避免被暴力破解
4. **定期更新证书**：Let's Encrypt 证书 90 天过期，配置自动续期

```bash
# 自动续期
sudo certbot renew --dry-run
```
