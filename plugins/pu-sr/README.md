# PU-SR

PU-CN-Wiki 搜索与反馈插件，基于 Qtine 平台。

## 功能

通过 Wikit GraphQL API 搜索 pu-cn-wiki 页面信息，并提供反馈/建议系统。

## 命令

### /sr - 搜索

- `/sr` — 显示帮助
- `/sr <页面名>` — 按页面名搜索，返回首个匹配（标题/评分/作者/标签/讨论/链接）
- `/sr <页面名> #tag <标签> [标签...]` — 页面名 + 标签检索（全包含）
- `/sr <页面名> <作者名>` — 页面名 + 作者组合检索
- `/sr #au <作者名>` — 查看作者在本站所有页面（QQ 合并转发消息）

### /au - 作者

- `/au <作者名>` — 显示作者排行与总分，格式 `#排名 作者名 总分：值`

### /putc - 反馈

- `/putc` — 反馈/建议菜单
- `/putc <内容>` — 提交反馈
- `/putc me` — 查看自己的反馈受理状态
- `/putc <编号>` — 查看指定编号反馈
- `/putc list` — 列出所有反馈（管理员）
- `/putc add <编号>` — 受理反馈（管理员）
- `/putc kill <编号>` — 拒绝反馈（管理员）

## 配置

管理员 QQ 通过插件配置项 `admins` 设置（WebUI 可改），控制 `/putc list/add/kill` 权限。

## 数据来源

Wikit GraphQL API: `https://wikit.unitreaty.org/apiv1/graphql`

## 版本

1.0.1
