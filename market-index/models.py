# -*- coding: utf-8 -*-
"""数据库模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON

from database import Base


class PluginRepo(Base):
    """插件仓库注册表。"""

    __tablename__ = "plugin_repos"

    id = Column(Integer, primary_key=True, index=True)
    repo = Column(String(256), unique=True, index=True)  # owner/repo
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_error = Column(String(512), nullable=True)


class Plugin(Base):
    """插件信息。"""

    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True)
    repo = Column(String(256), index=True)  # owner/repo
    author = Column(String(128), default="")
    description = Column(String(512), default="")
    version = Column(String(32), default="0.0.0")
    tags = Column(JSON, default=list)
    homepage = Column(String(512), default="")
    readme = Column(Text, default="")
    size = Column(String(32), default="")
    download_url = Column(String(1024), default="")
    downloads = Column(Integer, default=0)
    stars = Column(Integer, default=0)
    approved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PluginVersion(Base):
    """插件版本历史。"""

    __tablename__ = "plugin_versions"

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String(128), index=True)
    version = Column(String(32))
    release_notes = Column(Text, default="")
    download_url = Column(String(1024), default="")
    size = Column(String(32), default="")
    published_at = Column(DateTime, default=datetime.utcnow)
