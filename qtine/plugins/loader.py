# -*- coding: utf-8 -*-
"""Plugin loader - supports loading plugins from zip packages."""

import os
import sys
import json
import zipfile
import tempfile
import shutil
import importlib
import importlib.util
from typing import Optional, Dict, Any, List
from qtine.plugins.base import BasePlugin
from qtine.utils.logger import get_logger


class PluginPackage:
    """Represents a plugin package loaded from zip or directory."""

    def __init__(self, path: str):
        self.path = path
        self.manifest: Dict[str, Any] = {}
        self.requirements: List[str] = []
        self.entry_module = ""
        self.is_zip = path.endswith(".zip")

    def load_manifest(self) -> bool:
        if self.is_zip:
            return self._load_from_zip()
        return self._load_from_dir()

    def _load_from_dir(self) -> bool:
        manifest_path = os.path.join(self.path, "package.json")
        if not os.path.isfile(manifest_path):
            return False
        with open(manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)
        self._parse_manifest()
        return True

    def _load_from_zip(self) -> bool:
        with zipfile.ZipFile(self.path, "r") as zf:
            file_list = zf.namelist()
            for name in file_list:
                if name.endswith("package.json") and (
                    name == "package.json" or name.count("/") == 1
                ):
                    self.manifest = json.loads(zf.read(name).decode("utf-8"))
                    self._parse_manifest()
                    return True
        return False

    def _parse_manifest(self):
        self.entry_module = self.manifest.get("main", "main.py")
        if self.entry_module.endswith(".py"):
            self.entry_module = self.entry_module[:-3]
        reqs = self.manifest.get("requirements", [])
        if isinstance(reqs, list):
            self.requirements = reqs

    def install_requirements(self) -> bool:
        if not self.requirements:
            return True
        logger = get_logger()
        import subprocess
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *self.requirements],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                logger.info(f"Dependencies installed: {self.requirements}")
                return True
            logger.error(f"Dependency install failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Dependency install error: {e}")
            return False

    def extract_to(self, dest_dir: str) -> str:
        """Extract zip to destination directory, return plugin root path."""
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(self.path, "r") as zf:
            zf.extractall(dest_dir)
        root_dir = self.manifest.get("name", "plugin")
        full_path = os.path.join(dest_dir, root_dir)
        if not os.path.isdir(full_path):
            files = os.listdir(dest_dir)
            if len(files) == 1 and os.path.isdir(os.path.join(dest_dir, files[0])):
                full_path = os.path.join(dest_dir, files[0])
        return full_path


class PluginLoader:
    """Loads plugin modules from directory or zip package."""

    def __init__(self):
        self.logger = get_logger()

    def load_from_dir(self, plugin_dir: str) -> Optional[BasePlugin]:
        """Load a plugin from an extracted directory."""
        pkg = PluginPackage(plugin_dir)
        if not pkg.load_manifest():
            self.logger.error(f"No package.json found in {plugin_dir}")
            return None

        module = self._import_module(plugin_dir, pkg)
        if module is None:
            return None
        return self._find_plugin_class(module)

    def load_from_zip(self, zip_path: str, extract_dir: str) -> Optional[BasePlugin]:
        """Load a plugin from a zip package."""
        pkg = PluginPackage(zip_path)
        if not pkg.load_manifest():
            self.logger.error(f"No package.json found in {zip_path}")
            return None

        pkg.install_requirements()

        plugin_path = pkg.extract_to(extract_dir)
        self.logger.info(f"Extracted plugin to: {plugin_path}")

        module = self._import_module(plugin_path, pkg)
        if module is None:
            shutil.rmtree(plugin_path, ignore_errors=True)
            return None
        return self._find_plugin_class(module)

    def _import_module(self, plugin_dir: str, pkg: PluginPackage):
        """Import the main module of a plugin."""
        sys.path.insert(0, plugin_dir)

        main_name = pkg.entry_module
        main_file = os.path.join(plugin_dir, f"{main_name}.py")

        if not os.path.isfile(main_file):
            sys.path.pop(0)
            self.logger.error(f"Entry file not found: {main_file}")
            return None

        module_name = f"qtine_plugin_{pkg.manifest.get('name', main_name)}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, main_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {main_file}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            self.logger.error(f"Failed to import plugin module: {e}")
            return None
        finally:
            if plugin_dir in sys.path:
                sys.path.remove(plugin_dir)

    def _find_plugin_class(self, module) -> Optional[BasePlugin]:
        """Find BasePlugin subclass in module."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                    issubclass(attr, BasePlugin) and
                    attr is not BasePlugin):
                return attr
        self.logger.error("No BasePlugin subclass found in module")
        return None
