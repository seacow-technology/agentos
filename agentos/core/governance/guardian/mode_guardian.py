"""
Mode Guardian - Verify Mode constraint violations

This Guardian verifies Mode constraint compliance by checking if operations
are actually allowed by the Mode policy.

Design:
- Receives mode_violation events from OnModeViolationPolicy
- Consults ModePolicy to verify if operation is truly forbidden
- Returns PASS if false positive, FAIL if confirmed violation
- Provides recommendations for NEEDS_CHANGES cases

Task 28: Guardian Integration
Date: 2026-01-30
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import logging

from .base import Guardian
from .models import GuardianVerdictSnapshot, VerdictStatus
from agentos.core.mode import get_mode, check_mode_permission
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class ModeGuardian(Guardian):
    """
    Mode Guardian - Verifies Mode constraint compliance

    Verdict Logic:
    - PASS: Operation is allowed (false positive from alert)
    - FAIL: Confirmed violation, block task
    - NEEDS_CHANGES: Violation can be resolved with changes

    This Guardian acts as the verification layer in the alert → guardian → verdict flow.
    """

    code = "mode_guardian"

    def verify(
        self,
        task_id: str,
        context: Dict[str, Any]
    ) -> GuardianVerdictSnapshot:
        """
        Verify Mode constraint violation

        Args:
            task_id: Task ID
            context: Contains mode_violation details from OnModeViolationPolicy
                Expected keys:
                - mode_id: Mode identifier
                - operation: Operation name (e.g., "apply_diff", "commit")
                - violation_context: Additional context about the violation
                - event_id: Original event ID

        Returns:
            GuardianVerdictSnapshot with verification result
        """
        logger.info(f"ModeGuardian verifying task {task_id}")

        # Extract assignment ID
        assignment_id = context.get("assignment_id", "")

        # Extract mode violation details from guardian_context
        guardian_context = context.get("guardian_context", {})
        mode_id = guardian_context.get("mode_id", "unknown")
        operation = guardian_context.get("operation", "unknown")
        violation_context = guardian_context.get("violation_context", {})
        event_id = guardian_context.get("event_id", "")

        logger.info(
            f"Verifying Mode violation: mode={mode_id}, "
            f"operation={operation}, task={task_id}"
        )

        try:
            # Get the Mode instance to check permissions
            mode = get_mode(mode_id)

            # Verify the operation against Mode policy
            status, flags, evidence, recommendations = self._verify_operation(
                mode=mode,
                mode_id=mode_id,
                operation=operation,
                violation_context=violation_context,
            )

            # Add metadata to evidence
            evidence["task_id"] = task_id
            evidence["event_id"] = event_id
            evidence["verified_at"] = utc_now_iso()
            evidence["guardian_code"] = self.code

        except Exception as e:
            # If verification fails, default to FAIL (safe default)
            logger.error(f"ModeGuardian verification failed: {e}", exc_info=True)
            status = "FAIL"
            flags = [{
                "type": "verification_error",
                "severity": "critical",
                "message": f"Guardian verification failed: {str(e)}",
            }]
            evidence = {
                "error": str(e),
                "mode_id": mode_id,
                "operation": operation,
                "task_id": task_id,
            }
            recommendations = [
                "Review the Mode configuration",
                "Check if Mode policy is accessible",
                "Verify task context is valid",
            ]

        # Create verdict snapshot
        verdict = GuardianVerdictSnapshot.create(
            assignment_id=assignment_id,
            task_id=task_id,
            guardian_code=self.code,
            status=status,
            flags=flags,
            evidence=evidence,
            recommendations=recommendations,
        )

        logger.info(
            f"ModeGuardian verdict: {status} for task {task_id} "
            f"(mode={mode_id}, operation={operation})"
        )

        return verdict

    def _verify_operation(
        self,
        mode: Any,
        mode_id: str,
        operation: str,
        violation_context: Dict[str, Any],
    ) -> tuple[VerdictStatus, List[Dict], Dict, List[str]]:
        """
        Verify if operation violates Mode constraints

        Args:
            mode: Mode instance
            mode_id: Mode identifier
            operation: Operation name
            violation_context: Additional context

        Returns:
            Tuple of (status, flags, evidence, recommendations)
        """
        flags = []
        evidence = {
            "mode_id": mode_id,
            "operation": operation,
            "context": violation_context,
        }
        recommendations = []

        # Map operation names to permission checks
        operation_permission_map = {
            "apply_diff": "allows_diff",
            "commit": "allows_commit",
            "git_commit": "allows_commit",
            "write_file": "allows_diff",  # Writing files implies diff capability
        }

        # Check if operation has a known permission check
        if operation not in operation_permission_map:
            # Unknown operation - treat as potential violation
            logger.warning(f"Unknown operation: {operation}")

            # Check if operation is in mode's allowed_operations
            is_allowed = check_mode_permission(mode_id, operation)

            if is_allowed:
                # Operation is explicitly allowed
                status = "PASS"
                evidence["reason"] = f"Operation '{operation}' is allowed for mode '{mode_id}'"
                evidence["permission_check"] = "allowed_operations"
            else:
                # Operation not explicitly allowed - FAIL
                status = "FAIL"
                flags.append({
                    "type": "mode_violation_confirmed",
                    "severity": "error",
                    "message": f"Operation '{operation}' not allowed in mode '{mode_id}'",
                    "operation": operation,
                    "mode_id": mode_id,
                })
                evidence["reason"] = f"Operation '{operation}' not in allowed operations"
                recommendations = [
                    f"Change mode to one that allows '{operation}'",
                    "Review task requirements and mode selection",
                    "Consider splitting task into mode-appropriate stages",
                ]
        else:
            # Known operation - check specific permission
            permission_attr = operation_permission_map[operation]
            is_allowed = check_mode_permission(mode_id, operation)

            if is_allowed:
                # False positive - operation is actually allowed
                status = "PASS"
                evidence["reason"] = (
                    f"False positive: Operation '{operation}' is allowed "
                    f"for mode '{mode_id}' (permission={permission_attr})"
                )
                evidence["permission_check"] = permission_attr
                evidence["permission_value"] = True

                logger.info(
                    f"Mode violation was false positive: {mode_id}/{operation} is allowed"
                )
            else:
                # Confirmed violation
                status = "FAIL"
                flags.append({
                    "type": "mode_violation_confirmed",
                    "severity": "error",
                    "message": (
                        f"Mode '{mode_id}' does not allow operation '{operation}'"
                    ),
                    "operation": operation,
                    "mode_id": mode_id,
                    "permission": permission_attr,
                })
                evidence["reason"] = (
                    f"Mode '{mode_id}' policy forbids '{operation}' "
                    f"(permission={permission_attr}=False)"
                )
                evidence["permission_check"] = permission_attr
                evidence["permission_value"] = False

                recommendations = [
                    f"Change to a mode that allows '{operation}' (e.g., 'implementation')",
                    "Split task into design and implementation phases",
                    f"Remove '{operation}' from task if not required",
                    "Review mode selection criteria for this task",
                ]

                logger.info(
                    f"Mode violation confirmed: {mode_id} does not allow {operation}"
                )

        return status, flags, evidence, recommendations
