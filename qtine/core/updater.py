# -*- coding: utf-8 -*-
"""Qtine 核心更新模块。

功能：
  - 从 GitHub Releases API 获取版本列表
  - 语义版本比较
  - 下载指定版本（支持镜像加速）
  - 备份当前安装
  - 安装/回滚
"""

import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger("qtine.updater")

# 默认 GitHub 加速镜像列表（与 app.py 中的 DEFAULT_GITHUB_MIRRORS 保持一致）
DEFAULT_MIRRORS = [
    "https://github.com",
    "https://ghproxy.com",
    "https://gh.api.99988866.xyz",
    "https://mirror.ghproxy.com",
    "https://gh-proxy.com",
    "https://gh.xcxgw.com",
    "https://ghps.cc",
    "https://gh.d-ai.workers.dev",
    "https://gh.llkk.cc",
    "https://hub.gitmirror.com",
]

# GitHub API 镜像前缀（用于 fetch_releases / 下载等）
# 当直接访问 api.github.com 失败时，依次尝试这些镜像代理
API_MIRRORS = [
    "https://ghproxy.com/",
    "https://gh.api.99988866.xyz/",
    "https://mirror.ghproxy.com/",
    "https://gh-proxy.com/",
    "https://gh.xcxgw.com/",
    "https://ghps.cc/",
    "https://gh.llkk.cc/",
    "https://hub.gitmirror.com/",
]

REPO_OWNER = "QtineNiko"
REPO_NAME = "Qtine"
RELEASES_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
)

# 更新时跳过的路径（用户数据）
SKIP_PATHS = {
    "config.yml",
    "plugins",
    "data",
    "market-index",
    ".git",
    ".deps",
    "__pycache__",
    ".venv",
    "venv",
}

BACKUP_DIR = os.path.join("data", "backup")
MAX_BACKUPS = 5


@dataclass
class ReleaseInfo:
    tag_name: str          # v1.2.0
    name: str              # "v1.2.0 - 新增主题定制"
    body: str              # changelog (markdown)
    published_at: str      # ISO datetime
    prerelease: bool
    assets: list = field(default_factory=list)  # [{name, browser_download_url, size}]
    html_url: str = ""


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """解析版本号字符串为 (major, minor, patch) 元组。"""
    # 移除 v 前缀
    clean = version_str.strip().lstrip("vV")
    # 移除预发布标签
    clean = re.split(r"[-+]", clean)[0]
    parts = clean.split(".")
    nums = []
    for i in range(3):
        try:
            nums.append(int(parts[i]) if i < len(parts) else 0)
        except (ValueError, IndexError):
            nums.append(0)
    return tuple(nums[:3])  # type: ignore


def compare_versions(v1: str, v2: str) -> int:
    """比较两个版本号。返回 1(v1>v2), 0(相等), -1(v1<v2)。"""
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    if p1 > p2:
        return 1
    if p1 < p2:
        return -1
    return 0


