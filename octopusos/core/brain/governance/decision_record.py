"""
Decision Record - 决策记录系统

核心概念：
- 每次 Navigation/Compare/Time 调用都生成一个不可变的 DecisionRecord
- 记录输入、输出、触发的规则、置信度、时间戳
- 支持 replay 和 audit
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
import json
import uuid


class DecisionType(Enum):
    """决策类型"""
    NAVIGATION = "NAVIGATION"
    COMPARE = "COMPARE"
    HEALTH = "HEALTH"  # Time 的健康报告


class DecisionStatus(Enum):
    """决策状态"""
    PENDING = "PENDING"          # 等待处理
    APPROVED = "APPROVED"        # 已批准
    BLOCKED = "BLOCKED"          # 被阻止
    SIGNED = "SIGNED"            # 已签字
    FAILED = "FAILED"            # 失败


class GovernanceAction(Enum):
    """治理动作"""
    ALLOW = "ALLOW"                    # 允许
    WARN = "WARN"                      # 警告
    BLOCK = "BLOCK"                    # 阻止
    REQUIRE_SIGNOFF = "REQUIRE_SIGNOFF"  # 需要签字


@dataclass
class RuleTrigger:
    """触发的规则"""
    rule_id: str
    rule_name: str
    action: GovernanceAction
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "action": self.action.value,
            "rationale": self.rationale
        }


@dataclass
class DecisionRecord:
    """决策记录（不可变）"""
    # 标识
    decision_id: str  # UUID
    decision_type: DecisionType

    # 输入
    seed: str  # 种子实体
    inputs: Dict[str, Any]  # 输入参数（coverage, blind_spots, risk_level, etc.）

    # 输出
    outputs: Dict[str, Any]  # 输出结果（recommendation_level, warnings, paths, etc.）

    # 治理
    rules_triggered: List[RuleTrigger]
    final_verdict: GovernanceAction  # 最终裁决（所有规则中最严格的）

    # 置信度
    confidence_score: float  # 0-1

    # 时间
    timestamp: str  # ISO 8601

    # 快照引用（可选，用于 replay）
    snapshot_ref: Optional[str] = None

    # 签字（可选）
    signed_by: Optional[str] = None
    sign_timestamp: Optional[str] = None
    sign_note: Optional[str] = None

    # 状态
    status: DecisionStatus = DecisionStatus.PENDING

    # 完整性
    record_hash: str = ""  # SHA256 hash

    def compute_hash(self) -> str:
        """
        计算记录的 hash（用于完整性验证）

        包含字段：
        - decision_id
        - decision_type
        - seed
        - inputs
        - outputs
        - rules_triggered
        - timestamp
        """
        hash_input = {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "seed": self.seed,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "rules_triggered": [r.to_dict() for r in self.rules_triggered],
            "timestamp": self.timestamp
        }

        # 序列化为 JSON（排序键）
        json_str = json.dumps(hash_input, sort_keys=True)

        # 计算 SHA256
        return hashlib.sha256(json_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """
        验证记录完整性

        Returns:
            True if hash matches, False otherwise
        """
        computed = self.compute_hash()
        return computed == self.record_hash

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "seed": self.seed,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "rules_triggered": [r.to_dict() for r in self.rules_triggered],
            "final_verdict": self.final_verdict.value,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp,
            "snapshot_ref": self.snapshot_ref,
            "signed_by": self.signed_by,
            "sign_timestamp": self.sign_timestamp,
            "sign_note": self.sign_note,
            "status": self.status.value,
            "record_hash": self.record_hash
        }


@dataclass
class DecisionSignoff:
    """决策签字"""
    signoff_id: str
    decision_id: str
    signed_by: str  # 用户 ID 或名称
    timestamp: str
    note: str  # 签字备注（必填）

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signoff_id": self.signoff_id,
            "decision_id": self.decision_id,
            "signed_by": self.signed_by,
            "timestamp": self.timestamp,
            "note": self.note
        }


# ============================================
# Database Schema Notes
# ============================================
#
# DEPRECATED: create_decision_tables() function removed
#
# Schema is now managed by migration scripts.
# See: agentos/store/migrations/schema_v36_decision_records.sql
#
# Tables defined in migration:
# - decision_records
# - decision_signoffs
#
# Run migrations before using this module:
#   python -m agentos.store.migrations.run_p0_migration
# ============================================
