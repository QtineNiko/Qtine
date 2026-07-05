# -*- coding: utf-8 -*-
"""Qtine Core Application — Flask + WebSocket server."""

import os
import platform
import secrets
import sys
import time
import threading
from typing import Optional, Dict

from flask import Flask, request, jsonify, send_from_directory, redirect, abort
from flask_socketio import SocketIO
from simple_websocket import Server
from werkzeug.utils import secure_filename

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from qtine.core.config import Config
from qtine.core.bus import EventBus
from qtine.core.pipeline import MessagePipeline, PipelineContext
from qtine.core.session import SessionManager
from qtine.core.plugin_manager import PluginManager
from qtine.core.adapter_manager import AdapterManager
from qtine.utils.models import Message, Sender, AdapterStatus
from qtine.utils.logger import QtineLogger, get_logger
from qtine.storage.backend import Storage


UPLOAD_DIR = os.path.join("data", "uploads")
MAX_UPLOAD_MB = 50
ALLOWED_EXTENSIONS = {"zip"}

# Built-in marketplace demo entries. Used as fallback when no remote
# marketplace source is configured (or the configured source is unreachable),
# so the WebUI can still render the plugin market page out of the box.
BUILTIN_MARKET_PLUGINS = [
    {
        "name": "ai-chat",
        "version": "1.2.0",
        "author": "QtineNiko",
        "description": "AI 聊天插件，支持 OpenAI / Claude / 本地模型多轮对话与上下文记忆。",
        "tags": ["AI", "聊天"],
        "downloads": 1280,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "32 KB",
    },
    {
        "name": "image-gen",
        "version": "0.6.1",
        "author": "白然",
        "description": "文生图插件，调用 Stable Diffusion / 漫画风生成图片并发送。",
        "tags": ["AI", "图像"],
        "downloads": 642,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "48 KB",
    },
    {
        "name": "weather",
        "version": "2.0.3",
        "author": "三月七",
        "description": "天气查询，输入城市名返回实时天气与未来三天预报。",
        "tags": ["工具", "查询"],
        "downloads": 2150,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "16 KB",
    },
    {
        "name": "music",
        "version": "1.4.0",
        "author": "QtineNiko",
        "description": "点歌插件，支持网易云 / QQ 音乐搜索并分享卡片。",
        "tags": ["娱乐", "音乐"],
        "downloads": 3170,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "26 KB",
    },
    {
        "name": "translate",
        "version": "1.0.5",
        "author": "白然",
        "description": "多语言翻译，自动检测语种并翻译为目标语言。",
        "tags": ["工具", "翻译"],
        "downloads": 980,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "12 KB",
    },
    {
        "name": "reminder",
        "version": "0.9.2",
        "author": "三月七",
        "description": "定时提醒，支持一次性 / 周期任务，到点自动 @ 提醒对象。",
        "tags": ["工具", "定时"],
        "downloads": 1420,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "20 KB",
    },
    {
        "name": "sign-in",
        "version": "2.3.1",
        "author": "QtineNiko",
        "description": "签到积分系统，每日签到 / 连签奖励 / 排行榜。",
        "tags": ["娱乐", "积分"],
        "downloads": 2680,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "30 KB",
    },
    {
        "name": "anti-recall",
        "version": "1.1.0",
        "author": "白然",
        "description": "防撤回，记录群成员撤回的消息内容并提示管理员。",
        "tags": ["管理", "工具"],
        "downloads": 1730,
        "homepage": "https://github.com/QtineNiko/Qtine",
        "size": "14 KB",
    },
]