def fetch_releases(
    include_prerelease: bool = False,
    github_token: Optional[str] = None,
) -> List[ReleaseInfo]:
    """从 GitHub API 获取所有 Release 列表。

    先尝试直连 api.github.com，失败后依次尝试 API_MIRRORS。
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    urls_to_try = [RELEASES_URL] + [
        m.rstrip("/") + "/" + RELEASES_URL
        for m in API_MIRRORS
    ]

    last_error = None
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            raw = resp.json()
            # 检查是否是有效的 release 列表
            if not isinstance(raw, list):
                logger.warning(f"Unexpected response from {url}: {type(raw)}")
                continue
            logger.info(f"Fetched {len(raw)} releases from {url.split('//')[1].split('/')[0]}")
            break  # 成功，跳出
        except requests.RequestException as e:
            last_error = e
            continue  # 尝试下一个镜像
    else:
        # 所有 URL 都失败
        logger.error(f"Failed to fetch releases from all sources: {last_error}")
        return []

    releases = []
    for r in raw:
        if r.get("draft"):
            continue
        if r.get("prerelease") and not include_prerelease:
            continue
        assets = []
        for a in r.get("assets", []):
            assets.append({
                "name": a.get("name", ""),
                "browser_download_url": a.get("browser_download_url", ""),
                "size": a.get("size", 0),
            })
        releases.append(ReleaseInfo(
            tag_name=r.get("tag_name", ""),
            name=r.get("name", ""),
            body=r.get("body", ""),
            published_at=r.get("published_at", ""),
            prerelease=r.get("prerelease", False),
            assets=assets,
            html_url=r.get("html_url", ""),
        ))

    # 按版本降序
    releases.sort(key=lambda r: parse_version(r.tag_name), reverse=True)
    return releases


def find_update(
    current_version: str,
    include_prerelease: bool = False,
    github_token: Optional[str] = None,
    check_url: Optional[str] = None,
) -> Optional[ReleaseInfo]:
    """检查是否存在比当前版本更新的 Release。

    如果提供了 check_url，优先从该自建服务器端点获取；
    否则从 GitHub API 获取。
    """
    if check_url:
        release = _fetch_from_custom_url(check_url)
        if release and compare_versions(release.tag_name, current_version) > 0:
            return release
        # 自建服务器返回的版本不比当前新，回退到 API 检查
        if release:
            logger.info(
                f"Custom URL returned {release.tag_name}, "
                f"not newer than current {current_version}"
            )
            return None
    releases = fetch_releases(include_prerelease, github_token)
    for r in releases:
        if compare_versions(r.tag_name, current_version) > 0:
            return r
    return None


def _fetch_from_custom_url(url: str) -> Optional[ReleaseInfo]:
    """从自建更新检查服务器获取最新版本信息。

    期望响应格式：
    {"has_update": true, "latest": {"tag_name": "v1.2.0", ...}}
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("has_update") or not data.get("latest"):
            return None
        latest = data["latest"]
        return ReleaseInfo(
            tag_name=latest.get("tag_name", ""),
            name=latest.get("name", ""),
            body=latest.get("body", ""),
            published_at=latest.get("published_at", ""),
            prerelease=latest.get("prerelease", False),
            assets=latest.get("assets", []),
            html_url=latest.get("html_url", ""),
        )
    except Exception as e:
        logger.warning(f"Custom check_url failed: {e}")
        return None


def find_release_by_tag(
    tag: str,
    github_token: Optional[str] = None,
) -> Optional[ReleaseInfo]:
    """按 tag 查找 Release（用于升级/降级到指定版本）。"""
    # 确保 tag 带 v 前缀
    if not tag.startswith("v"):
        tag = f"v{tag}"
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{tag}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        r = resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch release {tag}: {e}")
        return None

    if r.get("draft"):
        return None
    assets = []
    for a in r.get("assets", []):
        assets.append({
            "name": a.get("name", ""),
            "browser_download_url": a.get("browser_download_url", ""),
            "size": a.get("size", 0),
        })
    return ReleaseInfo(
        tag_name=r.get("tag_name", ""),
        name=r.get("name", ""),
        body=r.get("body", ""),
        published_at=r.get("published_at", ""),
        prerelease=r.get("prerelease", False),
        assets=assets,
        html_url=r.get("html_url", ""),
    )


def speed_test_mirror(mirror_url: str) -> float:
    """测试单个镜像延迟（秒），超时或失败返回 999。"""
    test_url = mirror_url.rstrip("/") + f"/{REPO_OWNER}/{REPO_NAME}"
    try:
        start = time.time()
        resp = requests.head(test_url, timeout=5, allow_redirects=True)
        return time.time() - start
    except requests.RequestException:
        return 999.0


def pick_fastest_mirror(mirrors: List[str]) -> str:
    """从镜像列表中选最快的。"""
    best = mirrors[0] if mirrors else "https://github.com"
    best_lat = float("inf")
    for m in mirrors:
        lat = speed_test_mirror(m)
        if lat < best_lat:
            best_lat = lat
            best = m
    return best


