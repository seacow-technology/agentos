"""
Path Engine - 证据加权路径搜索

核心算法：
- 使用 Dijkstra 算法
- 边权重 = 1 / (evidence_count + 1) - 证据越多，权重越小（越"近"）
- 额外惩罚：盲区节点 +5，零覆盖节点 +10
"""

import logging
from typing import List, Optional, Dict, Set, Tuple
from collections import defaultdict
import heapq
from .models import Path, PathNode, PathType, RiskLevel, CognitiveZone
from .zone_detector import detect_zone
from .risk_model import compute_path_score, compute_path_confidence, compute_path_risk, generate_recommendation_reason
from ..store import SQLiteStore

logger = logging.getLogger(__name__)


def find_paths(
    store: SQLiteStore,
    seed: str,
    goal: Optional[str] = None,
    max_hops: int = 3,
    max_paths: int = 3
) -> List[Path]:
    """
    查找从 seed 到 goal 的推荐路径（如果 goal 为 None，则探索性推荐）

    返回 3 种类型的路径（如果存在）：
    1. SAFE: 最安全路径（高证据、低盲区）
    2. INFORMATIVE: 最信息增量路径（探索新区域）
    3. CONSERVATIVE: 最保守路径（避开盲区）

    Args:
        store: BrainOS 数据库
        seed: 起点实体（格式: "file:xxx" or entity_id）
        goal: 终点实体（可选）
        max_hops: 最大跳数
        max_paths: 最多返回路径数

    Returns:
        List[Path]: 推荐路径列表
    """
    # 1. 解析 seed 和 goal
    seed_id = resolve_entity_id(store, seed)
    goal_id = resolve_entity_id(store, goal) if goal else None

    logger.info(f"Finding paths from {seed_id} to {goal_id or 'exploration'} (max_hops={max_hops})")

    # 2. 如果有明确 goal，用 Dijkstra 找路径
    if goal_id:
        all_paths = dijkstra_paths(store, seed_id, goal_id, max_hops)
    else:
        # 探索模式：找到周围可达的节点
        all_paths = explore_paths(store, seed_id, max_hops)

    logger.info(f"Found {len(all_paths)} raw paths")

    # 3. 对路径分类和排序
    categorized_paths = categorize_paths(store, all_paths)

    # 4. 从每个类别选最佳路径
    recommended_paths = []

    for path_type in [PathType.SAFE, PathType.INFORMATIVE, PathType.CONSERVATIVE]:
        if path_type in categorized_paths and categorized_paths[path_type]:
            best_path = categorized_paths[path_type][0]
            recommended_paths.append(best_path)

    logger.info(f"Returning {len(recommended_paths)} recommended paths")
    return recommended_paths[:max_paths]


def dijkstra_paths(
    store: SQLiteStore,
    start_id: str,
    goal_id: str,
    max_hops: int
) -> List[List[str]]:
    """
    使用 Dijkstra 算法查找路径

    边权重 = 1 / (evidence_count + 1) + blind_spot_penalty

    返回：
    - 所有从 start 到 goal 的路径（距离 <= max_hops）
    """
    # 构建图（邻接表）
    graph = build_graph(store)

    # Dijkstra
    distances = {start_id: 0}
    visited = set()
    pq = [(0, start_id, [])]  # (distance, node_id, path)

    all_paths = []

    while pq:
        dist, current, path = heapq.heappop(pq)

        if current in visited:
            continue

        visited.add(current)
        path = path + [current]

        # 找到目标
        if current == goal_id:
            if len(path) <= max_hops + 1:
                all_paths.append(path)
            continue

        # 探索邻居
        if len(path) > max_hops:
            continue

        for neighbor, edge_data in graph.get(current, []):
            if neighbor not in visited:
                weight = compute_edge_weight(store, edge_data, neighbor)
                new_dist = dist + weight

                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor, path))

    return all_paths


