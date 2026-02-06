"""
Diff Engine - 差异计算引擎

核心算法：
1. 加载两个快照
2. 对比实体、边、盲区
3. 计算变化类型（ADDED/REMOVED/WEAKENED/STRENGTHENED）
4. 生成变化描述

Red Line 2 验证：必须显示所有 WEAKENED 和 REMOVED 变化
"""

from typing import Dict, List
from datetime import datetime, timezone

from .snapshot import load_snapshot, Snapshot, SnapshotEntity, SnapshotEdge
from agentos.core.time import utc_now_iso
from .diff_models import (
    ChangeType,
    EntityDiff,
    EdgeDiff,
    BlindSpotDiff,
    CoverageDiff,
    CompareResult
)


def compare_snapshots(
    store,  # SQLiteStore
    from_snapshot_id: str,
    to_snapshot_id: str
) -> CompareResult:
    """
    对比两个快照

    Red Line 2 验证点：
    - 必须显示所有 WEAKENED 和 REMOVED 变化
    - 不能隐藏退化

    Args:
        store: BrainOS 数据库
        from_snapshot_id: 起始快照
        to_snapshot_id: 结束快照

    Returns:
        CompareResult: 完整对比结果
    """
    # 1. 加载快照
    snap_from = load_snapshot(store, from_snapshot_id)
    snap_to = load_snapshot(store, to_snapshot_id)

    # 2. 对比实体
    entity_diffs = compare_entities(snap_from.entities, snap_to.entities)

    # 3. 对比边
    edge_diffs = compare_edges(snap_from.edges, snap_to.edges)

    # 4. 对比盲区
    blind_spot_diffs = compare_blind_spots(snap_from.entities, snap_to.entities)

    # 5. 对比覆盖度
    coverage_diffs = compare_coverage(snap_from.summary, snap_to.summary)

    # 6. 统计
    entities_added = len([d for d in entity_diffs if d.change_type == ChangeType.ADDED])
    entities_removed = len([d for d in entity_diffs if d.change_type == ChangeType.REMOVED])
    entities_weakened = len([d for d in entity_diffs if d.change_type == ChangeType.WEAKENED])
    entities_strengthened = len([d for d in entity_diffs if d.change_type == ChangeType.STRENGTHENED])

    edges_added = len([d for d in edge_diffs if d.change_type == ChangeType.ADDED])
    edges_removed = len([d for d in edge_diffs if d.change_type == ChangeType.REMOVED])
    edges_weakened = len([d for d in edge_diffs if d.change_type == ChangeType.WEAKENED])
    edges_strengthened = len([d for d in edge_diffs if d.change_type == ChangeType.STRENGTHENED])

    blind_spots_added = len([d for d in blind_spot_diffs if d.change_type == ChangeType.ADDED])
    blind_spots_removed = len([d for d in blind_spot_diffs if d.change_type == ChangeType.REMOVED])

    # 7. 总体评估
    overall_assessment, health_score_change = assess_overall_change(
        entities_added, entities_removed, entities_weakened, entities_strengthened,
        edges_added, edges_removed, edges_weakened, edges_strengthened,
        blind_spots_added, blind_spots_removed,
        coverage_diffs
    )

    result = CompareResult(
        from_snapshot_id=from_snapshot_id,
        to_snapshot_id=to_snapshot_id,
        from_timestamp=snap_from.summary.timestamp,
        to_timestamp=snap_to.summary.timestamp,
        entity_diffs=entity_diffs,
        entities_added=entities_added,
        entities_removed=entities_removed,
        entities_weakened=entities_weakened,
        entities_strengthened=entities_strengthened,
        edge_diffs=edge_diffs,
        edges_added=edges_added,
        edges_removed=edges_removed,
        edges_weakened=edges_weakened,
        edges_strengthened=edges_strengthened,
        blind_spot_diffs=blind_spot_diffs,
        blind_spots_added=blind_spots_added,
        blind_spots_removed=blind_spots_removed,
        coverage_diffs=coverage_diffs,
        overall_assessment=overall_assessment,
        health_score_change=health_score_change,
        computed_at=utc_now_iso()
    )

    # P4-A Hook: 生成决策记录
    try:
        from ..governance.decision_recorder import record_compare_decision
        record_compare_decision(store, from_snapshot_id, to_snapshot_id, result)
    except Exception as e:
        # 不影响主流程
        import logging
        logging.getLogger(__name__).warning(f"Failed to record compare decision: {e}")

    return result


