# -*- coding: utf-8 -*-
"""Qtine Core Application — Flask + WebSocket server."""

import hmac
import os
import platform
import secrets
import sys
import time
import threading
import json
import shutil
import zipfile
from typing import Optional, Dict
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_from_directory, redirect, abort, Response
from flask_socketio import SocketIO
from simple_websocket import Server
from werkzeug.middleware.proxy_fix import ProxyFix
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
from qtine.core.scheduler import TaskScheduler
from qtine.core.updater import (
    find_update,
    find_release_by_tag,
    fetch_releases,
    download_release,
    backup_current,
    install_release,
    rollback_to,
    list_backups,
    get_current_version,
    compare_versions,
    DEFAULT_MIRRORS,
)
from qtine.utils.models import Message, Sender, AdapterStatus
from qtine.utils.logger import QtineLogger, get_logger
from qtine.utils.network import safe_urlopen, validate_public_http_url
from qtine.storage.backend import Storage


UPLOAD_DIR = os.path.join("data", "uploads")
MAX_UPLOAD_MB = 50
ALLOWED_EXTENSIONS = {"zip"}

# 主题相关路径
THEMES_DIR = os.path.join("data", "themes")
BUILTIN_THEMES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "web", "static", "builtin-themes.json",
)
DEFAULT_THEME = "material-purple"

