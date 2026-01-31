"""
Time Module - 认知时间监控

核心概念：
- Time = "认知健康监控，而不是历史回放"
- 回答："我的理解是在变好，还是在变坏？"

核心功能：
1. 趋势分析（覆盖率、盲区、证据密度）
2. 认知债务识别（长期无覆盖区域）
3. 健康评分（0-100）
4. 预警和建议

使用场景：
- 监控认知健康度趋势
- 识别退化区域
- 预警认知债务
- 提供改善建议
"""

from .models import (
    TrendDirection,
    HealthLevel,
    TimePoint,
    TrendLine,
    CognitiveDebt,
    HealthReport
)

from .trend_analyzer import (
    analyze_trends,
    compute_health_score,
    score_to_level
)

__all__ = [
    # Models
    "TrendDirection",
    "HealthLevel",
    "TimePoint",
    "TrendLine",
    "CognitiveDebt",
    "HealthReport",

    # Functions
    "analyze_trends",
    "compute_health_score",
    "score_to_level",
]
