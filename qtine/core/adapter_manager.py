# -*- coding: utf-8 -*-
"""
Adapter manager for Qtine.

Supports:
- Built-in adapters (OneBot V11, etc.)
- Import external adapters from zip packages
"""

import importlib
import importlib.util
import json
import os
import shutil
import sys
import zipfile
from typing import Dict, List, Optional

from qtine.adapters.base import BaseAdapter
from qtine.adapters.onebot_v11 import OneBotV11Adapter
from qtine.utils.logger import get_logger
from qtine.utils.models import AdapterInfo
from qtine.utils.archive import safe_extract_zip, validate_package_name


class AdapterManager:
    _instance: "AdapterManager" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._adapters: Dict[str, BaseAdapter] = {}
        self._adapter_sources: Dict[str, dict] = {}
        self.logger = get_logger()

    # ── registry ────────────────────────────────────────────────────

    def register(self, adapter: BaseAdapter) -> None:
        self._adapters[adapter.name] = adapter
        self.logger.info(f"Adapter registered: {adapter.name}")

    def get(self, name: str) -> Optional[BaseAdapter]:
        return self._adapters.get(name)

    def get_all(self) -> List[BaseAdapter]:
        return list(self._adapters.values())

    def get_all_info(self) -> List[AdapterInfo]:
        return [a.info for a in self._adapters.values()]

    def send_message(
        self,
        adapter_name: str,
        target: str,
        message: str,
        message_type: str = "group",
    ) -> bool:
        adapter = self.get(adapter_name)
        if adapter is None:
            self.logger.error(f"Adapter not found: {adapter_name}")
            return False
        return adapter.send_message(target, message, message_type)

    # ── built-in ─────────────────────────────────────────────────────

    def create_onebot_adapter(self, config: dict, bot=None) -> OneBotV11Adapter:
        adapter = OneBotV11Adapter(
            name="onebot_v11",
            access_token=config.get("access_token", ""),
            forward_ws_enabled=config.get("forward_ws_enabled", False),
            forward_ws_url=config.get("forward_ws_url", ""),
            reconnect_interval=int(config.get("reconnect_interval", 5)),
            heartbeat_interval=int(config.get("heartbeat_interval", 30)),
        )
        adapter.bot = bot
        self.register(adapter)
        return adapter

    # ── start / stop ─────────────────────────────────────────────────

    def start_all(self) -> None:
        for adapter in self._adapters.values():
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
        """
        Import an adapter from a .zip package.

        Expected zip structure:
            adapter.zip
            └── adapter.json          # manifest
            └── adapter.py            # entry  (BaseAdapter subclass)
            └── ... (extra modules)

        adapter.json format:
        {
            "name": "discord",
            "protocol": "Discord",
            "version": "1.0.0",
            "entry": "adapter.py",
            "config": {
                "ws_endpoint": "/discord/ws",
                "port_requirement": null
            }
        }
        """
        self.logger.info(f"Importing adapter from: {zip_path}")

        if not os.path.isfile(zip_path):
            self.logger.error(f"File not found: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()

                # Find adapter.json
                manifest_path = None
                for n in names:
                    if n.endswith("adapter.json") and (
                        n == "adapter.json" or n.count("/") == 1
                    ):
                        manifest_path = n
                        break

                if manifest_path is None:
                    self.logger.error(
                        "adapter.json not found in zip root"
                    )
                    return None

                manifest = json.loads(zf.read(manifest_path).decode("utf-8"))
                adapter_name = manifest.get("name", "")
                if not adapter_name:
                    self.logger.error("Manifest missing 'name'")
                    return None
                adapter_name = validate_package_name(adapter_name)

                # Extract to ./adapters/<name>/
                dest = os.path.join("adapters", adapter_name)
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                os.makedirs(dest, exist_ok=True)
                safe_extract_zip(zf, dest)

                # The real extracted path (may have a wrapper dir)
                actual_dir = dest
                files = os.listdir(dest)
                if len(files) == 1:
                    inner = os.path.join(dest, files[0])
                    if os.path.isdir(inner):
                        actual_dir = inner

                # Import and instantiate
                instance = self._load_from_dir(actual_dir, manifest)
                if instance is None:
                    shutil.rmtree(dest, ignore_errors=True)
                    return None

                self._adapter_sources[adapter_name] = {
                    "type": "zip",
                    "source": zip_path,
                    "extract_to": dest,
                }
                self.register(instance)
                self.logger.info(
                    f"Adapter '{adapter_name}' imported successfully"
                )
                return adapter_name

        except zipfile.BadZipFile:
            self.logger.error(f"Invalid zip file: {zip_path}")
            return None
        except Exception as e:
            self.logger.error(f"Adapter import error: {e}")
            return None

    def import_from_dir(self, dir_path: str) -> Optional[str]:
        """Import adapter from a prepared directory."""
        self.logger.info(f"Importing adapter from directory: {dir_path}")

        manifest_path = os.path.join(dir_path, "adapter.json")
        if not os.path.isfile(manifest_path):
            self.logger.error("adapter.json not found")
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        instance = self._load_from_dir(dir_path, manifest)
        if instance is None:
            return None

        self._adapter_sources[manifest["name"]] = {
            "type": "directory",
            "source": dir_path,
        }
        self.register(instance)
        self.logger.info(
            f"Adapter '{manifest['name']}' imported successfully"
        )
        return manifest["name"]

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
            # Try to find it one level down
            for root, _, files in os.walk(dir_path):
                if entry_file in files:
                    entry_path = os.path.join(root, entry_file)
                    break

        if not os.path.isfile(entry_path):
            self.logger.error(f"Entry file not found: {entry_file}")
            return None

        # Import module
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

            # Find BaseAdapter subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseAdapter)
                    and attr is not BaseAdapter
                ):
                    # Build kwargs from manifest config
                    kwargs = manifest.get("config", {})
                    instance = attr(**kwargs)
                    return instance

            self.logger.error("No BaseAdapter subclass found")
            return None
        except Exception as e:
            self.logger.error(f"Failed to load adapter module: {e}")
            return None
        finally:
            if dir_path in sys.path:
                sys.path.remove(dir_path)

    def remove(self, name: str) -> bool:
        adapter = self._adapters.get(name)
        if adapter is None:
            return False
        if name == "onebot_v11":
            self.logger.warning("Cannot remove built-in onebot_v11 adapter")
            return False
        try:
            adapter.stop()
        except Exception:
            pass
        del self._adapters[name]
        source = self._adapter_sources.pop(name, {})
        if source.get("type") == "zip":
            extract = source.get("extract_to", "")
            if extract and os.path.isdir(extract):
                shutil.rmtree(extract, ignore_errors=True)
        self.logger.info(f"Adapter removed: {name}")
        return True
