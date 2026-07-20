# -*- coding: utf-8 -*-
"""PU-SR 插件 - 通过 Wikit GraphQL API 搜索 pu-cn-wiki 页面信息。

命令：
  /sr                    显示帮助
  /sr <页面名>           按页面名搜索（返回首个匹配）
  /sr <页面名> #tag <标签> [标签...]  页面名+标签检索
  /sr <页面名> <作者名>  页面名+作者检索
  /sr #au <作者名>       查看作者在本站的所有页面（合并消息）
  /au <作者名>           显示作者在本站的排行与总分
  /putc                  反馈/建议菜单
"""

import time

import requests

from qtine.plugins.base import BasePlugin

GRAPHQL_URL = "https://wikit.unitreaty.org/apiv1/graphql"
WIKI = "pu-cn-wiki"
PLUGIN_VERSION = "1.0.1"

HELP_TEXT = (
    "欢迎使用PU-SR插件！\n"
    "本插件认准平台:Qtine\n"
    f"插件版本:{PLUGIN_VERSION}\n"
    "数据来源:Wikit GraphQL API\n\n"
    "指令列表：\n"
    "/sr - 搜索分类\n"
    "/sr 页面名 直接搜索页面\n"
    "/sr 页面名 #tag 标签 标签  页面名+标签检索\n"
    "/sr #au 作者名 查看自己在本站的所有页面\n"
    "/au - 作者分类\n"
    "/au 作者名 显示作者的基本数据\n\n"
    "如果想为本插件的完善提出建议，请输入/putc进入建议菜单。"
)

PUTC_MENU = (
    "欢迎打开反馈/建议菜单！\n"
    "插件：PU-SR\n"
    "/putc 内容 - 提出反馈/建议\n"
    "/putc me 查看自己的建议是否被受理\n"
    "/putc 受理编号 查看固定编号反馈/建议是否被受理"
)

STATUS_MAP = {
    "pending": "等待受理",
    "accepted": "已受理",
    "rejected": "已拒绝",
}


