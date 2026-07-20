# -*- coding: utf-8 -*-
"""
Plugin manager for Qtine.

Supports:
- Built-in plugins
- External plugins from zip (standard format)
- External plugins from directory (standard format)

Zip plugin structure:
    plugin.zip
    ├── main.py          # entry file (contains BasePlugin subclass)
    ├── data.json        # plugin metadata
    ├── icon.png         # optional icon
    └── command/         # optional command modules
        ├── cmd1.py
        └── ...

Directory plugin structure:
    插件名/
    ├── main.py
    ├── data.json
    ├── icon.png         # optional
    └── command/
        ├── cmd1.py
        └── ...
"""

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from typing import Dict, List, Optional

from qtine.plugins.base import BasePlugin
from qtine.utils.logger import get_logger
from qtine.utils.models import PluginInfo, PluginType
from qtine.utils.archive import safe_extract_zip, validate_package_name


class PluginManager:
    _instance: "PluginManager" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_sources: Dict[str, dict] = {}
        self._plugin_dir = "./plugins"
        self.logger = get_logger()
        self.bot = None
        self.allow_dependency_install = False
        self._index_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._indexes_dirty = True
        self._command_index = {}
        self._max_command_tokens = 0
        self._regex_index = []
        self._keyword_index = []
        self._listener_index = []
    def set_bot(self, bot):
        self.bot = bot
        self.allow_dependency_install = bool(
            bot.config.get("plugins.allow_dependency_install", False)
        )

    def set_plugin_dir(self, path: str):
        self._plugin_dir = path
        os.makedirs(path, exist_ok=True)

    def _mark_indexes_dirty(self) -> None:
        with self._index_lock:
            self._indexes_dirty = True

    def _ensure_indexes(self) -> None:
        with self._index_lock:
            if not self._indexes_dirty:
                return
            command_index = {}
            max_command_tokens = 0
            regex_index = []
            keyword_index = []
            listener_index = []
            for plugin in self._plugins.values():
                if not plugin.enabled:
                    continue
                for command, aliases, permission, handler in (
                    plugin.get_all_command_handlers()
                ):
                    for name in [command, *(aliases or [])]:
                        key = tuple(str(name).strip().split())
                        if key:
                            command_index.setdefault(key, []).append(
                                (plugin, handler, permission)
                            )
                            max_command_tokens = max(
                                max_command_tokens, len(key)
                            )
                for pattern, handler in plugin.get_all_regex_handlers():
                    regex_index.append((plugin, pattern, handler))
                for keywords, handler in plugin.get_all_keyword_handlers():
                    for keyword in keywords:
                        if keyword:
                            keyword_index.append((plugin, keyword, handler))
                if plugin.has_listeners():
                    listener_index.append(plugin)
            self._command_index = command_index
            self._max_command_tokens = max_command_tokens
            self._regex_index = regex_index
            self._keyword_index = keyword_index
            self._listener_index = listener_index
            self._indexes_dirty = False

    # ── builtin registration ────────────────────────────────────────

    def load_builtin(self, plugin_instance: BasePlugin):
        plugin_instance.plugin_type = PluginType.BUILTIN
        self._register(plugin_instance)

    # ── load from plugins dir (legacy .py + new format) ─────────────

    def load_from_dir(self) -> List[str]:
        """Scan plugins/ directory and load all recognized plugins.

        Plugins with plugin dependencies (depends_on in data.json) are
        loaded in dependency order; if a dependency is missing the
        plugin is skipped with a warning.
        """
        loaded: List[str] = []
        if not os.path.isdir(self._plugin_dir):
            return loaded

        candidates: List[dict] = []

        for item in os.listdir(self._plugin_dir):
            item_path = os.path.join(self._plugin_dir, item)

            # --- Zip plugin ---
            if item.endswith(".zip"):
                try:
                    meta = self._peek_zip_meta(item_path)
                    if meta:
                        candidates.append({
                            "type": "zip",
                            "path": item_path,
                            "meta": meta,
                            "name": meta.get("name", ""),
                            "depends": meta.get("depends_on", []) or [],
                        })
                except Exception as e:
                    self.logger.error(
                        f"Failed to read zip plugin [{item}]: {e}"
                    )
                continue

            # --- Directory plugin (with data.json) ---
            if os.path.isdir(item_path):
                data_json = os.path.join(item_path, "data.json")
                if os.path.isfile(data_json):
                    try:
                        with open(data_json, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        candidates.append({
                            "type": "dir",
                            "path": item_path,
                            "meta": meta,
                            "name": meta.get("name", ""),
                            "depends": meta.get("depends_on", []) or [],
                        })
                    except Exception as e:
                        self.logger.error(
                            f"Failed to read dir plugin [{item}]: {e}"
                        )
                    continue

                # Legacy directory with __init__.py
                init_file = os.path.join(item_path, "__init__.py")
                if os.path.isfile(init_file):
                    candidates.append({
                        "type": "legacy_dir",
                        "path": init_file,
                        "meta": {},
                        "name": item,
                        "depends": [],
                    })
                continue

            # --- Legacy single .py file ---
            if item.endswith(".py") and not item.startswith("_"):
                name = item[:-3]
                candidates.append({
                    "type": "legacy_file",
                    "path": item_path,
                    "meta": {},
                    "name": name,
                    "depends": [],
                })

        # Topological sort by depends_on
        ordered = self._topo_sort(candidates)
        for cand in ordered:
            try:
                if cand["type"] == "zip":
                    result = self.import_from_zip(cand["path"])
                elif cand["type"] == "dir":
                    result = self.import_from_dir(cand["path"])
                elif cand["type"] == "legacy_dir":
                    self._load_legacy_file(cand["path"], cand["name"])
                    result = cand["name"]
                elif cand["type"] == "legacy_file":
                    self._load_legacy_file(cand["path"], cand["name"])
                    result = cand["name"]
                else:
                    result = None
                if result:
                    loaded.append(result)
            except Exception as e:
                self.logger.error(
                    f"Failed to load plugin [{cand['name']}]: {e}"
                )

        return loaded

    def _peek_zip_meta(self, zip_path: str) -> Optional[dict]:
        """Read data.json from a zip without extracting."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                data_entry = next(
                    (n for n in names
                     if n == "data.json" or n.endswith("/data.json")),
                    None
                )
                if not data_entry:
                    return None
                return json.loads(zf.read(data_entry).decode("utf-8"))
        except Exception:
            return None

    def _topo_sort(self, candidates: List[dict]) -> List[dict]:
        """Sort plugins so that dependencies come first.

        Plugins with unmet dependencies are dropped with a warning.
        """
        name_map = {c["name"]: c for c in candidates if c.get("name")}
        builtin_names = {p.name for p in self._plugins.values()}
        result: List[dict] = []
        visited: set = set()
        temp: set = set()

        def visit(name: str) -> bool:
            if name in visited:
                return True
            if name in temp:
                self.logger.warning(
                    f"Circular plugin dependency detected at: {name}"
                )
                return False
            temp.add(name)
            cand = name_map.get(name)
            if cand:
                for dep in cand.get("depends", []) or []:
                    # Built-in plugin counts as satisfied
                    if dep in builtin_names:
                        continue
                    if dep not in name_map:
                        self.logger.warning(
                            f"Plugin '{name}' requires '{dep}' which "
                            f"is not available; skipping"
                        )
                        temp.discard(name)
                        return False
                    if not visit(dep):
                        temp.discard(name)
                        return False
                result.append(cand)
            temp.discard(name)
            visited.add(name)
            return True

        for c in candidates:
            n = c.get("name")
            if n and n not in visited:
                visit(n)
        return result

    # ── zip import (new standard) ───────────────────────────────────

    def import_from_zip(self, zip_path: str) -> Optional[str]:
        """
        Import a plugin from a standard zip package.

        Required:
            main.py       – entry, contains exactly one BasePlugin subclass
            data.json     – plugin metadata

        Optional:
            icon.png      – plugin icon
            command/      – extra command modules
        """
        if not os.path.isfile(zip_path):
            self.logger.error(f"File not found: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()

                # Validate required files exist
                has_main = any(
                    n == "main.py" or n.endswith("/main.py")
                    for n in names
                )
                has_data = any(
                    n == "data.json" or n.endswith("/data.json")
                    for n in names
                )
                if not has_main:
                    self.logger.error("main.py not found in zip root")
                    return None
                if not has_data:
                    self.logger.error("data.json not found in zip root")
                    return None

                # Read data.json to get plugin name
                data_entry = next(
                    n for n in names
                    if n == "data.json" or n.endswith("/data.json")
                )
                meta = json.loads(zf.read(data_entry).decode("utf-8"))
                plugin_name = meta.get("name", "")
                if not plugin_name:
                    self.logger.error("data.json missing 'name'")
                    return None
                plugin_name = validate_package_name(plugin_name)

                # Extract to plugins/<name>/
                dest = os.path.join(self._plugin_dir, plugin_name)
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                os.makedirs(dest, exist_ok=True)
                safe_extract_zip(zf, dest)

                # Handle wrapper directory
                actual_dir = self._resolve_extracted_dir(dest)

            return self._load_plugin(actual_dir, meta, source=zip_path)

        except zipfile.BadZipFile:
            self.logger.error(f"Invalid zip: {zip_path}")
            return None
        except Exception as e:
            self.logger.error(f"Zip import error: {e}")
            return None

    # ── directory import (new standard) ─────────────────────────────

    def import_from_dir(self, dir_path: str) -> Optional[str]:
        """Import a plugin from a directory matching the new format."""
        data_json = os.path.join(dir_path, "data.json")
        if not os.path.isfile(data_json):
            self.logger.error(f"data.json not found in {dir_path}")
            return None

        with open(data_json, "r", encoding="utf-8") as f:
            meta = json.load(f)

        plugin_name = meta.get("name", "")
        if not plugin_name:
            self.logger.error("data.json missing 'name'")
            return None

        return self._load_plugin(dir_path, meta, source=dir_path)

    # ── dependency resolver ─────────────────────────────────────────

    def _install_requires(self, requires: list) -> bool:
        """Install plugin pip dependencies.

        `data.json` may contain:
          "requires": ["requests>=2.28", "Pillow"]

        Returns True if all installed successfully.
        """
        if not requires:
            return True
        self.logger.info(f"Installing dependencies: {requires}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *requires],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self.logger.info("Dependencies installed successfully")
                return True
            self.logger.error(
                f"Dependency install failed:\n{result.stderr}"
            )
            return False
        except subprocess.TimeoutExpired:
            self.logger.error("Dependency install timed out")
            return False
        except Exception as e:
            self.logger.error(f"Dependency install error: {e}")
            return False

    # ── internal loader ─────────────────────────────────────────────

    def _load_plugin(
        self, dir_path: str, meta: dict, source: str
    ) -> Optional[str]:
        plugin_name = meta["name"]

        # Install dependencies if specified
        requires = meta.get("requires", [])
        if isinstance(requires, list) and requires:
            if not self.allow_dependency_install:
                self.logger.error(
                    f"[{plugin_name}] Dependency installation is disabled"
                )
                return None
            if not self._install_requires(requires):
                self.logger.warning(
                    f"[{plugin_name}] Dependency install had errors, "
                    f"plugin may not work correctly"
                )

        # Find main.py
        main_path = os.path.join(dir_path, "main.py")
        if not os.path.isfile(main_path):
            self.logger.error(f"main.py not found in {dir_path}")
            return None

        # Import
        sys.path.insert(0, dir_path)
        try:
            module_name = f"qtine_plugin_{plugin_name}"
            spec = importlib.util.spec_from_file_location(
                module_name, main_path
            )
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find BasePlugin subclass
            instance = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    instance = attr(bot=self.bot)
                    break

            if instance is None:
                self.logger.error(
                    f"No BasePlugin subclass found in main.py of {plugin_name}"
                )
                return None

            # Ensure name matches
            if not instance.name:
                instance.name = plugin_name
            if meta.get("version"):
                instance.version = meta["version"]
            if meta.get("description"):
                instance.description = meta["description"]
            if meta.get("author"):
                instance.author = meta["author"]
            if meta.get("requires"):
                instance.requires = meta["requires"]
            icon_path = self._find_icon(dir_path)
            if icon_path:
                instance.icon = icon_path

            instance.plugin_type = PluginType.EXTERNAL
            self._register(instance)

            self._plugin_sources[instance.name] = {
                "type": "zip" if source.endswith(".zip") else "directory",
                "source": source,
                "extract_to": dir_path,
                "icon": icon_path,
            }

            self.logger.info(
                f"Plugin loaded: {instance.name} v{instance.version}"
            )
            return instance.name

        except Exception as e:
            self.logger.error(f"Plugin load error [{plugin_name}]: {e}")
            return None
        finally:
            if dir_path in sys.path:
                sys.path.remove(dir_path)

    @staticmethod
    def _find_icon(dir_path: str) -> str:
        """Return path to icon.png if it exists."""
        icon = os.path.join(dir_path, "icon.png")
        if os.path.isfile(icon):
            return icon
        return ""

    @staticmethod
    def _resolve_extracted_dir(dest: str) -> str:
        """If zip extracted into a single wrapper dir, use that."""
        files = os.listdir(dest)
        if len(files) == 1:
            inner = os.path.join(dest, files[0])
            if os.path.isdir(inner):
                return inner
        return dest

    # ── legacy loader ───────────────────────────────────────────────

    def _load_legacy_file(self, filepath: str, plugin_name: str):
        """Load old-style .py plugin (backwards compat)."""
        module_name = f"qtine_user_plugin_{plugin_name}"
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {filepath}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                instance = attr(bot=self.bot)
                self._register(instance)
                return
        raise ValueError(f"No BasePlugin subclass found in {filepath}")

    # ── register ────────────────────────────────────────────────────

    def _register(self, plugin: BasePlugin):
        with self._lifecycle_lock:
            old_plugin = self.get(plugin.name)
            if old_plugin is not None and old_plugin is not plugin:
                try:
                    old_plugin.on_disable()
                    old_plugin.on_unload()
                except Exception as e:
                    self.logger.error(
                        f"Plugin [{plugin.name}] replacement error: {e}"
                    )
                finally:
                    try:
                        old_plugin.cleanup()
                    except Exception as e:
                        self.logger.error(
                            f"Plugin [{plugin.name}] replacement cleanup error: {e}"
                        )
            with self._index_lock:
                self._plugins[plugin.name] = plugin
                self._indexes_dirty = True
            try:
                plugin.on_load()
                plugin.on_enable()
            except Exception as e:
                self.logger.error(
                    f"Plugin [{plugin.name}] enable error: {e}"
                )
            self._mark_indexes_dirty()
            if self.bot and getattr(self.bot, "event_bus", None):
                self.bot.event_bus.publish(
                    "plugin.loaded", {"plugin": plugin.name}
                )
            self.logger.info(
                f"Plugin registered: {plugin.name} v{plugin.version}"
            )

    # ── lifecycle ───────────────────────────────────────────────────

    def unload(self, name: str) -> bool:
        with self._lifecycle_lock:
            plugin = self.get(name)
            if plugin is None:
                return False
            if plugin.plugin_type == PluginType.BUILTIN:
                self.logger.warning(f"Cannot unload builtin plugin: {name}")
                return False
            try:
                plugin.on_disable()
                plugin.on_unload()
            except Exception as e:
                self.logger.error(f"Plugin [{name}] unload error: {e}")
            finally:
                try:
                    plugin.cleanup()
                except Exception as e:
                    self.logger.error(f"Plugin [{name}] cleanup error: {e}")
            with self._index_lock:
                if self._plugins.get(name) is not plugin:
                    return False
                del self._plugins[name]
                self._plugin_sources.pop(name, None)
                self._indexes_dirty = True
            self.logger.info(f"Plugin unloaded: {name}")
            return True

    def uninstall(self, name: str) -> bool:
        with self._lifecycle_lock:
            plugin = self.get(name)
            if plugin is None:
                return False
            if plugin.plugin_type == PluginType.BUILTIN:
                self.logger.warning(f"Cannot uninstall builtin plugin: {name}")
                return False
            source = dict(self._plugin_sources.get(name, {}))
            if not self.unload(name):
                return False

            if source.get("type") == "directory":
                plug_path = source.get("source", "")
                if (
                    plug_path
                    and os.path.isdir(plug_path)
                    and plug_path.startswith(self._plugin_dir)
                ):
                    shutil.rmtree(plug_path, ignore_errors=True)
                    self.logger.info(f"Plugin directory removed: {plug_path}")

            return True

    def reload(self, name: str) -> bool:
        with self._lifecycle_lock:
            plugin = self.get(name)
            if plugin is None:
                return False
            if plugin.plugin_type == PluginType.BUILTIN:
                self.logger.warning(f"Cannot reload builtin plugin: {name}")
                return False
            source = dict(self._plugin_sources.get(name, {}))
            if not source:
                return False

            if not self.unload(name):
                return False

            src_path = source.get("source", "")
            src_type = source.get("type", "")
            if src_type == "zip" and os.path.isfile(src_path):
                return bool(self.import_from_zip(src_path))
            if src_type == "directory" and os.path.isdir(src_path):
                return bool(self.import_from_dir(src_path))
            return False

    def enable(self, name: str) -> bool:
        with self._lifecycle_lock:
            plugin = self.get(name)
            if plugin is None:
                return False
            plugin.enabled = True
            try:
                plugin.on_enable()
            except Exception as e:
                self.logger.error(f"Plugin [{name}] enable error: {e}")
            if self.bot and getattr(self.bot, "event_bus", None):
                self.bot.event_bus.publish("plugin.enabled", {"plugin": name})
            return True
    def disable(self, name: str) -> bool:
        with self._lifecycle_lock:
            plugin = self.get(name)
            if plugin is None:
                return False
            plugin.enabled = False
            try:
                plugin.on_disable()
            except Exception as e:
                self.logger.error(f"Plugin [{name}] disable error: {e}")
            if self.bot and getattr(self.bot, "event_bus", None):
                self.bot.event_bus.publish("plugin.disabled", {"plugin": name})
            return True
        return True

    # ── query ───────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[BasePlugin]:
        with self._index_lock:
            return self._plugins.get(name)

    def get_all(self) -> List[BasePlugin]:
        with self._index_lock:
            return list(self._plugins.values())

    def get_all_info(self) -> List[PluginInfo]:
        with self._index_lock:
            plugins = list(self._plugins.values())
        return [p.get_info() for p in plugins]

    def get_enabled(self) -> List[BasePlugin]:
        with self._index_lock:
            return [p for p in self._plugins.values() if p.enabled]

    # ── command dispatch ────────────────────────────────────────────

    def dispatch_message_listeners(self, message) -> None:
        self._ensure_indexes()
        for plugin in tuple(self._listener_index):
            plugin.dispatch_listeners(message)

    def find_command_handler(self, content: str):
        parts = content.strip().split()
        if not parts:
            return None, None, []
        self._ensure_indexes()
        max_length = min(len(parts), self._max_command_tokens)
        for length in range(max_length, 0, -1):
            match = self._command_index.get(tuple(parts[:length]))
            if match:
                plugin, handler, _permission = match[0]
                return plugin, handler, parts[length:]
        return None, None, []

    def find_regex_handler(self, content: str):
        self._ensure_indexes()
        for plugin, pattern, handler in tuple(self._regex_index):
            match = pattern.match(content)
            if match:
                return plugin, handler, match
        return None, None, None

    def find_keyword_handler(self, content: str):
        self._ensure_indexes()
        for plugin, keyword, handler in tuple(self._keyword_index):
            if keyword in content:
                return plugin, handler
        return None, None

    @property
    def count(self) -> int:
        with self._index_lock:
            return len(self._plugins)

    @property
    def enabled_count(self) -> int:
        with self._index_lock:
            return len([p for p in self._plugins.values() if p.enabled])
