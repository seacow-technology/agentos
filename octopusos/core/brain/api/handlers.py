"""
BrainOS API Handlers

WebUI API 适配器（包含 P3-A Navigation 和 P3-B Compare）

提供的端点：
- /api/brain/navigate - 导航查询
- /api/brain/zone - 区域检测
- /api/brain/coverage - 覆盖度查询
- /api/brain/blind-spots - 盲区检测
- /api/brain/snapshots - 快照管理（P3-B）
- /api/brain/compare - 快照对比（P3-B）
"""

import logging
from typing import Dict, Any, Optional
from ..store import SQLiteStore
from ..navigation import navigate, detect_zone, compute_zone_metrics
from ..service.coverage import compute_coverage
from ..service.blind_spot import detect_blind_spots
from ..compare import (
    capture_snapshot,
    list_snapshots,
    load_snapshot,
    delete_snapshot,
    compare_snapshots
)

logger = logging.getLogger(__name__)


def handle_navigate(
    store: SQLiteStore,
    seed: str,
    goal: Optional[str] = None,
    max_hops: int = 3,
    max_paths: int = 3
) -> Dict[str, Any]:
    """
    处理导航请求

    Args:
        store: BrainOS 数据库
        seed: 起点实体
        goal: 终点实体（可选）
        max_hops: 最大跳数
        max_paths: 最多返回路径数

    Returns:
        Dict: 导航结果（JSON 格式）
    """
    try:
        result = navigate(store, seed, goal, max_hops, max_paths)
        return {
            "status": "success",
            "data": result.to_dict()
        }
    except Exception as e:
        logger.error(f"Navigation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_zone_detection(
    store: SQLiteStore,
    entity_id: str
) -> Dict[str, Any]:
    """
    处理区域检测请求

    Args:
        store: BrainOS 数据库
        entity_id: 实体 ID

    Returns:
        Dict: 区域检测结果（JSON 格式）
    """
    try:
        zone = detect_zone(store, entity_id)
        metrics = compute_zone_metrics(store, entity_id)

        return {
            "status": "success",
            "data": {
                "entity_id": entity_id,
                "zone": zone.value,
                "metrics": metrics.to_dict()
            }
        }
    except Exception as e:
        logger.error(f"Zone detection failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_coverage(store: SQLiteStore) -> Dict[str, Any]:
    """
    处理覆盖度查询请求

    Args:
        store: BrainOS 数据库

    Returns:
        Dict: 覆盖度结果（JSON 格式）
    """
    try:
        metrics = compute_coverage(store)
        return {
            "status": "success",
            "data": metrics.to_dict()
        }
    except Exception as e:
        logger.error(f"Coverage computation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_blind_spots(
    store: SQLiteStore,
    threshold: int = 5,
    max_results: int = 50
) -> Dict[str, Any]:
    """
    处理盲区检测请求

    Args:
        store: BrainOS 数据库
        threshold: 高扇入阈值
        max_results: 最多返回结果数

    Returns:
        Dict: 盲区检测结果（JSON 格式）
    """
    try:
        report = detect_blind_spots(store, threshold, max_results)
        return {
            "status": "success",
            "data": report.to_dict()
        }
    except Exception as e:
        logger.error(f"Blind spot detection failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# ========== P3-B: Compare API Handlers ==========


def handle_create_snapshot(
    store: SQLiteStore,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建快照

    Args:
        store: BrainOS 数据库
        description: 快照描述（可选）

    Returns:
        Dict: 创建结果（JSON 格式）
    """
    try:
        snapshot_id = capture_snapshot(store, description)
        return {
            "status": "success",
            "data": {
                "snapshot_id": snapshot_id,
                "message": f"Snapshot created: {snapshot_id}"
            }
        }
    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_list_snapshots(
    store: SQLiteStore,
    limit: int = 10
) -> Dict[str, Any]:
    """
    列出快照

    Args:
        store: BrainOS 数据库
        limit: 返回数量限制

    Returns:
        Dict: 快照列表（JSON 格式）
    """
    try:
        snapshots = list_snapshots(store, limit)
        return {
            "status": "success",
            "data": {
                "snapshots": [
                    {
                        "snapshot_id": s.snapshot_id,
                        "timestamp": s.timestamp,
                        "description": s.description,
                        "entity_count": s.entity_count,
                        "edge_count": s.edge_count,
                        "evidence_count": s.evidence_count,
                        "coverage_percentage": s.coverage_percentage,
                        "blind_spot_count": s.blind_spot_count,
                        "graph_version": s.graph_version
                    }
                    for s in snapshots
                ],
                "total": len(snapshots)
            }
        }
    except Exception as e:
        logger.error(f"List snapshots failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_get_snapshot(
    store: SQLiteStore,
    snapshot_id: str
) -> Dict[str, Any]:
    """
    获取快照详情

    Args:
        store: BrainOS 数据库
        snapshot_id: 快照 ID

    Returns:
        Dict: 快照详情（JSON 格式）
    """
    try:
        snapshot = load_snapshot(store, snapshot_id)
        return {
            "status": "success",
            "data": {
                "summary": {
                    "snapshot_id": snapshot.summary.snapshot_id,
                    "timestamp": snapshot.summary.timestamp,
                    "description": snapshot.summary.description,
                    "entity_count": snapshot.summary.entity_count,
                    "edge_count": snapshot.summary.edge_count,
                    "evidence_count": snapshot.summary.evidence_count,
                    "coverage_percentage": snapshot.summary.coverage_percentage,
                    "blind_spot_count": snapshot.summary.blind_spot_count,
                    "graph_version": snapshot.summary.graph_version
                },
                "entities_count": len(snapshot.entities),
                "edges_count": len(snapshot.edges)
            }
        }
    except ValueError as e:
        return {
            "status": "error",
            "error": f"Snapshot not found: {snapshot_id}"
        }
    except Exception as e:
        logger.error(f"Get snapshot failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_delete_snapshot(
    store: SQLiteStore,
    snapshot_id: str
) -> Dict[str, Any]:
    """
    删除快照

    Args:
        store: BrainOS 数据库
        snapshot_id: 快照 ID

    Returns:
        Dict: 删除结果（JSON 格式）
    """
    try:
        success = delete_snapshot(store, snapshot_id)
        if success:
            return {
                "status": "success",
                "data": {
                    "message": f"Snapshot deleted: {snapshot_id}"
                }
            }
        else:
            return {
                "status": "error",
                "error": f"Snapshot not found: {snapshot_id}"
            }
    except Exception as e:
        logger.error(f"Delete snapshot failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def handle_compare_snapshots(
    store: SQLiteStore,
    from_snapshot_id: str,
    to_snapshot_id: str
) -> Dict[str, Any]:
    """
    对比两个快照

    Red Line 2 验证：必须显示所有退化变化

    Args:
        store: BrainOS 数据库
        from_snapshot_id: 起始快照
        to_snapshot_id: 结束快照

    Returns:
        Dict: 对比结果（JSON 格式）
    """
    try:
        result = compare_snapshots(store, from_snapshot_id, to_snapshot_id)

        return {
            "status": "success",
            "data": {
                "from_snapshot_id": result.from_snapshot_id,
                "to_snapshot_id": result.to_snapshot_id,
                "from_timestamp": result.from_timestamp,
                "to_timestamp": result.to_timestamp,

                # 实体变化统计
                "entities_summary": {
                    "added": result.entities_added,
                    "removed": result.entities_removed,
                    "weakened": result.entities_weakened,
                    "strengthened": result.entities_strengthened
                },

                # 边变化统计
                "edges_summary": {
                    "added": result.edges_added,
                    "removed": result.edges_removed,
                    "weakened": result.edges_weakened,
                    "strengthened": result.edges_strengthened
                },

                # 盲区变化统计
                "blind_spots_summary": {
                    "added": result.blind_spots_added,
                    "removed": result.blind_spots_removed
                },

                # 覆盖度变化
                "coverage_changes": [
                    {
                        "metric": c.metric_name,
                        "before": c.before_value,
                        "after": c.after_value,
                        "change_percentage": c.change_percentage,
                        "is_degradation": c.is_degradation
                    }
                    for c in result.coverage_diffs
                ],

                # 实体变化详情（前 20 个）
                "entity_changes": [
                    {
                        "entity_id": d.entity_id,
                        "entity_type": d.entity_type,
                        "entity_name": d.entity_name,
                        "change_type": d.change_type.value,
                        "before_evidence_count": d.before_evidence_count,
                        "after_evidence_count": d.after_evidence_count,
                        "change_description": d.change_description
                    }
                    for d in result.entity_diffs[:20]
                ],

                # 边变化详情（前 20 个）
                "edge_changes": [
                    {
                        "edge_id": d.edge_id,
                        "src_entity_id": d.src_entity_id,
                        "dst_entity_id": d.dst_entity_id,
                        "edge_type": d.edge_type,
                        "change_type": d.change_type.value,
                        "before_evidence_count": d.before_evidence_count,
                        "after_evidence_count": d.after_evidence_count,
                        "change_description": d.change_description
                    }
                    for d in result.edge_diffs[:20]
                ],

                # 盲区变化详情（前 20 个）
                "blind_spot_changes": [
                    {
                        "entity_id": d.entity_id,
                        "entity_name": d.entity_name,
                        "change_type": d.change_type.value,
                        "before_severity": d.before_severity,
                        "after_severity": d.after_severity,
                        "change_description": d.change_description
                    }
                    for d in result.blind_spot_diffs[:20]
                ],

                # 总体评估
                "overall_assessment": result.overall_assessment,
                "health_score_change": result.health_score_change,
                "computed_at": result.computed_at
            }
        }
    except ValueError as e:
        return {
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Compare snapshots failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
