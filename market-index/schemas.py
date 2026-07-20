# -*- coding: utf-8 -*-
"""Pydantic schemas。"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PluginOut(BaseModel):
    name: str
    repo: str
    author: str = ""
    description: str = ""
    version: str = "0.0.0"
    tags: List[str] = []
    homepage: str = ""
    size: str = ""
    download_url: str = ""
    downloads: int = 0
    stars: int = 0

    class Config:
        from_attributes = True


class PluginDetail(PluginOut):
    readme: str = ""


class PluginVersionOut(BaseModel):
    version: str
    release_notes: str = ""
    download_url: str = ""
    size: str = ""
    published_at: Optional[str] = None


class PluginListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    plugins: List[PluginOut]


class MirrorItem(BaseModel):
    name: str
    url: str
    latency: Optional[float] = None


class SpeedTestResult(BaseModel):
    mirrors: List[MirrorItem]
    fastest: Optional[str] = None


class AddRepoRequest(BaseModel):
    repo: str = Field(..., description="GitHub 仓库，格式 owner/repo")


class AdminResponse(BaseModel):
    success: bool
    message: str = ""