def compare_entities(
    before: List[SnapshotEntity],
    after: List[SnapshotEntity]
) -> List[EntityDiff]:
    """
    对比实体变化

    逻辑：
    1. 按 entity_id 分组
    2. 只在 before：REMOVED
    3. 只在 after：ADDED
    4. 都在：比较属性
       - evidence_count 减少：WEAKENED
       - coverage_sources 减少：WEAKENED
       - evidence_count 增加：STRENGTHENED
    """
    before_map = {e.entity_id: e for e in before}
    after_map = {e.entity_id: e for e in after}

    diffs = []

    all_ids = set(before_map.keys()) | set(after_map.keys())

    for entity_id in all_ids:
        before_entity = before_map.get(entity_id)
        after_entity = after_map.get(entity_id)

        if before_entity and not after_entity:
            # REMOVED
            diffs.append(EntityDiff(
                entity_id=entity_id,
                entity_type=before_entity.entity_type,
                entity_key=before_entity.entity_key,
                entity_name=before_entity.entity_name,
                change_type=ChangeType.REMOVED,
                before_evidence_count=before_entity.evidence_count,
                after_evidence_count=None,
                before_coverage_sources=before_entity.coverage_sources,
                after_coverage_sources=None,
                before_is_blind_spot=before_entity.is_blind_spot,
                after_is_blind_spot=None,
                change_description=f"Entity removed from graph"
            ))

        elif after_entity and not before_entity:
            # ADDED
            diffs.append(EntityDiff(
                entity_id=entity_id,
                entity_type=after_entity.entity_type,
                entity_key=after_entity.entity_key,
                entity_name=after_entity.entity_name,
                change_type=ChangeType.ADDED,
                before_evidence_count=None,
                after_evidence_count=after_entity.evidence_count,
                before_coverage_sources=None,
                after_coverage_sources=after_entity.coverage_sources,
                before_is_blind_spot=None,
                after_is_blind_spot=after_entity.is_blind_spot,
                change_description=f"New entity added to graph"
            ))

        else:
            # 比较属性
            before_ev = before_entity.evidence_count
            after_ev = after_entity.evidence_count

            before_cov = len(before_entity.coverage_sources)
            after_cov = len(after_entity.coverage_sources)

            if after_ev < before_ev or after_cov < before_cov:
                # WEAKENED
                change_desc = []
                if after_ev < before_ev:
                    change_desc.append(f"Evidence reduced from {before_ev} to {after_ev}")
                if after_cov < before_cov:
                    change_desc.append(f"Coverage reduced from {before_cov} to {after_cov} sources")

                diffs.append(EntityDiff(
                    entity_id=entity_id,
                    entity_type=after_entity.entity_type,
                    entity_key=after_entity.entity_key,
                    entity_name=after_entity.entity_name,
                    change_type=ChangeType.WEAKENED,
                    before_evidence_count=before_ev,
                    after_evidence_count=after_ev,
                    before_coverage_sources=before_entity.coverage_sources,
                    after_coverage_sources=after_entity.coverage_sources,
                    before_is_blind_spot=before_entity.is_blind_spot,
                    after_is_blind_spot=after_entity.is_blind_spot,
                    change_description="; ".join(change_desc)
                ))

            elif after_ev > before_ev or after_cov > before_cov:
                # STRENGTHENED
                change_desc = []
                if after_ev > before_ev:
                    change_desc.append(f"Evidence increased from {before_ev} to {after_ev}")
                if after_cov > before_cov:
                    change_desc.append(f"Coverage increased from {before_cov} to {after_cov} sources")

                diffs.append(EntityDiff(
                    entity_id=entity_id,
                    entity_type=after_entity.entity_type,
                    entity_key=after_entity.entity_key,
                    entity_name=after_entity.entity_name,
                    change_type=ChangeType.STRENGTHENED,
                    before_evidence_count=before_ev,
                    after_evidence_count=after_ev,
                    before_coverage_sources=before_entity.coverage_sources,
                    after_coverage_sources=after_entity.coverage_sources,
                    before_is_blind_spot=before_entity.is_blind_spot,
                    after_is_blind_spot=after_entity.is_blind_spot,
                    change_description="; ".join(change_desc)
                ))

    return diffs


