"""
Supervisor Policies

Policies 负责处理特定类型的事件并做出决策。

MVP 包含三个核心 policy：
- OnTaskCreatedPolicy: 任务创建时的红线预检和冲突预检
- OnStepCompletedPolicy: 步骤完成后的风险再评估
- OnTaskFailedPolicy: 任务失败时的归因和重试建议
"""

from .base import BasePolicy
from .on_task_created import OnTaskCreatedPolicy
from .on_step_completed import OnStepCompletedPolicy
from .on_task_failed import OnTaskFailedPolicy
from .on_mode_violation import OnModeViolationPolicy

__all__ = [
    "BasePolicy",
    "OnTaskCreatedPolicy",
    "OnStepCompletedPolicy",
    "OnTaskFailedPolicy",
    "OnModeViolationPolicy",
]