def explore_paths(
    store: SQLiteStore,
    start_id: str,
    max_hops: int
) -> List[List[str]]:
    """
    探索模式：从 start 开始，找到所有可达的节点

    返回：
    - 到达不同节点的路径（按权重排序，取前 10 条）
    """
    graph = build_graph(store)

    # BFS + 权重排序
    visited = set()
    pq = [(0, start_id, [])]

    all_paths = []

    while pq and len(all_paths) < 20:  # 最多探索 20 条路径
        dist, current, path = heapq.heappop(pq)

        if current in visited:
            continue

        visited.add(current)
        path = path + [current]

        # 记录路径（排除起点）
        if len(path) > 1 and len(path) <= max_hops + 1:
            all_paths.append(path)

        # 继续探索
        if len(path) > max_hops:
            continue

        for neighbor, edge_data in graph.get(current, []):
            if neighbor not in visited:
                weight = compute_edge_weight(store, edge_data, neighbor)
                new_dist = dist + weight
                heapq.heappush(pq, (new_dist, neighbor, path))

    return all_paths


def build_graph(store: SQLiteStore) -> Dict[str, List[Tuple[str, Dict]]]:
    """
    构建图的邻接表

    返回：
    {
        entity_id: [
            (neighbor_id, {"edge_id": ..., "evidence_count": ...}),
            ...
        ]
    }
    """
    cursor = store.conn.cursor()

    # 查询所有有证据的边
    cursor.execute("""
        SELECT
            e.id as edge_id,
            e.src_entity_id,
            e.dst_entity_id,
            e.type as edge_type,
            COUNT(DISTINCT ev.id) as evidence_count
        FROM edges e
        LEFT JOIN evidence ev ON ev.edge_id = e.id
        GROUP BY e.id
        HAVING evidence_count > 0
    """)

    graph = defaultdict(list)

    for row in cursor.fetchall():
        edge_id, src_id, dst_id, edge_type, evidence_count = row

        edge_data = {
            "edge_id": edge_id,
            "edge_type": edge_type,
            "evidence_count": evidence_count
        }

        # 无向图（双向边）
        graph[src_id].append((dst_id, edge_data))
        graph[dst_id].append((src_id, edge_data))

    return graph


def compute_edge_weight(store: SQLiteStore, edge_data: Dict, target_entity_id: str) -> float:
    """
    计算边权重

    公式：
    weight = 1 / (evidence_count + 1) + blind_spot_penalty

    越多证据 = 权重越小（越"近"）
    """
    evidence_count = edge_data.get("evidence_count", 0)

    base_weight = 1.0 / (evidence_count + 1)

    # 检查目标节点是否为盲区，添加惩罚
    from ..service.blind_spot import detect_blind_spots_for_entities
    blind_spots = detect_blind_spots_for_entities(store, entity_ids=[target_entity_id])

    blind_spot_penalty = 5.0 if blind_spots else 0.0

    return base_weight + blind_spot_penalty


def categorize_paths(store: SQLiteStore, all_paths: List[List[str]]) -> Dict[PathType, List[Path]]:
    """
    对路径分类

    - SAFE: 总 blind_spot_count 最小
    - INFORMATIVE: zone_diversity 最大（探索新区域）
    - CONSERVATIVE: 避开 NEAR_BLIND 区域

    返回：
    {
        PathType.SAFE: [Path, ...],
        PathType.INFORMATIVE: [Path, ...],
        PathType.CONSERVATIVE: [Path, ...]
    }
    """
    categorized = {
        PathType.SAFE: [],
        PathType.INFORMATIVE: [],
        PathType.CONSERVATIVE: []
    }

    for path_node_ids in all_paths:
        # 构建 Path 对象
        path = build_path_object(store, path_node_ids)

        # 计算评分
        score = compute_path_score(store, path)

        # 分类
        if score.blind_spot_penalty == 0:
            path.recommendation_reason = generate_recommendation_reason(path, "SAFE")
            categorized[PathType.SAFE].append(path)

        if score.coverage_diversity > 0.5:
            path_copy = Path(
                path_id=path.path_id + "_informative",
                path_type=PathType.INFORMATIVE,
                nodes=path.nodes,
                confidence=path.confidence,
                risk_level=path.risk_level,
                total_hops=path.total_hops,
                total_evidence=path.total_evidence,
                coverage_sources=path.coverage_sources,
                blind_spot_count=path.blind_spot_count,
                recommendation_reason=generate_recommendation_reason(path, "INFORMATIVE")
            )
            categorized[PathType.INFORMATIVE].append(path_copy)

        if path.blind_spot_count == 0:
            path_copy = Path(
                path_id=path.path_id + "_conservative",
                path_type=PathType.CONSERVATIVE,
                nodes=path.nodes,
                confidence=path.confidence,
                risk_level=path.risk_level,
                total_hops=path.total_hops,
                total_evidence=path.total_evidence,
                coverage_sources=path.coverage_sources,
                blind_spot_count=path.blind_spot_count,
                recommendation_reason=generate_recommendation_reason(path, "CONSERVATIVE")
            )
            categorized[PathType.CONSERVATIVE].append(path_copy)

    # 排序
    for path_type in categorized:
        categorized[path_type].sort(key=lambda p: p.confidence, reverse=True)

    return categorized


