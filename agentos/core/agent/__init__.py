"""
Agent Capability Authorization System - AgentOS v3

Task #27: 重构Agent定义为Capability授权模型

核心哲学：Agent ≠ Capability，Agent是Capability的使用者
- Agent本身没有超能力
- Agent只是一组被授权的Capability调用者
- 权力在系统，授权给Agent

Components:
- AgentCapabilityProfile: Agent的Capability配置文件
- CapabilityAuthorizer: 授权检查引擎
- AgentTierSystem: Agent信任等级系统
- EscalationEngine: 权限升级请求引擎

Usage:
    from agentos.core.agent import (
        AgentCapabilityProfile,
        CapabilityAuthorizer,
        AgentTierSystem,
        EscalationEngine,
    )

    # 创建Agent Profile
    profile = AgentCapabilityProfile(
        agent_id="chat_agent",
        tier=2,
        allowed_capabilities=["state.read", "decision.propose"],
        forbidden_capabilities=["action.execute.*"]
    )

    # 检查授权
    authorizer = CapabilityAuthorizer(registry, governance)
    result = authorizer.authorize(
        agent_id="chat_agent",
        capability_id="state.memory.read",
        context={"operation": "read"}
    )

    if result.allowed:
        # Proceed with operation
        pass
"""

from agentos.core.agent.models import (
    AgentTier,
    EscalationStatus,
    EscalationPolicy,
    AuthorizationResult,
    EscalationRequest,
)
from agentos.core.agent.agent_profile import AgentCapabilityProfile
from agentos.core.agent.capability_authorizer import CapabilityAuthorizer
from agentos.core.agent.agent_tier import AgentTierSystem
from agentos.core.agent.escalation_engine import EscalationEngine

__all__ = [
    # Models
    "AgentTier",
    "EscalationStatus",
    "EscalationPolicy",
    "AuthorizationResult",
    "EscalationRequest",
    # Components
    "AgentCapabilityProfile",
    "CapabilityAuthorizer",
    "AgentTierSystem",
    "EscalationEngine",
]
