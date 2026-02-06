"""
Root Cause Classification System

Provides standard taxonomy for failure attribution, enabling clear distinction
between system bugs, model limitations, policy blocks, and other failure modes.

PR-0131-2026-3: Root Cause Classification (v0.6 "能力不足 vs Bug" 闭环)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class RootCauseCategory(str, Enum):
    """
    Standard root cause taxonomy for failure attribution

    This enables clear operational distinction between different failure modes:
    - System engineers focus on SYSTEM_BUG
    - ML engineers focus on MODEL_LIMITATION
    - Policy owners focus on POLICY_BLOCKED
    - Users can distinguish their errors from system errors
    """

    SYSTEM_BUG = "SYSTEM_BUG"
    """Internal system error (code bug, unhandled exception, etc.)"""

    MODEL_LIMITATION = "MODEL_LIMITATION"
    """LLM model unable to perform required reasoning or generation"""

    POLICY_BLOCKED = "POLICY_BLOCKED"
    """Operation blocked by governance policy (risk, budget, permissions, etc.)"""

    USER_INPUT = "USER_INPUT"
    """Invalid user input or configuration"""

    ENVIRONMENT = "ENVIRONMENT"
    """External environment issue (network, filesystem, dependencies, etc.)"""

    TIMEOUT = "TIMEOUT"
    """Operation exceeded time limit"""

    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    """External dependency failed (API, database, service unavailable, etc.)"""

    UNKNOWN = "UNKNOWN"
    """Root cause not yet classified"""


@dataclass(frozen=True)
class RootCauseAnalysis:
    """
    Immutable root cause analysis result

    Provides structured attribution for failures with evidence and confidence.
    """
    category: RootCauseCategory
    reason: str
    evidence: Dict[str, Any]
    confidence: str = "HIGH"  # HIGH | MEDIUM | LOW
    remediation_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "category": self.category.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "remediation_hint": self.remediation_hint
        }


class RootCauseClassifier:
    """
    Automatic root cause classification from exceptions and context

    Provides heuristic classification with confidence scoring.
    """

    @staticmethod
    def classify_exception(
        exc: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> RootCauseAnalysis:
        """
        Classify exception into root cause category

        Args:
            exc: Exception instance
            context: Optional context (task_id, operation, etc.)

        Returns:
            RootCauseAnalysis with classified category
        """
        from agentos.core.task.errors import (
            BudgetExceededError,
            HighRiskBlockedError,
            PlanningSideEffectForbiddenError,
            ChatExecutionForbiddenError,
            SpecNotFrozenError,
            ModeViolationError
        )

        context = context or {}

        # Policy-blocked exceptions
        if isinstance(exc, (
            BudgetExceededError,
            HighRiskBlockedError,
            PlanningSideEffectForbiddenError,
            ChatExecutionForbiddenError,
            SpecNotFrozenError,
            ModeViolationError
        )):
            return RootCauseAnalysis(
                category=RootCauseCategory.POLICY_BLOCKED,
                reason=str(exc),
                evidence={"exception_type": type(exc).__name__, **context},
                confidence="HIGH",
                remediation_hint="Review governance policy and approval requirements"
            )

        # Model limitation indicators
        if "schema" in str(exc).lower() or "validation" in str(exc).lower():
            if "llm" in str(exc).lower() or "model" in str(exc).lower():
                return RootCauseAnalysis(
                    category=RootCauseCategory.MODEL_LIMITATION,
                    reason=f"Model output validation failed: {exc}",
                    evidence={"exception_type": type(exc).__name__, **context},
                    confidence="MEDIUM",
                    remediation_hint="Consider prompt tuning or model upgrade"
                )

        # Timeout
        if isinstance(exc, TimeoutError) or "timeout" in str(exc).lower():
            return RootCauseAnalysis(
                category=RootCauseCategory.TIMEOUT,
                reason=str(exc),
                evidence={"exception_type": type(exc).__name__, **context},
                confidence="HIGH",
                remediation_hint="Increase timeout limit or optimize operation"
            )

        # User input
        if "validation" in type(exc).__name__.lower():
            return RootCauseAnalysis(
                category=RootCauseCategory.USER_INPUT,
                reason=str(exc),
                evidence={"exception_type": type(exc).__name__, **context},
                confidence="HIGH",
                remediation_hint="Check input parameters and constraints"
            )

        # Environment/dependency
        if any(keyword in str(exc).lower() for keyword in ["connection", "network", "unavailable", "not found"]):
            return RootCauseAnalysis(
                category=RootCauseCategory.DEPENDENCY_FAILURE,
                reason=str(exc),
                evidence={"exception_type": type(exc).__name__, **context},
                confidence="MEDIUM",
                remediation_hint="Check network connectivity and service status"
            )

        # Default: System bug (internal code error)
        return RootCauseAnalysis(
            category=RootCauseCategory.SYSTEM_BUG,
            reason=str(exc),
            evidence={"exception_type": type(exc).__name__, **context},
            confidence="MEDIUM",
            remediation_hint="Report to system maintainers with stack trace"
        )
