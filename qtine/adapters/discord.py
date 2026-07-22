# -*- coding: utf-8 -*-
"""Discord Bot Adapter for Qtine."""

import json
import threading
import time
from typing import Any

import requests
import websocket

from qtine.adapters.base import BaseAdapter
from qtine.utils.models import Message, Sender, AdapterStatus


class DiscordAdapter(BaseAdapter):
    PROTOCOL_NAME = "Discord"
    DESCRIPTION = "Discord Bot 适配器，通过 Gateway WebSocket 接收和发送消息"
    _builtin = True

    def __init__(self, name: str = "", config: dict = None):
        super().__init__(name=name, protocol="discord", config=config)
        self.token = self.config.get("token", "")
        self.intents = self.config.get("intents", 32767)
        self._ws = None
        self._heartbeat_thread = None
        self._running = False
        self._session_id = None
        self._resume_url = None
        self._seq = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._update_status(AdapterStatus.CONNECTING)
        if not self.token:
            self.logger.error(f"[{self.name}] Discord token not configured")
            self._update_status(AdapterStatus.ERROR)
            return
        thread = threading.Thread(target=self._connect, daemon=True)
        thread.start()
        self.logger.info(f"[{self.name}] Discord adapter started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._update_status(AdapterStatus.DISCONNECTED)
        self.logger.info(f"[{self.name}] Discord adapter stopped")

    def send_message(self, target: str, message: str, message_type: str = "group") -> bool:
        if not self.token:
            return False
        try:
            url = f"https://discord.com/api/v10/channels/{target}/messages"
            headers = {
                "Authorization": f"Bot {self.token}",
                "Content-Type": "application/json",
            }
            data = {"content": message}
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            if resp.status_code in (200, 201):
                self._adapter_info.sent_count += 1
                return True
            self.logger.warning(f"[{self.name}] Send failed: {resp.status_code} {resp.text}")
            return False
        except Exception as e:
            self.logger.error(f"[{self.name}] Send error: {e}")
            return False

    def _connect(self):
        gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"
        while self._running:
            try:
                ws_url = self._resume_url or gateway_url
                self._ws = websocket.create_connection(ws_url, timeout=10)
                self._handle_ws()
            except Exception as e:
                self.logger.error(f"[{self.name}] Connection error: {e}")
                self._update_status(AdapterStatus.DISCONNECTED)
                if self._running:
                    time.sleep(5)

    def _handle_ws(self):
        while self._running and self._ws:
            try:
                raw = self._ws.recv()
                data = json.loads(raw)
                self._seq = data.get("s", self._seq)
                op = data.get("op")
                if op == 10:  # Hello
                    self._send_identify()
                    interval = data["d"]["heartbeat_interval"] / 1000
                    self._start_heartbeat(interval)
                elif op == 11:  # Heartbeat ACK
                    pass
                elif op == 1:  # Heartbeat request
                    self._send_heartbeat()
                elif op == 0:  # Dispatch
                    self._handle_dispatch(data)
                elif op == 7:  # Reconnect
                    self._resume_url = None
                    self._session_id = None
                    break
                elif op == 9:  # Invalid session
                    self._session_id = None
                    time.sleep(5)
                    self._send_identify()
            except websocket.WebSocketConnectionClosedException:
                break
            except Exception as e:
                self.logger.error(f"[{self.name}] WS handle error: {e}")
                break

    def _start_heartbeat(self, interval: float):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        def heartbeat_loop():
            while self._running:
                time.sleep(interval)
                if self._running:
                    self._send_heartbeat()
        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _send_heartbeat(self):
        if self._ws:
            try:
                self._ws.send(json.dumps({"op": 1, "d": self._seq}))
            except Exception:
                pass

    def _send_identify(self):
        if not self._ws:
            return
        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": self.intents,
                "properties": {
                    "os": "linux",
                    "browser": "Qtine",
                    "device": "Qtine",
                },
            },
        }
        if self._session_id and self._seq:
            payload = {
                "op": 6,
                "d": {
                    "token": self.token,
                    "session_id": self._session_id,
                    "seq": self._seq,
                },
            }
        self._ws.send(json.dumps(payload))

    def _handle_dispatch(self, data: dict):
        event = data.get("t")
        if event == "READY":
            self._session_id = data["d"].get("session_id")
            self._resume_url = data["d"].get("resume_gateway_url")
            user = data["d"].get("user", {})
            self._update_status(AdapterStatus.CONNECTED, user.get("id", ""), user.get("username", ""))
        elif event == "MESSAGE_CREATE":
            self._handle_message(data["d"])

    def _handle_message(self, data: dict):
        if data.get("author", {}).get("bot"):
            return
        channel_id = str(data.get("channel_id", ""))
        guild_id = str(data.get("guild_id", ""))
        author = data.get("author", {})
        user_id = str(author.get("id", ""))
        nickname = author.get("username", "Unknown")
        content = data.get("content", "")

        sender = Sender(user_id=user_id, nickname=nickname)
        msg = Message(
            adapter=self.name,
            type="group" if guild_id else "private",
            content=content,
            sender=sender,
            group_id=channel_id,
            raw=data,
            message_id=str(data.get("id", "")),
            timestamp=time.time(),
        )
        self._adapter_info.received_count += 1
        self._adapter_info.message_count += 1
        self._emit_message(msg)