def build_path_object(store: SQLiteStore, node_ids: List[str]) -> Path:
    """
    从节点 ID 列表构建 Path 对象
    """
    cursor = store.conn.cursor()

    path_nodes = []
    total_evidence = 0
    blind_spot_count = 0
    coverage_sources = set()

    for i, node_id in enumerate(node_ids):
        # 查询节点信息
        cursor.execute("""
            SELECT type, key, name
            FROM entities
            WHERE id = ?
        """, (node_id,))

        entity = cursor.fetchone()
        if not entity:
            continue

        entity_type, entity_key, entity_name = entity

        # 判断区域
        zone = detect_zone(store, node_id)

        # 检查盲区
        from ..service.blind_spot import detect_blind_spots_for_entities
        blind_spots = detect_blind_spots_for_entities(store, entity_ids=[node_id])
        is_blind_spot = len(blind_spots) > 0

        if is_blind_spot:
            blind_spot_count += 1

        # 获取覆盖来源
        cursor.execute("""
            SELECT DISTINCT ev.source_type
            FROM evidence ev
            JOIN edges e ON e.id = ev.edge_id
            WHERE e.src_entity_id = ? OR e.dst_entity_id = ?
        """, (node_id, node_id))

        evidence_types = [row[0] for row in cursor.fetchall()]
        from .zone_detector import infer_sources
        node_sources = infer_sources(evidence_types)
        coverage_sources.update(node_sources)

        # 获取边信息（如果不是第一个节点）
        edge_id = None
        edge_type = None
        evidence_count = 0

        if i > 0:
            prev_node_id = node_ids[i - 1]

            cursor.execute("""
                SELECT e.id, e.type, COUNT(DISTINCT ev.id)
                FROM edges e
                LEFT JOIN evidence ev ON ev.edge_id = e.id
                WHERE (e.src_entity_id = ? AND e.dst_entity_id = ?)
                   OR (e.src_entity_id = ? AND e.dst_entity_id = ?)
                GROUP BY e.id
                LIMIT 1
            """, (prev_node_id, node_id, node_id, prev_node_id))

            edge_row = cursor.fetchone()
            if edge_row:
                edge_id, edge_type, evidence_count = edge_row
                total_evidence += evidence_count

        path_node = PathNode(
            entity_id=node_id,
            entity_type=entity_type,
            entity_name=entity_name,
            edge_id=edge_id,
            edge_type=edge_type,
            evidence_count=evidence_count,
            zone=zone,
            is_blind_spot=is_blind_spot,
            coverage_sources=node_sources
        )

        path_nodes.append(path_node)

    # 计算路径整体属性
    confidence = compute_path_confidence(total_evidence, blind_spot_count, len(node_ids) - 1)
    risk_level = compute_path_risk(blind_spot_count, list(coverage_sources))

    path = Path(
        path_id=f"path_{node_ids[0]}_{node_ids[-1]}",
        path_type=PathType.SAFE,  # 暂时，后面会重新分类
        nodes=path_nodes,
        confidence=confidence,
        risk_level=risk_level,
        total_hops=len(node_ids) - 1,
        total_evidence=total_evidence,
        coverage_sources=sorted(list(coverage_sources)),
        blind_spot_count=blind_spot_count,
        recommendation_reason="To be determined"
    )

    return path


def resolve_entity_id(store: SQLiteStore, seed: str) -> str:
    """
    解析实体 ID

    支持：
    - 直接 entity_id: "entity_123"
    - seed 格式: "file:manager.py"
    """
    if seed.startswith("entity_"):
        return seed

    # 解析 seed
    if ":" not in seed:
        raise ValueError(f"Invalid seed format: {seed}")

    entity_type, entity_key = seed.split(":", 1)

    cursor = store.conn.cursor()
    cursor.execute("""
        SELECT id
        FROM entities
        WHERE type = ? AND key = ?
        LIMIT 1
    """, (entity_type, entity_key))

    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Entity not found: {seed}")

    return row[0]
