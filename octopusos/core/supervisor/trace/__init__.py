"""
Trace Module - Decision Replay 追踪和重建

这个模块提供决策历史的追踪、查询和统计功能。

核心组件：
- TraceAssembler: 组装完整的决策 trace
- TraceStorage: 数据访问层
- StatsCalculator: 统计计算

主要功能：
1. 获取任务的决策历史（时间序列）
2. 查询单个决策的完整快照
3. 统计决策延迟、类型分布等指标
"""

from agentos.core.supervisor.trace.replay import (
    TraceItem,
    TaskGovernanceSummary,
    TraceAssembler,
)

from agentos.core.supervisor.trace.storage import TraceStorage

from agentos.core.supervisor.trace.stats import StatsCalculator

__all__ = [
    "TraceItem",
    "TaskGovernanceSummary",
    "TraceAssembler",
    "TraceStorage",
    "StatsCalculator",
]
