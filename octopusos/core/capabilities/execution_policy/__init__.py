"""
Execution Policy Engine Module

The final arbiter for extension execution decisions.

Phase D4: Policy Engine
- Non-bypassable governance layer
- Integrates D1-D3 (Sandbox/Risk/Tier) and C3 (Authorization)
- Returns ALLOW/DENY/REQUIRE_APPROVAL decisions
- Complete audit trail

Note: This is separate from ToolPolicyEngine in policy.py

Usage:
    from agentos.core.capabilities.execution_policy import (
        PolicyEngine,
        PolicyEvaluationRequest,
        PolicyDecision
    )

    engine = PolicyEngine(db_path)

    request = PolicyEvaluationRequest(
        extension_id="tools.postman",
        action_id="get",
        session_id="session-123",
        user_id="user-456"
    )

    result = engine.evaluate(request)

    if result.decision == PolicyDecision.DENY:
        print(f"Denied: {result.reason}")
    elif result.decision == PolicyDecision.REQUIRE_APPROVAL:
        print(f"Requires approval: {result.reason}")
    else:
        print("Allowed")
"""

from .engine import PolicyEngine
from .models import (
    PolicyDecision,
    PolicyDecisionResult,
    PolicyEvaluationRequest,
    PolicyContext
)
from .rules import ALL_RULES
from .context import PolicyContextBuilder

__all__ = [
    "PolicyEngine",
    "PolicyDecision",
    "PolicyDecisionResult",
    "PolicyEvaluationRequest",
    "PolicyContext",
    "PolicyContextBuilder",
    "ALL_RULES",
]
