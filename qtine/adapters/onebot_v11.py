# -*- coding: utf-8 -*-
"""
OneBot V11 adapter — full protocol compliance.

Supports:
- Reverse WebSocket  (NapCat connects to Qtine)
- Forward WebSocket  (Qtine connects to NapCat)
- HTTP API           (Qtine exposes REST endpoints for OneBot actions)
- Both directions simultaneously

Reference: https://11.onebot.dev / https://github.com/botuniverse/onebot-11
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs

import websocket

from qtine.adapters.base import BaseAdapter
from qtine.utils.models import AdapterStatus, Message, Sender


class OneBotV11Adapter(BaseAdapter):
    """OneBot V11 adapter implementing standard protocol."""

    # ── lifecycle ────────────────────────────────────────────────────

    def __init__(
        self,
        name: str = "onebot_v11",
        access_token: str = "",
        forward_ws_enabled: bool = False,
        forward_ws_url: str = "",
        reconnect_interval: float = 5,
        heartbeat_interval: int = 30,
    ):
        super().__init__(name, "OneBot v11")
        self.access_token = access_token
        self.forward_ws_enabled = forward_ws_enabled
        self.forward_ws_url = forward_ws_url
        self.reconnect_interval = reconnect_interval
        self.heartbeat_interval = heartbeat_interval

        # reverse WS clients (NapCat -> Qtine)
        self._reverse_clients: Dict[str, Any] = {}
        self._reverse_lock = threading.Lock()

        # forward WS client (Qtine -> NapCat)
        self._forward_ws: Optional[websocket.WebSocket] = None
        self._forward_sid: Optional[str] = None
        self._forward_thread: Optional[threading.Thread] = None
        self._forward_write_lock = threading.Lock()

        # pending API calls  (echo -> Event)
        self._pending: Dict[str, threading.Event] = {}
        self._pending_results: Dict[str, Any] = {}
        self._pending_lock = threading.Lock()

        self._bot_info: Dict[str, str] = {}
        self._echo_counter: int = 0
        self._echo_lock = threading.Lock()
        self._stop_event = threading.Event()

    # ── start / stop ─────────────────────────────────────────────────

    def start(self) -> None:
        self.logger.info(f"[{self.name}] Adapter starting ...")
        self._update_status(AdapterStatus.CONNECTING)
        self._running = True
        self._stop_event.clear()
        self._load_cached_bot_info()

        if self.forward_ws_enabled and self.forward_ws_url:
            self._forward_thread = threading.Thread(
                target=self._forward_loop,
                name="qtine-fwd-ws",
                daemon=True,
            )
            self._forward_thread.start()
            self.logger.info(
                f"[{self.name}] Forward WS -> {self.forward_ws_url}"
            )

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

        with self._reverse_lock:
            clients = list(self._reverse_clients.values())
            self._reverse_clients.clear()
        for ws in clients:
            try:
                ws.close()
            except Exception:
                pass

        try:
            if self._forward_ws:
                self._forward_ws.close()
        except Exception:
            pass

        self._release_all_pending()
        self._adapter_info.connected_at = 0.0
        self._update_status(AdapterStatus.DISCONNECTED)
        self.logger.info(f"[{self.name}] Adapter stopped")

    # ── auth ─────────────────────────────────────────────────────────

    def is_authorized(
        self, headers: Mapping[str, str], query_string: str = ""
    ) -> bool:
        if not self.access_token:
            return True
        auth = headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip() == self.access_token
        q = parse_qs(query_string).get("access_token", [""])[0]
        return q == self.access_token

    # ── HTTP API (OneBot V11 REST) ───────────────────────────────────

    def handle_http_action(self, action: str, params: dict) -> dict:
        """Handle an HTTP API call directly (no WS echo needed)."""
        return self._call_api_sync(action, params)

    def _call_api_sync(self, action: str, params: dict) -> dict:
        """Call API via WebSocket, block until response.

        Returns a OneBot response dict:
          {"status": "ok", "retcode": 0, "data": {...}}
        or
          {"status": "failed", "retcode": -1, "data": {}}
        """
        echo = self._next_echo()
        payload = {"action": action, "params": params, "echo": echo}
        ev = threading.Event()
        with self._pending_lock:
            self._pending[echo] = ev
        try:
            if not self._send_raw(payload):
                return {
                    "status": "failed",
                    "retcode": -1,
                    "msg": "No connection",
                    "data": {},
                }
            if not ev.wait(timeout=10):
                self._adapter_info.error_count += 1
                return {
                    "status": "failed",
                    "retcode": -1,
                    "msg": "Timeout",
                    "data": {},
                }
            with self._pending_lock:
                result = self._pending_results.pop(echo, None)
            if result is None:
                return {
                    "status": "failed",
                    "retcode": -1,
                    "msg": "No response",
                    "data": {},
                }
            return result
        finally:
            with self._pending_lock:
                self._pending.pop(echo, None)
                self._pending_results.pop(echo, None)

    # ── serve reverse WS connection ──────────────────────────────────

    def serve(self, ws: Any, environ: Mapping[str, Any]) -> None:
        sid = uuid.uuid4().hex
        self._register_reverse_client(sid, ws)
        self.logger.info(f"[{self.name}] Reverse WS serving: {sid}")
        # Fetch bot info in a background thread to avoid blocking
        # the receive loop (the API response arrives via ws.receive()).
        threading.Thread(
            target=self._fetch_bot_info, daemon=True
        ).start()
        try:
            while self._running:
                raw = ws.receive()
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    self._adapter_info.error_count += 1
                    self.logger.warning(
                        f"[{self.name}] Invalid JSON frame"
                    )
                    continue
                if not isinstance(data, dict):
                    self._adapter_info.error_count += 1
                    continue
                pt = data.get("post_type", "api_response")
                if pt == "message":
                    mt = data.get("message_type", "?")
                    sid_val = data.get("sender", {})
                    sn = sid_val.get("nickname", "?") if isinstance(
                        sid_val, dict
                    ) else "?"
                    raw_msg = data.get("raw_message", "")
                    self.logger.info(
                        f"[{self.name}] << {mt} from {sn}: "
                        f"{str(raw_msg)[:150]}"
                    )
                self._dispatch(sid, data)
        except Exception as e:
            if self._running:
                self.logger.warning(
                    f"[{self.name}] WS serve error: {e}"
                )
        finally:
            self._deregister_reverse_client(sid)

    def _fetch_bot_info(self) -> None:
        """Proactively call get_login_info after connection."""
        result = self._call_api_sync("get_login_info", {})
        if result.get("status") == "ok":
            data = result.get("data", {})
            self_id = str(data.get("user_id", data.get("self_id", "")))
            nickname = str(data.get("nickname", ""))
            if self_id:
                self._bot_info["self_id"] = self_id
            if nickname:
                self._bot_info["nickname"] = nickname
            self._update_status(AdapterStatus.CONNECTED, self_id)
            self._cache_bot_info()
            self.logger.info(f"[{self.name}] Bot info: {self_id} ({nickname})")
        else:
            self.logger.warning(
                f"[{self.name}] Failed to fetch bot info"
            )

    def _cache_bot_info(self) -> None:
        """Persist bot info to storage so it survives restarts."""
        if self.bot and hasattr(self.bot, "storage"):
            self.bot.storage.set("onebot_bot_info", {
                "self_id": self._bot_info.get("self_id", ""),
                "nickname": self._bot_info.get("nickname", ""),
            })

    def _load_cached_bot_info(self) -> None:
        """Load cached bot info from storage."""
        if self.bot and hasattr(self.bot, "storage"):
            cached = self.bot.storage.get("onebot_bot_info", {})
            if cached and cached.get("self_id"):
                self._bot_info["self_id"] = cached["self_id"]
                self._bot_info["nickname"] = cached.get("nickname", "")
                self._adapter_info.account_id = cached["self_id"]
                self.logger.info(
                    f"[{self.name}] Loaded cached bot info: "
                    f"{cached['self_id']}"
                )

    def _forward_headers(self) -> Dict[str, str]:
        """Return headers for forward WS connection."""
        headers: Dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    # ── forward WS loop ──────────────────────────────────────────────

    def _forward_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                ws = websocket.create_connection(
                    self.forward_ws_url,
                    header=self._forward_headers(),
                    timeout=10,
                )
                self._forward_ws = ws
                sid = f"fwd-{uuid.uuid4().hex}"
                self._forward_sid = sid
                self._register_forward_client(sid)
                self._fetch_bot_info()
                self._read_forward_loop(sid, ws)
            except Exception as e:
                if self._running:
                    self._adapter_info.error_count += 1
                    self.logger.warning(
                        f"[{self.name}] Forward WS error: {e}"
                    )
            finally:
                self._forward_ws = None
                self._forward_sid = None
                self._deregister_forward_client()
            if self._running:
                self._stop_event.wait(self.reconnect_interval)

    def _read_forward_loop(self, sid: str, ws) -> None:
        while self._running:
            try:
                raw = ws.recv()
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                self._dispatch(sid, data)
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break

    # ── client tracking ──────────────────────────────────────────────

    def _register_reverse_client(self, sid: str, ws) -> None:
        with self._reverse_lock:
            self._reverse_clients[sid] = ws
            first = len(self._reverse_clients) == 1
        if first:
            self._adapter_info.connected_at = time.time()
        self._update_status(AdapterStatus.CONNECTED)
        self.logger.info(f"[{self.name}] Reverse client connected: {sid}")

    def _deregister_reverse_client(self, sid: str) -> None:
        with self._reverse_lock:
            self._reverse_clients.pop(sid, None)
            alive = bool(self._reverse_clients)
        if not alive and not self._forward_ws:
            self._adapter_info.connected_at = 0.0
            self._update_status(
                AdapterStatus.CONNECTING
                if self._running
                else AdapterStatus.DISCONNECTED
            )
        self._release_all_pending()
        self.logger.info(
            f"[{self.name}] Reverse client disconnected: {sid}"
        )

    def _register_forward_client(self, sid: str) -> None:
        self._adapter_info.connected_at = time.time()
        self._update_status(AdapterStatus.CONNECTED)
        self.logger.info(f"[{self.name}] Forward WS connected: {sid}")

    def _deregister_forward_client(self) -> None:
        with self._reverse_lock:
            has_reverse = bool(self._reverse_clients)
        if not has_reverse:
            self._adapter_info.connected_at = 0.0
            self._update_status(
                AdapterStatus.CONNECTING
                if self._running
                else AdapterStatus.DISCONNECTED
            )
        self._release_all_pending()

    # ── dispatch ─────────────────────────────────────────────────────

    def _dispatch(self, sid: str, data: dict) -> None:
        # API response (has echo, no post_type)
        if "echo" in data and "post_type" not in data:
            self._handle_response(data)
            return

        post_type = data.get("post_type", "")

        if post_type == "meta_event":
            self._handle_meta(data)
        elif post_type == "message":
            self._handle_message(data)
        elif post_type == "notice":
            self._emit_event("notice", data)
        elif post_type == "request":
            self._emit_event("request", data)

    def handle_message(self, sid: str, data: dict) -> None:
        """Public alias for _dispatch (used by tests)."""
        self._dispatch(sid, data)

    # ── meta event ───────────────────────────────────────────────────

    def _handle_meta(self, data: dict) -> None:
        meta_type = data.get("meta_event_type", "")
        if meta_type == "lifecycle":
            self_id = str(data.get("self_id", ""))
            self._bot_info["self_id"] = self_id
            self._update_status(AdapterStatus.CONNECTED, self_id)
            self.logger.info(f"[{self.name}] Bot online: {self_id}")
        elif meta_type == "heartbeat":
            self._send_heartbeat_response(data)
        self._emit_event("meta_event", data)

    def _send_heartbeat_response(self, data: dict) -> None:
        echo = data.get("echo")
        if echo is None:
            return
        resp = {"status": "ok", "retcode": 0, "data": {}, "echo": echo}
        self._send_raw(resp)

    # ── message event ────────────────────────────────────────────────

    def _handle_message(self, data: dict) -> None:
        sender_data = data.get("sender") or {}
        message_type = data.get("message_type", "private")

        sender = Sender(
            user_id=str(
                sender_data.get("user_id", data.get("user_id", ""))
            ),
            nickname=str(sender_data.get("nickname", "")),
            role=str(sender_data.get("role", "member")),
            card=str(sender_data.get("card", "")),
        )

        message = Message(
            adapter=self.name,
            type=message_type,
            content=self._normalize(
                data.get("message", data.get("raw_message", ""))
            ),
            sender=sender,
            group_id=str(data.get("group_id", ""))
            if message_type == "group"
            else None,
            raw=data,
            message_id=str(data.get("message_id", "")),
            timestamp=float(data.get("time", time.time())),
        )

        self._adapter_info.received_count += 1
        self._adapter_info.message_count += 1

        threading.Thread(
            target=self._emit_message, args=(message,), daemon=True
        ).start()

    # ── message normalisation (CQ codes) ─────────────────────────────

    @staticmethod
    def _normalize(value: Any) -> str:
        """Convert OneBot message (str or array) into CQ-code string."""
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return str(value or "")
        parts: List[str] = []
        for seg in value:
            if not isinstance(seg, dict):
                parts.append(str(seg))
                continue
            t = str(seg.get("type", ""))
            d = seg.get("data") or {}
            if t == "text":
                parts.append(str(d.get("text", "")))
            elif t:
                params = ",".join(
                    f"{k}={OneBotV11Adapter._esc(v)}"
                    for k, v in d.items()
                )
                parts.append(
                    f"[CQ:{t}{',' if params else ''}{params}]"
                )
        return "".join(parts)

    @staticmethod
    def _esc(v: Any) -> str:
        return (
            str(v)
            .replace("&", "&")
            .replace("[", "&#91;")
            .replace("]", "&#93;")
            .replace(",", "&#44;")
        )

    # ── API response handling ────────────────────────────────────────

    def _handle_response(self, data: dict) -> None:
        echo = str(data.get("echo", ""))
        with self._pending_lock:
            ev = self._pending.get(echo)
            if ev:
                self._pending_results[echo] = data
                ev.set()

    # ── send API call (internal with echo + Event) ───────────────────

    def _call_api(
        self, action: str, params: dict, timeout: float = 10
    ) -> Optional[dict]:
        echo = self._next_echo()
        payload = {"action": action, "params": params, "echo": echo}
        ev = threading.Event()
        with self._pending_lock:
            self._pending[echo] = ev
        try:
            if not self._send_raw(payload):
                return None
            if not ev.wait(timeout=timeout):
                self.logger.warning(
                    f"[{self.name}] API timeout: {action}"
                )
                self._adapter_info.error_count += 1
                return None
            with self._pending_lock:
                result = self._pending_results.pop(echo, None)
            return result
        finally:
            with self._pending_lock:
                self._pending.pop(echo, None)
                self._pending_results.pop(echo, None)

    # ── send raw frame ───────────────────────────────────────────────

    def _send_raw(self, data: dict) -> bool:
        frame = json.dumps(data, ensure_ascii=False)
        with self._reverse_lock:
            ws = next(iter(self._reverse_clients.values()), None)
        if ws is not None:
            try:
                ws.send(frame)
                return True
            except Exception:
                pass
        if self._forward_ws:
            with self._forward_write_lock:
                try:
                    self._forward_ws.send(frame)
                    return True
                except Exception as e:
                    self.logger.error(
                        f"[{self.name}] Forward send error: {e}"
                    )
        self.logger.warning(f"[{self.name}] No active connection")
        return False

    # ── public send_message ──────────────────────────────────────────

    def send_message(
        self,
        target: str,
        message: str,
        message_type: str = "group",
    ) -> bool:
        try:
            target_id = int(target)
        except (TypeError, ValueError):
            self._adapter_info.error_count += 1
            self.logger.error(f"[{self.name}] Invalid target: {target}")
            return False

        action = (
            "send_group_msg"
            if message_type == "group"
            else "send_private_msg"
        )
        id_key = "group_id" if message_type == "group" else "user_id"
        self.logger.info(
            f"[{self.name}] >> {action} target={target_id}: "
            f"{str(message)[:150]}"
        )
        result = self._call_api(
            action, {id_key: target_id, "message": message}
        )
        if result and result.get("status") == "ok":
            self._adapter_info.sent_count += 1
            self._adapter_info.message_count += 1
            return True
        self.logger.error(
            f"[{self.name}] Send failed: {result}"
        )
        self._adapter_info.error_count += 1
        return False

    # ── helpers ──────────────────────────────────────────────────────

    def _next_echo(self) -> str:
        with self._echo_lock:
            self._echo_counter += 1
            return f"qtine_{self._echo_counter}_{int(time.time() * 1000)}"

    def _release_all_pending(self) -> None:
        with self._pending_lock:
            events = list(self._pending.values())
        for ev in events:
            ev.set()

    @property
    def bot_qq(self) -> str:
        return self._bot_info.get("self_id", "")

    @property
    def bot_nickname(self) -> str:
        return self._bot_info.get("nickname", "")
