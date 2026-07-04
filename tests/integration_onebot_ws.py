import json
import os
import subprocess
import sys
import time
import urllib.request

import yaml
from simple_websocket import Client


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wait_for_health(url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.load(response)
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Qtine did not become healthy")


def main():
    with open(os.path.join(ROOT, "config.yml"), encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    port = config["server"]["port"]
    onebot = config["adapters"]["onebot_v11"]
    path = onebot.get("ws_path", "/onebot/v11")
    token = onebot.get("access_token", "")
    url = f"ws://127.0.0.1:{port}{path}"
    if token:
        url += f"?access_token={token}"

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation_flags,
    )
    try:
        health = wait_for_health(f"http://127.0.0.1:{port}/health")
        assert health["status"] == "ok"
        ws = Client.connect(url)
        ws.send(json.dumps({
            "time": int(time.time()),
            "self_id": 10001,
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }))
        time.sleep(0.2)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/adapters", timeout=2
        ) as response:
            adapters = json.load(response)
        assert adapters[0]["account_id"] == "10001"
        assert adapters[0]["status"] == "connected"
        ws.close()
        print("HTTP health, native WebSocket handshake, and lifecycle event: OK")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
