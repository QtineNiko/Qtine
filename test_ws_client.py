# -*- coding: utf-8 -*-
"""Simulate a NapCat reverse WS client sending a command message."""
import json
import time
import websocket

WS_URL = "ws://127.0.0.1:4990/onebot/v11"

def main():
    print(f"Connecting to {WS_URL} ...")
    ws = websocket.create_connection(WS_URL, timeout=5)
    print("Connected.")

    # Send a lifecycle event first (like NapCat does on connect)
    lifecycle = {
        "post_type": "meta_event",
        "meta_event_type": "lifecycle",
        "sub_type": "connect",
        "self_id": 3105259061,
        "time": int(time.time()),
        "self_id": 3105259061,
    }
    ws.send(json.dumps(lifecycle))
    print(f">> {json.dumps(lifecycle)[:120]}")

    # Simulate user sending "#help" in a private message.
    # Message as array (OneBot v11 standard) with an @ prefix to test CQ stripping.
    msg = {
        "post_type": "message",
        "message_type": "private",
        "sub_type": "friend",
        "user_id": 1945826346,
        "self_id": 3105259061,
        "message_id": 999001,
        "time": int(time.time()),
        "sender": {
            "user_id": 1945826346,
            "nickname": "TestUser",
        },
        # Array form: @bot then text command
        "message": [
            {"type": "at", "data": {"qq": "3105259061"}},
            {"type": "text", "data": {"text": " #help