# 默认 GitHub 加速镜像（10 个）
DEFAULT_GITHUB_MIRRORS = [
    {"name": "GitHub 官方", "url": "https://github.com"},
    {"name": "ghproxy", "url": "https://ghproxy.com"},
    {"name": "99988866", "url": "https://gh.api.99988866.xyz"},
    {"name": "mirror.ghproxy", "url": "https://mirror.ghproxy.com"},
    {"name": "gh-proxy", "url": "https://gh-proxy.com"},
    {"name": "xcxgw", "url": "https://gh.xcxgw.com"},
    {"name": "ghps", "url": "https://ghps.cc"},
    {"name": "d-ai workers", "url": "https://gh.d-ai.workers.dev"},
    {"name": "llkk", "url": "https://gh.llkk.cc"},
    {"name": "gitmirror", "url": "https://hub.gitmirror.com"},
]

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
        self.scheduler = TaskScheduler()
        self.scheduler.set_bot(self)
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

        # 记录消息历史
        try:
            self.storage.add_message(
                message_id=message.message_id or "",
                group_id=message.group_id if message.is_group() else None,
                user_id=sender_id,
                nickname=sender_name,
                content=message.content,
                message_type=message.message_type or "text",
                adapter=message.adapter or "",
            )
        except Exception as e:
            self.logger.warning(f"Failed to log message history: {e}")

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

        # Trigger webhooks
        try:
            self._trigger_webhooks("message.received", {
                "message_id": message.message_id,
                "group_id": message.group_id,
                "user_id": sender_id,
                "nickname": sender_name,
                "content": message.content,
                "adapter": message.adapter,
                "timestamp": time.time(),
            })
        except Exception as e:
            self.logger.warning(f"Webhook trigger error: {e}")

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

    def _trigger_webhooks(self, event: str, payload: dict):
        """Send webhook requests for matching webhooks."""
        webhooks = self.storage.get("webhooks", [])
        if not webhooks:
            return
        import urllib.request
        import json as _json

        for wh in webhooks:
            if not wh.get("enabled", True):
                continue
            if wh.get("event") != event:
                continue
            url = wh.get("url", "")
            if not url:
                continue
            try:
                url = self._validate_outbound_url(url)
                data = _json.dumps({
                    "event": event,
                    "timestamp": time.time(),
                    "data": payload,
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Qtine-Bot",
                    },
                    method="POST",
                )
                # Fire and forget with timeout
                def do_req(r):
                    try:
                        with safe_urlopen(r, timeout=5):
                            pass
                    except Exception as e:
                        self.logger.warning(
                            f"Webhook '{wh.get('name', url)}' failed: {e}"
                        )
                threading.Thread(target=do_req, args=(req,), daemon=True).start()
            except Exception as e:
                self.logger.warning(f"Webhook prepare failed: {e}")

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
        from qtine.plugins.builtin.repeat import RepeatPlugin
        from qtine.plugins.builtin.ban import BanPlugin

        builtins = [
            HelpPlugin(bot=self),
            EchoPlugin(bot=self),
            AdminPlugin(bot=self),
            RepeatPlugin(bot=self),
            BanPlugin(bot=self),
        ]
        for p in builtins:
            self.plugin_manager.load_builtin(p)
        self.logger.info(f"Loaded {len(builtins)} builtin plugins")

    def start(self):
        self._running = True
        self.scheduler.start()
        self.event_bus.publish("bot.started", {"time": time.time()})
        self.logger.info("Qtine bot started")

    def shutdown(self):
        self._running = False
        self.scheduler.stop()
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
            static_folder=os.path.join(web_dir, "img"),
            static_url_path="/static/img",
        )
        self._web_dir = web_dir
        session_secret = os.environ.get("QTINE_SESSION_SECRET")
        if not session_secret:
            session_secret = self.config.get("webui.session_secret", "")
        self.flask_app.config.update(
            SECRET_KEY=session_secret or secrets.token_hex(32),
            MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Strict",
        )

        proxy_hops = max(
            0, int(self.config.get("server.trusted_proxy_hops", 0))
        )
        if proxy_hops:
            self.flask_app.wsgi_app = ProxyFix(
                self.flask_app.wsgi_app,
                x_for=proxy_hops,
                x_proto=proxy_hops,
                x_host=proxy_hops,
            )

        self._login_buckets: Dict[str, list] = {}
        self._login_lock = threading.Lock()
        self._validate_production_config()
        self._init_token()
        os.makedirs(UPLOAD_DIR, mode=0o700, exist_ok=True)
        os.makedirs(THEMES_DIR, mode=0o700, exist_ok=True)

        allowed_origins = self.config.get(
            "webui.allowed_origins", []
        ) or None
        self.socketio = SocketIO(
            self.flask_app,
            async_mode="threading",
            cors_allowed_origins=allowed_origins,
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

    def _validate_production_config(self) -> None:
        if not self.config.get("security.production_mode", False):
            return
        errors = []
        if self.config.get("server.debug", False):
            errors.append("server.debug must be false")
        onebot = self.config.get("adapters.onebot_v11", {}) or {}
        onebot_token = (
            os.environ.get("QTINE_ONEBOT_ACCESS_TOKEN", "").strip()
            or str(onebot.get("access_token", "")).strip()
        )
        if onebot.get("enabled", False) and len(onebot_token) < 16:
            errors.append("OneBot access token must be at least 16 characters")
        admin_token = os.environ.get("QTINE_ADMIN_TOKEN", "").strip()
        if os.environ.get("QTINE_MANAGED_SERVER") == "1" and len(admin_token) < 32:
            errors.append("QTINE_ADMIN_TOKEN must be at least 32 characters")
        session_secret = os.environ.get("QTINE_SESSION_SECRET", "").strip()
        if os.environ.get("QTINE_MANAGED_SERVER") == "1" and len(session_secret) < 32:
            errors.append("QTINE_SESSION_SECRET must be at least 32 characters")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

    def _init_token(self):
        token_file = os.path.join("data", "token.txt")
        env_token = os.environ.get("QTINE_ADMIN_TOKEN", "").strip()
        if env_token:
            if len(env_token) < 32:
                raise RuntimeError("QTINE_ADMIN_TOKEN must be at least 32 characters")
            self._admin_token = env_token
            self.logger.info("Admin token loaded from environment")
            return

        os.makedirs("data", mode=0o700, exist_ok=True)
        if os.path.isfile(token_file):
            with open(token_file, "r", encoding="utf-8") as f:
                self._admin_token = f.read().strip()
            if len(self._admin_token) < 32:
                raise RuntimeError("Admin token file is invalid")
        else:
            self._admin_token = secrets.token_hex(32)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(token_file, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(self._admin_token)
        try:
            os.chmod(token_file, 0o600)
        except OSError:
            pass
        self.logger.info(f"Admin token loaded from {token_file}")

    def _provided_admin_token(self) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return request.cookies.get("qtine_token", "")

    def _is_authenticated(self) -> bool:
        token = self._provided_admin_token()
        return bool(token) and hmac.compare_digest(token, self._admin_token)

    def _check_auth(self):
        if not self._is_authenticated():
            return redirect("/webui/login")
        return None

    def _login_allowed(self, client: str) -> bool:
        now = time.monotonic()
        limit = max(1, int(self.config.get("security.login_attempts", 5)))
        window = max(10, int(self.config.get("security.login_window_seconds", 300)))
        with self._login_lock:
            attempts = [
                stamp for stamp in self._login_buckets.get(client, [])
                if now - stamp < window
            ]
            self._login_buckets[client] = attempts
            return len(attempts) < limit

    def _record_login_failure(self, client: str) -> None:
        with self._login_lock:
            self._login_buckets.setdefault(client, []).append(time.monotonic())

    @staticmethod
    def _request_origin_matches() -> bool:
        origin = request.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.netloc.lower() == request.host.lower()
        )
    @staticmethod
    def _validate_outbound_url(url: str) -> str:
        return validate_public_http_url(url)


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

        @app.before_request
        def protect_management_api():
            if not request.path.startswith("/api/"):
                return None
            if request.path == "/api/verify-token":
                if not self._request_origin_matches():
                    return jsonify({"error": "Invalid request origin"}), 403
                return None
            if not self._is_authenticated():
                return jsonify({"error": "Unauthorized"}), 401
            if (
                request.method not in {"GET", "HEAD", "OPTIONS"}
                and not self._request_origin_matches()
            ):
                return jsonify({"error": "Invalid request origin"}), 403
            return None

        @app.after_request
        def add_security_headers(response):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=()",
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline' "
                "https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self' ws: wss:; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
            )
            if request.path.startswith(("/api/", "/webui")):
                response.headers["Cache-Control"] = "no-store"
            if request.is_secure:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
            return response

        @app.errorhandler(413)
        def request_too_large(_error):
            return jsonify({"error": "Request body too large"}), 413

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
            if self._is_authenticated():
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

        @app.route("/webui/messages")
        def serve_messages():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("messages.html")

        @app.route("/webui/tasks")
        def serve_tasks():
            auth = self._check_auth()
            if auth:
                return auth
            return serve_page("tasks.html")

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

        # ── backup / restore ──────────────────────────────────────

        @app.route("/api/backup", methods=["GET"])
        def api_backup():
            """导出配置 + 存储数据 + 插件列表为 zip。"""
            import io
            import zipfile
            import yaml as _yaml
            from datetime import datetime

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # config.yml
                try:
                    config_yaml = _yaml.dump(
                        self.config.data,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False,
                    )
                    zf.writestr("config.yml", config_yaml)
                except Exception as e:
                    self.logger.warning(f"backup: config export failed: {e}")

                # storage (as JSON)
                try:
                    all_keys = bot.storage.keys()
                    storage_data = {k: bot.storage.get(k) for k in all_keys}
                    zf.writestr(
                        "storage.json",
                        json.dumps(storage_data, ensure_ascii=False, indent=2),
                    )
                except Exception as e:
                    self.logger.warning(f"backup: storage export failed: {e}")

                # plugin list
                try:
                    plugins = [p.to_dict() for p in bot.plugin_manager.get_all_info()]
                    zf.writestr(
                        "plugins.json",
                        json.dumps(plugins, ensure_ascii=False, indent=2),
                    )
                except Exception as e:
                    self.logger.warning(f"backup: plugin list failed: {e}")

                # metadata
                meta = {
                    "version": "1",
                    "generated_at": datetime.now().isoformat(),
                    "qtine_version": __import__("qtine").__version__,
                }
                zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

            buffer.seek(0)
            filename = f"qtine-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
            return Response(
                buffer.getvalue(),
                mimetype="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @app.route("/api/restore", methods=["POST"])
        def api_restore():
            """从 zip 恢复配置、存储数据。"""
            import zipfile
            import yaml as _yaml

            if "file" not in request.files:
                return jsonify({"success": False, "error": "没有文件"}), 400
            f = request.files["file"]
            if not f.filename.endswith(".zip"):
                return jsonify({"success": False, "error": "只支持 .zip 文件"}), 400

            try:
                dest = self._save_upload(f)
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 400

            try:
                with zipfile.ZipFile(dest, "r") as zf:
                    names = zf.namelist()

                    # 恢复 config.yml
                    if "config.yml" in names:
                        try:
                            data = _yaml.safe_load(zf.read("config.yml").decode("utf-8"))
                            if isinstance(data, dict):
                                self.config.data = data
                                self.config.save()
                                self.logger.info("restore: config restored")
                        except Exception as e:
                            self.logger.warning(f"restore: config failed: {e}")

                    # 恢复 storage
                    if "storage.json" in names:
                        try:
                            data = json.loads(zf.read("storage.json").decode("utf-8"))
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    bot.storage.set(k, v)
                                # 清所有插件配置缓存
                                for p in bot.plugin_manager.get_all():
                                    p._config_cache.clear()
                                self.logger.info(
                                    f"restore: {len(data)} storage keys restored"
                                )
                        except Exception as e:
                            self.logger.warning(f"restore: storage failed: {e}")

                return jsonify({"success": True, "message": "恢复成功，部分设置可能需要重启生效"})
            except Exception as e:
                return jsonify({"success": False, "error": f"恢复失败: {str(e)}"}), 400

        # ── message history ────────────────────────────────────────

        @app.route("/api/messages")
        def api_messages():
            group_id = request.args.get("group_id", type=str)
            if group_id == "":
                group_id = None
            user_id = request.args.get("user_id", type=str) or None
            keyword = request.args.get("keyword", type=str) or None
            limit = min(request.args.get("limit", 50, type=int), 200)
            offset = request.args.get("offset", 0, type=int)
            messages = bot.storage.get_messages(
                group_id=group_id,
                limit=limit,
                offset=offset,
                user_id=user_id,
                keyword=keyword,
            )
            return jsonify({
                "success": True,
                "messages": messages,
                "total": len(messages),
            })

        @app.route("/api/messages/groups")
        def api_message_groups():
            groups = bot.storage.get_message_groups()
            return jsonify({"success": True, "groups": groups})

        @app.route("/api/messages/clear", methods=["POST"])
        def api_messages_clear():
            data = request.get_json(silent=True) or {}
            group_id = data.get("group_id")
            if group_id == "":
                group_id = None
            count = bot.storage.clear_messages(group_id=group_id)
            return jsonify({"success": True, "cleared": count})

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
            client = request.remote_addr or "unknown"
            if not self._login_allowed(client):
                return jsonify({"valid": False, "error": "Too many attempts"}), 429
            data = request.get_json(silent=True) or {}
            supplied = str(data.get("token", ""))
            valid = bool(supplied) and hmac.compare_digest(
                supplied, self._admin_token
            )
            resp = jsonify({"valid": valid})
            if valid:
                with self._login_lock:
                    self._login_buckets.pop(client, None)
                resp.set_cookie(
                    "qtine_token",
                    self._admin_token,
                    max_age=12 * 3600,
                    httponly=True,
                    secure=bool(self.config.get("webui.secure_cookie", False)),
                    samesite="Strict",
                    path="/",
                )
            else:
                self._record_login_failure(client)
            return resp

        @app.route("/api/token")
        def api_token():
            return jsonify({"token": self._admin_token})

        # ── security: super admins ────────────────────────────────

        @app.route("/api/security/admins")
        def api_security_admins():
            admins = self.config.get("security.super_admins", []) or []
            return jsonify({"admins": admins})

        @app.route("/api/security/admins", methods=["POST"])
        def api_security_admins_save():
            data = request.get_json(silent=True) or {}
            admins = data.get("admins", [])
            if not isinstance(admins, list):
                return jsonify({"error": "Invalid admins format"}), 400
            admins = [str(a).strip() for a in admins if str(a).strip()]
            self.config.set("security.super_admins", admins)
            self.config.save()
            return jsonify({"success": True, "admins": admins})

        # ── themes ─────────────────────────────────────────────────

        def _load_builtin_themes() -> list:
            """加载内置主题列表。"""
            try:
                with open(BUILTIN_THEMES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("themes", [])
            except Exception as e:
                self.logger.warning(f"Failed to load builtin themes: {e}")
                return []

        def _load_imported_themes() -> list:
            """加载已导入的主题列表（从 data/themes/ 目录）。"""
            themes = []
            if not os.path.isdir(THEMES_DIR):
                return themes
            for name in os.listdir(THEMES_DIR):
                theme_file = os.path.join(THEMES_DIR, name, "theme.json")
                if not os.path.isfile(theme_file):
                    continue
                try:
                    with open(theme_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["builtin"] = False
                    data["name"] = data.get("name", name)
                    themes.append(data)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load imported theme {name}: {e}"
                    )
            return themes

        def _find_theme(name: str) -> Optional[dict]:
            """查找指定名称的主题（内置 + 已导入）。"""
            for t in _load_builtin_themes():
                if t.get("name") == name:
                    return t
            for t in _load_imported_themes():
                if t.get("name") == name:
                    return t
            return None

        @app.route("/api/themes")
        def api_themes_list():
            """列出所有可用主题。"""
            builtin = _load_builtin_themes()
            imported = _load_imported_themes()
            current = (
                self.config.get("webui.theme", DEFAULT_THEME) or DEFAULT_THEME
            )
            return jsonify({
                "current": current,
                "builtin": builtin,
                "imported": imported,
                "total": len(builtin) + len(imported),
            })

        @app.route("/api/themes/current")
        def api_themes_current():
            """获取当前主题（含变量定义）。"""
            name = (
                self.config.get("webui.theme", DEFAULT_THEME) or DEFAULT_THEME
            )
            theme = _find_theme(name)
            if not theme:
                theme = _find_theme(DEFAULT_THEME)
            if not theme:
                return jsonify({
                    "name": DEFAULT_THEME,
                    "variables": {},
                })
            return jsonify({
                "name": theme.get("name", DEFAULT_THEME),
                "display_name": theme.get("display_name", ""),
                "mode": theme.get("mode", "dark"),
                "variables": theme.get("variables", {}),
            })

        @app.route("/api/themes/current", methods=["POST"])
        def api_themes_set_current():
            """切换当前主题。"""
            token = request.cookies.get("qtine_token", "")
            if token != self._admin_token:
                return jsonify({"error": "Unauthorized"}), 401
            data = request.get_json(silent=True) or {}
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"error": "name is required"}), 400
            theme = _find_theme(name)
            if not theme:
                return jsonify({"error": "Theme not found"}), 404
            self.config.set("webui.theme", name)
            self.config.save()
            self.logger.info(f"Theme switched to: {name}")
            return jsonify({
                "success": True,
                "name": name,
                "mode": theme.get("mode", "dark"),
                "variables": theme.get("variables", {}),
            })

        @app.route("/api/themes/import", methods=["POST"])
        def api_themes_import():
            """导入主题包（.qttheme 或 .zip）。

            主题包格式：zip，包含 theme.json（必需）和 preview.png（可选）。
            """
            token = request.cookies.get("qtine_token", "")
            if token != self._admin_token:
                return jsonify({"error": "Unauthorized"}), 401
            if "file" not in request.files:
                return jsonify({"error": "No file provided"}), 400
            f = request.files["file"]
            if f.filename == "":
                return jsonify({"error": "Empty filename"}), 400
            filename = (f.filename or "").lower()
            if not (filename.endswith(".zip") or filename.endswith(".qttheme")):
                return jsonify({"error": "Only .zip or .qttheme allowed"}), 400

            # 保存到临时文件
            tmp_dir = os.path.join(THEMES_DIR, "_tmp_import")
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_zip = os.path.join(tmp_dir, "theme.zip")
            f.save(tmp_zip)

            try:
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    names = zf.namelist()
                    # 查找 theme.json（可能在根目录或子目录）
                    theme_entry = next(
                        (n for n in names
                         if n == "theme.json" or n.endswith("/theme.json")),
                        None,
                    )
                    if not theme_entry:
                        return jsonify(
                            {"error": "theme.json not found in package"}
                        ), 400

                    meta = json.loads(zf.read(theme_entry).decode("utf-8"))
                    theme_name = meta.get("name", "").strip()
                    if not theme_name:
                        return jsonify(
                            {"error": "theme.json missing 'name'"}
                        ), 400
                    if not meta.get("variables"):
                        return jsonify(
                            {"error": "theme.json missing 'variables'"}
                        ), 400

                    # 内置主题名称冲突检查
                    builtin_names = {
                        t.get("name") for t in _load_builtin_themes()
                    }
                    if theme_name in builtin_names:
                        return jsonify(
                            {"error": f"Theme '{theme_name}' is builtin, cannot override"}
                        ), 400

                    # 解压到 data/themes/<name>/
                    dest = os.path.join(THEMES_DIR, theme_name)
                    if os.path.exists(dest):
                        shutil.rmtree(dest, ignore_errors=True)
                    os.makedirs(dest, exist_ok=True)
                    zf.extractall(dest)

                    self.logger.info(f"Theme imported: {theme_name}")
                    return jsonify({
                        "success": True,
                        "name": theme_name,
                        "display_name": meta.get("display_name", theme_name),
                    })
            except zipfile.BadZipFile:
                return jsonify({"error": "Invalid zip file"}), 400
            except Exception as e:
                return jsonify({"error": str(e)}), 400
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        @app.route("/api/themes/<name>", methods=["DELETE"])
        def api_themes_delete(name: str):
            """删除已导入的主题。"""
            token = request.cookies.get("qtine_token", "")
            if token != self._admin_token:
                return jsonify({"error": "Unauthorized"}), 401
            # 不允许删除内置主题
            builtin_names = {t.get("name") for t in _load_builtin_themes()}
            if name in builtin_names:
                return jsonify({"error": "Cannot delete builtin theme"}), 400

            theme_dir = os.path.join(THEMES_DIR, name)
            if not os.path.isdir(theme_dir):
                return jsonify({"error": "Theme not found"}), 404

            shutil.rmtree(theme_dir, ignore_errors=True)

            # 如果删除的是当前主题，回退到默认
            current = self.config.get("webui.theme", DEFAULT_THEME)
            if current == name:
                self.config.set("webui.theme", DEFAULT_THEME)
                self.config.save()

            self.logger.info(f"Theme deleted: {name}")
            return jsonify({"success": True, "name": name})

        # ── update ─────────────────────────────────────────────────

        def _check_auth_json():
            token = request.cookies.get("qtine_token", "")
            if token != self._admin_token:
                return jsonify({"error": "Unauthorized"}), 401
            return None

        @app.route("/api/update/check")
        def api_update_check():
            """检查是否有更新（优先使用自建服务器代理）。"""
            import threading

            result = {"has_update": False, "current": "", "latest": None}

            def _do_check():
                current = get_current_version()
                check_url = (
                    self.config.get("update.check_url", "")
                    or ""
                ).strip()
                # 默认使用 jsDelivr CDN
                if not check_url:
                    check_url = "https://cdn.jsdelivr.net/gh/QtineNiko/Qtine@main/latest.json"
                result["current"] = current
                release = find_update(
                    current, check_url=check_url or None
                )
                if release:
                    result["has_update"] = True
                    result["latest"] = {
                        "tag_name": release.tag_name,
                        "name": release.name,
                        "body": release.body,
                        "published_at": release.published_at,
                        "prerelease": release.prerelease,
                        "html_url": release.html_url,
                    }

            # 用线程避免阻塞请求
            t = threading.Thread(target=_do_check, daemon=True)
            t.start()
            t.join(timeout=15)

            return jsonify(result)

        @app.route("/api/update/versions")
        def api_update_versions():
            """获取所有可用版本列表。"""
            import threading

            result = {"current": "", "versions": []}

            def _do_fetch():
                releases = fetch_releases()
                current = get_current_version()
                result["current"] = current
                result["versions"] = [
                    {
                        "tag_name": r.tag_name,
                        "name": r.name,
                        "body": r.body,
                        "published_at": r.published_at,
                        "prerelease": r.prerelease,
                        "html_url": r.html_url,
                        "is_current": compare_versions(r.tag_name, current) == 0,
                        "is_newer": compare_versions(r.tag_name, current) > 0,
                    }
                    for r in releases
                ]

            t = threading.Thread(target=_do_fetch, daemon=True)
            t.start()
            t.join(timeout=20)

            return jsonify(result)

        @app.route("/api/update/download", methods=["POST"])
        def api_update_download():
            """下载并安装指定版本。

            Body: {"tag": "v1.2.0", "mirror": "https://gh.llkk.cc"} (mirror 可选)
            """
            auth_err = _check_auth_json()
            if auth_err:
                return auth_err
            data = request.get_json(silent=True) or {}
            tag = (data.get("tag") or "").strip()
            if not tag:
                return jsonify({"error": "tag is required"}), 400

            mirror = (data.get("mirror") or "").strip() or None

            current = get_current_version()
            if compare_versions(tag, current) == 0:
                return jsonify({
                    "success": False,
                    "error": f"Already on version {tag}",
                })

            release = find_release_by_tag(tag)
            if not release:
                return jsonify({
                    "success": False,
                    "error": f"Release {tag} not found",
                }), 404

            # 下载
            zip_path = download_release(release, mirror)
            if not zip_path:
                return jsonify({
                    "success": False,
                    "error": "Download failed",
                }), 500

            # 备份
            backup_current(PROJECT_ROOT, current)

            # 安装
            ok = install_release(
                zip_path, PROJECT_ROOT,
                old_version=current,
                new_version=release.tag_name,
            )

            if ok:
                self.logger.info(
                    f"Update completed: {current} → {release.tag_name}"
                )
                return jsonify({
                    "success": True,
                    "from": current,
                    "to": release.tag_name,
                    "message": "更新完成，请重启 Qtine 使新版本生效",
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Install failed, restored from backup",
                }), 500

        @app.route("/api/update/backups")
        def api_update_backups():
            """列出所有备份。"""
            return jsonify({
                "backups": list_backups(),
            })

        @app.route("/api/update/rollback", methods=["POST"])
        def api_update_rollback():
            """回滚到指定备份版本。"""
            auth_err = _check_auth_json()
            if auth_err:
                return auth_err
            data = request.get_json(silent=True) or {}
            version = (data.get("version") or "").strip()
            if not version:
                return jsonify({"error": "version is required"}), 400

            ok = rollback_to(PROJECT_ROOT, version)
            if ok:
                self.logger.info(f"Rollback to {version} completed")
                return jsonify({
                    "success": True,
                    "version": version,
                    "message": f"已回滚到 {version}，请重启 Qtine",
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"回滚到 {version} 失败",
                }), 500

        @app.route("/api/update/mirrors")
        def api_update_mirrors():
            """返回可用加速镜像列表，包含官方源和加速镜像。"""
            return jsonify({
                "mirrors": [
                    {"name": "官方源 (GitHub)", "url": "https://github.com", "is_official": True},
                    {"name": "ghproxy", "url": "https://ghproxy.com"},
                    {"name": "99988866", "url": "https://gh.api.99988866.xyz"},
                    {"name": "mirror.ghproxy", "url": "https://mirror.ghproxy.com"},
                    {"name": "gh-proxy", "url": "https://gh-proxy.com"},
                    {"name": "xcxgw", "url": "https://gh.xcxgw.com"},
                    {"name": "ghps", "url": "https://ghps.cc"},
                    {"name": "d-ai workers", "url": "https://gh.d-ai.workers.dev"},
                    {"name": "llkk", "url": "https://gh.llkk.cc"},
                    {"name": "hub.gitmirror", "url": "https://hub.gitmirror.com"},
                ],
            })

        @app.route("/api/update/check-url")
        def api_update_check_url():
            """返回当前配置的更新检查代理 URL。"""
            return jsonify({
                "url": self.config.get("update.check_url", "") or "",
            })

        @app.route("/api/update/check-url", methods=["POST"])
        def api_update_check_url_set():
            """设置更新检查代理 URL。"""
            data = request.get_json(silent=True) or {}
            url = (data.get("url") or "").strip()
            try:
                self.config.set("update.check_url", url)
                self.config.save()
            except Exception as e:
                self.logger.error(f"Save update.check_url failed: {e}")
                return jsonify(
                    {"success": False, "error": f"写入配置失败: {e}"}
                ), 500
            self.logger.info(f"Update check URL set: {url or '(cleared)'}")
            return jsonify({"success": True, "url": url})

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

        @app.route("/api/plugins/<name>/uninstall", methods=["POST"])
        def api_plugin_uninstall(name):
            ok = bot.plugin_manager.uninstall(name)
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

        # ── plugin config ──────────────────────────────────────────

        @app.route("/api/plugins/<name>/config")
        def api_plugin_config(name):
            plugin = bot.plugin_manager.get(name)
            if not plugin:
                return jsonify({"success": False, "error": "Plugin not found"}), 404
            schema = plugin.get_config_schema()
            values = plugin.get_all_config_values()
            return jsonify({
                "success": True,
                "name": name,
                "schema": schema,
                "values": values,
            })

        @app.route("/api/plugins/<name>/config", methods=["POST"])
        def api_plugin_config_save(name):
            plugin = bot.plugin_manager.get(name)
            if not plugin:
                return jsonify({"success": False, "error": "Plugin not found"}), 404
            data = request.get_json(silent=True) or {}
            values = data.get("values", {})
            for key, value in values.items():
                plugin.set_config(key, value)
            # 清缓存
            plugin._config_cache.clear()
            return jsonify({"success": True, "values": plugin.get_all_config_values()})

        # ── plugin group config ────────────────────────────────────

        @app.route("/api/plugins/<name>/group-config")
        def api_plugin_group_config(name):
            plugin = bot.plugin_manager.get(name)
            if not plugin:
                return jsonify({"success": False, "error": "Plugin not found"}), 404
            group_id = request.args.get("group_id", "")
            if not group_id:
                return jsonify({"success": False, "error": "缺少 group_id"}), 400
            schema = plugin.get_config_schema()
            values = plugin.get_group_config_values(group_id)
            return jsonify({
                "success": True,
                "name": name,
                "group_id": group_id,
                "schema": schema,
                "values": values,
            })

        @app.route("/api/plugins/<name>/group-config", methods=["POST"])
        def api_plugin_group_config_save(name):
            plugin = bot.plugin_manager.get(name)
            if not plugin:
                return jsonify({"success": False, "error": "Plugin not found"}), 404
            data = request.get_json(silent=True) or {}
            group_id = data.get("group_id", "")
            if not group_id:
                return jsonify({"success": False, "error": "缺少 group_id"}), 400
            values = data.get("values", {})
            for key, value in values.items():
                plugin.set_group_config(group_id, key, value)
            return jsonify({
                "success": True,
                "values": plugin.get_group_config_values(group_id),
            })

        @app.route("/api/plugins/<name>/group-config/reset", methods=["POST"])
        def api_plugin_group_config_reset(name):
            plugin = bot.plugin_manager.get(name)
            if not plugin:
                return jsonify({"success": False, "error": "Plugin not found"}), 404
            data = request.get_json(silent=True) or {}
            group_id = data.get("group_id", "")
            if not group_id:
                return jsonify({"success": False, "error": "缺少 group_id"}), 400
            count = plugin.reset_group_config(group_id)
            return jsonify({"success": True, "reset": count})

        # ── marketplace ────────────────────────────────────────────

        @app.route("/api/market/plugins")
        def api_market_plugins():
            """Return plugin market listings.

            Tries to fetch from the configured ``plugins.marketplace_url``
            first; falls back to the built-in demo list when the source
            is empty or unreachable so the WebUI always renders a list.
            Each entry is annotated with ``installed`` based on the
            currently loaded plugins.

            Locally imported plugins that are not in any remote source
            are also included so they appear on the market page.
            """
            installed_infos = bot.plugin_manager.get_all_info()
            installed_names = {p.name for p in installed_infos}
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
                    with safe_urlopen(
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
                    if isinstance(plugins, dict):
                        plugins = plugins.get("plugins") or []
                    plugins = plugins if isinstance(plugins, list) else []
                    using_fallback = False
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Market source {url} unreachable: {e}"
                    )
                    continue

            if using_fallback:
                plugins = list(BUILTIN_MARKET_PLUGINS)

            # Annotate installed state.
            for p in plugins:
                if isinstance(p, dict):
                    p["installed"] = p.get("name") in installed_names

            # Include locally imported plugins not present in the
            # remote / fallback list so they show up on the page.
            market_names = {
                p.get("name") for p in plugins if isinstance(p, dict)
            }
            for info in installed_infos:
                if info.name in market_names:
                    continue
                plugins.insert(0, {
                    "name": info.name,
                    "version": info.version or "0.0.0",
                    "author": info.author or "本地",
                    "description": info.description or "",
                    "tags": ["本地", "已安装"],
                    "installed": True,
                    "is_local": True,
                })

            return jsonify({
                "source": source_url,
                "mirrors": mirrors,
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
            """Update the marketplace source URL and mirrors, persist to config."""
            data = request.get_json(silent=True) or {}
            url = (data.get("url") or "").strip()
            mirrors = data.get("mirrors") or []
            if not url:
                return jsonify(
                    {"success": False, "error": "url is required"}
                ), 400
            try:
                url = validate_public_http_url(url)
            except (OSError, ValueError) as e:
                return jsonify({"success": False, "error": str(e)}), 400
            self.config.set("plugins.marketplace_url", url)
            self.config.set("plugins.marketplace_mirrors", [])
            try:
                self.config.save()
            except Exception as e:
                return jsonify(
                    {"success": False, "error": f"Save failed: {e}"}
                ), 500
            self.logger.info(
                f"Marketplace source updated: {url}, mirrors: {len(clean_mirrors)}"
            )
            return jsonify({
                "success": True,
                "url": url,
                "mirrors": clean_mirrors,
            })

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

                    with safe_urlopen(
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

            # Apply mirror if configured and download_url is from GitHub
            mirror_url = self.storage.get("market_mirror", "") or ""
            if (
                mirror_url
                and "github.com" in download_url
                and mirror_url != "https://github.com"
            ):
                download_url = download_url.replace(
                    "https://github.com", mirror_url.rstrip("/")
                )

            # Download to data/uploads/<name>.zip
            try:
                import urllib.request

                os.makedirs(UPLOAD_DIR, exist_ok=True)
                dest = os.path.join(UPLOAD_DIR, f"{name}.zip")
                with safe_urlopen(download_url, timeout=30) as r, open(
                    dest, "wb"
                ) as out:
                    remaining = MAX_UPLOAD_MB * 1024 * 1024
                    while True:
                        chunk = r.read(min(1024 * 1024, remaining + 1))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        if remaining < 0:
                            raise ValueError("Plugin download is too large")
                        out.write(chunk)
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

        # ── marketplace: mirrors / speedtest / readme ──────────────

        @app.route("/api/market/mirrors")
        def api_market_mirrors():
            """返回 GitHub 加速镜像列表，含用户自定义的。"""
            custom = self.storage.get("market_custom_mirrors", []) or []
            current = self.storage.get(
                "market_mirror", "https://github.com"
            ) or "https://github.com"
            all_mirrors = list(DEFAULT_GITHUB_MIRRORS) + [
                {"name": m.get("name", "自定义"), "url": m.get("url", "")}
                for m in custom
                if m.get("url")
            ]
            return jsonify({
                "mirrors": all_mirrors,
                "current": current,
            })

        @app.route("/api/market/mirrors/set", methods=["POST"])
        def api_market_mirrors_set():
            """设置当前使用的加速源。"""
            data = request.get_json(silent=True) or {}
            url = (data.get("url") or "").strip()
            if not url:
                return jsonify(
                    {"success": False, "error": "url is required"}
                ), 400
            try:
                url = validate_public_http_url(url)
            except (OSError, ValueError) as e:
                return jsonify({"success": False, "error": str(e)}), 400
            self.storage.set("market_mirror", url)
            return jsonify({"success": True, "current": url})

        @app.route("/api/market/mirrors/speedtest")
        def api_market_mirrors_speedtest():
            """对所有镜像进行测速，返回最快的。"""
            import urllib.request

            mirrors = DEFAULT_GITHUB_MIRRORS[:]
            custom = self.storage.get("market_custom_mirrors", []) or []
            for m in custom:
                if m.get("url"):
                    mirrors.append(
                        {"name": m.get("name", "自定义"), "url": m["url"]}
                    )

            results = []
            test_path = "/QtineNiko/Qtine"
            for m in mirrors:
                url = m["url"].rstrip("/") + test_path
                start = time.time()
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    with safe_urlopen(req, timeout=5) as r:
                        latency = (time.time() - start) * 1000
                        results.append({
                            "name": m["name"],
                            "url": m["url"],
                            "latency": round(latency, 0),
                        })
                except Exception:
                    results.append({
                        "name": m["name"],
                        "url": m["url"],
                        "latency": 99999,
                    })

            results.sort(key=lambda x: x["latency"])
            fastest = (
                results[0]["url"]
                if results and results[0]["latency"] < 99999
                else None
            )
            return jsonify({"results": results, "fastest": fastest})

        @app.route("/api/market/mirrors/custom", methods=["POST"])
        def api_market_mirrors_custom_add():
            """添加自定义加速源。"""
            data = request.get_json(silent=True) or {}
            name = (data.get("name") or "").strip()
            url = (data.get("url") or "").strip()
            if not url:
                return jsonify(
                    {"success": False, "error": "url is required"}
                ), 400
            try:
                url = validate_public_http_url(url)
            except (OSError, ValueError) as e:
                return jsonify({"success": False, "error": str(e)}), 400
            if not name:
                name = url[:20]
            custom = self.storage.get("market_custom_mirrors", []) or []
            custom.append({"name": name, "url": url})
            self.storage.set("market_custom_mirrors", custom)
            return jsonify({"success": True, "mirrors": custom})

        @app.route(
            "/api/market/mirrors/custom/<int:idx>", methods=["DELETE"]
        )
        def api_market_mirrors_custom_remove(idx):
            """删除自定义加速源。"""
            custom = self.storage.get("market_custom_mirrors", []) or []
            if idx < 0 or idx >= len(custom):
                return jsonify(
                    {"success": False, "error": "index out of range"}
                ), 400
            removed = custom.pop(idx)
            self.storage.set("market_custom_mirrors", custom)
            return jsonify({"success": True, "removed": removed})

        @app.route("/api/market/plugins/<name>/readme")
        def api_market_plugin_readme(name):
            """获取插件 README。

            优先从市场源拉取；源不可用时返回空字符串。
            """
            source_url = (
                self.config.get("plugins.marketplace_url", "") or ""
            ).strip()
            readme = ""
            if source_url:
                try:
                    import urllib.request
                    import json as _json

                    url = (
                        source_url.rstrip("/")
                        + f"/plugins/{name}/readme"
                    )
                    with safe_urlopen(
                        url, timeout=10
                    ) as r:
                        d = _json.loads(
                            r.read().decode("utf-8", "ignore")
                        )
                        readme = d.get("readme", "") or ""
                except Exception as e:
                    self.logger.warning(
                        f"Fetch readme for {name} failed: {e}"
                    )
            return jsonify({"name": name, "readme": readme})

        @app.route("/api/market/plugins/<name>/detail")
        def api_market_plugin_detail(name):
            """获取插件详情（含 readme）。"""
            source_url = (
                self.config.get("plugins.marketplace_url", "") or ""
            ).strip()
            if source_url:
                try:
                    import urllib.request
                    import json as _json

                    url = source_url.rstrip("/") + f"/plugins/{name}"
                    with safe_urlopen(
                        url, timeout=10
                    ) as r:
                        d = _json.loads(
                            r.read().decode("utf-8", "ignore")
                        )
                        return jsonify(d)
                except Exception as e:
                    self.logger.warning(
                        f"Fetch detail for {name} failed: {e}"
                    )
            return jsonify({"error": "not found"}), 404

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

        # ── scheduler / tasks ──────────────────────────────────────

        @app.route("/api/tasks")
        def api_tasks():
            plugin = request.args.get("plugin", type=str) or None
            tasks = bot.scheduler.list_tasks(plugin=plugin)
            return jsonify({
                "success": True,
                "tasks": tasks,
                "count": len(tasks),
            })

        @app.route("/api/tasks", methods=["POST"])
        def api_task_add():
            data = request.get_json(silent=True) or {}
            name = data.get("name", "").strip()
            cron_expr = data.get("cron", "").strip()
            plugin = data.get("plugin", "") or ""
            description = data.get("description", "") or ""
            action_type = data.get("action_type", "message")
            action_data = data.get("action_data", {}) or {}
            if not name or not cron_expr:
                return jsonify({
                    "success": False,
                    "error": "name 和 cron 是必填项",
                }), 400

            def task_callback():
                try:
                    if action_type == "message" and action_data:
                        target = action_data.get("target", "")
                        target_type = action_data.get("target_type", "group")
                        content = action_data.get("content", "")
                        if target and content:
                            bot.adapter_manager.send_message(
                                "onebot_v11", target, content, target_type
                            )
                except Exception as e:
                    self.logger.error(f"Task '{name}' action error: {e}")

            ok = bot.scheduler.add_task(
                name=name,
                cron_expr=cron_expr,
                callback=task_callback,
                plugin=plugin,
                description=description,
            )
            if ok:
                return jsonify({"success": True, "name": name})
            return jsonify({
                "success": False,
                "error": "添加任务失败，请检查 cron 表达式",
            }), 400

        @app.route("/api/tasks/<name>", methods=["DELETE"])
        def api_task_delete(name):
            ok = bot.scheduler.remove_task(name)
            return jsonify({"success": ok, "name": name})

        @app.route("/api/tasks/<name>/run", methods=["POST"])
        def api_task_run(name):
            task = None
            with bot.scheduler._lock:
                task = bot.scheduler._tasks.get(name)
            if not task:
                return jsonify({
                    "success": False,
                    "error": "任务不存在",
                }), 404
            threading.Thread(target=task.run, daemon=True).start()
            return jsonify({"success": True, "name": name})

        # ── logs ───────────────────────────────────────────────────

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

        # ── metrics / performance ─────────────────────────────────

        @app.route("/api/metrics")
        def api_metrics():
            """Performance and health metrics."""
            import os

            cpu_percent = 0
            memory_rss = 0
            memory_vms = 0
            memory_mb = 0
            cpu_count = 0
            total_memory = 0
            available_memory = 0

            try:
                import psutil
                proc = psutil.Process(os.getpid())
                try:
                    cpu_percent = proc.cpu_percent(interval=0.1)
                except Exception:
                    cpu_percent = 0
                mem_info = proc.memory_info()
                memory_rss = mem_info.rss
                memory_vms = mem_info.vms
                memory_mb = round(memory_rss / 1024 / 1024, 2)
                cpu_count = psutil.cpu_count() or 0
                total_memory = psutil.virtual_memory().total
                available_memory = psutil.virtual_memory().available
            except ImportError:
                pass

            adapter_stats = []
            for adapter in bot.adapter_manager.get_all():
                info = adapter.info
                adapter_stats.append({
                    "name": info.name,
                    "status": info.status.value,
                    "message_count": info.message_count,
                    "received_count": info.received_count,
                    "sent_count": info.sent_count,
                    "error_count": info.error_count,
                })

            return jsonify({
                "success": True,
                "uptime": bot.uptime,
                "version": __import__("qtine").__version__,
                "process": {
                    "pid": os.getpid(),
                    "cpu_percent": cpu_percent,
                    "memory_rss": memory_rss,
                    "memory_vms": memory_vms,
                    "memory_mb": memory_mb,
                },
                "system": {
                    "cpu_count": cpu_count,
                    "total_memory": total_memory,
                    "available_memory": available_memory,
                },
                "plugins": {
                    "total": bot.plugin_manager.count,
                    "enabled": bot.plugin_manager.enabled_count,
                },
                "adapters": adapter_stats,
                "tasks": {
                    "total": len(bot.scheduler._tasks),
                },
            })

        # ── webhook ───────────────────────────────────────────────

        @app.route("/api/webhooks")
        def api_webhooks_list():
            webhooks = bot.storage.get("webhooks", [])
            return jsonify({"success": True, "webhooks": webhooks})

        @app.route("/api/webhooks", methods=["POST"])
        def api_webhook_add():
            data = request.get_json(silent=True) or {}
            url = (data.get("url") or "").strip()
            event = (data.get("event") or "message.received").strip()
            name = (data.get("name") or "").strip()
            if not url:
                return jsonify({
                    "success": False,
                    "error": "url 是必填项",
                }), 400
            try:
                url = self._validate_outbound_url(url)
            except (OSError, ValueError) as e:
                return jsonify({"success": False, "error": str(e)}), 400
            webhooks = bot.storage.get("webhooks", [])
            webhook = {
                "id": secrets.token_hex(8),
                "name": name or url,
                "url": url,
                "event": event,
                "enabled": True,
                "created_at": time.time(),
            }
            webhooks.append(webhook)
            bot.storage.set("webhooks", webhooks)
            return jsonify({"success": True, "webhook": webhook})

        @app.route("/api/webhooks/<wh_id>", methods=["DELETE"])
        def api_webhook_delete(wh_id):
            webhooks = bot.storage.get("webhooks", [])
            webhooks = [w for w in webhooks if w.get("id") != wh_id]
            bot.storage.set("webhooks", webhooks)
            return jsonify({"success": True})

        @app.route("/api/webhooks/<wh_id>/toggle", methods=["POST"])
        def api_webhook_toggle(wh_id):
            webhooks = bot.storage.get("webhooks", [])
            for w in webhooks:
                if w.get("id") == wh_id:
                    w["enabled"] = not w.get("enabled", True)
                    break
            bot.storage.set("webhooks", webhooks)
            return jsonify({"success": True})

        # ── message templates ─────────────────────────────────────

        @app.route("/api/templates")
        def api_templates_list():
            templates = bot.storage.get("message_templates", [])
            return jsonify({"success": True, "templates": templates})

        @app.route("/api/templates", methods=["POST"])
        def api_template_add():
            data = request.get_json(silent=True) or {}
            name = (data.get("name") or "").strip()
            content = data.get("content", "")
            if not name or not content:
                return jsonify({
                    "success": False,
                    "error": "name 和 content 是必填项",
                }), 400
            templates = bot.storage.get("message_templates", [])
            template = {
                "id": secrets.token_hex(8),
                "name": name,
                "content": content,
                "variables": data.get("variables", []) or [],
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            templates.append(template)
            bot.storage.set("message_templates", templates)
            return jsonify({"success": True, "template": template})

        @app.route("/api/templates/<tpl_id>", methods=["PUT"])
        def api_template_update(tpl_id):
            data = request.get_json(silent=True) or {}
            templates = bot.storage.get("message_templates", [])
            for t in templates:
                if t.get("id") == tpl_id:
                    t["name"] = data.get("name", t["name"])
                    t["content"] = data.get("content", t["content"])
                    t["variables"] = data.get("variables", t.get("variables", []))
                    t["updated_at"] = time.time()
                    break
            bot.storage.set("message_templates", templates)
            return jsonify({"success": True})

        @app.route("/api/templates/<tpl_id>", methods=["DELETE"])
        def api_template_delete(tpl_id):
            templates = bot.storage.get("message_templates", [])
            templates = [t for t in templates if t.get("id") != tpl_id]
            bot.storage.set("message_templates", templates)
            return jsonify({"success": True})

        @app.route("/api/templates/<tpl_id>/render", methods=["POST"])
        def api_template_render(tpl_id):
            data = request.get_json(silent=True) or {}
            variables = data.get("variables", {}) or {}
            templates = bot.storage.get("message_templates", [])
            template = next(
                (t for t in templates if t.get("id") == tpl_id), None
            )
            if not template:
                return jsonify({
                    "success": False,
                    "error": "模板不存在",
                }), 404
            content = template["content"]
            for key, value in variables.items():
                content = content.replace("{{" + key + "}}", str(value))
            return jsonify({"success": True, "content": content})

        # ── i18n / locales ────────────────────────────────────────

        @app.route("/api/i18n/locales")
        def api_i18n_locales():
            return jsonify({
                "success": True,
                "current": bot.storage.get("locale", "zh-CN"),
                "available": ["zh-CN", "en-US", "ja-JP"],
            })

        @app.route("/api/i18n/locale", methods=["POST"])
        def api_i18n_set_locale():
            data = request.get_json(silent=True) or {}
            locale = (data.get("locale") or "zh-CN").strip()
            bot.storage.set("locale", locale)
            return jsonify({"success": True, "locale": locale})

        @app.route("/api/i18n/strings")
        def api_i18n_strings():
            locale = request.args.get("locale",
                                     bot.storage.get("locale", "zh-CN"))
            strings = {
                "zh-CN": {
                    "app.name": "Qtine 聊天机器人",
                    "nav.dashboard": "仪表盘",
                    "nav.plugins": "插件",
                    "nav.market": "市场",
                    "nav.adapters": "适配器",
                    "nav.tasks": "任务",
                    "nav.messages": "消息",
                    "nav.logs": "日志",
                    "nav.settings": "设置",
                    "nav.about": "关于",
                    "common.save": "保存",
                    "common.cancel": "取消",
                    "common.delete": "删除",
                    "common.edit": "编辑",
                    "common.refresh": "刷新",
                },
                "en-US": {
                    "app.name": "Qtine Chat Bot",
                    "nav.dashboard": "Dashboard",
                    "nav.plugins": "Plugins",
                    "nav.market": "Market",
                    "nav.adapters": "Adapters",
                    "nav.tasks": "Tasks",
                    "nav.messages": "Messages",
                    "nav.logs": "Logs",
                    "nav.settings": "Settings",
                    "nav.about": "About",
                    "common.save": "Save",
                    "common.cancel": "Cancel",
                    "common.delete": "Delete",
                    "common.edit": "Edit",
                    "common.refresh": "Refresh",
                },
                "ja-JP": {
                    "app.name": "Qtine チャットボット",
                    "nav.dashboard": "ダッシュボード",
                    "nav.plugins": "プラグイン",
                    "nav.market": "マーケット",
                    "nav.adapters": "アダプター",
                    "nav.tasks": "タスク",
                    "nav.messages": "メッセージ",
                    "nav.logs": "ログ",
                    "nav.settings": "設定",
                    "nav.about": "概要",
                    "common.save": "保存",
                    "common.cancel": "キャンセル",
                    "common.delete": "削除",
                    "common.edit": "編集",
                    "common.refresh": "更新",
                },
            }
            return jsonify({
                "success": True,
                "locale": locale,
                "strings": strings.get(locale, strings["zh-CN"]),
            })

        # ── WebUI WebSocket ────────────────────────────────────────

        @self.socketio.on("connect", namespace="/ws/webui")
        def webui_connect(auth=None):
            if not self._is_authenticated() or not self._request_origin_matches():
                return False
            self.logger.info("WebUI client connected")

        @self.socketio.on("disconnect", namespace="/ws/webui")
        def webui_disconnect():
            self.logger.info("WebUI client disconnected")

        # ── shutdown / restart ─────────────────────────────────────

        @app.route("/api/shutdown", methods=["POST"])
        def api_shutdown():
            if (
                os.environ.get("QTINE_MANAGED_SERVER") == "1"
                or not self.config.get("webui.allow_process_control", False)
            ):
                return jsonify({"error": "Process control is disabled"}), 403
            self.logger.warning("Shutdown requested via WebUI")
            threading.Thread(
                target=lambda: (self.shutdown(), os._exit(0)),
                daemon=True,
            ).start()
            return jsonify({"success": True})

        @app.route("/api/restart", methods=["POST"])
        def api_restart():
            if (
                os.environ.get("QTINE_MANAGED_SERVER") == "1"
                or not self.config.get("webui.allow_process_control", False)
            ):
                return jsonify({"error": "Process control is disabled"}), 403
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
        onebot_config = dict(
            self.config.get("adapters.onebot_v11", {}) or {}
        )
        env_token = os.environ.get("QTINE_ONEBOT_ACCESS_TOKEN", "").strip()
        if env_token:
            onebot_config["access_token"] = env_token
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
                if hasattr(adapter_ref, "is_authorized"):
                    headers = {
                        key[5:].replace("_", "-").title(): value
                        for key, value in environ.items()
                        if key.startswith("HTTP_")
                    }
                    if not adapter_ref.is_authorized(
                        headers, environ.get("QUERY_STRING", "")
                    ):
                        start_response(
                            "401 Unauthorized",
                            [("Content-Type", "text/plain")],
                        )
                        return [b"Unauthorized"]
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

        if debug:
            self.logger.warning("Debug mode is enabled; do not use it in production")
        self.socketio.run(
            self.flask_app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=bool(debug),
            use_reloader=False,
        )

    def shutdown(self):
        self.bot.shutdown()
        self.logger.info("Qtine shutdown complete")
