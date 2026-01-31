"""
Time Models - 认知时间数据模型

核心概念：
- TimePoint: 时间点（快照 + 健康指标）
- TrendLine: 趋势线（指标随时间变化）
- HealthReport: 健康报告（当前状态 + 趋势分析）
- CognitiveDebt: 认知债务（长期无覆盖区域）

设计原则：
- Time 不是"回放"，而是"监控"
- 关注健康度趋势，而不是 commit 历史
- 识别退化区域，预警认知债务
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class TrendDirection(Enum):
    """趋势方向"""
    IMPROVING = "IMPROVING"      # 改善 🟢
    DEGRADING = "DEGRADING"      # 退化 🔴
    STABLE = "STABLE"            # 稳定 🟡
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # 数据不足 ⚪


class HealthLevel(Enum):
    """健康等级"""
    EXCELLENT = "EXCELLENT"  # 优秀：>= 80
    GOOD = "GOOD"            # 良好：60-80
    FAIR = "FAIR"            # 一般：40-60
    POOR = "POOR"            # 较差：20-40
    CRITICAL = "CRITICAL"    # 危险：< 20


@dataclass
class TimePoint:
    """
    时间点（快照 + 健康指标）

    不是简单的 commit，而是包含健康指标的时间快照
    """
    snapshot_id: str
    timestamp: str  # ISO 8601

    # 健康指标
    coverage_percentage: float  # 覆盖率（0-1）
    evidence_density: float     # 证据密度（平均每节点证据数）
    blind_spot_ratio: float     # 盲区比例（0-1）

    # 来源分布
    git_coverage: float
    doc_coverage: float
    code_coverage: float

    # 总数
    entity_count: int
    edge_count: int
    evidence_count: int

    # 健康评分（0-100）
    health_score: float


@dataclass
class TrendLine:
    """
    趋势线（指标随时间变化）

    核心：使用线性回归拟合趋势方向和斜率
    """
    metric_name: str  # "coverage_percentage", "blind_spot_ratio", etc.
    time_points: List[TimePoint]

    # 趋势分析
    direction: TrendDirection
    slope: float  # 斜率（正=上升，负=下降）

    # 统计
    avg_value: float
    max_value: float
    min_value: float

    # 预测（简单线性）
    predicted_next_value: Optional[float]


@dataclass
class CognitiveDebt:
    """
    认知债务（长期无覆盖/退化区域）

    定义：
    - UNCOVERED: 长期无覆盖（>= 14 天）
    - DEGRADING: 证据持续减少（>= 7 天）
    - ORPHANED: 长期孤立（无边连接，>= 14 天）
    """
    entity_id: str
    entity_type: str
    entity_key: str
    entity_name: str

    # 债务类型
    debt_type: str  # "UNCOVERED", "DEGRADING", "ORPHANED"

    # 持续时间
    duration_days: int  # 多少天无改善

    # 严重度（0-1）
    severity: float

    # 描述
    description: str

    # 建议
    recommendation: str


@dataclass
class HealthReport:
    """
    健康报告

    核心：回答"我的理解是在变好，还是在变坏？"
    """
    # 时间窗口
    window_start: str
    window_end: str
    window_days: int

    # 当前状态
    current_health_level: HealthLevel
    current_health_score: float

    # 趋势线
    coverage_trend: TrendLine
    blind_spot_trend: TrendLine
    evidence_density_trend: TrendLine

    # 来源迁移分析
    source_migration: Dict[str, TrendDirection]  # {"git": IMPROVING, "doc": DEGRADING, ...}

    # 认知债务
    cognitive_debts: List[CognitiveDebt]
    total_debt_count: int

    # 预警
    warnings: List[str]

    # 建议
    recommendations: List[str]

    computed_at: str
