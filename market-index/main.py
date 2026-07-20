# -*- coding: utf-8 -*-
"""Qtine 插件市场索引服务。

API 列表：
  GET  /api/plugins              插件列表
  GET  /api/plugins/<name>       插件详情
  GET  /api/plugins/<name>/readme  插件 README
  GET  /api/plugins/<name>/versions  插件版本历史
  GET  /api/plugins/<name>/download  下载重定向（统计下载量）
  GET  /api/tags                 所有标签
  GET  /api/mirrors              GitHub 加速镜像列表
  GET  /api/mirrors/speedtest    测速并返回最快的
  POST /api/admin/repos          添加插件仓库（需 token）
  DELETE /api/admin/repos/<repo> 删除插件仓库（需 token）
  GET  /api/admin/repos          列出所有仓库（需 token）
  POST /api/admin/sync           手动触发同步（需 token）
  GET  /health                   健康检查
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from config import Config
from database import get_db, init_db
from models import Plugin, PluginRepo, PluginVersion
from schemas import (
    AddRepoRequest,
    AdminResponse,
    MirrorItem,
    PluginDetail,
    PluginListResponse,
    PluginOut,
    PluginVersionOut,
    SpeedTestResult,
)
from sync import sync_all, sync_plugin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("market-index")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    os.makedirs("data", exist_ok=True)
    init_db()

    # 注册默认仓库
    if Config.DEFAULT_REPOS:
        db = next(get_db())
        for repo in Config.DEFAULT_REPOS:
            if not db.query(PluginRepo).filter(
                PluginRepo.repo == repo
            ).first():
                db.add(PluginRepo(repo=repo, enabled=True))
        db.commit()
        db.close()

    # 定时同步
    scheduler.add_job(
        lambda: asyncio.run(sync_all()),
        "interval",
        minutes=Config.SYNC_INTERVAL_MINUTES,
        id="sync_all",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started: sync every {Config.SYNC_INTERVAL_MINUTES} min"
    )

    # 启动时同步
    if Config.SYNC_ON_STARTUP:
        logger.info("Syncing on startup...")

        def _startup_sync():
            asyncio.run(sync_all())

        import threading

        threading.Thread(target=_startup_sync, daemon=True).start()

    yield
    # 关闭
    scheduler.shutdown()


app = FastAPI(title="Qtine Plugin Market Index", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_admin(authorization: Optional[str] = Header(None)):
    """验证管理员 token。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.replace("Bearer ", "").strip()
    if token != Config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ── 插件列表/详情 ────────────────────────────────────────────────────


