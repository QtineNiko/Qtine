# 快速开始

本页介绍如何从零安装并运行 Qtine。

## 环境要求

- **Python** 3.9 或更高版本
- **pip** 包管理器
- **NapCat** 或其他 OneBot V11 实现（用于对接 QQ）

## 1. 获取源码

```bash
git clone https://github.com/QtineNiko/Qtine.git
cd Qtine
```

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 3. 配置

编辑 `config.yml`：

```yaml
server:
  host: "0.0.0.0"
  port: 4990

adapters:
  onebot_v11:
    enabled: true
    ws_path: "/onebot/v11"
    access_token: ""

security:
  super_admins:
    - "你的QQ号"   # 改成你自己的 QQ 号
```

::: tip
`super_admins` 是管理员 QQ 号列表，管理员才能执行管理类命令。
:::

## 4. 启动

```bash
python main.py
```

启动成功后会看到类似输出：

```
[INFO] Qtine v1.0.0
[INFO] Initializing Qtine...
[INFO] Adapter [onebot_v11] WS: ws://0.0.0.0:4990/onebot/v11
[INFO] Loaded 6 builtin plugins
[INFO] Qtine bot started
[INFO] Server running on http://0.0.0.0:4990
[INFO] WebUI: http://localhost:4990/webui
[INFO] Token: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## 5. 访问 WebUI

打开浏览器访问 `http://localhost:4990/webui`，使用启动时显示的 Token 登录。

## 6. 对接 NapCat

让 Qtine 真正连上 QQ，请参考 [对接 NapCat](/guide/connect-napcat)。

## 常见问题

### 启动报错 `ModuleNotFoundError`

确认依赖安装完整：

```bash
pip install -r requirements.txt
```

### 端口被占用

修改 `config.yml` 中的 `server.port`。

### NapCat 连接不上

参考 [对接 NapCat](/guide/connect-napcat) 排查连接问题。
