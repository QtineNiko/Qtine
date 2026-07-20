# -*- coding: utf-8 -*-
"""从 GitHub 仓库同步插件信息。

每个插件对应一个 GitHub 仓库。同步内容：
- 仓库根目录 data.json → 插件元信息（名称、描述、作者、标签、版本等）
- 仓库根目录 README.md → 插件说明
- GitHub Releases → 版本历史和下载地址
- 仓库 Star 数
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from config import Config
from database import SessionLocal
from models import Plugin, PluginRepo, PluginVersion

logger = logging.getLogger("sync")

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if Config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {Config.GITHUB_TOKEN}"
    return headers


async def fetch_data_json(repo: str) -> Optional[dict]:
    """从仓库根目录抓取 data.json。"""
    url = (
        f"https://raw.githubusercontent.com/{repo}/main/data.json"
    )
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(url, headers=_gh_headers())
            if r.status_code == 200:
                return r.json()
            # 试 master 分支
            url2 = url.replace("/main/", "/master/")
            r2 = await c.get(url2, headers=_gh_headers())
            if r2.status_code == 200:
                return r2.json()
            logger.warning(f"[{repo}] data.json not found ({r.status_code})")
            return None
    except Exception as e:
        logger.error(f"[{repo}] fetch data.json error: {e}")
        return None


async def fetch_readme(repo: str) -> str:
    """从仓库根目录抓取 README.md。"""
    url = (
        f"https://raw.githubusercontent.com/{repo}/main/README.md"
    )
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(url, headers=_gh_headers())
            if r.status_code == 200:
                return r.text
            url2 = url.replace("/main/", "/master/")
            r2 = await c.get(url2, headers=_gh_headers())
            if r2.status_code == 200:
                return r2.text
            return ""
    except Exception as e:
        logger.error(f"[{repo}] fetch README error: {e}")
        return ""


async def fetch_releases(repo: str) -> list:
    """获取仓库的 Release 列表。"""
    url = f"{GITHUB_API}/repos/{repo}/releases?per_page=20"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(url, headers=_gh_headers())
            if r.status_code == 200:
                return r.json()
            return []
    except Exception as e:
        logger.error(f"[{repo}] fetch releases error: {e}")
        return []


async def fetch_repo_info(repo: str) -> dict:
    """获取仓库基本信息（star 数等）。"""
    url = f"{GITHUB_API}/repos/{repo}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(url, headers=_gh_headers())
            if r.status_code == 200:
                return r.json()
            return {}
    except Exception as e:
        logger.error(f"[{repo}] fetch repo info error: {e}")
        return {}


async def sync_plugin(repo: str, db: Session) -> bool:
    """同步单个插件仓库。

    返回 True 表示成功。
    """
    repo_entry = (
        db.query(PluginRepo).filter(PluginRepo.repo == repo).first()
    )

    # 1. data.json
    data = await fetch_data_json(repo)
    if not data:
        if repo_entry:
            repo_entry.last_sync_error = "data.json 抓取失败"
            repo_entry.last_sync_at = datetime.utcnow()
            db.commit()
        return False

    name = data.get("name") or repo.split("/")[-1]
    version = data.get("version", "0.0.0")
    author = data.get("author", "")
    description = data.get("description", "")
    tags = data.get("tags", []) or []
    homepage = data.get("homepage", f"https://github.com/{repo}")

    # 2. README
    readme = await fetch_readme(repo)

    # 3. Releases
    releases = await fetch_releases(repo)

    # 4. 仓库信息（star）
    repo_info = await fetch_repo_info(repo)
    stars = repo_info.get("stargazers_count", 0)

    # 5. 确定下载地址和版本
    latest_version = version
    download_url = ""
    size = ""

    if releases:
        latest = releases[0]
        tag = latest.get("tag_name", "")
        if tag:
            latest_version = tag.lstrip("v")
        # 找 .zip 格式的 asset
        assets = latest.get("assets", [])
        zip_asset = None
        for a in assets:
            if a.get("name", "").endswith(".zip"):
                zip_asset = a
                break
        if zip_asset:
            download_url = zip_asset.get("browser_download_url", "")
            size_bytes = zip_asset.get("size", 0)
            size = _format_size(size_bytes)
        else:
            # 回退到源码压缩包
            download_url = latest.get(
                "zipball_url",
                f"https://github.com/{repo}/archive/refs/tags/{tag}.zip",
            )

        # 保存版本历史
        db.query(PluginVersion).filter(
            PluginVersion.plugin_name == name
        ).delete()
        for rel in releases:
            tag_v = rel.get("tag_name", "").lstrip("v")
            if not tag_v:
                continue
            rel_assets = rel.get("assets", [])
            rel_zip = next(
                (a for a in rel_assets if a.get("name", "").endswith(".zip")),
                None,
            )
            rel_url = ""
            rel_size = ""
            if rel_zip:
                rel_url = rel_zip.get("browser_download_url", "")
                rel_size = _format_size(rel_zip.get("size", 0))
            else:
                rel_url = rel.get(
                    "zipball_url",
                    f"https://github.com/{repo}/archive/refs/tags/{rel.get('tag_name','')}.zip",
                )
            pub_at_str = rel.get("published_at", "")
            pub_at = None
            if pub_at_str:
                try:
                    pub_at = datetime.fromisoformat(
                        pub_at_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    pub_at = None
            pv = PluginVersion(
                plugin_name=name,
                version=tag_v,
                release_notes=rel.get("body", "") or "",
                download_url=rel_url,
                size=rel_size,
                published_at=pub_at or datetime.utcnow(),
            )
            db.add(pv)

    # 6. 更新或创建插件记录
    plugin = db.query(Plugin).filter(Plugin.name == name).first()
    if plugin:
        plugin.repo = repo
        plugin.author = author
        plugin.description = description
        plugin.version = latest_version
        plugin.tags = tags
        plugin.homepage = homepage
        plugin.readme = readme
        plugin.size = size
        plugin.download_url = download_url
        plugin.stars = stars
        plugin.updated_at = datetime.utcnow()
    else:
        plugin = Plugin(
            name=name,
            repo=repo,
            author=author,
            description=description,
            version=latest_version,
            tags=tags,
            homepage=homepage,
            readme=readme,
            size=size,
            download_url=download_url,
            stars=stars,
            downloads=0,
            approved=True,
        )
        db.add(plugin)

    # 7. 更新仓库同步状态
    if repo_entry:
        repo_entry.last_sync_at = datetime.utcnow()
        repo_entry.last_sync_error = None
    else:
        repo_entry = PluginRepo(repo=repo, enabled=True)
        db.add(repo_entry)

    db.commit()
    logger.info(f"[{repo}] synced: {name} v{latest_version}")
    return True


async def sync_all():
    """同步所有已注册的插件仓库。"""
    db = SessionLocal()
    try:
        repos = (
            db.query(PluginRepo)
            .filter(PluginRepo.enabled == True)  # noqa: E712
            .all()
        )
        if not repos:
            logger.info("No plugin repos to sync.")
            return

        logger.info(f"Syncing {len(repos)} plugin repos...")
        ok = 0
        for r in repos:
            try:
                if await sync_plugin(r.repo, db):
                    ok += 1
            except Exception as e:
                logger.error(f"[{r.repo}] sync error: {e}")
                r.last_sync_error = str(e)
                r.last_sync_at = datetime.utcnow()
                db.commit()
        logger.info(f"Sync done: {ok}/{len(repos)} succeeded")
    finally:
        db.close()


def _format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"
