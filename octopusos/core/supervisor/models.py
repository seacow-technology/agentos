"""
Supervisor 数据模型

定义 Supervisor 的核心数据结构：
- SupervisorEvent: 统一的事件契约
- Finding: 发现的问题（风险、冲突、红线违规）
- Decision: Supervisor 的决策
- Action: 要执行的动作
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from agentos.core.time import utc_now_iso



class EventSource(str, Enum):
    """事件来源"""
    EVENTBUS = "eventbus"  # 来自 EventBus 的实时事件
    POLLING = "polling"     # 来自 Polling 的兜底事件


class DecisionType(str, Enum):
    """决策类型"""
    ALLOW = "allow"              # 允许继续
    PAUSE = "pause"              # 暂停等待
    BLOCK = "block"              # 阻塞
    RETRY = "retry"              # 建议重试（不强制）
    REQUIRE_REVIEW = "require_review"  # 需要人工审查


class ActionType(str, Enum):
    """动作类型"""
    PAUSE_GATE = "pause_gate"              # 触发 pause gate
    RUNTIME_ENFORCE = "runtime_enforce"    # 触发 runtime enforcer
    REDLINE_VIOLATION = "redline_violation"  # 红线违规
    MARK_BLOCKED = "mark_blocked"          # 标记任务为 BLOCKED
    MARK_VERIFYING = "mark_verifying"      # 标记任务为 VERIFYING
    WRITE_AUDIT = "write_audit"            # 写审计日志
    NOOP = "noop"                          # 无操作


@dataclass
class SupervisorEvent:
    """
    统一的 Supervisor 事件模型

    无论来自 EventBus 还是 Polling，都映射成这个统一格式。
    这是 Supervisor 的"输入契约"。
    """
    event_id: str                           # 全局唯一 ID（UUID 或 DB ID）
    source: EventSource                     # 事件来源
    task_id: str                            # 关联的任务 ID
    event_type: str                         # TASK_CREATED / TASK_STEP_COMPLETED / TASK_FAILED / TASK_STATE_CHANGED
    ts: str                                 # ISO 时间戳
    payload: Dict[str, Any] = field(default_factory=dict)  # 事件载荷

    @classmethod
    def from_eventbus(cls, event: Any) -> "SupervisorEvent":
        """从 EventBus 事件转换"""
        return cls(
            event_id=str(uuid.uuid4()),
            source=EventSource.EVENTBUS,
            task_id=event.entity.id,
            event_type=event.type.value if hasattr(event.type, 'value') else str(event.type),
            ts=event.ts,
            payload=event.payload or {}
        )

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SupervisorEvent":
        """从数据库行转换（用于 Polling）"""
        # 假设 row 来自 task_audits 或类似表
        return cls(
            event_id=str(row.get("audit_id") or row.get("id")),
            source=EventSource.POLLING,
            task_id=row["task_id"],
            event_type=row["event_type"],
            ts=row.get("created_at", utc_now_iso()),
            payload=row.get("payload", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "event_id": self.event_id,
            "source": self.source.value,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "ts": self.ts,
            "payload": self.payload
        }


@dataclass
class Finding:
    """
    发现的问题

    代表 Supervisor 在评估过程中发现的风险、冲突、红线违规等。
    """
    finding_id: str = field(default_factory=lambda: f"finding_{uuid.uuid4().hex[:12]}")
    category: str = ""                      # risk|conflict|redline|constraint
    severity: str = ""                      # low|medium|high|critical
    description: str = ""                   # 问题描述
    evidence: List[str] = field(default_factory=list)  # 证据引用
    source: str = ""                        # evaluator|gate|policy

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
            "source": self.source
        }


@dataclass
class Decision:
    """
    Supervisor 决策

    基于 Findings 做出的最终决策。
    """
    decision_id: str = field(default_factory=lambda: f"decision_{uuid.uuid4().hex[:12]}")
    decision_type: DecisionType = DecisionType.ALLOW
    reason: str = ""                        # 决策理由
    findings: List[Finding] = field(default_factory=list)  # 相关发现
    actions: List["Action"] = field(default_factory=list)   # 要执行的动作
    timestamp: str = field(default_factory=lambda: utc_now_iso())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "findings": [f.to_dict() for f in self.findings],
            "actions": [a.to_dict() for a in self.actions],
            "timestamp": self.timestamp
        }


@dataclass
class Action:
    """
    执行的动作

    Decision 映射到具体的 Gate/Task 动作。
    """
    action_id: str = field(default_factory=lambda: f"action_{uuid.uuid4().hex[:12]}")
    action_type: ActionType = ActionType.NOOP
    target: str = ""                        # 目标（task_id / gate_name / ...）
    params: Dict[str, Any] = field(default_factory=dict)  # 动作参数

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "params": self.params
        }