def download_release(
    release: ReleaseInfo,
    mirror: Optional[str] = None,
) -> Optional[str]:
    """下载 Release 的 zip 资产到临时文件，返回路径。

    优先尝试：
    1. 名为 qtine.zip / qtine-v*.zip 的资产
    2. 源码 zipball: /archive/refs/tags/<tag>.zip
    """
    # 查找 .zip 资产
    zip_url = None
    for a in release.assets:
        name = a.get("name", "").lower()
        if name.endswith(".zip"):
            zip_url = a.get("browser_download_url", "")
            break

    if not zip_url:
        # 回退到 GitHub 源码 zip
        tag = release.tag_name
        if mirror:
            zip_url = mirror.rstrip("/") + f"/{REPO_OWNER}/{REPO_NAME}/archive/refs/tags/{tag}.zip"
        else:
            zip_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/tags/{tag}.zip"
    elif mirror and "github.com" in zip_url:
        # 应用镜像替换
        zip_url = zip_url.replace("https://github.com", mirror.rstrip("/"))

    logger.info(f"Downloading release from: {zip_url}")
    try:
        resp = requests.get(zip_url, timeout=120, stream=True)
        resp.raise_for_status()

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="qtine-update-")
        with os.fdopen(tmp_fd, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return tmp_path
    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        return None


def backup_current(target_dir: str, version: str) -> Optional[str]:
    """备份当前项目文件到 data/backup/<version>/。"""
    backup_path = os.path.join(BACKUP_DIR, version)
    os.makedirs(backup_path, exist_ok=True)

    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.basename(item_path) in SKIP_PATHS:
                continue
            dest = os.path.join(backup_path, item)
            if os.path.isdir(item_path):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(item_path, dest)
            else:
                shutil.copy2(item_path, dest)
        logger.info(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def cleanup_old_backups():
    """清理超出 MAX_BACKUPS 限制的旧备份。"""
    if not os.path.isdir(BACKUP_DIR):
        return
    backups = sorted(
        [d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))],
        key=lambda b: parse_version(b),
        reverse=True,
    )
    while len(backups) > MAX_BACKUPS:
        old = backups.pop()
        shutil.rmtree(os.path.join(BACKUP_DIR, old), ignore_errors=True)
        logger.info(f"Removed old backup: {old}")


def install_release(
    zip_path: str,
    target_dir: str,
    old_version: str,
    new_version: str,
) -> bool:
    """安装下载的 zip 包到目标目录。

    1. 先解压到临时目录
    2. 如果有顶层包装目录（如 Qtine-1.2.0/），进入该目录
    3. 逐文件/目录复制到项目根目录，跳过 SKIP_PATHS
    """
    tmp_dir = tempfile.mkdtemp(prefix="qtine-install-")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        # 检查是否有单层包装目录
        entries = os.listdir(tmp_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp_dir, entries[0])):
            src_dir = os.path.join(tmp_dir, entries[0])
        else:
            src_dir = tmp_dir

        # 逐项复制
        for item in os.listdir(src_dir):
            if item in SKIP_PATHS:
                logger.info(f"Skipping {item}")
                continue

            src = os.path.join(src_dir, item)
            dst = os.path.join(target_dir, item)

            try:
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                logger.error(f"Failed to copy {item}: {e}")
                return False

        logger.info(f"Update installed: {old_version} → {new_version}")
        return True

    except zipfile.BadZipFile:
        logger.error("Invalid zip file")
        return False
    except Exception as e:
        logger.error(f"Install failed: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # 清理下载的 zip
        try:
            os.remove(zip_path)
        except OSError:
            pass


def rollback_to(target_dir: str, version: str) -> bool:
    """回滚到指定备份版本。"""
    backup_path = os.path.join(BACKUP_DIR, version)
    if not os.path.isdir(backup_path):
        logger.error(f"Backup not found: {version}")
        return False

    try:
        for item in os.listdir(backup_path):
            if item in SKIP_PATHS:
                continue
            src = os.path.join(backup_path, item)
            dst = os.path.join(target_dir, item)

            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        logger.info(f"Rolled back to {version}")
        return True
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False


def list_backups() -> List[dict]:
    """列出所有备份，按版本降序。"""
    if not os.path.isdir(BACKUP_DIR):
        return []
    result = []
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if not os.path.isdir(path):
            continue
        try:
            mtime = os.path.getmtime(path)
            ts = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except OSError:
            ts = "unknown"
        result.append({"version": name, "created_at": ts})
    result.sort(key=lambda b: parse_version(b["version"]), reverse=True)
    return result


def get_current_version() -> str:
    """读取当前 Qtine 版本号。"""
    try:
        import qtine
        return getattr(qtine, "__version__", "0.0.0")
    except ImportError:
        return "0.0.0"
