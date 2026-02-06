"""
OnModeViolationPolicy - Supervisor policy for Mode violations

Evaluates MODE_VIOLATION events and determines appropriate actions:
- INFO/WARNING: Audit only (no enforcement)
- ERROR/CRITICAL: Assign Guardian for verification

Task 27: Mode Event Listener Implementation
Date: 2026-01-30
"""

import logging
import sqlite3
from typing import Optional
from pathlib import Path

from .base import BasePolicy
from ..models import SupervisorEvent, Decision, DecisionType, Action, ActionType, Finding

logger = logging.getLogger(__name__)


class OnModeViolationPolicy(BasePolicy):
    """
    Mode Violation Policy

    Processes MODE_VIOLATION events from the Mode system.

    Decision flow:
    1. Extract severity from event payload
    2. INFO/WARNING → Audit only (no action)
    3. ERROR/CRITICAL → Assign Guardian for verification

    This implements the "alert → guardian → verdict" flow designed in Task 26.
    """

    def evaluate(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        Evaluate MODE_VIOLATION event

        Args:
            event: Supervisor event
            cursor: Database cursor

        Returns:
            Decision object or None
        """
        # Validate event type
        if event.event_type != "mode.violation":
            logger.debug(f"Event type mismatch: {event.event_type}, skipping")
            return None

        # Extract payload
        payload = event.payload
        mode_id = payload.get("mode_id", "unknown")
        operation = payload.get("operation", "unknown")
        severity = payload.get("severity", "error").lower()
        message = payload.get("message", "Mode violation detected")
        context = payload.get("context", {})

        logger.info(
            f"Processing MODE_VIOLATION: mode={mode_id}, "
            f"operation={operation}, severity={severity}"
        )

        # Create finding
        finding = Finding(
            category="mode_violation",
            severity=severity,
            description=message,
            evidence=[
                f"mode_id={mode_id}",
                f"operation={operation}",
                f"context={context}",
            ],
            source="mode_system",
        )

        # Decision based on severity
        if severity in ["info", "warning"]:
            # Audit only (no enforcement)
            return self._create_audit_only_decision(event, finding, severity)
        elif severity in ["error", "critical"]:
            # Assign Guardian for verification
            return self._create_guardian_assignment_decision(
                event, finding, mode_id, operation, context
            )
        else:
            logger.warning(f"Unknown severity level: {severity}, defaulting to audit")
            return self._create_audit_only_decision(event, finding, "unknown")

    def _create_audit_only_decision(
        self, event: SupervisorEvent, finding: Finding, severity: str
    ) -> Decision:
        """
        Create audit-only decision for INFO/WARNING violations

        Args:
            event: Supervisor event
            finding: Finding object
            severity: Severity level

        Returns:
            Decision with ALLOW decision type (audit action)
        """
        return Decision(
            decision_type=DecisionType.ALLOW,
            reason=f"Mode violation at {severity.upper()} level - audit only",
            findings=[finding],
            actions=[
                Action(
                    action_type=ActionType.WRITE_AUDIT,
                    target=event.task_id,
                    params={
                        "event_id": event.event_id,
                        "severity": severity,
                        "category": "mode_violation_audit",
                    },
                )
            ],
        )

    def _create_guardian_assignment_decision(
        self,
        event: SupervisorEvent,
        finding: Finding,
        mode_id: str,
        operation: str,
        context: dict,
    ) -> Decision:
        """
        Create Guardian assignment decision for ERROR/CRITICAL violations

        This implements the deep integration path:
        Mode → Supervisor → Guardian → Verdict

        Args:
            event: Supervisor event
            finding: Finding object
            mode_id: Mode identifier
            operation: Operation name
            context: Violation context

        Returns:
            Decision with REQUIRE_REVIEW decision type (Guardian assignment)
        """
        return Decision(
            decision_type=DecisionType.REQUIRE_REVIEW,
            reason=f"Mode violation requires Guardian verification: {mode_id}/{operation}",
            findings=[finding],
            actions=[
                # Action 1: Assign Guardian
                Action(
                    action_type=ActionType.MARK_VERIFYING,
                    target=event.task_id,
                    params={
                        "guardian_code": "mode_guardian",  # Guardian code for ModeGuardian
                        "guardian_type": "ModeGuardian",   # For logging/audit
                        "guardian_context": {
                            "mode_id": mode_id,
                            "operation": operation,
                            "violation_context": context,
                            "event_id": event.event_id,
                        },
                        "reason": f"Mode '{mode_id}' violated constraint: {operation}",
                    },
                ),
                # Action 2: Write audit
                Action(
                    action_type=ActionType.WRITE_AUDIT,
                    target=event.task_id,
                    params={
                        "event_id": event.event_id,
                        "severity": finding.severity,
                        "category": "mode_violation_guardian_assigned",
                        "guardian_type": "ModeGuardian",
                    },
                ),
            ],
        )


def create_on_mode_violation_policy(db_path: Path) -> OnModeViolationPolicy:
    """
    Factory function to create OnModeViolationPolicy

    Args:
        db_path: Database path

    Returns:
        OnModeViolationPolicy instance
    """
    return OnModeViolationPolicy(db_path)
