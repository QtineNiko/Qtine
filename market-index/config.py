# -*- coding: utf-8 -*-
"""配置。"""

import os
from typing import List


class Config:
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "2456"))

    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "sqlite:///./data/market.db"
    )

    ADMIN_TOKEN: str = os.environ.get(
        "ADMIN_TOKEN", "qtine-admin-change-me"
    )

    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

    SYNC_INTERVAL_MINUTES: int = int(
        os.environ.get("SYNC_INTERVAL", "60")
    )

    SYNC_ON_STARTUP: bool = os.environ.get("SYNC_ON_STARTUP", "1") == "1"

    # 默认插件仓库列表（owner/repo 格式）
    DEFAULT_REPOS: List[str] = []

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # GitHub 加速镜像（用于国内访问加速）
    GITHUB_MIRRORS: List[str] = [
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
