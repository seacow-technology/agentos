# agentos/core/storage/engines.py
from __future__ import annotations
from typing import Dict
from sqlalchemy import create_engine, event, Engine
from .paths import ensure_db_exists, component_db_path, ALLOWED_COMPONENTS

_ENGINE_REGISTRY: Dict[str, Engine] = {}

def _sqlite_url(path) -> str:
    """统一使用绝对路径，避免相对路径导致多DB"""
    return f"sqlite:///{path.resolve().as_posix()}"

def get_engine(component: str) -> Engine:
    """获取组件的SQLAlchemy Engine（单例模式）

    Args:
        component: 组件名称（agentos/memoryos/brainos/communicationos/kb）

    Returns:
        SQLAlchemy Engine（每个组件全局唯一）

    Raises:
        ValueError: 组件名称不合法
        RuntimeError: DB路径不匹配（防止意外创建第二个DB）
    """
    if component not in ALLOWED_COMPONENTS:
        raise ValueError(f"Unknown component: {component}. Allowed: {ALLOWED_COMPONENTS}")

    # 如果已注册，直接返回
    if component in _ENGINE_REGISTRY:
        return _ENGINE_REGISTRY[component]

    # 确保DB存在并获取路径
    db_path = ensure_db_exists(component)

    # 硬校验：路径必须等于我们定义的唯一路径
    if db_path != component_db_path(component):
        raise RuntimeError(f"DB path mismatch: {db_path} != {component_db_path(component)}")

    # 创建Engine（并发友好配置）
    engine = create_engine(
        _sqlite_url(db_path),
        future=True,
        pool_pre_ping=True,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # seconds
        },
        pool_size=5,
        max_overflow=10,
    )

    # SQLite并发优化：WAL + busy_timeout
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, conn_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA busy_timeout=30000;")  # 30秒
        cur.close()

    # 注册到全局registry
    _ENGINE_REGISTRY[component] = engine
    return engine

def get_registered_engines() -> Dict[str, Engine]:
    """获取所有已注册的Engine（调试用）"""
    return _ENGINE_REGISTRY.copy()
