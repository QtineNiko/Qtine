import json
import threading
import time
import unittest
from unittest.mock import patch

from qtine.adapters.onebot_v11 import OneBotV11Adapter
from qtine.utils.models import AdapterStatus


class FakeWebSocket:
    def __init__(self, adapter=None):
        self.adapter = adapter
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)
        payload = json.loads(data)
        if self.adapter:
            self.adapter.handle_message("client", {
                "status": "ok",
                "retcode": 0,
                "data": {"message_id": 1},
                "echo": payload["echo"],
            })

    def close(self):
        self.closed = True


class OneBotV11AdapterTests(unittest.TestCase):
    def test_authorization_supports_bearer_and_query_token(self):
        adapter = OneBotV11Adapter(access_token="secret")
        self.assertTrue(adapter.is_authorized({"Authorization": "Bearer secret"}))
        self.assertTrue(adapter.is_authorized({}, "access_token=secret"))
        self.assertFalse(adapter.is_authorized({"Authorization": "Bearer wrong"}))
        self.assertFalse(adapter.is_authorized({}, "access_token=wrong"))

    def test_empty_token_allows_connection(self):
        self.assertTrue(OneBotV11Adapter().is_authorized({}))

    def test_forward_connection_uses_bearer_token(self):
        adapter = OneBotV11Adapter(
            access_token="secret",
            forward_ws_enabled=True,
            forward_ws_url="ws://127.0.0.1:3001",
        )
        self.assertEqual(
            adapter._forward_headers(),
            {"Authorization": "Bearer secret"},
        )

    def test_forward_client_connects_and_processes_frames(self):
        adapter = OneBotV11Adapter(
            forward_ws_enabled=True,
            forward_ws_url="ws://127.0.0.1:3001",
            reconnect_interval=0.01,
        )

        class ForwardWebSocket(FakeWebSocket):
            def __init__(self):
                super().__init__()
                self.frames = [json.dumps({
                    "post_type": "meta_event",
                    "meta_event_type": "lifecycle",
                    "self_id": 10001,
                })]

            def recv(self):
                if self.frames:
                    return self.frames.pop(0)
                adapter._running = False
                raise RuntimeError("test connection closed")

        ws = ForwardWebSocket()
        with patch(
            "qtine.adapters.onebot_v11.websocket.create_connection",
            return_value=ws,
        ), patch.object(adapter, "_fetch_bot_info"):
            adapter.start()
            deadline = time.time() + 1
            while adapter.info.account_id != "10001" and time.time() < deadline:
                time.sleep(0.01)
            adapter.stop()

        self.assertEqual(adapter.info.account_id, "10001")
        self.assertTrue(ws.closed)

    def test_normalizes_array_message_segments(self):
        value = [
            {"type": "text", "data": {"text": "hello "}},
            {"type": "at", "data": {"qq": "123"}},
            {"type": "image", "data": {"file": "a,b.png"}},
        ]
        self.assertEqual(
            OneBotV11Adapter.normalize_message(value),
            "hello [CQ:at,qq=123][CQ:image,file=a&#44;b.png]",
        )

    def test_message_is_emitted_without_blocking_receive_loop(self):
        adapter = OneBotV11Adapter()
        received = []
        ready = threading.Event()
        adapter.on_message(lambda message: (received.append(message), ready.set()))
        adapter.handle_message("client", {
            "post_type": "message",
            "message_type": "private",
            "user_id": 42,
            "sender": {"nickname": "tester"},
            "message": [{"type": "text", "data": {"text": "ping"}}],
        })
        self.assertTrue(ready.wait(1))
        self.assertEqual(received[0].content, "ping")
        self.assertEqual(received[0].sender.user_id, "42")
        self.assertEqual(adapter.info.received_count, 1)

    def test_send_waits_for_matching_echo_response(self):
        adapter = OneBotV11Adapter()
        adapter.start()
        ws = FakeWebSocket(adapter)
        adapter.handle_connect("client", ws)
        self.assertTrue(adapter.send_message("123", "hello", "group"))
        payload = json.loads(ws.sent[0])
        self.assertEqual(payload["action"], "send_group_msg")
        self.assertEqual(payload["params"]["group_id"], 123)
        self.assertEqual(adapter.info.sent_count, 1)
        self.assertEqual(adapter.info.status, AdapterStatus.CONNECTED)

    def test_notice_and_request_are_forwarded(self):
        adapter = OneBotV11Adapter()
        events = []
        adapter.on_event(lambda event_type, data: events.append((event_type, data)))
        adapter.handle_message("client", {"post_type": "notice", "notice_type": "group_increase"})
        adapter.handle_message("client", {"post_type": "request", "request_type": "friend"})
        self.assertEqual([event[0] for event in events], ["notice", "request"])


if __name__ == "__main__":
    unittest.main()