class QtineBot:
    """Core bot instance that ties everything together."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger()
        self.storage = Storage()
        self.event_bus = EventBus()
        self.pipeline = MessagePipeline()
        self.session_manager = SessionManager()
        self.plugin_manager = PluginManager()
        self.adapter_manager = AdapterManager()
        self._start_time = time.time()
        self._running = False
        # rate limiting state: {user_id: [timestamps]}
        self._rate_buckets: dict = {}
        self._rate_lock = threading.Lock()

        self.plugin_manager.set_bot(self)
        self.plugin_manager.set_plugin_dir(
            self.config.get("plugins.dir", "./plugins")
        )

        self.storage.init_backend(
            self.config.get("storage.backend", "sqlite"),
            sqlite_path=self.config.get(
                "storage.sqlite_path", "./data/qtine.db"
            ),
        )

        self._setup_pipeline()

    def _setup_pipeline(self):
        pipeline = self.pipeline

        def pre_blacklist(ctx: PipelineContext, next_fn):
            user_id = (
                ctx.message.sender.user_id
                if ctx.message.sender
                else ""
            )
            blacklist = self.storage.get("blacklist_users", [])
            if user_id in blacklist:
                ctx.abort("User is blacklisted")
                self.logger.debug(f"Blocked blacklisted user: {user_id}")
                return None
            return next_fn(ctx)

        def pre_rate_limit(ctx: PipelineContext, next_fn):
            if not self.config.get("security.rate_limit.enabled", False):
                return next_fn(ctx)
            user_id = (
                ctx.message.sender.user_id
                if ctx.message.sender
                else "anon"
            )
            if self._check_rate_limit(user_id):
                return next_fn(ctx)
            ctx.abort("Rate limited")
            self.logger.debug(f"Rate limited user: {user_id}")
            return None

        def handler_commands(ctx: PipelineContext, next_fn):
            import re
            # Strip CQ codes (at/reply/image/etc.) so commands like
            # "[CQ:at,qq=123] #help" still match "#help".
            raw_content = ctx.message.content or ""
            content = re.sub(r"\[CQ:[^\]]+\]", "", raw_content).strip()
            if not content:
                return next_fn(ctx)

            plugin, handler, args = (
                self.plugin_manager.find_command_handler(content)
            )
            if handler:
                self.logger.info(
                    f"Command matched: '{content}' -> "
                    f"[{plugin.name}] {handler.__name__}"
                )
                # Check permission
                perm = self._get_handler_permission(plugin, handler)
                if perm == "admin" and not self._is_admin(ctx.message):
                    self.logger.warning(
                        f"Blocked unauthorized command: {content}"
                    )
                    ctx.reply("Permission denied. Admin only.")
                    return None
                try:
                    result = handler(ctx, args)
                    if result:
                        ctx.reply(str(result))
                        self.logger.info(
                            f"Command reply: {str(result)[:100]}"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Command handler [{plugin.name}] error: {e}"
                    )
                    ctx.reply(f"Plugin error: {e}")
                return None

            plugin, handler, match = (
                self.plugin_manager.find_regex_handler(content)
            )
            if handler:
                try:
                    result = handler(ctx, match)
                    if result:
                        ctx.reply(str(result))
                except Exception as e:
                    self.logger.error(
                        f"Regex handler [{plugin.name}] error: {e}"
                    )
                return None

            plugin, handler = (
                self.plugin_manager.find_keyword_handler(content)
            )
            if handler:
                try:
                    result = handler(ctx)
                    if result:
                        ctx.reply(str(result))
                except Exception as e:
                    self.logger.error(
                        f"Keyword handler [{plugin.name}] error: {e}"
                    )
                return None

            return next_fn(ctx)

        def post_repeat(ctx: PipelineContext, next_fn):
            repeat_plugin = self.plugin_manager.get("repeat")
            if repeat_plugin and repeat_plugin.enabled:
                result = repeat_plugin.handle_message(ctx)
                if result:
                    ctx.reply(result)
            return next_fn(ctx)

        pipeline.pre(pre_blacklist)
        pipeline.pre(pre_rate_limit)
        pipeline.handler(handler_commands)
        pipeline.post(post_repeat)

    def handle_message(self, message: Message):
        sender_name = (
            message.sender.nickname if message.sender else "?"
        )
        sender_id = (
            message.sender.user_id if message.sender else "?"
        )
        scope = (
            f"group:{message.group_id}"
            if message.is_group()
            else "private"
        )
        self.logger.info(
            f"<{message.adapter}> [{scope}] "
            f"{sender_name}({sender_id}): {message.content[:200]}"
        )

        blacklist = self.storage.get("blacklist_users", [])
        if message.sender and message.sender.user_id in blacklist:
            self.logger.debug(
                f"Blocked blacklisted user: {sender_id}"
            )
            return

        try:
            response = self.pipeline.process(message)
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            return

        if response:
            self.logger.info(
                f"Reply [{scope}] -> {sender_name}: "
                f"{response[:200]}"
            )
            if message.is_group() and message.group_id:
                self.adapter_manager.send_message(
                    message.adapter,
                    message.group_id,
                    response,
                    "group",
                )
            elif message.sender:
                self.adapter_manager.send_message(
                    message.adapter,
                    message.sender.user_id,
                    response,
                    "private",
                )

        self.event_bus.publish(
            "message.processed",
            {"message": message, "response": response},
        )

    def send(self, message: Message, text: str):
        if message.is_group() and message.group_id:
            return self.adapter_manager.send_message(
                message.adapter, message.group_id, text, "group"
            )
        elif message.sender:
            return self.adapter_manager.send_message(
                message.adapter,
                message.sender.user_id,
                text,
                "private",
            )
        return False

    @staticmethod
    def _get_handler_permission(plugin, handler) -> str:
        """Extract permission level from a command handler."""
        for cmd, aliases, perm, h in plugin.get_all_command_handlers():
            if h is handler:
                return perm
        return "user"

    def _is_admin(self, message: Message) -> bool:
        """Check if the sender is a super admin."""
        if not message.sender:
            return False
        admins = self.config.get("security.super_admins", [])
        return message.sender.user_id in admins

    def _check_rate_limit(self, user_id: str) -> bool:
        """Token-bucket style rate limit check. Returns True if allowed."""
        rate = self.config.get(
            "security.rate_limit.messages_per_second", 5
        )
        burst = self.config.get("security.rate_limit.burst", 10)
        now = time.time()
        with self._rate_lock:
            bucket = self._rate_buckets.setdefault(
                user_id, {"tokens": float(burst), "last": now}
            )
            elapsed = now - bucket["last"]
            bucket["last"] = now
            bucket["tokens"] = min(
                burst, bucket["tokens"] + elapsed * rate
            )
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True
            return False

    def format_status(self, public: bool = True) -> str:
        uptime_seconds = int(time.time() - self._start_time)
        d = uptime_seconds // 86400
        h = (uptime_seconds % 86400) // 3600
        m = (uptime_seconds % 3600) // 60
        s = uptime_seconds % 60

        lines = ["Qtine: [Running]"]

        onebot = self.adapter_manager.get("onebot_v11")
        if onebot and onebot.bot_qq:
            lines.append(f"QQ: {onebot.bot_qq}")
        else:
            lines.append("QQ: Not bound")

        lines.append(f"Version: {__import__('qtine').__version__}")
        lines.append(f"Device: {platform.system()}")
        lines.append(f"Uptime: {d}d {h}h {m}m {s}s")

        if not public:
            lines.append(
                f"Plugins: {self.plugin_manager.count} "
                f"({self.plugin_manager.enabled_count} enabled)"
            )
            for a in self.adapter_manager.get_all_info():
                lines.append(
                    f"Adapter {a.name}: [{a.status.value}] "
                    f"msgs:{a.message_count} errs:{a.error_count}"
                )
        return "\n".join(lines)

    def load_builtin_plugins(self):
        from qtine.plugins.builtin.help import HelpPlugin
        from qtine.plugins.builtin.echo import EchoPlugin
        from qtine.plugins.builtin.admin import AdminPlugin
        from qtine.plugins.builtin.welcome import WelcomePlugin
        from qtine.plugins.builtin.repeat import RepeatPlugin
        from qtine.plugins.builtin.ban import BanPlugin

        builtins = [
            HelpPlugin(bot=self),
            EchoPlugin(bot=self),
            AdminPlugin(bot=self),
            WelcomePlugin(bot=self),
            RepeatPlugin(bot=self),
            BanPlugin(bot=self),
        ]
        for p in builtins:
            self.plugin_manager.load_builtin(p)
        self.logger.info(f"Loaded {len(builtins)} builtin plugins")

    def start(self):
        self._running = True
        self.event_bus.publish("bot.started", {"time": time.time()})
        self.logger.info("Qtine bot started")

    def shutdown(self):
        self._running = False
        self.event_bus.publish("bot.stopped", {"time": time.time()})
        self.adapter_manager.stop_all()
        self.storage.close()
        self.logger.info("Qtine bot shutdown complete")

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time


class QtineApp:
    """Main application — Flask + SocketIO + Bot."""

    def __init__(self, config_path: str = "config.yml"):
        self.config = Config(config_path)

        log_config = self.config.data.get("logging", {})
        self.logger = QtineLogger(
            level=log_config.get("level", "INFO"),
            log_file=log_config.get("file", "./data/logs/qtine.log"),
            max_size_mb=log_config.get("max_size_mb", 10),
            backup_count=log_config.get("backup_count", 5),
        )

        self.logger.info("Initializing Qtine...")
        self.logger.info(f"Qtine v{__import__('qtine').__version__}")

        web_dir = os.path.join(
            os.path.dirname(__file__), "..", "web", "static"
        )
        web_dir = os.path.abspath(web_dir)
        self.flask_app = Flask(
            __name__,
            static_folder=web_dir,
            static_url_path="/static",
        )
        self._web_dir = web_dir
        self.flask_app.config["SECRET_KEY"] = self.config.get(
            "webui.session_secret", "qtine-secret-key-change-me"
        )
        self.flask_app.config["MAX_CONTENT_LENGTH"] = (
            MAX_UPLOAD_MB * 1024 * 1024
        )

        self._init_token()
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        self.socketio = SocketIO(
            self.flask_app,
            async_mode="threading",
            cors_allowed_origins="*",
            logger=False,
            engineio_logger=False,
        )

        self.bot = QtineBot(self.config)
        self._adapter_ws_paths: Dict[str, str] = (
            {}
        )  # adapter_name -> ws_path

        self._setup_routes()
        self._setup_adapters()

        self.bot.load_builtin_plugins()
        self.bot.plugin_manager.load_from_dir()

    # ── auth ─────────────────────────────────────────────────────────

    def _init_token(self):
        token_file = os.path.join("data", "token.txt")
        if os.path.isfile(token_file):
            with open(token_file, "r") as f:
                self._admin_token = f.read().strip()
        else:
            self._admin_token = secrets.token_hex(16)
            os.makedirs("data", exist_ok=True)
            with open(token_file, "w") as f:
                f.write(self._admin_token)
        self.logger.info(
            f"Admin token: {self._admin_token} "
            f"(also available at /api/token and in WebUI Settings)"
        )

    def _check_auth(self):
        token = request.cookies.get("qtine_token", "")
        if token != self._admin_token:
            return redirect("/webui/login")
        return None

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _allowed_file(filename: str) -> bool:
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    def _save_upload(self, file_storage) -> str:
        """Save uploaded file to data/uploads/ and return path."""
        filename = secure_filename(file_storage.filename)
        dest = os.path.join(UPLOAD_DIR, filename)
        file_storage.save(dest)
        return dest

    # ── routes ───────────────────────────────────────────────────────

    def _setup_routes(self):
        app = self.flask_app
        bot = self.bot
        web_dir = self._web_dir

        def serve_page(filename):
            return send_from_directory(web_dir, filename)

        # ── WebUI pages ────────────────────────────────────────────

        @app.route("/")
        def index():
            return redirect("/webui/login")

        @app.route("/webui")
        def webui_root():
            return redirect("/webui/login")

        @app.route("/webui/login")
        def serve_login():
            token = request.cookies.get("qtine_token", "")
            if token == self._admin_token:
                return redirect("/webui/dashboard")
            return serve_page("login.html")

        @app.route("/webui/dashboard")
        def serve_dashboard():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("dashboard.html")

        @app.route("/webui/plugins")
        def serve_plugins():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("plugins.html")

        @app.route("/webui/adapters")
        def serve_adapters():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("adapters.html")

        @app.route("/webui/logs")
        def serve_logs():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("logs.html")

        @app.route("/webui/settings")
        def serve_settings():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("settings.html")

        @app.route("/webui/market")
        def serve_market():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("market.html")

        @app.route("/webui/about")
        def serve_about():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("about.html")

        # ── health ─────────────────────────────────────────────────

        @app.route("/health")
        def health():
            return jsonify({
                "status": "ok" if bot._running else "stopped",
                "uptime": bot.uptime,
                "version": __import__("qtine").__version__,
            })

        # ── auth ───────────────────────────────────────────────────

        @app.route("/api/verify-token", methods=["POST"])
        def api_verify_token():
            data = request.get_json(silent=True) or {}
            valid = data.get("token", "") == self._admin_token
            resp = jsonify({"valid": valid})
            if valid:
                resp.set_cookie(
                    "qtine_token",
                    self._admin_token,
                    max_age=30 * 24 * 3600,
                    httponly=True,
                    samesite="Lax",
                )
            return resp

        @app.route("/api/token")
        def api_token():
            """Return the admin token (only if authenticated)."""
            token = request.cookies.get("qtine_token", "")
            if token != self._admin_token:
                return jsonify({"error": "Unauthorized"}), 401
            return jsonify({"token": self._admin_token})

        # ── status ─────────────────────────────────────────────────

        @app.route("/api/status")
        def api_status():
            return jsonify({
                "status": "running" if bot._running else "stopped",
                "uptime": bot.uptime,
                "version": __import__("qtine").__version__,
                "plugins": bot.plugin_manager.count,
                "plugins_enabled": bot.plugin_manager.enabled_count,
                "adapters": [
                    {
                        "name": adapter.info.name,
                        "protocol": adapter.info.protocol,
                        "status": adapter.info.status.value,
                        "message_count": adapter.info.message_count,
                        "received_count": adapter.info.received_count,
                        "sent_count": adapter.info.sent_count,
                        "error_count": adapter.info.error_count,
                        "account_id": adapter.info.account_id,
                        "nickname": getattr(
                            adapter, "_bot_info", {}
                        ).get("nickname", ""),
                        "connected_at": adapter.info.connected_at,
                    }
                    for adapter in bot.adapter_manager.get_all()
                ],
            })

        # ── plugins CRUD ───────────────────────────────────────────

        @app.route("/api/plugins")
        def api_plugins():
            info_list = bot.plugin_manager.get_all_info()
            return jsonify([
                {
                    "name": p.name,
                    "package": p.package,
                    "version": p.version,
                    "enabled": p.enabled,
                    "plugin_type": (
                        p.plugin_type.value
                        if hasattr(p.plugin_type, "value")
                        else str(p.plugin_type)
                    ),
                    "description": p.description,
                    "author": p.author,
                    "hooks": p.hooks,
                    "requires": p.requires,
                    "icon": p.icon,
                }
                for p in info_list
            ])

        @app.route("/api/plugins/<name>/enable", methods=["POST"])
        def api_plugin_enable(name):
            ok = bot.plugin_manager.enable(name)
            return jsonify({"success": ok, "name": name})

        @app.route("/api/plugins/<name>/disable", methods=["POST"])
        def api_plugin_disable(name):
            ok = bot.plugin_manager.disable(name)
            return jsonify({"success": ok, "name": name})

        @app.route("/api/plugins/<name>/reload", methods=["POST"])
        def api_plugin_reload(name):
            ok = bot.plugin_manager.reload(name)
            return jsonify({"success": ok, "name": name})

        # ── plugin upload ──────────────────────────────────────────

        @app.route("/api/plugins/upload", methods=["POST"])
        def api_plugin_upload():
            if "file" not in request.files:
                return jsonify(
                    {"success": False, "error": "No file provided"}
                ), 400
            f = request.files["file"]
            if f.filename == "":
                return jsonify(
                    {"success": False, "error": "Empty filename"}
                ), 400
            if not self._allowed_file(f.filename):
                return jsonify(
                    {
                        "success": False,
                        "error": f"Only .zip allowed",
                    }
                ), 400

            dest = self._save_upload(f)
            result = bot.plugin_manager.import_from_zip(dest)
            if result:
                return jsonify(
                    {"success": True, "name": result, "uploaded": dest}
                )
            return jsonify(
                {"success": False, "error": "Plugin import failed"}
            ), 400

        # ── marketplace ────────────────────────────────────────────

        @app.route("/api/market/plugins")
        def api_market_plugins():
            """Return plugin market listings.

            Tries to fetch from the configured ``plugins.marketplace_url``
            first; falls back to the built-in demo list when the source
            is empty or unreachable so the WebUI always renders a list.
            Each entry is annotated with ``installed`` based on the
            currently loaded plugins.
            """
            installed_names = {
                p.name for p in bot.plugin_manager.get_all_info()
            }
            source_url = (
                self.config.get("plugins.marketplace_url", "") or ""
            ).strip()
            mirrors = (
                self.config.get("plugins.marketplace_mirrors", []) or []
            )
            using_fallback = True
            plugins: list = []

            urls_to_try = [source_url] + list(mirrors)
            for url in urls_to_try:
                if not url:
                    continue
                try:
                    import urllib.request
                    import json as _json

                    req = urllib.request.Request(
                        url, headers={"Accept": "application/json"}
                    )
                    with urllib.request.urlopen(
                        req, timeout=5
                    ) as resp:
                        raw = resp.read().decode("utf-8", "ignore")
                    data = _json.loads(raw)
                    # Support both {plugins: [...]} and bare list.
                    if isinstance(data, list):
                        plugins = data
                    elif isinstance(data, dict):
                        plugins = data.get("plugins") or data.get(
                            "data"
                        ) or []
                    else:
                        plugins = []
                    plugins = plugins if isinstance(plugins, list) else []
                    using_fallback = False
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Market source {url} unreachable: {e}"
                    )
                    continue

            if using_fallback:
                # Deep copy the built-in demo list so callers can't mutate
                # the module-level constant via the response.
                plugins = [dict(p) for p in BUILTIN_MARKET_PLUGINS]

            # Annotate installed state.
            for p in plugins:
                if isinstance(p, dict):
                    p["installed"] = p.get("name") in installed_names

            return jsonify({
                "source": source_url,
                "using_fallback": using_fallback,
                "count": len(plugins),
                "plugins": plugins,
            })

        @app.route("/api/market/source")
        def api_market_source():
            """Return the configured marketplace source URLs."""
            return jsonify({
                "url": self.config.get("plugins.marketplace_url", "") or "",
                "mirrors": (
                    self.config.get("plugins.marketplace_mirrors", []) or []
                ),
            })

        @app.route("/api/market/source", methods=["POST"])
        def api_market_source_set():
            """Update the marketplace source URL and persist to config."""
            data = request.get_json(silent=True) or {}
            url = (data.get("url") or "").strip()
            if not url:
                return jsonify(
                    {"success": False, "error": "url is required"}
                ), 400
            self.config.set("plugins.marketplace_url", url)
            try:
                self.config.save()
            except Exception as e:
                return jsonify(
                    {"success": False, "error": f"Save failed: {e}"}
                ), 500
            self.logger.info(f"Marketplace source updated: {url}")
            return jsonify({"success": True, "url": url})

        @app.route("/api/market/install/<name>", methods=["POST"])
        def api_market_install(name):
            """Install a plugin from the marketplace source.

            Resolves the plugin entry from the configured source (or the
            built-in fallback list), downloads its ``download_url`` if
            present, then hands the archive to PluginManager.
            """
            # Resolve plugin entry
            source_url = (
                self.config.get("plugins.marketplace_url", "") or ""
            ).strip()
            entry = None
            try:
                fetch_url = (
                    source_url.rstrip("/") + "/plugins/" + name
                    if source_url
                    else ""
                )
                if fetch_url:
                    import urllib.request
                    import json as _json

                    with urllib.request.urlopen(
                        fetch_url, timeout=5
                    ) as resp:
                        entry = _json.loads(
                            resp.read().decode("utf-8", "ignore")
                        )
            except Exception:
                entry = None

            if not entry:
                for p in BUILTIN_MARKET_PLUGINS:
                    if p["name"] == name:
                        entry = p
                        break

            if not entry:
                return jsonify(
                    {"success": False, "error": "Plugin not found"}
                ), 404

            download_url = entry.get("download_url") or entry.get("url")
            if not download_url:
                return jsonify({
                    "success": False,
                    "error": "Plugin entry has no download_url; configure "
                    "a real marketplace source to enable install.",
                    "name": name,
                }), 400

            # Download to data/uploads/<name>.zip
            try:
                import urllib.request

                os.makedirs(UPLOAD_DIR, exist_ok=True)
                dest = os.path.join(UPLOAD_DIR, f"{name}.zip")
                with urllib.request.urlopen(
                    download_url, timeout=30
                ) as r, open(dest, "wb") as out:
                    out.write(r.read())
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"Download failed: {e}",
                }), 500

            result = bot.plugin_manager.import_from_zip(dest)
            if result:
                return jsonify({"success": True, "name": result})
            return jsonify(
                {"success": False, "error": "Plugin import failed"}
            ), 400

        # ── adapters CRUD ──────────────────────────────────────────

        @app.route("/api/adapters")
        def api_adapters():
            adapters_info = []
            for adapter in bot.adapter_manager.get_all():
                info = adapter.info
                bot_info = getattr(adapter, "_bot_info", {})
                adapters_info.append({
                    "name": info.name,
                    "protocol": info.protocol,
                    "status": info.status.value,
                    "message_count": info.message_count,
                    "received_count": info.received_count,
                    "sent_count": info.sent_count,
                    "error_count": info.error_count,
                    "account_id": info.account_id,
                    "nickname": bot_info.get("nickname", ""),
                    "connected_at": info.connected_at,
                })
            return jsonify(adapters_info)

        @app.route("/api/adapters/<name>/reconnect", methods=["POST"])
        def api_adapter_reconnect(name):
            adapter = bot.adapter_manager.get(name)
            if adapter:
                adapter.stop()
                adapter.start()
                return jsonify({"success": True, "name": name})
            return jsonify(
                {"success": False, "error": "Adapter not found"}
            ), 404

        # ── adapter upload ─────────────────────────────────────────

        @app.route("/api/adapters/upload", methods=["POST"])
        def api_adapter_upload():
            if "file" not in request.files:
                return jsonify(
                    {"success": False, "error": "No file provided"}
                ), 400
            f = request.files["file"]
            if f.filename == "":
                return jsonify(
                    {"success": False, "error": "Empty filename"}
                ), 400
            if not self._allowed_file(f.filename):
                return jsonify(
                    {"success": False, "error": "Only .zip allowed"}
                ), 400

            dest = self._save_upload(f)
            result = bot.adapter_manager.import_from_zip(dest)
            if result:
                # Auto-register WS endpoint if the adapter defines one
                self._register_adapter_ws(result)
                return jsonify(
                    {"success": True, "name": result, "uploaded": dest}
                )
            return jsonify(
                {"success": False, "error": "Adapter import failed"}
            ), 400

        # ── OneBot V11 HTTP API ────────────────────────────────────

        @app.route("/onebot/v11/<action>", methods=["GET", "POST"])
        def onebot_http_action(action):
            """OneBot V11 HTTP API endpoint.

            GET  /onebot/v11/get_login_info
            POST /onebot/v11/send_private_msg
            Body: {"user_id": 123, "message": "hello"}
            """
            adapter = bot.adapter_manager.get("onebot_v11")
            if adapter is None or not adapter.running:
                return jsonify(
                    {
                        "status": "failed",
                        "retcode": -1,
                        "msg": "Adapter offline",
                        "data": {},
                    }
                ), 503

            # Check Authorization
            auth = request.headers.get("Authorization", "")
            if adapter.access_token:
                expected = f"Bearer {adapter.access_token}"
                if auth != expected:
                    return jsonify(
                        {
                            "status": "failed",
                            "retcode": 1403,
                            "msg": "Unauthorized",
                            "data": {},
                        }
                    ), 403

            # GET: merge query params; POST: use JSON body
            if request.method == "GET":
                params = dict(request.args)
            else:
                params = request.get_json(silent=True) or {}

            result = adapter.handle_http_action(action, params)
            return jsonify(result)

        @app.route("/onebot/v11", methods=["GET"])
        def onebot_http_root():
            """Discovery endpoint."""
            return jsonify({
                "version": "v11",
                "status": "ok",
                "actions": [
                    "send_private_msg",
                    "send_group_msg",
                    "get_login_info",
                    "get_friend_list",
                    "get_group_list",
                    "get_group_member_list",
                    "get_stranger_info",
                ],
            })

        # ── messages ───────────────────────────────────────────────

        @app.route("/api/messages")
        def api_messages():
            return jsonify({"messages": [], "count": 0})

        @app.route("/api/logs")
        def api_logs():
            """Read recent log entries from in-memory buffer."""
            level = request.args.get("level", "ALL")
            lines_arg = request.args.get("lines", 200, type=int)
            lines = max(1, min(lines_arg, 500))
            entries = self.logger.get_recent_logs(
                level=level, limit=lines
            )
            return jsonify({
                "entries": entries,
                "count": len(entries),
            })

        @app.route("/api/logs/clear", methods=["POST"])
        def api_logs_clear():
            self.logger.clear_logs()
            return jsonify({"success": True})

        # ── WebUI WebSocket ────────────────────────────────────────

        @self.socketio.on("connect", namespace="/ws/webui")
        def webui_connect():
            self.logger.info("WebUI client connected")

        @self.socketio.on("disconnect", namespace="/ws/webui")
        def webui_disconnect():
            self.logger.info("WebUI client disconnected")

        # ── shutdown / restart ─────────────────────────────────────

        @app.route("/api/shutdown", methods=["POST"])
        def api_shutdown():
            self.logger.warning("Shutdown requested via WebUI")
            threading.Thread(
                target=lambda: (self.shutdown(), os._exit(0)),
                daemon=True,
            ).start()
            return jsonify({"success": True})

        @app.route("/api/restart", methods=["POST"])
        def api_restart():
            self.logger.warning("Restart requested via WebUI")
            import subprocess
            threading.Thread(
                target=lambda: (
                    self.shutdown(),
                    subprocess.Popen(
                        [sys.executable, "main.py"],
                        cwd=PROJECT_ROOT,
                    ),
                    os._exit(0),
                ),
                daemon=True,
            ).start()
            return jsonify({"success": True})

    # ── adapter setup ────────────────────────────────────────────────

    def _setup_adapters(self):
        # OneBot V11 (built-in)
        onebot_config = self.config.get("adapters.onebot_v11", {})
        if onebot_config.get("enabled", False):
            adapter = self.bot.adapter_manager.create_onebot_adapter(
                onebot_config, bot=self.bot
            )
            adapter.on_message(self.bot.handle_message)
            adapter.on_event(
                lambda event_type, data: self.bot.event_bus.publish(
                    f"adapter.onebot_v11.{event_type}", data
                )
            )
            ws_path = str(onebot_config.get("ws_path", "/onebot/v11"))
            if not ws_path.startswith("/"):
                ws_path = f"/{ws_path}"
            self._register_adapter_ws_endpoint(
                "onebot_v11", ws_path, adapter
            )
            adapter.start()
            self.logger.info(
                f"OneBot v11 adapter: WS={ws_path}"
            )

    def _register_adapter_ws(self, adapter_name: str) -> None:
        """Auto-register WebSocket endpoint for a newly imported adapter."""
        adapter = self.bot.adapter_manager.get(adapter_name)
        if adapter is None:
            return

        # Check manifest for ws_endpoint
        sources = self.bot.adapter_manager._adapter_sources
        source = sources.get(adapter_name, {})
        manifest = {}

        if source.get("type") == "zip" or source.get("type") == "directory":
            extract_dir = source.get("extract_to", "")
            json_path = os.path.join(extract_dir, "adapter.json")
            if os.path.isfile(json_path):
                import json as _json

                with open(json_path, "r", encoding="utf-8") as f:
                    manifest = _json.load(f)

        ws_endpoint = manifest.get("ws_endpoint", "")
        if ws_endpoint:
            self._register_adapter_ws_endpoint(
                adapter_name, ws_endpoint, adapter
            )
            self.logger.info(
                f"Adapter '{adapter_name}' WS endpoint auto-registered: "
                f"{ws_endpoint}"
            )

    def _register_adapter_ws_endpoint(
        self, name: str, ws_path: str, adapter
    ) -> None:
        """Register a WebSocket endpoint for an adapter.

        Uses a WSGI middleware to intercept WebSocket upgrade requests
        before they reach Flask — avoids Werkzeug 3.1+ native websocket
        route issues in threading mode.
        """
        if not ws_path.startswith("/"):
            ws_path = f"/{ws_path}"

        self._adapter_ws_paths[name] = ws_path

        # Build a WSGI middleware wrapper for this adapter
        original_wsgi = self.flask_app.wsgi_app
        adapter_ref = adapter
        ws_path_ref = ws_path
        name_ref = name
        logger_ref = self.logger

        def ws_middleware(environ, start_response):
            path = environ.get("PATH_INFO", "")
            upgrade = environ.get("HTTP_UPGRADE", "").lower()
            if path == ws_path_ref and "websocket" in upgrade:
                # WebSocket upgrade — handle directly
                logger_ref.info(
                    f"[{name_ref}] WS upgrade from "
                    f"{environ.get('REMOTE_ADDR', '?')}"
                )
                try:
                    ws = Server.accept(
                        environ,
                        ping_interval=30,
                        max_message_size=16 * 1024 * 1024,
                    )
                except Exception as e:
                    logger_ref.error(
                        f"[{name_ref}] WS accept failed: {e}"
                    )
                    start_response(
                        "400 Bad Request", [("Content-Type", "text/plain")]
                    )
                    return [b"WebSocket upgrade failed"]
                # serve() blocks until client disconnects
                try:
                    adapter_ref.serve(ws, environ)
                except Exception as e:
                    logger_ref.error(
                        f"[{name_ref}] WS serve error: {e}"
                    )
                return []
            return original_wsgi(environ, start_response)

        self.flask_app.wsgi_app = ws_middleware

    # ── run / shutdown ───────────────────────────────────────────────

    def run(self):
        host = self.config.get("server.host", "0.0.0.0")
        port = self.config.get("server.port", 4990)
        debug = self.config.get("server.debug", False)

        self.bot.start()

        self.logger.info(f"Qtine starting on http://{host}:{port}")
        self.logger.info(f"WebUI: http://{host}:{port}/webui")
        for name, path in self._adapter_ws_paths.items():
            self.logger.info(
                f"Adapter [{name}] WS: ws://{host}:{port}{path}"
            )

        self.socketio.run(
            self.flask_app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True,
        )

    def shutdown(self):
        self.bot.shutdown()
        self.logger.info("Qtine shutdown complete")