@app.get("/api/plugins", response_model=PluginListResponse)
def list_plugins(
    search: Optional[str] = Query(None, description="搜索关键词"),
    tag: Optional[str] = Query(None, description="按标签过滤"),
    sort: str = Query("downloads", description="排序: downloads/stars/new/name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Plugin).filter(Plugin.approved == True)  # noqa: E712

    if search:
        kw = f"%{search}%"
        q = q.filter(
            or_(
                Plugin.name.like(kw),
                Plugin.description.like(kw),
                Plugin.author.like(kw),
            )
        )

    if tag:
        q = q.filter(Plugin.tags.like(f'%"{tag}"%')).filter(
            Plugin.tags.like(f"%{tag}%")
        )

    total = q.count()

    if sort == "stars":
        q = q.order_by(Plugin.stars.desc())
    elif sort == "new":
        q = q.order_by(Plugin.updated_at.desc())
    elif sort == "name":
        q = q.order_by(Plugin.name.asc())
    else:
        q = q.order_by(Plugin.downloads.desc())

    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return PluginListResponse(
        total=total,
        page=page,
        page_size=page_size,
        plugins=[PluginOut.model_validate(p) for p in items],
    )


@app.get("/api/plugins/{name}", response_model=PluginDetail)
def get_plugin(name: str, db: Session = Depends(get_db)):
    p = db.query(Plugin).filter(Plugin.name == name).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return PluginDetail.model_validate(p)


@app.get("/api/plugins/{name}/readme")
def get_plugin_readme(name: str, db: Session = Depends(get_db)):
    p = db.query(Plugin).filter(Plugin.name == name).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"name": name, "readme": p.readme or ""}


@app.get("/api/plugins/{name}/versions", response_model=list[PluginVersionOut])
def get_plugin_versions(name: str, db: Session = Depends(get_db)):
    versions = (
        db.query(PluginVersion)
        .filter(PluginVersion.plugin_name == name)
        .order_by(PluginVersion.published_at.desc())
        .all()
    )
    result = []
    for v in versions:
        result.append(
            PluginVersionOut(
                version=v.version,
                release_notes=v.release_notes,
                download_url=v.download_url,
                size=v.size,
                published_at=(
                    v.published_at.isoformat() if v.published_at else None
                ),
            )
        )
    return result


@app.get("/api/plugins/{name}/download")
def download_plugin(
    name: str,
    mirror: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    p = db.query(Plugin).filter(Plugin.name == name).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found")

    p.downloads += 1
    db.commit()

    url = p.download_url or ""

    # 如果指定了镜像且原始地址是 github.com，替换为镜像
    if mirror and "github.com" in url:
        mirror = mirror.rstrip("/")
        url = url.replace("https://github.com", mirror)

    return RedirectResponse(url=url)


@app.get("/api/tags")
def list_tags(db: Session = Depends(get_db)):
    plugins = db.query(Plugin).filter(Plugin.approved == True).all()  # noqa: E712
    tag_set = set()
    for p in plugins:
        if p.tags:
            for t in p.tags:
                tag_set.add(t)
    return {"tags": sorted(list(tag_set))}


# ── 加速镜像 ────────────────────────────────────────────────────────


@app.get("/api/mirrors", response_model=list[MirrorItem])
def list_mirrors():
    """返回 GitHub 加速镜像列表。"""
    names = [
        "GitHub 官方",
        "ghproxy",
        "99988866",
        "mirror.ghproxy",
        "gh-proxy",
        "xcxgw",
        "ghps",
        "d-ai workers",
        "llkk",
        "gitmirror",
    ]
    items = []
    for i, url in enumerate(Config.GITHUB_MIRRORS):
        name = names[i] if i < len(names) else f"镜像{i + 1}"
        items.append(MirrorItem(name=name, url=url))
    return items


@app.get("/api/mirrors/speedtest", response_model=SpeedTestResult)
async def speed_test_mirrors():
    """对所有镜像进行测速，返回最快的。"""
    results = []

    async def test_one(name: str, url: str):
        test_url = url.rstrip("/") + "/QtineNiko/Qtine"
        start = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=5.0, follow_redirects=True
            ) as c:
                r = await c.head(test_url)
                latency = (time.time() - start) * 1000
                results.append(
                    MirrorItem(name=name, url=url, latency=latency)
                )
        except Exception:
            results.append(
                MirrorItem(name=name, url=url, latency=99999)
            )

    mirrors = list_mirrors()
    tasks = [test_one(m.name, m.url) for m in mirrors]
    await asyncio.gather(*tasks)

    # 按延迟排序
    results.sort(key=lambda x: x.latency or 99999)
    fastest = results[0].url if results and results[0].latency < 99999 else None

    return SpeedTestResult(mirrors=results, fastest=fastest)


# ── 管理接口 ────────────────────────────────────────────────────────


@app.get("/api/admin/repos")
def admin_list_repos(
    _: bool = Depends(verify_admin), db: Session = Depends(get_db)
):
    repos = db.query(PluginRepo).order_by(PluginRepo.created_at.desc()).all()
    return {
        "repos": [
            {
                "id": r.id,
                "repo": r.repo,
                "enabled": r.enabled,
                "last_sync_at": (
                    r.last_sync_at.isoformat() if r.last_sync_at else None
                ),
                "last_sync_error": r.last_sync_error,
            }
            for r in repos
        ]
    }


@app.post("/api/admin/repos", response_model=AdminResponse)
async def admin_add_repo(
    req: AddRepoRequest,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    repo = req.repo.strip()
    if not repo or "/" not in repo:
        raise HTTPException(status_code=400, detail="仓库格式应为 owner/repo")

    if db.query(PluginRepo).filter(PluginRepo.repo == repo).first():
        return AdminResponse(success=False, message="仓库已存在")

    # 先同步一次试试
    ok = await sync_plugin(repo, db)
    if not ok:
        # 即使同步失败也先加入，等下次定时同步重试
        db.add(PluginRepo(repo=repo, enabled=True, last_sync_error="首次同步失败"))
        db.commit()
        return AdminResponse(
            success=False, message="已添加但首次同步失败，请检查仓库是否有效"
        )

    return AdminResponse(success=True, message="添加成功")


@app.delete("/api/admin/repos/{repo:path}", response_model=AdminResponse)
def admin_delete_repo(
    repo: str,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    r = db.query(PluginRepo).filter(PluginRepo.repo == repo).first()
    if not r:
        raise HTTPException(status_code=404, detail="仓库不存在")

    # 同时删除该仓库对应的插件
    plugins = db.query(Plugin).filter(Plugin.repo == repo).all()
    for p in plugins:
        db.query(PluginVersion).filter(
            PluginVersion.plugin_name == p.name
        ).delete()
        db.delete(p)

    db.delete(r)
    db.commit()
    return AdminResponse(success=True, message="已删除")


@app.post("/api/admin/sync", response_model=AdminResponse)
async def admin_sync(
    _: bool = Depends(verify_admin),
):
    import threading

    def _do_sync():
        asyncio.run(sync_all())

    threading.Thread(target=_do_sync, daemon=True).start()
    return AdminResponse(success=True, message="同步已启动")


# ── 健康检查 ────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False,
    )
