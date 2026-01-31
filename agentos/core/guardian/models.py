"""
Guardian 数据模型

Guardian = 验收事实记录器（Verification / Acceptance Authority）
- 不修改 task 状态机
- 不引入强制卡死流程
- Guardian 是叠加层（Overlay），不是 Gate

核心数据结构：
- GuardianReview: 验收审查记录，记录验收事实（PASS/FAIL/NEEDS_REVIEW）
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Literal
import uuid
from agentos.core.time import utc_now_iso



@dataclass
class GuardianReview:
    """
    Guardian 验收审查记录

    代表 Guardian 对某个治理对象（task/decision/finding）的验收审查结果。
    Guardian 只记录验收事实，不控制流程。

    核心原则：
    - Guardian 记录验收事实，不修改状态机
    - Verdict 是不可变的（immutable），一旦写入就是治理事实
    - 支持自动验收（AUTO）和人工验收（MANUAL）
    - Evidence 存储完整的验收证据（可追溯）
    """
    review_id: str                                          # 唯一审查 ID
    target_type: Literal["task", "decision", "finding"]    # 审查目标类型
    target_id: str                                          # 审查目标 ID
    guardian_id: str                                        # Guardian ID（agent name / human id）
    review_type: Literal["AUTO", "MANUAL"]                 # 审查类型
    verdict: Literal["PASS", "FAIL", "NEEDS_REVIEW"]       # 验收结论
    confidence: float                                       # 置信度（0.0-1.0）
    rule_snapshot_id: str | None                            # 规则快照 ID（用于审计）
    evidence: Dict[str, Any]                                # 验收证据（JSON 结构）
    created_at: str = field(                                # 创建时间（ISO8601）
        default_factory=lambda: utc_now_iso()
    )

    def __post_init__(self):
        """验证数据完整性"""
        # 验证 target_type
        valid_target_types = ["task", "decision", "finding"]
        if self.target_type not in valid_target_types:
            raise ValueError(
                f"Invalid target_type: {self.target_type}. "
                f"Must be one of: {valid_target_types}"
            )

        # 验证 review_type
        valid_review_types = ["AUTO", "MANUAL"]
        if self.review_type not in valid_review_types:
            raise ValueError(
                f"Invalid review_type: {self.review_type}. "
                f"Must be one of: {valid_review_types}"
            )

        # 验证 verdict
        valid_verdicts = ["PASS", "FAIL", "NEEDS_REVIEW"]
        if self.verdict not in valid_verdicts:
            raise ValueError(
                f"Invalid verdict: {self.verdict}. "
                f"Must be one of: {valid_verdicts}"
            )

        # 验证 confidence
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid confidence: {self.confidence}. "
                f"Must be between 0.0 and 1.0"
            )

    @classmethod
    def create_auto_review(
        cls,
        target_type: Literal["task", "decision", "finding"],
        target_id: str,
        guardian_id: str,
        verdict: Literal["PASS", "FAIL", "NEEDS_REVIEW"],
        confidence: float,
        evidence: Dict[str, Any],
        rule_snapshot_id: str | None = None
    ) -> "GuardianReview":
        """
        创建自动验收审查记录

        Args:
            target_type: 审查目标类型
            target_id: 审查目标 ID
            guardian_id: Guardian ID（agent name）
            verdict: 验收结论
            confidence: 置信度
            evidence: 验收证据
            rule_snapshot_id: 规则快照 ID（可选）

        Returns:
            GuardianReview 实例
        """
        return cls(
            review_id=f"review_{uuid.uuid4().hex[:12]}",
            target_type=target_type,
            target_id=target_id,
            guardian_id=guardian_id,
            review_type="AUTO",
            verdict=verdict,
            confidence=confidence,
            rule_snapshot_id=rule_snapshot_id,
            evidence=evidence
        )

    @classmethod
    def create_manual_review(
        cls,
        target_type: Literal["task", "decision", "finding"],
        target_id: str,
        guardian_id: str,
        verdict: Literal["PASS", "FAIL", "NEEDS_REVIEW"],
        evidence: Dict[str, Any]
    ) -> "GuardianReview":
        """
        创建人工验收审查记录

        Args:
            target_type: 审查目标类型
            target_id: 审查目标 ID
            guardian_id: Guardian ID（human id）
            verdict: 验收结论
            evidence: 验收证据

        Returns:
            GuardianReview 实例
        """
        return cls(
            review_id=f"review_{uuid.uuid4().hex[:12]}",
            target_type=target_type,
            target_id=target_id,
            guardian_id=guardian_id,
            review_type="MANUAL",
            verdict=verdict,
            confidence=1.0,  # 人工审查置信度为 1.0
            rule_snapshot_id=None,  # 人工审查不关联规则快照
            evidence=evidence
        )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "review_id": self.review_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "guardian_id": self.guardian_id,
            "review_type": self.review_type,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rule_snapshot_id": self.rule_snapshot_id,
            "evidence": self.evidence,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuardianReview":
        """从字典反序列化"""
        return cls(
            review_id=data["review_id"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            guardian_id=data["guardian_id"],
            review_type=data["review_type"],
            verdict=data["verdict"],
            confidence=data["confidence"],
            rule_snapshot_id=data.get("rule_snapshot_id"),
            evidence=data.get("evidence", {}),
            created_at=data.get("created_at", utc_now_iso())
        )
