# agentos/core/storage/paths.py
from __future__ import annotations
from pathlib import Path
import os

# 允许的组件列表（单组件单数据库原则）
# agentos: 核心任务与会话管理
# memoryos: 长期记忆与向量存储
# brainos: 知识图谱与决策记录
# communicationos: Agent间通信与证据链
# networkos: 网络隧道管理（Cloudflare Tunnel等）
# appos: 应用层组合与交付
# kb: 知识库索引
# skill: 技能定义与执行历史
ALLOWED_COMPONENTS = {"agentos", "memoryos", "brainos", "communicationos", "networkos", "appos", "kb", "skill"}

def agentos_home() -> Path:
    """强制使用 ~/.agentos（Windows也如此）"""
    return Path.home() / ".agentos"

def store_root() -> Path:
    """统一存储根目录"""
    return agentos_home() / "store"

def component_db_dir(component: str) -> Path:
    """获取组件数据库目录"""
    if component not in ALLOWED_COMPONENTS:
        raise ValueError(f"Unknown component: {component}. Allowed: {ALLOWED_COMPONENTS}")
    return store_root() / component

def component_db_path(component: str) -> Path:
    """获取组件数据库文件路径（唯一允许的路径）"""
    return component_db_dir(component) / "db.sqlite"

def ensure_db_exists(component: str) -> Path:
    """确保数据库目录存在，返回数据库文件路径"""
    import sqlite3

    d = component_db_dir(component)
    d.mkdir(parents=True, exist_ok=True)
    p = component_db_path(component)

    # 如果DB不存在，创建并初始化WAL模式
    if not p.exists():
        conn = sqlite3.connect(str(p))
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.commit()
        finally:
            conn.close()

    return p
