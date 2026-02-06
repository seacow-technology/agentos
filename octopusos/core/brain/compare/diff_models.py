"""
Diff Models - 差异数据模型

核心概念：
- ChangeType: 变化类型（ADDED/REMOVED/MODIFIED/UNCHANGED）
- EntityDiff: 实体变化
- EdgeDiff: 边变化
- CompareResult: 完整对比结果

Red Line 2 验证：禁止隐藏理解退化
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ChangeType(Enum):
    """变化类型"""
    ADDED = "ADDED"        # 新增 🟢
    REMOVED = "REMOVED"    # 删除 🔴
    WEAKENED = "WEAKENED"  # 弱化 🟡（证据减少、覆盖降低）
    STRENGTHENED = "STRENGTHENED"  # 增强 🟦（证据增加、覆盖提升）
    UNCHANGED = "UNCHANGED"  # 无变化


@dataclass
class EntityDiff:
    """实体变化"""
    entity_id: str
    entity_type: str
    entity_key: str
    entity_name: str

    change_type: ChangeType

    # 变化前后的属性
    before_evidence_count: Optional[int]
    after_evidence_count: Optional[int]

    before_coverage_sources: Optional[List[str]]
    after_coverage_sources: Optional[List[str]]

    before_is_blind_spot: Optional[bool]
    after_is_blind_spot: Optional[bool]

    # 变化描述
    change_description: str


@dataclass
class EdgeDiff:
    """边变化"""
    edge_id: str
    src_entity_id: str
    dst_entity_id: str
    edge_type: str

    change_type: ChangeType

    # 变化前后的属性
    before_evidence_count: Optional[int]
    after_evidence_count: Optional[int]

    before_evidence_types: Optional[List[str]]
    after_evidence_types: Optional[List[str]]

    # 变化描述
    change_description: str


@dataclass
class BlindSpotDiff:
    """盲区变化"""
    entity_id: str
    entity_name: str

    change_type: ChangeType  # ADDED, REMOVED, UNCHANGED

    before_severity: Optional[float]
    after_severity: Optional[float]

    change_description: str


@dataclass
class CoverageDiff:
    """覆盖度变化"""
    metric_name: str  # "coverage_percentage", "git_coverage", etc.

    before_value: float
    after_value: float

    change_percentage: float  # (after - before) / before * 100
    is_degradation: bool  # True if after < before


@dataclass
class CompareResult:
    """完整对比结果"""
    from_snapshot_id: str
    to_snapshot_id: str

    from_timestamp: str
    to_timestamp: str

    # 实体变化
    entity_diffs: List[EntityDiff]
    entities_added: int
    entities_removed: int
    entities_weakened: int
    entities_strengthened: int

    # 边变化
    edge_diffs: List[EdgeDiff]
    edges_added: int
    edges_removed: int
    edges_weakened: int
    edges_strengthened: int

    # 盲区变化
    blind_spot_diffs: List[BlindSpotDiff]
    blind_spots_added: int
    blind_spots_removed: int

    # 覆盖度变化
    coverage_diffs: List[CoverageDiff]

    # 总体评估
    overall_assessment: str  # "IMPROVED", "DEGRADED", "MIXED"
    health_score_change: float  # -1 to +1

    computed_at: str
