"""
BrainOS Compare Module - Understanding Evolution Audit

P3-B: Compare = "理解结构的演化审计"

核心功能：
1. Snapshot - 图谱快照管理
2. Diff Engine - 差异计算引擎
3. Compare Result - 对比结果可视化

Red Line 2 验证：
- 禁止隐藏理解退化（WEAKENED, REMOVED）
- 必须明确标注所有变化类型
"""

from .snapshot import (
    capture_snapshot,
    list_snapshots,
    load_snapshot,
    delete_snapshot,
    Snapshot,
    SnapshotSummary,
    SnapshotEntity,
    SnapshotEdge
)

from .diff_models import (
    ChangeType,
    EntityDiff,
    EdgeDiff,
    BlindSpotDiff,
    CoverageDiff,
    CompareResult
)

from .diff_engine import compare_snapshots

__all__ = [
    # Snapshot
    'capture_snapshot',
    'list_snapshots',
    'load_snapshot',
    'delete_snapshot',
    'Snapshot',
    'SnapshotSummary',
    'SnapshotEntity',
    'SnapshotEdge',

    # Diff Models
    'ChangeType',
    'EntityDiff',
    'EdgeDiff',
    'BlindSpotDiff',
    'CoverageDiff',
    'CompareResult',

    # Diff Engine
    'compare_snapshots',
]