def compare_edges(
    before: List[SnapshotEdge],
    after: List[SnapshotEdge]
) -> List[EdgeDiff]:
    """
    对比边变化

    逻辑同 compare_entities
    """
    before_map = {e.edge_id: e for e in before}
    after_map = {e.edge_id: e for e in after}

    diffs = []

    all_ids = set(before_map.keys()) | set(after_map.keys())

    for edge_id in all_ids:
        before_edge = before_map.get(edge_id)
        after_edge = after_map.get(edge_id)

        if before_edge and not after_edge:
            # REMOVED
            diffs.append(EdgeDiff(
                edge_id=edge_id,
                src_entity_id=before_edge.src_entity_id,
                dst_entity_id=before_edge.dst_entity_id,
                edge_type=before_edge.edge_type,
                change_type=ChangeType.REMOVED,
                before_evidence_count=before_edge.evidence_count,
                after_evidence_count=None,
                before_evidence_types=before_edge.evidence_types,
                after_evidence_types=None,
                change_description="Edge removed from graph"
            ))

        elif after_edge and not before_edge:
            # ADDED
            diffs.append(EdgeDiff(
                edge_id=edge_id,
                src_entity_id=after_edge.src_entity_id,
                dst_entity_id=after_edge.dst_entity_id,
                edge_type=after_edge.edge_type,
                change_type=ChangeType.ADDED,
                before_evidence_count=None,
                after_evidence_count=after_edge.evidence_count,
                before_evidence_types=None,
                after_evidence_types=after_edge.evidence_types,
                change_description="New edge added to graph"
            ))

        else:
            # 比较证据
            before_ev = before_edge.evidence_count
            after_ev = after_edge.evidence_count

            if after_ev < before_ev:
                diffs.append(EdgeDiff(
                    edge_id=edge_id,
                    src_entity_id=after_edge.src_entity_id,
                    dst_entity_id=after_edge.dst_entity_id,
                    edge_type=after_edge.edge_type,
                    change_type=ChangeType.WEAKENED,
                    before_evidence_count=before_ev,
                    after_evidence_count=after_ev,
                    before_evidence_types=before_edge.evidence_types,
                    after_evidence_types=after_edge.evidence_types,
                    change_description=f"Evidence reduced from {before_ev} to {after_ev}"
                ))

            elif after_ev > before_ev:
                diffs.append(EdgeDiff(
                    edge_id=edge_id,
                    src_entity_id=after_edge.src_entity_id,
                    dst_entity_id=after_edge.dst_entity_id,
                    edge_type=after_edge.edge_type,
                    change_type=ChangeType.STRENGTHENED,
                    before_evidence_count=before_ev,
                    after_evidence_count=after_ev,
                    before_evidence_types=before_edge.evidence_types,
                    after_evidence_types=after_edge.evidence_types,
                    change_description=f"Evidence increased from {before_ev} to {after_ev}"
                ))

    return diffs


def compare_blind_spots(
    before: List[SnapshotEntity],
    after: List[SnapshotEntity]
) -> List[BlindSpotDiff]:
    """
    对比盲区变化
    """
    before_blind_spots = {e.entity_id: e for e in before if e.is_blind_spot}
    after_blind_spots = {e.entity_id: e for e in after if e.is_blind_spot}

    diffs = []

    all_ids = set(before_blind_spots.keys()) | set(after_blind_spots.keys())

    for entity_id in all_ids:
        before_bs = before_blind_spots.get(entity_id)
        after_bs = after_blind_spots.get(entity_id)

        if before_bs and not after_bs:
            # 盲区被解决
            diffs.append(BlindSpotDiff(
                entity_id=entity_id,
                entity_name=before_bs.entity_name,
                change_type=ChangeType.REMOVED,
                before_severity=before_bs.blind_spot_severity,
                after_severity=None,
                change_description="Blind spot resolved"
            ))

        elif after_bs and not before_bs:
            # 新盲区出现
            diffs.append(BlindSpotDiff(
                entity_id=entity_id,
                entity_name=after_bs.entity_name,
                change_type=ChangeType.ADDED,
                before_severity=None,
                after_severity=after_bs.blind_spot_severity,
                change_description="New blind spot detected"
            ))

    return diffs


def compare_coverage(
    before,  # SnapshotSummary
    after   # SnapshotSummary
) -> List[CoverageDiff]:
    """
    对比覆盖度变化
    """
    diffs = []

    metrics = [
        ("coverage_percentage", before.coverage_percentage, after.coverage_percentage),
    ]

    for metric_name, before_val, after_val in metrics:
        change_pct = ((after_val - before_val) / before_val * 100) if before_val > 0 else 0

        diffs.append(CoverageDiff(
            metric_name=metric_name,
            before_value=before_val,
            after_value=after_val,
            change_percentage=change_pct,
            is_degradation=(after_val < before_val)
        ))

    return diffs


def assess_overall_change(
    entities_added, entities_removed, entities_weakened, entities_strengthened,
    edges_added, edges_removed, edges_weakened, edges_strengthened,
    blind_spots_added, blind_spots_removed,
    coverage_diffs
) -> tuple:
    """
    总体评估

    返回：
    - overall_assessment: "IMPROVED" / "DEGRADED" / "MIXED"
    - health_score_change: -1 to +1
    """
    # 实体和边的变化权重更高
    positive_score = (
        entities_added * 2 +
        entities_strengthened * 3 +
        edges_added * 2 +
        edges_strengthened * 3 +
        blind_spots_removed * 5
    )

    negative_score = (
        entities_removed * 3 +
        entities_weakened * 4 +
        edges_removed * 3 +
        edges_weakened * 4 +
        blind_spots_added * 1  # 盲区新增权重较低（可能是正常的新实体）
    )

    # 覆盖度退化惩罚
    for cov_diff in coverage_diffs:
        if cov_diff.is_degradation:
            negative_score += 10

    total_changes = positive_score + negative_score

    if total_changes == 0:
        return "UNCHANGED", 0.0

    health_score_change = (positive_score - negative_score) / total_changes

    if health_score_change > 0.15:
        return "IMPROVED", health_score_change
    elif health_score_change < -0.15:
        return "DEGRADED", health_score_change
    else:
        return "MIXED", health_score_change
