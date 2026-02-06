"""
Executor Core - 受控执行引擎

提供安全的、可审计的、可回滚的执行能力
"""

from .allowlist import Allowlist
from .sandbox import Sandbox
from .rollback import RollbackManager
from .lock import ExecutionLock
from .review_gate import ReviewGate
from .audit_logger import AuditLogger
from .executor_engine import ExecutorEngine, DiffRejected  # 🔩 H3-2

__all__ = [
    "Allowlist",
    "Sandbox",
    "RollbackManager",
    "ExecutionLock",
    "ReviewGate",
    "AuditLogger",
    "ExecutorEngine",
    "DiffRejected",  # 🔩 H3-2
]
