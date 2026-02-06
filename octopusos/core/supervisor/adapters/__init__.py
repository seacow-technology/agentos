"""
Supervisor Adapters

Adapters 负责将 Supervisor 的决策映射到具体的执行：
- GateAdapter: 触发 gates（pause/enforcer/redlines）
- EvaluatorAdapter: 调用评估引擎
- AuditAdapter: 写入审计事件
"""

from .gate_adapter import GateAdapter
from .evaluator_adapter import EvaluatorAdapter
from .audit_adapter import AuditAdapter

__all__ = [
    "GateAdapter",
    "EvaluatorAdapter",
    "AuditAdapter",
]
