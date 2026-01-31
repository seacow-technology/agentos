"""
BrainOS Navigation System (P3-A)

第三次认知跃迁：从"看到地形"到"在地形中行动"

核心能力：
- Zone Detection: 判断当前所在认知区域（CORE/EDGE/NEAR_BLIND）
- Path Finding: 查找证据加权的推荐路径
- Risk Assessment: 评估路径风险和置信度

三条红线（验收 Gate）：
1. 禁止认知瞬移：所有路径必须沿证据边移动
2. 禁止时间抹平：明确标注理解变化（预留接口）
3. 禁止推荐掩盖风险：每条推荐路径必须带风险评分

Usage:
    from agentos.core.brain.navigation import navigate, detect_zone

    # 查找导航路径
    result = navigate(store, seed="file:manager.py", goal="file:executor.py")

    # 判断区域
    zone = detect_zone(store, entity_id="entity_123")
"""

from .models import (
    CognitiveZone,
    PathType,
    RiskLevel,
    PathNode,
    Path,
    NavigationResult,
    ZoneMetrics,
    PathScore
)

from .zone_detector import (
    detect_zone,
    compute_zone_metrics,
    get_zone_description
)

from .navigator import (
    navigate,
    navigate_explore,
    navigate_to_goal
)

__all__ = [
    # Enums
    "CognitiveZone",
    "PathType",
    "RiskLevel",

    # Data Models
    "PathNode",
    "Path",
    "NavigationResult",
    "ZoneMetrics",
    "PathScore",

    # Zone Detection
    "detect_zone",
    "compute_zone_metrics",
    "get_zone_description",

    # Navigation
    "navigate",
    "navigate_explore",
    "navigate_to_goal",
]
