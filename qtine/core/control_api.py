# -*- coding: utf-8 -*-
"""Qtine Control API — external application control interface.

All endpoints under /api/control/ require a control password.
The password must be set in config (api_control.password) and
contain uppercase, lowercase, digits, and special characters.
"""

import re
import time
from functools import wraps
from typing import Callable, Optional

from flask import request, jsonify


def _get_control_password(bot) -> Optional[str]:
    """Get the configured control password."""
    cfg = bot.config.get("api_control", {}) or {}
    return cfg.get("password", "")


def _is_control_enabled(bot) -> bool:
    """Check if control API is enabled."""
    cfg = bot.config.get("api_control", {}) or {}
    return cfg.get("enabled", False)


def _validate_password_strength(password: str) -> bool:
    """Check if password contains uppercase, lowercase, digits, and special chars."""
    if len(password) < 8:
        return False
    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password))
    return has_upper and has_lower and has_digit and has_special


def control_auth_required(bot_getter: Callable):
    """Decorator for control API endpoints that require password authentication."""
    def decorator(f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            bot = bot_getter()
            if not _is_control_enabled(bot):
                return jsonify({"success": False, "error": "Control API is disabled"}), 403

            password = _get_control_password(bot)
            if not password:
                return jsonify({"success": False, "error": "Control password not set"}), 403

            # Check password from header or body
            provided = request.headers.get("X-Control-Password", "")
            if not provided:
                data = request.get_json(silent=True) or {}
                provided = data.get("password", "")

            if provided != password:
                return jsonify({"success": False, "error": "Invalid control password"}), 401

            return f(*args, **kwargs)
        return wrapper
    return decorator


def register_control_routes(app, bot_getter: Callable):
    """Register all control API routes on the Flask app."""
    auth = control_auth_required(bot_getter)

    # ── System ─────────────────────────────────────────────────────

    @app.route("/api/control/status", methods=["GET"])
    @auth
    def control_status():
        bot = bot_getter()
        return jsonify({
            "success": True,
            "running": bot._running,
            "uptime": bot.uptime,
            "version": bot.config.get("version", "1.0.0"),
            "plugins": len(bot.plugin_manager.get_all()),
            "adapters": len(bot.adapter_manager.get_all()),
        })

    @app.route("/api/control/start", methods=["POST"])
    @auth
    def control_start():
        bot = bot_getter()
        if bot._running:
            return jsonify({"success": False, "error": "Already running"})
        bot.start()
        return jsonify({"success": True})

    @app.route("/api/control/stop", methods=["POST"])
    @auth
    def control_stop():
        bot = bot_getter()
        if not bot._running:
            return jsonify({"success": False, "error": "Not running"})
        bot.shutdown()
        return jsonify({"success": True})

    @app.route("/api/control/restart", methods=["POST"])
    @auth
    def control_restart():
        bot = bot_getter()
        bot.shutdown()
        time.sleep(1)
        bot.start()
        return jsonify({"success": True})

    # ── Adapters ────────────────────────────────────────────────────

    @app.route("/api/control/adapters", methods=["GET"])
    @auth
    def control_adapters():
        bot = bot_getter()
        result = []
        for a in bot.adapter_manager.get_all():
            info = a.info
            result.append({
                "name": info.name,
                "protocol": info.protocol,
                "status": info.status.value,
                "enabled": info.enabled,
                "message_count": info.message_count,
                "account_id": info.account_id,
                "nickname": info.nickname,
            })
        return jsonify({"success": True, "adapters": result})

    @app.route("/api/control/adapters/<name>/start", methods=["POST"])
    @auth
    def control_adapter_start(name):
        bot = bot_getter()
        if bot.adapter_manager.start(name):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to start"}), 400

    @app.route("/api/control/adapters/<name>/stop", methods=["POST"])
    @auth
    def control_adapter_stop(name):
        bot = bot_getter()
        if bot.adapter_manager.stop(name):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to stop"}), 400

    @app.route("/api/control/adapters/<name>/enable", methods=["POST"])
    @auth
    def control_adapter_enable(name):
        bot = bot_getter()
        if bot.adapter_manager.enable(name):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Not found"}), 404

    @app.route("/api/control/adapters/<name>/disable", methods=["POST"])
    @auth
    def control_adapter_disable(name):
        bot = bot_getter()
        if bot.adapter_manager.disable(name):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Not found"}), 404

    # ── Plugins ─────────────────────────────────────────────────────

    @app.route("/api/control/plugins", methods=["GET"])
    @auth
    def control_plugins():
        bot = bot_getter()
        result = []
        for p in bot.plugin_manager.get_all():
            info = p.get_info()
            result.append({
                "name": info.name,
                "version": info.version,
                "enabled": info.enabled,
                "status": info.status.value if hasattr(info.status, "value") else str(info.status),
                "description": info.description,
            })
        return jsonify({"success": True, "plugins": result})

    @app.route("/api/control/plugins/<name>/enable", methods=["POST"])
    @auth
    def control_plugin_enable(name):
        bot = bot_getter()
        plugin = bot.plugin_manager.get(name)
        if plugin is None:
            return jsonify({"success": False, "error": "Plugin not found"}), 404
        bot.plugin_manager.enable_plugin(name)
        return jsonify({"success": True})

    @app.route("/api/control/plugins/<name>/disable", methods=["POST"])
    @auth
    def control_plugin_disable(name):
        bot = bot_getter()
        plugin = bot.plugin_manager.get(name)
        if plugin is None:
            return jsonify({"success": False, "error": "Plugin not found"}), 404
        bot.plugin_manager.disable_plugin(name)
        return jsonify({"success": True})

    # ── Messages ────────────────────────────────────────────────────

    @app.route("/api/control/messages", methods=["GET"])
    @auth
    def control_messages():
        bot = bot_getter()
        limit = request.args.get("limit", 50, type=int)
        try:
            msgs = bot.storage.get_recent_messages(limit=limit)
            return jsonify({"success": True, "messages": msgs})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/control/send", methods=["POST"])
    @auth
    def control_send():
        bot = bot_getter()
        data = request.get_json() or {}
        adapter = data.get("adapter")
        target = data.get("target")
        content = data.get("content")
        msg_type = data.get("type", "group")
        if not adapter or not target or not content:
            return jsonify({"success": False, "error": "adapter, target, content required"}), 400
        success = bot.adapter_manager.send_message(adapter, target, content, msg_type)
        return jsonify({"success": success})

    # ── Metrics ─────────────────────────────────────────────────────

    @app.route("/api/control/metrics", methods=["GET"])
    @auth
    def control_metrics():
        bot = bot_getter()
        try:
            import psutil
            process = psutil.Process()
            mem = process.memory_info()
            return jsonify({
                "success": True,
                "uptime": bot.uptime,
                "memory": {
                    "rss_mb": mem.rss / (1024 * 1024),
                    "vms_mb": mem.vms / (1024 * 1024),
                },
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "adapters": len(bot.adapter_manager.get_all()),
                "plugins": len(bot.plugin_manager.get_all()),
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ── Config ──────────────────────────────────────────────────────

    @app.route("/api/control/config", methods=["GET"])
    @auth
    def control_config_get():
        bot = bot_getter()
        return jsonify({"success": True, "config": bot.config._data})

    @app.route("/api/control/config", methods=["PUT"])
    @auth
    def control_config_put():
        bot = bot_getter()
        data = request.get_json() or {}
        for key, value in data.items():
            bot.config.set(key, value)
        return jsonify({"success": True})

    # ── Password validation helper ──────────────────────────────────

    @app.route("/api/control/password/validate", methods=["POST"])
    def control_password_validate():
        """Public endpoint to validate password strength (no auth required)."""
        data = request.get_json() or {}
        password = data.get("password", "")
        valid = _validate_password_strength(password)
        return jsonify({
            "valid": valid,
            "requirements": {
                "min_length": 8,
                "uppercase": bool(re.search(r"[A-Z]", password)),
                "lowercase": bool(re.search(r"[a-z]", password)),
                "digit": bool(re.search(r"\d", password)),
                "special": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password)),
            }
        })
