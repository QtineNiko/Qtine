# FAQ 常见问题

## 安装与启动

### Q: 启动报错 `ModuleNotFoundError: No module named 'flask'`

依赖未安装完整，执行：

```bash
pip install -r requirements.txt
```

如果使用虚拟环境，确认已激活。

### Q: 启动报错 `Address already in use` 端口被占用

修改 `config.yml` 中的端口：

```yaml
server:
  port: 4991   # 改成其他端口
```

或查找并结束占用进程：

```bash
# Windows
netstat -ano | findstr :4990
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :4990
kill -9 <PID>
```

### Q: 启动后无任何输出

可能原因：

1. 日志级别过高，改为 `DEBUG`：
   ```yaml
   logging:
     level: "DEBUG"
   ```
2. WSGI 中间件初始化失败，检查 Python 版本（需 3.9+）
3. 使用 `python -u main.py` 禁用输出缓冲

## NapCat 连接

### Q: NapCat 连接后 Qtine 无反应

排查步骤：

1. **查看 Qtine 日志**是否有 `WS upgrade` 字样
   - 没有：网络层不通，检查防火墙、端口、IP
   - 有但马上断开：Token 不匹配

2. **检查 NapCat 配置**中的 URL 是否正确：
   - 反向 WS：`ws://Qtine的IP:4990/onebot/v11`
   - 路径必须是 `/onebot/v11`

3. **检查 Token**：Qtine 和 NapCat 的 `access_token` 必须一致

### Q: NapCat 显示已连接但收不到消息

1. 确认 NapCat 已登录 QQ
2. 在 QQ 里给机器人发消息，查看 Qtine 日志是否有 `<< message from`
3. 如果没有，检查 NapCat 是否启用了消息上报

### Q: Bot 账号显示为空

Qtine 连接后会调用 `get_login_info` 获取 Bot 信息：

- 失败会显示 `Failed to fetch bot info`
- 检查 NapCat 是否正常登录 QQ
- 重启 Qtine 重试

## 命令与回复

### Q: 发送 `#help` 没有回复

排查步骤：

1. **确认消息到达**：日志中应有 `<onebot_v11> [group:xxx] ...` 字样
2. **确认未触发限流**：日志中不应有 `Rate limited`
3. **确认未在黑名单**：检查 `blacklist_users`
4. **确认命令格式**：`#help`（注意是 `#` 不是其他符号）

### Q: 管理员命令提示 "Permission denied"

1. 检查 `config.yml` 中 `security.super_admins` 是否配置了你的 QQ 号
2. QQ 号必须是字符串：`- "123456789"`
3. 修改后重启 Qtine
4. 确认发消息的 QQ 号与配置一致

### Q: 命令前缀是什么

| 前缀 | 用途 | 示例 |
|------|------|------|
| `#` | 用户命令 | `#help`、`#qtine` |
| `/` | 工具命令 | `/echo`、`/ban` |
| `qtine` | 管理命令 | `qtine list` |

### Q: 自定义命令前缀

目前命令前缀由插件定义，修改需要改插件源码。

## WebUI

### Q: WebUI 打不开

1. 确认 Qtine 已启动：`http://localhost:4990/health` 应返回 `ok`
2. 检查端口是否正确
3. 检查防火墙是否放行端口

### Q: 忘记 Token

查看 `data/token.txt` 文件，或在 WebUI 设置页查看。

### Q: WebUI 显示数据为空

1. 等待几秒让数据加载
2. 刷新页面
3. 检查浏览器控制台是否有错误
4. 确认 Qtine 服务正在运行

## 插件

### Q: 导入插件失败

1. 检查 .zip 包结构：必须有 `plugin.json` 和 `main.py`
2. 检查 `plugin.json` 格式是否正确
3. 查看日志中的错误信息

### Q: 插件启用后不工作

1. 查看插件状态是否为 "已启用"
2. 查看日志是否有插件加载错误
3. 确认命令格式正确
4. 尝试重载插件：`qtine reload <插件名>`

### Q: 插件导致机器人崩溃

禁用插件：

```
qtine disable <插件名>
```

或通过 WebUI 禁用，然后联系插件作者修复。

## 性能

### Q: 机器人响应慢

可能原因：

1. **频率限制过严**：调高 `messages_per_second`
2. **插件过多**：禁用不必要的插件
3. **数据库过大**：清理 `data/qtine.db`
4. **服务器性能不足**：升级配置

### Q: 内存占用高

1. 检查是否有插件内存泄漏
2. 日志缓冲区限制为 500 条，已优化
3. 重启 Qtine 释放内存

## 升级

### Q: 如何升级 Qtine

```bash
git pull
pip install -r requirements.txt --upgrade
python main.py
```

### Q: 升级后配置不兼容

查看 [更新日志](/guide/changelog)，按说明迁移配置。

## 其他

### Q: 如何备份数据

```bash
# 备份整个 data 目录
cp -r data data.backup

# 或只备份数据库
cp data/qtine.db data/qtine.db.backup
```

### Q: 如何贡献代码

欢迎提交 Issue 和 PR：

1. Fork 项目
2. 创建分支：`git checkout -b feature/xxx`
3. 提交：`git commit -m "Add xxx"`
4. 推送：`git push origin feature/xxx`
5. 创建 Pull Request

### Q: 如何获取帮助

- 提交 [GitHub Issue](https://github.com/QtineNiko/Qtine/issues)
- 查看本站文档
- 阅读 [架构设计](/guide/architecture) 理解原理
