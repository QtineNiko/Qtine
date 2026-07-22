# -*- coding: utf-8 -*-
"""Adapter template for Qtine.

Copy this directory and modify to create your own adapter.
Required: Create a subclass of BaseAdapter and implement abstract methods.

Directory structure:
    my_adapter/
        adapter.json    # Manifest file
        adapter.py      # Entry point (this file)
"""

import threading
import time

from qtine.adapters.base import BaseAdapter
from qtine.utils.models import Message, Sender, AdapterStatus


class MyAdapter(BaseAdapter):
    """Custom adapter template.

    Replace 'MyAdapter' with your adapter name.
    Update PROTOCOL_NAME and DESCRIPTION.
    Set _builtin = False for external adapters.
    """

    PROTOCOL_NAME = "My Protocol"
    DESCRIPTION = "My custom adapter description"
    _builtin = False

    def __init__(self, name: str = "", config: dict = None):
        super().__init__(name=name, protocol="my_protocol", config=config)
        # Read config values
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get("base_url", "")
        self._polling = False
        self._thread = None

    def start(self):
        """Start the adapter. Called when user clicks 'Start' or on boot."""
        if self._running:
            return
        self._running = True
        self._update_status(AdapterStatus.CONNECTING)

        # Validate config
        if not self.api_key:
            self.logger.error(f"[{self.name}] api_key not configured")
            self._update_status(AdapterStatus.ERROR)
            return

        # Start connection in background thread
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()
        self.logger.info(f"[{self.name}] Adapter started")

    def stop(self):
        """Stop the adapter. Called when user clicks 'Stop' or on shutdown."""
        if not self._running:
            return
        self._running = False
        self._polling = False
        self._update_status(AdapterStatus.DISCONNECTED)
        self.logger.info(f"[{self.name}] Adapter stopped")

    def send_message(self, target: str, message: str, message_type: str = "group") -> bool:
        """Send a message to target.

        Args:
            target: Chat ID or user ID
            message: Text content
            message_type: 'group' or 'private'

        Returns:
            True if sent successfully
        """
        try:
            # TODO: Implement send logic using your platform's API
            # Example:
            # resp = requests.post(f"{self.base_url}/send", json={"chat": target, "text": message})
            # if resp.status_code == 200:
            #     self._adapter_info.sent_count += 1
            #     return True
            self.logger.info(f"[{self.name}] Would send to {target}: {message}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.name}] Send error: {e}")
            return False

    # ── Internal methods ──────────────────────────────────────────────

    def _connect(self):
        """Main connection loop. Run in background thread."""
        self._polling = True
        while self._polling and self._running:
            try:
                # TODO: Implement your connection logic
                # Examples:
                # - Poll HTTP API for new messages
                # - Connect WebSocket and listen
                # - Run a local server to receive webhooks

                # Example: polling HTTP API
                # messages = self._fetch_messages()
                # for msg in messages:
                #     self._handle_message(msg)

                time.sleep(5)
            except Exception as e:
                self.logger.error(f"[{self.name}] Connection error: {e}")
                if self._running:
                    time.sleep(5)

    def _handle_message(self, raw_data: dict):
        """Convert platform message to Qtine Message and emit."""
        # TODO: Parse your platform's message format
        sender_id = raw_data.get("sender_id", "")
        sender_name = raw_data.get("sender_name", "Unknown")
        content = raw_data.get("content", "")
        chat_id = raw_data.get("chat_id", "")
        is_group = raw_data.get("is_group", False)

        sender = Sender(user_id=sender_id, nickname=sender_name)
        msg = Message(
            adapter=self.name,
            type="group" if is_group else "private",
            content=content,
            sender=sender,
            group_id=chat_id if is_group else None,
            raw=raw_data,
            message_id=str(raw_data.get("message_id", "")),
            timestamp=time.time(),
        )
        self._adapter_info.received_count += 1
        self._adapter_info.message_count += 1
        self._emit_message(msg)
