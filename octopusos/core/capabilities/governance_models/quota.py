"""
Capability Quota Models

治理型配额系统的数据模型。配额是 AgentOS 的"决策约束",不是执行层的限流。
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class QuotaLimit(BaseModel):
    """配额限制定义"""
    calls_per_minute: Optional[int] = Field(
        None,
        description="每分钟最大调用次数"
    )
    max_concurrent: Optional[int] = Field(
        None,
        description="最大并发调用数"
    )
    max_runtime_ms: Optional[int] = Field(
        None,
        description="单次调用最大运行时间(毫秒)"
    )
    max_cost_units: Optional[float] = Field(
        None,
        description="最大成本单位(用于计费能力)"
    )


class CapabilityQuota(BaseModel):
    """能力配额配置(静态)"""
    quota_id: str = Field(description="配额 ID")
    scope: Literal["tool", "capability", "source"] = Field(
        description="配额范围:单个工具、整个能力、或整个来源"
    )
    target_id: str = Field(description="目标 ID (tool_id/capability_id/source_id)")
    limit: QuotaLimit = Field(description="配额限制")
    window: Literal["sliding", "fixed"] = Field(
        default="sliding",
        description="窗口类型:滑动窗口或固定窗口"
    )
    enabled: bool = Field(default=True, description="是否启用")


class QuotaState(BaseModel):
    """配额使用状态(运行态)"""
    quota_id: str
    used_calls: int = Field(default=0, description="已使用调用次数")
    used_runtime_ms: int = Field(default=0, description="已使用运行时间")
    used_cost_units: float = Field(default=0.0, description="已使用成本单位")
    current_concurrent: int = Field(default=0, description="当前并发数")
    window_start: datetime = Field(description="窗口开始时间")
    last_reset: Optional[datetime] = Field(None, description="上次重置时间")


class QuotaCheckResult(BaseModel):
    """配额检查结果"""
    allowed: bool = Field(description="是否允许")
    reason: Optional[str] = Field(None, description="拒绝原因")
    state: QuotaState = Field(description="当前状态")
    warning: bool = Field(default=False, description="是否接近限制(警告)")
    warning_threshold: float = Field(default=0.8, description="警告阈值(80%)")
