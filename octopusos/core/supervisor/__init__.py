"""
Supervisor 核心模块

Supervisor 负责监听任务状态变化、评估风险、做出决策并触发相应的 Gate 动作。
采用双通道事件摄入机制：
- EventBus 订阅（快路径）：实时响应
- Polling（慢路径）：兜底保证不丢事件

设计原则：
1. 安全稳定第一 - 永不丢事件
2. DB 为真相源 - EventBus 只做唤醒
3. 幂等和去重 - 基于 supervisor_inbox
4. 可审计 - 所有决策写入 audit
"""

from .models import (
    SupervisorEvent,
    EventSource,
    Finding,
    Decision,
    DecisionType,
    Action,
    ActionType,
)

__all__ = [
    "SupervisorEvent",
    "EventSource",
    "Finding",
    "Decision",
    "DecisionType",
    "Action",
    "ActionType",
]
