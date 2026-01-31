"""
Lead Agent 数据模型

定义 Lead Agent 的核心数据结构：
- ScanWindow: 扫描时间窗口
- LeadFinding: 风险线索发现（带 fingerprint 幂等去重）
- FollowUpTaskSpec: 后续任务规格
- ScanResult: 扫描结果
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
from agentos.core.time import utc_now_iso



class WindowKind(str, Enum):
    """扫描窗口类型"""
    HOUR_1 = "1h"       # 1小时窗口
    HOUR_24 = "24h"     # 24小时窗口
    DAY_7 = "7d"        # 7天窗口
    DAY_30 = "30d"      # 30天窗口


class FindingSeverity(str, Enum):
    """发现严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ScanWindow:
    """
    扫描时间窗口

    定义风险扫描的时间范围。
    """
    kind: WindowKind                # 窗口类型
    start_ts: str                   # 开始时间戳（ISO8601）
    end_ts: str                     # 结束时间戳（ISO8601）

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "kind": self.kind.value,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanWindow":
        """从字典反序列化"""
        return cls(
            kind=WindowKind(data["kind"]),
            start_ts=data["start_ts"],
            end_ts=data["end_ts"]
        )


@dataclass
class LeadFinding:
    """
    风险线索发现

    代表 Lead Agent 通过规则挖掘发现的系统性风险或异常模式。
    使用 fingerprint 实现幂等性，避免重复告警。
    """
    finding_id: str                             # 唯一 ID
    fingerprint: str                            # 幂等指纹（rule_code + window + 关键维度）
    rule_code: str                              # 规则代码（如 "blocked_reason_spike"）
    severity: str                               # 严重程度：low|medium|high|critical
    title: str                                  # 标题
    description: str                            # 详细描述
    evidence: Dict[str, Any]                    # 证据数据（count/samples/metrics等）
    window: ScanWindow                          # 扫描窗口
    detected_at: str = field(                   # 检测时间
        default_factory=lambda: utc_now_iso()
    )

    @staticmethod
    def generate_fingerprint(
        rule_code: str,
        window: ScanWindow,
        dimensions: Dict[str, Any]
    ) -> str:
        """
        生成幂等指纹 (FROZEN - Snapshot tested)

        fingerprint = SHA256(rule_code:window_kind:dimensions)

        ⚠️ CRITICAL: 只包含 window.kind，不包含 start_ts/end_ts
        这确保相同规则+窗口类型+维度在不同时间段产生相同 fingerprint，
        从而正确去重（例如：24h 窗口每天扫描不会产生重复 findings）。

        Args:
            rule_code: 规则代码（如 "blocked_reason_spike"）
            window: 扫描窗口（只使用 window.kind，忽略具体时间范围）
            dimensions: 关键维度（如 finding_code, task_id 等）

        Returns:
            16字符的 hex 指纹

        Examples:
            >>> # 相同规则+窗口类型+维度 → 相同 fingerprint（即使时间不同）
            >>> window1 = ScanWindow(kind=WindowKind.HOUR_24, start_ts="2025-01-01", end_ts="2025-01-02")
            >>> window2 = ScanWindow(kind=WindowKind.HOUR_24, start_ts="2025-01-02", end_ts="2025-01-03")
            >>> fp1 = generate_fingerprint("blocked_reason_spike", window1, {"finding_code": "ERR1"})
            >>> fp2 = generate_fingerprint("blocked_reason_spike", window2, {"finding_code": "ERR1"})
            >>> assert fp1 == fp2  # 相同！

            >>> # 不同窗口类型 → 不同 fingerprint（避免 24h 和 7d 混淆）
            >>> window_7d = ScanWindow(kind=WindowKind.DAY_7, start_ts="2025-01-01", end_ts="2025-01-08")
            >>> fp3 = generate_fingerprint("blocked_reason_spike", window_7d, {"finding_code": "ERR1"})
            >>> assert fp1 != fp3  # 不同！

        Frozen Contract:
            此方法的输入输出格式已冻结，由 snapshot 测试锁定。
            任何修改都必须更新测试并记录在 CHANGELOG 中。
            参考: tests/unit/lead/test_fingerprint_freeze.py
        """
        # 🔒 FROZEN: 构造稳定的输入字符串（只包含 window.kind，不包含时间范围）
        parts = [
            rule_code,
            window.kind.value,  # 只使用 window.kind（24h/7d），不使用具体时间
        ]

        # 添加排序后的维度（确保幂等性）
        for key in sorted(dimensions.keys()):
            parts.append(f"{key}={dimensions[key]}")

        input_str = "|".join(parts)

        # 计算 SHA256 并取前16字符
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "finding_id": self.finding_id,
            "fingerprint": self.fingerprint,
            "rule_code": self.rule_code,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "window": self.window.to_dict(),
            "detected_at": self.detected_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadFinding":
        """从字典反序列化"""
        window_data = data["window"]
        window = ScanWindow(
            kind=WindowKind(window_data["kind"]),
            start_ts=window_data["start_ts"],
            end_ts=window_data["end_ts"]
        )

        return cls(
            finding_id=data["finding_id"],
            fingerprint=data["fingerprint"],
            rule_code=data["rule_code"],
            severity=data["severity"],
            title=data["title"],
            description=data["description"],
            evidence=data["evidence"],
            window=window,
            detected_at=data.get("detected_at", utc_now_iso())
        )


@dataclass
class FollowUpTaskSpec:
    """
    后续任务规格

    描述基于 LeadFinding 需要创建的后续任务。
    与 TaskService 解耦，只定义规格，不创建任务。
    """
    finding_fingerprint: str  # 关联的 finding fingerprint
    title: str  # 任务标题
    description: str  # 任务描述
    priority: str = "medium"  # 优先级: low|medium|high|critical
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def __post_init__(self):
        """验证优先级"""
        valid_priorities = ["low", "medium", "high", "critical"]
        if self.priority not in valid_priorities:
            raise ValueError(f"Invalid priority: {self.priority}. Must be one of: {valid_priorities}")

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "finding_fingerprint": self.finding_fingerprint,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FollowUpTaskSpec":
        """从字典反序列化"""
        return cls(
            finding_fingerprint=data["finding_fingerprint"],
            title=data["title"],
            description=data["description"],
            priority=data.get("priority", "medium"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ScanResult:
    """
    扫描结果

    LeadService.run_scan() 的返回值结构。
    包含发现的风险、扫描窗口、创建的任务数等信息。
    """
    findings: List[LeadFinding] = field(default_factory=list)
    window: Optional[ScanWindow] = None
    tasks_created: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外信息（如规则统计等）

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "window": self.window.to_dict() if self.window else None,
            "tasks_created": self.tasks_created,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanResult":
        """从字典反序列化"""
        return cls(
            findings=[LeadFinding.from_dict(f) for f in data.get("findings", [])],
            window=ScanWindow.from_dict(data["window"]) if data.get("window") else None,
            tasks_created=data.get("tasks_created", 0),
            metadata=data.get("metadata", {}),
        )
