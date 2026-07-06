# WebUI 配置

```yaml
webui:
  enabled: true
  session_secret: "qtine-secret-key-change-me"
```

## enabled

- **类型**：bool
- **默认**：`true`
- **说明**：是否启用 WebUI

::: tip
如果不需要 WebUI（例如纯命令行运行），可以设为 `false` 节省资源。
:::

## session_secret

- **类型**：string
- **默认**：`"qtine-secret-key-change-me"`
- **说明**：WebUI 会话加密密钥

::: danger
生产环境**必须**修改为随机字符串！默认值会被攻击者猜到。
:::

### 生成随机密钥

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

输出示例：

```
a1b2c3d4e5f6...（64 个字符）
```

填入配置：

```yaml
webui:
  session_secret: "a1b2c3d4e5f6..."
```

## 访问地址

启动后访问：

```
http://host:port/webui
```

例如 `http://localhost:4990/webui`。

## Token 登录

WebUI 使用 Token 登录：

1. 首次启动时，命令行打印 Token
2. Token 保存在 `data/token.txt`
3. 在 WebUI 登录页粘贴 Token

::: tip
Token 也可以通过 WebUI 设置页查看、复制、隐藏。
:::

## 重新生成 Token

如果 Token 泄露：

1. 停止 Qtine
2. 删除 `data/token.txt`
3. 启动 Qtine，会生成新 Token

```bash
# 停止后
rm data/token.txt
# 启动
python main.py
```

## 安全建议

### 生产环境

- 修改 `session_secret` 为随机字符串
- 通过反向代理启用 HTTPS
- 限制 WebUI 访问 IP
- 定期检查 Token 是否泄露

### 反向代理示例

参考 [反向代理](/guide/reverse-proxy) 配置 Nginx：

```nginx
server {
    listen 443 ssl;
    server_name qtine.example.com;

    # ... SSL 配置

    location /webui {
        allow 192.168.1.0/24;    # 限制内网访问
        deny all;
        proxy_pass http://127.0.0.1:4990;
        # ...
    }
}
```

## WebUI 路由

| 路径 | 说明 |
|------|------|
| `/webui` | WebUI 入口 |
| `/webui/dashboard` | 仪表盘 |
| `/webui/plugins` | 插件管理 |
| `/webui/adapters` | 适配器管理 |
| `/webui/logs` | 日志查看 |
| `/webui/settings` | 系统设置 |

## API 路由

WebUI 后端 API：

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/token` | GET | 获取 Token |
| `/api/status` | GET | 系统状态 |
| `/api/plugins` | GET | 插件列表 |
| `/api/plugins/{name}/enable` | POST | 启用插件 |
| `/api/plugins/{name}/disable` | POST | 禁用插件 |
| `/api/plugins/{name}/reload` | POST | 重载插件 |
| `/api/plugins/import` | POST | 导入插件 |
| `/api/adapters` | GET | 适配器状态 |
| `/api/adapters/{name}/reconnect` | POST | 重连适配器 |
| `/api/adapters/import` | POST | 导入适配器 |
| `/api/logs` | GET | 获取日志 |
| `/health` | GET | 健康检查 |

详见 [API 接口](/develop/api)。
