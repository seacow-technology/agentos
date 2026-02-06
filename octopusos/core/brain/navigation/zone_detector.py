"""
Zone Detector - 判断节点所在的认知区域

核心逻辑：
- CORE: coverage_ratio >= 0.66 AND evidence_density > avg AND NOT blind_spot
- EDGE: 0.33 < coverage_ratio < 0.66 OR evidence_density ~ avg
- NEAR_BLIND: coverage_ratio <= 0.33 OR blind_spot_severity >= 0.5
"""

import logging
from typing import List
from .models import CognitiveZone, ZoneMetrics
from ..store import SQLiteStore

logger = logging.getLogger(__name__)


def detect_zone(store: SQLiteStore, entity_id: str) -> CognitiveZone:
    """
    判断实体所在的认知区域

    Args:
        store: BrainOS 数据库
        entity_id: 实体 ID

    Returns:
        CognitiveZone (CORE/EDGE/NEAR_BLIND)
    """
    # 1. 计算区域指标
    metrics = compute_zone_metrics(store, entity_id)

    # 2. 应用规则
    if is_core_zone(metrics):
        return CognitiveZone.CORE
    elif is_near_blind_zone(metrics):
        return CognitiveZone.NEAR_BLIND
    else:
        return CognitiveZone.EDGE


def compute_zone_metrics(store: SQLiteStore, entity_id: str) -> ZoneMetrics:
    """
    计算区域指标

    计算：
    1. evidence_count: 该实体的总证据数
    2. coverage_sources: Git/Doc/Code 覆盖情况
    3. is_blind_spot: 是否为盲区
    4. centrality: 拓扑中心性
    """
    cursor = store.conn.cursor()

    # 查询实体基本信息
    cursor.execute("""
        SELECT type, key, name
        FROM entities
        WHERE id = ?
    """, (entity_id,))

    entity = cursor.fetchone()
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")

    # 1. 证据数
    cursor.execute("""
        SELECT COUNT(DISTINCT ev.id)
        FROM evidence ev
        JOIN edges e ON e.id = ev.edge_id
        WHERE e.src_entity_id = ? OR e.dst_entity_id = ?
    """, (entity_id, entity_id))

    evidence_count = cursor.fetchone()[0]

    # 2. 覆盖来源
    cursor.execute("""
        SELECT DISTINCT ev.source_type
        FROM evidence ev
        JOIN edges e ON e.id = ev.edge_id
        WHERE e.src_entity_id = ? OR e.dst_entity_id = ?
    """, (entity_id, entity_id))

    evidence_types = [row[0] for row in cursor.fetchall()]
    coverage_sources = infer_sources(evidence_types)

    # 3. 盲区信息
    # 调用 P1 的 detect_blind_spots，但需要修改为支持单个实体查询
    from ..service.blind_spot import detect_blind_spots_for_entities

    blind_spots = detect_blind_spots_for_entities(store, entity_ids=[entity_id])

    is_blind_spot = len(blind_spots) > 0
    blind_spot_severity = blind_spots[0].severity if blind_spots else None

    # 4. 拓扑度数
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM edges WHERE dst_entity_id = ?) as in_degree,
            (SELECT COUNT(*) FROM edges WHERE src_entity_id = ?) as out_degree
    """, (entity_id, entity_id))

    in_degree, out_degree = cursor.fetchone()

    # 5. 计算平均度数（用于相对中心性）
    cursor.execute("""
        SELECT AVG(degree) FROM (
            SELECT COUNT(*) as degree
            FROM edges
            GROUP BY src_entity_id
            UNION ALL
            SELECT COUNT(*) as degree
            FROM edges
            GROUP BY dst_entity_id
        )
    """)

    avg_degree = cursor.fetchone()[0] or 1.0
    centrality = (in_degree + out_degree) / avg_degree

    # 6. 计算 zone_score（综合评分）
    coverage_ratio = len(coverage_sources) / 3.0
    evidence_density = evidence_count / 10.0  # 归一化，假设 10 为高密度阈值

    zone_score = (
        0.4 * coverage_ratio +
        0.3 * min(evidence_density, 1.0) +
        0.2 * (1.0 if not is_blind_spot else 0.0) +
        0.1 * min(centrality, 1.0)
    )

    return ZoneMetrics(
        entity_id=entity_id,
        evidence_count=evidence_count,
        evidence_density=evidence_density,
        coverage_sources=coverage_sources,
        coverage_ratio=coverage_ratio,
        is_blind_spot=is_blind_spot,
        blind_spot_severity=blind_spot_severity,
        in_degree=in_degree,
        out_degree=out_degree,
        centrality=centrality,
        zone_score=zone_score
    )


def is_core_zone(metrics: ZoneMetrics) -> bool:
    """
    判断是否为核心区

    条件：
    - coverage_ratio >= 0.66 (至少 2 源)
    - zone_score >= 0.6
    - NOT blind_spot OR blind_spot_severity < 0.3
    """
    return (
        metrics.coverage_ratio >= 0.66 and
        metrics.zone_score >= 0.6 and
        (not metrics.is_blind_spot or (metrics.blind_spot_severity and metrics.blind_spot_severity < 0.3))
    )


def is_near_blind_zone(metrics: ZoneMetrics) -> bool:
    """
    判断是否为近盲区

    条件：
    - coverage_ratio <= 0.33 (最多 1 源)
    - OR blind_spot_severity >= 0.5
    - OR zone_score < 0.3
    """
    return (
        metrics.coverage_ratio <= 0.33 or
        (metrics.is_blind_spot and metrics.blind_spot_severity and metrics.blind_spot_severity >= 0.5) or
        metrics.zone_score < 0.3
    )


def infer_sources(evidence_types: List[str]) -> List[str]:
    """
    从 evidence.type 推断覆盖来源

    映射：
    - git_commit, git_* -> "git"
    - doc_mention, doc_* -> "doc"
    - code_reference, code_* -> "code"
    """
    sources = set()

    for ev_type in evidence_types:
        if ev_type.startswith('git'):
            sources.add('git')
        elif ev_type.startswith('doc'):
            sources.add('doc')
        elif ev_type.startswith('code'):
            sources.add('code')

    return sorted(list(sources))


def get_zone_description(zone: CognitiveZone, metrics: ZoneMetrics) -> str:
    """
    生成区域描述（用户友好）
    """
    if zone == CognitiveZone.CORE:
        return f"CORE zone: High confidence area with {len(metrics.coverage_sources)} source types and {metrics.evidence_count} evidence."
    elif zone == CognitiveZone.EDGE:
        return f"EDGE zone: Moderate confidence area with {len(metrics.coverage_sources)} source types."
    else:
        return f"NEAR-BLIND zone: Low confidence area. Consider exploring safer paths."
