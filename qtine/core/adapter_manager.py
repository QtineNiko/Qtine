# -*- coding: utf-8 -*-
"""
Adapter manager for Qtine.

Supports:
- Multi-instance adapters
- Enable/disable control
- Config persistence
- Built-in adapters (OneBot V11, Telegram, Discord)
- External adapters from zip packages
"""

import importlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import zipfile
from typing import Dict, List, Optional

from qtine.adapters.base import BaseAdapter
from qtine.utils.logger import get_logger
from qtine.utils.models import AdapterInfo, AdapterStatus
from qtine.utils.archive import safe_extract_zip, validate_package_name


class AdapterManager:
    """Manage multiple adapter instances with config persistence."""

    def __init__(self, storage=None):
        self._adapters: Dict[str, BaseAdapter] = {}
        self._adapter_classes: Dict[str, type] = {}
        self._config: List[dict] = []
        self.logger = get_logger()
        self.storage = storage
        self._lock = threading.RLock()
        self._register_builtin_adapters()
        self._load_config()

    def _register_builtin_adapters(self):
        """Register built-in adapter classes."""
        try:
            from qtine.adapters.onebot_v11 import OneBotV11Adapter
            self._adapter_classes["onebot_v11"] = OneBotV11Adapter
        except Exception as e:
            self.logger.warning(f"Failed to load OneBot V11 adapter: {e}")

        try:
            from qtine.adapters.telegram import TelegramAdapter
            self._adapter_classes["telegram"] = TelegramAdapter
        except Exception as e:
            self.logger.warning(f"Failed to load Telegram adapter: {e}")

        try:
            from qtine.adapters.discord import DiscordAdapter
            self._adapter_classes["discord"] = DiscordAdapter
        except Exception as e:
            self.logger.warning(f"Failed to load Discord adapter: {e}")

    def _load_config(self):
        """Load adapter configs from storage and restore instances."""
        if self.storage is None:
            return
        try:
            configs = self.storage.get("adapters_config", [])
            self._config = configs
            for cfg in configs:
                self._restore_instance(cfg)
        except Exception:
            self._config = []

    def _restore_instance(self, cfg: dict):
        """Restore an adapter instance from saved config."""
        protocol = cfg.get("protocol")
        name = cfg.get("name")
        if not protocol or not name:
            return
        adapter_cls = self._adapter_classes.get(protocol)
        if adapter_cls is None:
            self.logger.warning(f"Cannot restore adapter {name}: protocol '{protocol}' not available")
            return
        try:
            instance = adapter_cls(name=name, config=cfg.get("config", {}))
            instance._adapter_info.id = cfg.get("id", instance._adapter_info.id)
            instance._adapter_info.protocol = protocol
            instance._adapter_info.remark = cfg.get("remark", "")
            instance._adapter_info.ws_port = cfg.get("ws_port", 0)
            instance._adapter_info.token = cfg.get("token", "")
            instance._adapter_info.enabled = cfg.get("enabled", True)
            instance._adapter_info.builtin = cfg.get("builtin", True)
            self._adapters[name] = instance
            self.logger.info(f"Adapter restored: {name} ({protocol})")
        except Exception as e:
            self.logger.error(f"Failed to restore adapter {name}: {e}")

    def _save_config(self):
        """Save adapter configs to storage."""
        if self.storage is None:
            return
        try:
            config = []
            for adapter in self._adapters.values():
                info = adapter.info
                config.append({
                    "id": info.id,
                    "name": info.name,
                    "protocol": info.protocol,
                    "enabled": info.enabled,
                    "remark": info.remark,
                    "config": info.config,
                    "ws_port": info.ws_port,
                    "token": info.token,
                    "builtin": info.builtin,
                })
            self.storage.set("adapters_config", config)
            self._config = config
        except Exception as e:
            self.logger.error(f"Failed to save adapter config: {e}")

    def create_adapter(self, protocol: str, name: str = None,
                       config: dict = None, remark: str = "",
                       ws_port: int = 0, token: str = "",
                       enabled: bool = True) -> Optional[BaseAdapter]:
        """Create a new adapter instance."""
        with self._lock:
            adapter_cls = self._adapter_classes.get(protocol)
            if adapter_cls is None:
                self.logger.error(f"Unknown adapter protocol: {protocol}")
                return None

            instance_name = name or f"{protocol}_{len(self._adapters) + 1}"
            cfg = dict(config or {})
            if token:
                cfg["token"] = token

            try:
                instance = adapter_cls(name=instance_name, config=cfg)
                instance._adapter_info.protocol = protocol
                instance._adapter_info.remark = remark
                instance._adapter_info.ws_port = ws_port
                instance._adapter_info.token = token
                instance._adapter_info.enabled = enabled
                instance._adapter_info.builtin = True
                self._adapters[instance_name] = instance
                self._save_config()
                self.logger.info(f"Adapter created: {instance_name} ({protocol})")
                return instance
            except Exception as e:
                self.logger.error(f"Failed to create adapter {instance_name}: {e}")
                return None

    def remove(self, name: str) -> bool:
        """Remove an adapter instance."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            try:
                adapter.stop()
            except Exception:
                pass
            del self._adapters[name]
            self._save_config()
            self.logger.info(f"Adapter removed: {name}")
            return True

    def start(self, name: str) -> bool:
        """Start a specific adapter."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            if not adapter.enabled:
                adapter.enabled = True
            try:
                adapter.start()
                self._save_config()
                return True
            except Exception as e:
                self.logger.error(f"Failed to start adapter {name}: {e}")
                return False

    def stop(self, name: str) -> bool:
        """Stop a specific adapter."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            try:
                adapter.stop()
                self._save_config()
                return True
            except Exception as e:
                self.logger.error(f"Failed to stop adapter {name}: {e}")
                return False

    def enable(self, name: str) -> bool:
        """Enable an adapter."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            adapter.enabled = True
            self._save_config()
            return True

    def disable(self, name: str) -> bool:
        """Disable an adapter."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            adapter.enabled = False
            try:
                adapter.stop()
            except Exception:
                pass
            self._save_config()
            return True

    def update_config(self, name: str, config: dict = None,
                      remark: str = None, ws_port: int = None,
                      token: str = None, enabled: bool = None) -> bool:
        """Update adapter config."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter is None:
                return False
            if config is not None:
                adapter.config.update(config)
                adapter._adapter_info.config = adapter.config
            if remark is not None:
                adapter._adapter_info.remark = remark
            if ws_port is not None:
                adapter._adapter_info.ws_port = ws_port
            if token is not None:
                adapter._adapter_info.token = token
            if enabled is not None:
                adapter.enabled = enabled
            self._save_config()
            return True

    def get(self, name: str) -> Optional[BaseAdapter]:
        return self._adapters.get(name)

    def get_all(self) -> List[BaseAdapter]:
        return list(self._adapters.values())

    def get_all_info(self) -> List[AdapterInfo]:
        return [a.info for a in self._adapters.values()]

    def get_builtin_protocols(self) -> List[dict]:
        """Return list of built-in adapter protocols."""
        protocols = []
        for key, cls in self._adapter_classes.items():
            protocols.append({
                "protocol": key,
                "name": getattr(cls, "PROTOCOL_NAME", key),
                "description": getattr(cls, "DESCRIPTION", ""),
            })
        return protocols

    def send_message(
        self,
        adapter_name: str,
        target: str,
        message: str,
        message_type: str = "group",
    ) -> bool:
        adapter = self.get(adapter_name)
        if adapter is None or not adapter.enabled:
            self.logger.error(f"Adapter not found or disabled: {adapter_name}")
            return False
        return adapter.send_message(target, message, message_type)

    def start_all(self) -> None:
        for adapter in self._adapters.values():
            if not adapter.enabled:
                continue
            try:
                adapter.start()
            except Exception as e:
                self.logger.error(
                    f"Failed to start adapter [{adapter.name}]: {e}"
                )

    def stop_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                adapter.stop()
            except Exception as e:
                self.logger.error(
                    f"Failed to stop adapter [{adapter.name}]: {e}"
                )

    # ── external adapter import ──────────────────────────────────────

    def import_from_zip(self, zip_path: str) -> Optional[str]:
        """Import an adapter from a .zip package."""
        self.logger.info(f"Importing adapter from: {zip_path}")

        if not os.path.isfile(zip_path):
            self.logger.error(f"File not found: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                manifest_path = None
                for n in names:
                    if n.endswith("adapter.json") and (
                        n == "adapter.json" or n.count("/") == 1
                    ):
                        manifest_path = n
                        break

                if manifest_path is None:
                    self.logger.error("adapter.json not found in zip root")
                    return None

                manifest = json.loads(zf.read(manifest_path).decode("utf-8"))
                adapter_name = manifest.get("name", "")
                if not adapter_name:
                    self.logger.error("Manifest missing 'name'")
                    return None
                adapter_name = validate_package_name(adapter_name)

                dest = os.path.join("adapters", adapter_name)
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                os.makedirs(dest, exist_ok=True)
                safe_extract_zip(zf, dest)

                actual_dir = dest
                files = os.listdir(dest)
                if len(files) == 1:
                    inner = os.path.join(dest, files[0])
                    if os.path.isdir(inner):
                        actual_dir = inner

                instance = self._load_from_dir(actual_dir, manifest)
                if instance is None:
                    shutil.rmtree(dest, ignore_errors=True)
                    return None

                self.logger.info(
                    f"External adapter '{adapter_name}' imported successfully"
                )
                return adapter_name

        except zipfile.BadZipFile:
            self.logger.error(f"Invalid zip file: {zip_path}")
            return None
        except Exception as e:
            self.logger.error(f"Adapter import error: {e}")
            return None

    def _load_from_dir(
        self, dir_path: str, manifest: dict
    ) -> Optional[BaseAdapter]:
        entry_file = manifest.get("entry", "adapter.py")
        entry_parts = entry_file.replace("\\", "/").split("/")
        if (
            os.path.isabs(entry_file)
            or ".." in entry_parts
            or not entry_file.endswith(".py")
        ):
            self.logger.error("Invalid adapter entry path")
            return None
        entry_path = os.path.join(dir_path, *entry_parts)
        if not os.path.isfile(entry_path):
            for root, _, files in os.walk(dir_path):
                if entry_file in files:
                    entry_path = os.path.join(root, entry_file)
                    break

        if not os.path.isfile(entry_path):
            self.logger.error(f"Entry file not found: {entry_file}")
            return None

        sys.path.insert(0, dir_path)
        try:
            module_name = f"qtine_adapter_{manifest.get('name', 'ext')}"
            spec = importlib.util.spec_from_file_location(
                module_name, entry_path
            )
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseAdapter)
                    and attr is not BaseAdapter
                ):
                    kwargs = manifest.get("config", {})
                    instance = attr(**kwargs)
                    instance._adapter_info.builtin = False
                    return instance

            self.logger.error("No BaseAdapter subclass found")
            return None
        except Exception as e:
            self.logger.error(f"Failed to load adapter module: {e}")
            return None
        finally:
            if dir_path in sys.path:
                sys.path.remove(dir_path)
