"""
Lead Agent - 自动化风险线索挖掘系统

Lead Agent 是一个自动化的风险检测和线索挖掘系统，通过分析 Supervisor 决策历史，
识别系统性风险、异常模式和潜在问题。

核心组件：
- LeadService: 扫描服务，协调扫描流程
- LeadFinding: 风险线索数据模型（带 fingerprint 幂等去重）
- ScanWindow: 扫描时间窗口定义
- FollowUpTaskSpec: 后续任务规格
- ScanResult: 扫描结果
"""

from agentos.core.lead.models import (
    LeadFinding,
    ScanWindow,
    WindowKind,
    FindingSeverity,
    FollowUpTaskSpec,
    ScanResult,
)
from agentos.core.lead.service import LeadService, LeadServiceConfig

__all__ = [
    # Models
    "LeadFinding",
    "ScanWindow",
    "WindowKind",
    "FindingSeverity",
    "FollowUpTaskSpec",
    "ScanResult",
    # Service
    "LeadService",
    "LeadServiceConfig",
]
