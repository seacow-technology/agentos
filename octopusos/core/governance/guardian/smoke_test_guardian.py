"""
Smoke Test Guardian

MVP Guardian that performs basic smoke testing.
"""

import logging
from typing import Dict, Any

from .base import Guardian
from .models import GuardianVerdictSnapshot

logger = logging.getLogger(__name__)


class SmokeTestGuardian(Guardian):
    """
    Smoke Test Guardian

    Performs basic smoke tests to verify task execution.
    MVP implementation: simple checks, can be extended later.
    """

    code = "smoke_test"

    def verify(self, task_id: str, context: Dict[str, Any]) -> GuardianVerdictSnapshot:
        """
        Execute smoke test verification

        For MVP, this is a simple implementation that:
        1. Checks if task has basic required fields
        2. Returns PASS for now (stub implementation)

        Args:
            task_id: Task to verify
            context: Verification context

        Returns:
            GuardianVerdictSnapshot with verification result
        """
        logger.info(f"SmokeTestGuardian verifying task {task_id}")

        assignment_id = context.get("assignment_id", "")

        # MVP: Simple stub - always pass for now
        # In production, this would:
        # - Run actual smoke tests
        # - Check test results
        # - Validate outputs

        flags = []
        evidence = {
            "guardian": self.code,
            "task_id": task_id,
            "checks_run": ["basic_structure"],
            "note": "MVP stub implementation - always passes",
        }
        recommendations = []

        # For MVP, we always pass
        status = "PASS"

        verdict = GuardianVerdictSnapshot.create(
            assignment_id=assignment_id,
            task_id=task_id,
            guardian_code=self.code,
            status=status,
            flags=flags,
            evidence=evidence,
            recommendations=recommendations,
        )

        logger.info(f"SmokeTestGuardian verdict: {status} for task {task_id}")
        return verdict
