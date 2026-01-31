"""
Risk Gate - Hard gate for HIGH/CRITICAL risk operations

Enforces mandatory review for high-risk operations at Supervisor level.
This is a system-level gate that cannot be bypassed by configuration.

PR-0131-2026-2: Risk Hard Gate (v0.9 → PASS)
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RiskLevel:
    """Risk level constants"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @staticmethod
    def requires_approval(level: str) -> bool:
        """Check if risk level requires approval"""
        return level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @staticmethod
    def from_string(level_str: str) -> str:
        """Normalize risk level string"""
        normalized = level_str.upper()
        if normalized in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            return normalized
        return RiskLevel.MEDIUM  # Default to MEDIUM if unknown


@dataclass
class RiskGateResult:
    """Result of risk gate evaluation"""
    allowed: bool
    reason: str
    risk_level: str
    requires_approval: bool
    approval_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "approval_ref": self.approval_ref
        }


class RiskGate:
    """
    Risk Gate - Enforces approval requirements for HIGH/CRITICAL operations

    This gate is enforced at Supervisor level before any execution.
    All paths (API / Extension / dry-run → exec) are protected.

    Architecture:
        - HIGH/CRITICAL + no approval → BLOCKED (hard)
        - HIGH/CRITICAL + approval → ALLOWED (with audit)
        - LOW/MEDIUM → ALLOWED (normal flow)
    """

    def __init__(self):
        """Initialize risk gate"""
        logger.info("RiskGate initialized")

    def evaluate(
        self,
        risk_level: str,
        operation: str,
        task_id: str,
        approval_ref: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskGateResult:
        """
        Evaluate if operation is allowed given risk level

        Args:
            risk_level: Risk level (LOW/MEDIUM/HIGH/CRITICAL)
            operation: Operation description
            task_id: Task ID
            approval_ref: Optional approval reference (from RunMode.INTERACTIVE approval)
            context: Optional additional context

        Returns:
            RiskGateResult indicating if operation is allowed
        """
        context = context or {}
        normalized_level = RiskLevel.from_string(risk_level)

        # LOW/MEDIUM risk: Always allow
        if not RiskLevel.requires_approval(normalized_level):
            logger.debug(f"Task {task_id}: {normalized_level} risk operation allowed")
            return RiskGateResult(
                allowed=True,
                reason="Low/medium risk operation - no approval required",
                risk_level=normalized_level,
                requires_approval=False
            )

        # HIGH/CRITICAL risk: Requires approval
        if approval_ref:
            logger.info(
                f"Task {task_id}: {normalized_level} risk operation allowed with approval {approval_ref}"
            )
            return RiskGateResult(
                allowed=True,
                reason=f"{normalized_level} risk operation approved",
                risk_level=normalized_level,
                requires_approval=True,
                approval_ref=approval_ref
            )

        # HIGH/CRITICAL without approval: BLOCKED
        logger.warning(
            f"Task {task_id}: {normalized_level} risk operation blocked - no approval"
        )
        return RiskGateResult(
            allowed=False,
            reason=f"{normalized_level} risk operation requires explicit approval",
            risk_level=normalized_level,
            requires_approval=True
        )

    def check_or_raise(
        self,
        risk_level: str,
        operation: str,
        task_id: str,
        approval_ref: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskGateResult:
        """
        Evaluate risk gate and raise exception if blocked

        Args:
            risk_level: Risk level
            operation: Operation description
            task_id: Task ID
            approval_ref: Optional approval reference
            context: Optional context

        Returns:
            RiskGateResult if allowed

        Raises:
            HighRiskBlockedError: If HIGH/CRITICAL risk operation is blocked
        """
        result = self.evaluate(
            risk_level=risk_level,
            operation=operation,
            task_id=task_id,
            approval_ref=approval_ref,
            context=context
        )

        if not result.allowed:
            from agentos.core.task.errors import HighRiskBlockedError
            raise HighRiskBlockedError(
                task_id=task_id,
                risk_level=result.risk_level,
                operation=operation,
                reason=result.reason,
                approval_required=result.requires_approval,
                metadata=context or {}
            )

        return result
