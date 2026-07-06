# Docker 部署

Qtine 提供完整的 Docker 部署支持，一行命令启动。

## 前置要求

- Docker 20.0+
- Docker Compose 2.0+

## 1. 准备配置

在项目根目录创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  qtine:
    build: .
    container_name: qtine
    restart: always
    ports:
      - "4990:4990"
    volumes:
      - ./data:/app/data
      - ./config.yml:/app/config.yml
      - ./plugins:/app/plugins
      - ./adapters:/app/adapters
    environment:
      - TZ=Asia/Shanghai
```

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 4990

# 启动
CMD ["python", "main.py"]
```

## 2. 启动

```bash
docker compose up -d
```

查看日志：

```bash
docker compose logs -f qtine
```

## 3. 访问

- WebUI：`http://localhost:4990/webui`
- API：`http://localhost:4990/api/...`

## 数据持久化

通过 volumes 挂载，数据持久化到宿主机：

| 容器路径 | 宿主机路径 | 用途 |
|----------|------------|------|
| `/app/data` | `./data` | 数据库、日志、Token |
| `/app/config.yml` | `./config.yml` | 配置文件 |
| `/app/plugins` | `./plugins` | 外部插件 |
| `/app/adapters` | `./adapters` | 外部适配器 |

## 更新

```bash
git pull
docker compose build
docker compose up -d
```

## 停止

```bash
docker compose down
```

## 与 NapCat 配合

### 方式一：NapCat 在宿主机

修改 `config.yml` 的 WS 地址：

```yaml
# 反向 WS - NapCat 连接 Qtine
# NapCat 配置中填 ws://宿主机IP:4990/onebot/v11

# 或正向 WS - Qtine 连接 NapCat
adapters:
  onebot_v11:
    forward_ws_enabled: true
    forward_ws_url: "ws://host.docker.internal:3001"
```

::: tip
`host.docker.internal` 是 Docker 访问宿主机的特殊域名。
:::

### 方式二：NapCat 也在 Docker

使用同一个 Docker 网络：

```yaml
version: '3.8'

services:
  qtine:
    build: .
    restart: always
    ports:
      - "4990:4990"
    networks:
      - bot-net

  napcat:
    image: mlikiowa/napcat-docker:latest
    restart: always
    networks:
      - bot-net
    volumes:
      - ./napcat/config:/app/napcat/config
      - ./napcat/QQ:/app/.config/QQ

networks:
  bot-net:
```

NapCat 配置中填：`ws://qtine:4990/onebot/v11`

## 常见问题

### 端口冲突

修改 `docker-compose.yml` 的端口映射：

```yaml
ports:
  - "8080:4990"   # 宿主机 8080 → 容器 4990
```

### 权限问题

Linux 下可能遇到挂载目录权限问题：

```bash
mkdir -p data plugins adapters
chmod -R 777 data
```

### 容器无法访问宿主机

Linux 下使用 `host.docker.internal` 需要额外配置：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
