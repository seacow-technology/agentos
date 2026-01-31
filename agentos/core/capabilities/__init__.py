"""
Capability System

This module provides:
1. Execution framework for extension capabilities (legacy)
2. Unified capability abstraction layer (PR-1)

The capability abstraction layer unifies Extension and MCP tools into
a consistent interface for discovery, invocation, and auditing.

Legacy components (for backward compatibility):
- CommandRoute, ExecutionContext, ExecutionResult
- CapabilityRunner
- Exceptions

New unified components (PR-1):
- ToolDescriptor, ToolInvocation, ToolResult (capability_models)
- CapabilityRegistry (registry)
- ToolRouter (router)
- Audit functions (audit)
- ToolPolicyEngine (policy)
"""

# Legacy components
from .models import (
    CommandRoute,
    ExecutionContext,
    ExecutionResult,
    CapabilityResult,
    ToolExecutionResult,
)
from .runner import CapabilityRunner
from .exceptions import (
    CapabilityError,
    ExecutionError,
    ToolNotFoundError,
    TimeoutError,
)

# New unified capability abstraction layer (PR-1)
from .capability_models import (
    ToolDescriptor,
    ToolInvocation,
    ToolResult,
    SideEffect,
    RiskLevel,
    ToolSource,
    ExecutionMode,
    PolicyDecision,
    TrustTier,
)
from .registry import CapabilityRegistry
from .router import ToolRouter, ToolRouterError, PolicyViolationError
from .audit import (
    emit_tool_invocation_start,
    emit_tool_invocation_end,
    emit_policy_violation,
    emit_tool_discovery,
)
from .policy import ToolPolicyEngine

__all__ = [
    # Legacy models
    "CommandRoute",
    "ExecutionContext",
    "ExecutionResult",
    "CapabilityResult",
    "ToolExecutionResult",
    # Legacy runner
    "CapabilityRunner",
    # Legacy exceptions
    "CapabilityError",
    "ExecutionError",
    "ToolNotFoundError",
    "TimeoutError",
    # New capability models (PR-1)
    "ToolDescriptor",
    "ToolInvocation",
    "ToolResult",
    "SideEffect",
    "RiskLevel",
    "ToolSource",
    "ExecutionMode",
    "PolicyDecision",
    "TrustTier",
    # New registry (PR-1)
    "CapabilityRegistry",
    # New router (PR-1)
    "ToolRouter",
    "ToolRouterError",
    "PolicyViolationError",
    # New audit (PR-1)
    "emit_tool_invocation_start",
    "emit_tool_invocation_end",
    "emit_policy_violation",
    "emit_tool_discovery",
    # New policy (PR-1)
    "ToolPolicyEngine",
]