class PuSrPlugin(BasePlugin):
    name = "pu-sr"
    package = "qtine-plugin-pu-sr"
    version = PLUGIN_VERSION
    description = "PU-CN-Wiki 搜索与反馈插件"
    author = "Qtine"

    def __init__(self, bot=None):
        super().__init__(bot)
        self.register_command("/sr", self.handle_sr)
        self.register_command("/au", self.handle_au)
        self.register_command("/putc", self.handle_putc)
        # 管理员QQ（逗号分隔），可使用 /putc list/add/kill
        self.add_config(
            "admins", "管理员QQ（逗号分隔）",
            "", "text",
            "可使用 /putc list / add / kill 的QQ号",
        )

    # ── GraphQL 请求 ────────────────────────────────────────────────

    def _gql(self, query: str, variables: dict) -> dict:
        resp = requests.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            msg = data["errors"][0].get("message", "GraphQL error")
            raise RuntimeError(msg)
        return data.get("data", {})

    # ── /sr 命令 ────────────────────────────────────────────────────

    def handle_sr(self, event, args):
        if not args:
            return HELP_TEXT

        # /sr #au 作者名 —— 查看作者在本站的所有页面
        if args[0] == "#au":
            if len(args) < 2:
                return "用法: /sr #au <作者名>"
            author = " ".join(args[1:])
            return self._search_by_author(event, author)

        # /sr 页面名 #tag 标签 标签 —— 页面名+标签检索
        if "#tag" in args:
            tag_idx = args.index("#tag")
            title_kw = " ".join(args[:tag_idx])
            tags = args[tag_idx + 1:]
            if not title_kw or not tags:
                return "用法: /sr <页面名> #tag <标签> [标签...]"
            return self._search_page(event, title_kw, tags=tags)

        # /sr 页面名 作者名 —— 页面名+作者检索（最后一个参数为作者名）
        if len(args) >= 2:
            *title_parts, author = args
            title_kw = " ".join(title_parts)
            return self._search_page(event, title_kw, author=author)

        # /sr 页面名 —— 直接搜索页面
        title_kw = " ".join(args)
        return self._search_page(event, title_kw)

    def _search_page(self, event, title_kw, author=None, tags=None):
        """按页面名搜索，返回首个匹配。"""
        filters = ["$wiki: [String]", "$titleKeyword: String"]
        args_str = "wiki: $wiki, titleKeyword: $titleKeyword"
        variables = {"wiki": [WIKI], "titleKeyword": title_kw}

        if author:
            filters.append("$author: String")
            args_str += ", author: $author"
            variables["author"] = author
        if tags:
            filters.append("$includeTags: [String]")
            args_str += ", includeTags: $includeTags"
            variables["includeTags"] = tags

        query = (
            "query Search(" + ", ".join(filters) + ") {\n"
            "  articles(" + args_str + ", page: 1, pageSize: 1) {\n"
            "    nodes {\n"
            "      title\n"
            "      rating\n"
            "      author\n"
            "      tags\n"
            "      comments\n"
            "      url\n"
            "    }\n"
            "  }\n"
            "}"
        )
        try:
            data = self._gql(query, variables)
        except Exception as e:
            self.logger.error(f"pu-sr search error: {e}")
            return f"查询失败: {e}"

        nodes = data.get("articles", {}).get("nodes", [])
        if not nodes:
            return f"未找到匹配「{title_kw}」的页面"

        return self._format_article(nodes[0], event)

    def _format_article(self, article, event):
        """格式化单篇文章信息。"""
        at_prefix = self._at_sender(event)
        tags = article.get("tags") or []
        tags_str = " ".join(tags) if tags else "无"
        url = article.get("url") or "无"

        lines = [
            at_prefix + (article.get("title") or ""),
            f"评分: {article.get('rating', 0)}",
            f"作者: {article.get('author') or '未知'}",
            f"标签: {tags_str}",
            f"讨论: {article.get('comments', 0)}",
            f"链接: {url}",
        ]
        return "\n".join(lines)

    def _search_by_author(self, event, author):
        """按作者查询本站所有页面，用合并转发消息发送。"""
        query = (
            "query AuthorPages($wiki: [String], $author: String) {\n"
            "  articles(wiki: $wiki, author: $author) {\n"
            "    nodes {\n"
            "      title\n"
            "      rating\n"
            "      url\n"
            "    }\n"
            "  }\n"
            "}"
        )
        try:
            data = self._gql(query, {"wiki": [WIKI], "author": author})
        except Exception as e:
            self.logger.error(f"pu-sr author pages error: {e}")
            return f"查询失败: {e}"

        nodes = data.get("articles", {}).get("nodes", [])
        if not nodes:
            return f"未找到作者「{author}」在本站的页面"

        # 尝试合并转发消息
        sent = self._send_forward(event, author, nodes)
        if sent:
            return None  # 已直接发送
        # 合并转发失败，退化为文本
        lines = [f"用户名: {author}", "以下是本站他创建的所有页面："]
        for i, n in enumerate(nodes, 1):
            lines.append(
                f"{i}. {n.get('title', '')} "
                f"(评分:{n.get('rating', 0)})"
            )
        return "\n".join(lines)

    def _send_forward(self, event, author, nodes):
        """发送合并转发消息。成功返回 True。"""
        if not self.bot:
            return False
        adapter = self.bot.adapter_manager.get("onebot_v11")
        if not adapter:
            return False

        bot_qq = adapter.bot_qq or "10000"
        bot_name = adapter.bot_nickname or "PU-SR"

        # 构建节点
        messages = [{
            "type": "node",
            "data": {
                "name": bot_name,
                "uin": str(bot_qq),
                "content": [{
                    "type": "text",
                    "data": {"text": f"用户名: {author}\n以下是本站他创建的所有页面："}
                }],
            },
        }]
        for i, n in enumerate(nodes, 1):
            text = (
                f"{i}. {n.get('title', '')}\n"
                f"评分: {n.get('rating', 0)}\n"
                f"{n.get('url', '')}"
            )
            messages.append({
                "type": "node",
                "data": {
                    "name": bot_name,
                    "uin": str(bot_qq),
                    "content": [{"type": "text", "data": {"text": text}}],
                },
            })

        # 调用合并转发 API
        if event.message.is_group():
            action = "send_group_forward_msg"
            params = {
                "group_id": int(event.message.group_id),
                "messages": messages,
            }
        elif event.message.sender:
            action = "send_private_forward_msg"
            params = {
                "user_id": int(event.message.sender.user_id),
                "messages": messages,
            }
        else:
            return False

        try:
            result = adapter._call_api_sync(action, params)
            ok = bool(result and result.get("status") == "ok")
            if not ok:
                self.logger.warning(
                    f"pu-sr forward failed: {result}"
                )
            return ok
        except Exception as e:
            self.logger.error(f"pu-sr forward msg error: {e}")
            return False

    # ── /au 命令 ────────────────────────────────────────────────────

    def handle_au(self, event, args):
        if not args:
            return "用法: /au <作者名>"

        author = " ".join(args)
        query = (
            "query AuthorRank($wiki: String!, $name: String!) {\n"
            "  authorWikiRank(wiki: $wiki, name: $name, by: RATING) {\n"
            "    rank\n"
            "    name\n"
            "    value\n"
            "  }\n"
            "}"
        )
        try:
            data = self._gql(query, {"wiki": WIKI, "name": author})
        except Exception as e:
            self.logger.error(f"pu-sr au error: {e}")
            return f"查询失败: {e}"

        info = data.get("authorWikiRank")
        if not info:
            return f"未找到作者「{author}」的排行信息"

        at_prefix = self._at_sender(event)
        return (
            f"{at_prefix}#{info.get('rank', 0)} "
            f"{info.get('name', author)} 总分：{info.get('value', 0)}"
        )

    # ── /putc 命令（反馈/建议系统）──────────────────────────────────

    def handle_putc(self, event, args):
        if not args:
            return PUTC_MENU

        sender_id = ""
        if event.message.sender:
            sender_id = event.message.sender.user_id

        sub = args[0]

        # /putc me
        if sub == "me":
            return self._putc_my(sender_id)

        # /putc list
        if sub == "list":
            if not self._is_admin(sender_id):
                return "无权限：仅管理员可查看所有反馈"
            return self._putc_list()

        # /putc kill 编号
        if sub == "kill":
            if not self._is_admin(sender_id):
                return "无权限：仅管理员可操作"
            if len(args) < 2:
                return "用法: /putc kill <编号>"
            return self._putc_set_status(args[1], "rejected")

        # /putc add 编号
        if sub == "add":
            if not self._is_admin(sender_id):
                return "无权限：仅管理员可操作"
            if len(args) < 2:
                return "用法: /putc add <编号>"
            return self._putc_set_status(args[1], "accepted")

        # /putc 编号
        if sub.isdigit():
            return self._putc_get(sub)

        # /putc 内容
        content = " ".join(args)
        return self._putc_add(sender_id, content)

    def _is_admin(self, qq: str) -> bool:
        admins_str = self.get_config("admins", "") or ""
        admins = [a.strip() for a in admins_str.split(",") if a.strip()]
        return qq in admins

    def _load_putc(self) -> list:
        if not self.bot or not self.bot.storage:
            return []
        return self.bot.storage.get("pu_sr_putc", []) or []

    def _save_putc(self, data: list) -> None:
        if not self.bot or not self.bot.storage:
            return
        self.bot.storage.set("pu_sr_putc", data)

    def _putc_add(self, qq: str, content: str) -> str:
        data = self._load_putc()
        fid = str(len(data) + 1)
        data.append({
            "id": fid,
            "qq": qq,
            "content": content,
            "status": "pending",
            "created_at": time.time(),
        })
        self._save_putc(data)
        return f"反馈已提交！编号：{fid}\n状态：等待受理"

    def _putc_my(self, qq: str) -> str:
        data = self._load_putc()
        mine = [d for d in data if d.get("qq") == qq]
        if not mine:
            return "你还没有提交过反馈"
        lines = ["你的反馈列表："]
        for d in mine:
            s = STATUS_MAP.get(d.get("status", "pending"), d.get("status"))
            lines.append(f"#{d['id']} [{s}] {d['content'][:30]}")
        return "\n".join(lines)

    def _putc_get(self, fid: str) -> str:
        data = self._load_putc()
        for d in data:
            if d.get("id") == fid:
                s = STATUS_MAP.get(d.get("status", "pending"), d.get("status"))
                return (
                    f"#{d['id']}\n"
                    f"状态：{s}\n"
                    f"提交者：{d.get('qq')}\n"
                    f"内容：{d.get('content')}"
                )
        return f"未找到编号 {fid} 的反馈"

    def _putc_list(self) -> str:
        data = self._load_putc()
        if not data:
            return "暂无反馈"
        lines = ["所有反馈："]
        for d in data:
            s = STATUS_MAP.get(d.get("status", "pending"), d.get("status"))
            content = d.get("content", "")[:30]
            lines.append(
                f"#{d['id']} [{s}] {d.get('qq')}: {content}"
            )
        return "\n".join(lines)

    def _putc_set_status(self, fid: str, status: str) -> str:
        data = self._load_putc()
        for d in data:
            if d.get("id") == fid:
                d["status"] = status
                self._save_putc(data)
                label = STATUS_MAP.get(status, status)
                return f"#{fid} 已标记为「{label}」"
        return f"未找到编号 {fid} 的反馈"

    # ── 辅助 ────────────────────────────────────────────────────────

    @staticmethod
    def _at_sender(event) -> str:
        """返回 @发送者 的 CQ 码前缀。"""
        if event.message.sender and event.message.sender.user_id:
            return f"[CQ:at,qq={event.message.sender.user_id}]\n"
        return ""
