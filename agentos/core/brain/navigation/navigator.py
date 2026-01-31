"""
Navigator - P3-A 主入口

提供统一的导航接口：
- navigate(): 智能导航（自动判断探索/目标模式）
- navigate_explore(): 探索模式
- navigate_to_goal(): 目标模式
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from .models import NavigationResult, CognitiveZone
from .zone_detector import detect_zone, compute_zone_metrics, get_zone_description
from .path_engine import find_paths, resolve_entity_id
from ..store import SQLiteStore
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


def navigate(
    store: SQLiteStore,
    seed: str,
    goal: Optional[str] = None,
    max_hops: int = 3,
    max_paths: int = 3
) -> NavigationResult:
    """
    主导航接口（智能模式）

    Args:
        store: BrainOS 数据库
        seed: 起点实体（格式: "file:xxx" or entity_id）
        goal: 终点实体（可选，None = 探索模式）
        max_hops: 最大跳数（默认 3）
        max_paths: 最多返回路径数（默认 3）

    Returns:
        NavigationResult: 导航结果

    Examples:
        # 探索模式
        result = navigate(store, seed="file:manager.py")

        # 目标模式
        result = navigate(store, seed="file:manager.py", goal="file:executor.py")
    """
    if goal:
        return navigate_to_goal(store, seed, goal, max_hops, max_paths)
    else:
        return navigate_explore(store, seed, max_hops, max_paths)


def navigate_explore(
    store: SQLiteStore,
    seed: str,
    max_hops: int = 3,
    max_paths: int = 3
) -> NavigationResult:
    """
    探索模式：从 seed 开始，探索周围可达的节点

    Args:
        store: BrainOS 数据库
        seed: 起点实体
        max_hops: 最大跳数
        max_paths: 最多返回路径数

    Returns:
        NavigationResult: 导航结果
    """
    logger.info(f"Navigation (explore mode): seed={seed}, max_hops={max_hops}")

    # 1. 解析 seed
    seed_id = resolve_entity_id(store, seed)

    # 2. 判断当前区域
    try:
        current_zone = detect_zone(store, seed_id)
        metrics = compute_zone_metrics(store, seed_id)
        zone_description = get_zone_description(current_zone, metrics)
    except Exception as e:
        logger.error(f"Failed to detect zone for {seed_id}: {e}")
        current_zone = CognitiveZone.EDGE
        zone_description = "Zone detection failed"

    # 3. 查找路径
    paths = find_paths(store, seed, goal=None, max_hops=max_hops, max_paths=max_paths)

    # 4. 检查是否有路径
    no_path_reason = None
    if not paths:
        no_path_reason = (
            f"No explorable paths found from {seed} within {max_hops} hops. "
            "This entity may be isolated or have no evidence-backed edges."
        )
        logger.warning(no_path_reason)

    # 5. 获取图版本
    metadata = store.get_last_build_metadata()
    graph_version = metadata['graph_version'] if metadata else 'unknown'

    result = NavigationResult(
        seed_entity=seed,
        goal_entity=None,
        current_zone=current_zone,
        current_zone_description=zone_description,
        paths=paths,
        no_path_reason=no_path_reason,
        computed_at=utc_now_iso(),
        graph_version=graph_version
    )

    # P4-A Hook: 生成决策记录
    try:
        from ..governance.decision_recorder import record_navigation_decision
        record_navigation_decision(store, seed, None, max_hops, result)
    except Exception as e:
        # 不影响主流程
        logger.warning(f"Failed to record navigation decision: {e}")

    return result


def navigate_to_goal(
    store: SQLiteStore,
    seed: str,
    goal: str,
    max_hops: int = 3,
    max_paths: int = 3
) -> NavigationResult:
    """
    目标模式：从 seed 导航到 goal

    Args:
        store: BrainOS 数据库
        seed: 起点实体
        goal: 终点实体
        max_hops: 最大跳数
        max_paths: 最多返回路径数

    Returns:
        NavigationResult: 导航结果
    """
    logger.info(f"Navigation (goal mode): seed={seed}, goal={goal}, max_hops={max_hops}")

    # 1. 解析 seed
    seed_id = resolve_entity_id(store, seed)

    # 2. 判断当前区域
    try:
        current_zone = detect_zone(store, seed_id)
        metrics = compute_zone_metrics(store, seed_id)
        zone_description = get_zone_description(current_zone, metrics)
    except Exception as e:
        logger.error(f"Failed to detect zone for {seed_id}: {e}")
        current_zone = CognitiveZone.EDGE
        zone_description = "Zone detection failed"

    # 3. 查找路径
    paths = find_paths(store, seed, goal=goal, max_hops=max_hops, max_paths=max_paths)

    # 4. 检查是否有路径
    no_path_reason = None
    if not paths:
        no_path_reason = (
            f"No path found from {seed} to {goal} within {max_hops} hops. "
            "There may be no evidence-backed connection, or the distance exceeds max_hops."
        )
        logger.warning(no_path_reason)

    # 5. 获取图版本
    metadata = store.get_last_build_metadata()
    graph_version = metadata['graph_version'] if metadata else 'unknown'

    result = NavigationResult(
        seed_entity=seed,
        goal_entity=goal,
        current_zone=current_zone,
        current_zone_description=zone_description,
        paths=paths,
        no_path_reason=no_path_reason,
        computed_at=utc_now_iso(),
        graph_version=graph_version
    )

    # P4-A Hook: 生成决策记录
    try:
        from ..governance.decision_recorder import record_navigation_decision
        record_navigation_decision(store, seed, goal, max_hops, result)
    except Exception as e:
        # 不影响主流程
        logger.warning(f"Failed to record navigation decision: {e}")

    return result
