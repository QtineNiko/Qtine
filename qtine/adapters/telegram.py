# -*- coding: utf-8 -*-
"""Telegram Bot Adapter for Qtine."""

import asyncio
import threading
import time
from typing import Any

import requests

from qtine.adapters.base import BaseAdapter
from qtine.utils.models import Message, Sender, AdapterStatus


class TelegramAdapter(BaseAdapter):
    PROTOCOL_NAME = "Telegram"
    DESCRIPTION = "Telegram Bot 适配器，通过 HTTP API 接收和发送消息"
    _builtin = True

    def __init__(self, name: str = "", config: dict = None):
        super().__init__(name=name, protocol="telegram", config=config)
        self.token = self.config.get("token", "")
        self.api_base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self._polling = False
        self._thread = None
        self._offset = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._update_status(AdapterStatus.CONNECTING)
        if not self.token:
            self.logger.error(f"[{self.name}] Telegram token not configured")
            self._update_status(AdapterStatus.ERROR)
            return
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"[{self.name}] Telegram adapter started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._polling = False
        self._update_status(AdapterStatus.DISCONNECTED)
        self.logger.info(f"[{self.name}] Telegram adapter stopped")

    def send_message(self, target: str, message: str, message_type: str = "group") -> bool:
        if not self.token:
            return False
        try:
            url = f"{self.api_base}/sendMessage"
            data = {
                "chat_id": target,
                "text": message,
                "parse_mode": "HTML",
            }
            resp = requests.post(url, json=data, timeout=30)
            if resp.status_code == 200:
                self._adapter_info.sent_count += 1
                return True
            self.logger.warning(f"[{self.name}] Send failed: {resp.text}")
            return False
        except Exception as e:
            self.logger.error(f"[{self.name}] Send error: {e}")
            return False

    def _poll_loop(self):
        self._polling = True
        while self._polling and self._running:
            try:
                url = f"{self.api_base}/getUpdates"
                params = {"offset": self._offset, "limit": 100, "timeout": 30}
                resp = requests.get(url, params=params, timeout=40)
                if resp.status_code != 200:
                    time.sleep(5)
                    continue
                data = resp.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue
                updates = data.get("result", [])
                if updates:
                    self._update_status(AdapterStatus.CONNECTED)
                for update in updates:
                    self._offset = update["update_id"] + 1
                    self._handle_update(update)
            except Exception as e:
                self.logger.error(f"[{self.name}] Poll error: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        message_data = update.get("message") or update.get("edited_message")
        if not message_data:
            return
        chat = message_data.get("chat", {})
        from_user = message_data.get("from", {})
        text = message_data.get("text", "")
        chat_id = str(chat.get("id", ""))
        user_id = str(from_user.get("id", ""))
        nickname = from_user.get("first_name", "") + " " + from_user.get("last_name", "")
        nickname = nickname.strip() or "Unknown"
        chat_type = chat.get("type", "private")

        is_group = chat_type in ("group", "supergroup")

        sender = Sender(user_id=user_id, nickname=nickname)
        msg = Message(
            adapter=self.name,
            type="group" if is_group else "private",
            content=text,
            sender=sender,
            group_id=chat_id if is_group else None,
            raw=update,
            message_id=str(message_data.get("message_id", "")),
            timestamp=time.time(),
        )
        self._adapter_info.received_count += 1
        self._adapter_info.message_count += 1
        self._emit_message(msg)
