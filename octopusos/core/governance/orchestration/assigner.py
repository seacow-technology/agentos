"""
Guardian Assigner

Responsible for choosing the appropriate Guardian for a task based on findings.
"""

import logging
from typing import Dict, Any, List

from ..guardian.registry import GuardianRegistry
from ..guardian.models import GuardianAssignment

logger = logging.getLogger(__name__)


class GuardianAssigner:
    """
    Guardian Assigner

    Selects the appropriate Guardian for task verification based on:
    - Findings from Lead Agent or other sources
    - Task context and metadata
    - Risk profiles

    MVP Rules:
    - RISK_RUNTIME finding -> smoke_test
    - CONFLICT finding -> smoke_test (diff guardian not yet implemented)
    - Default -> smoke_test
    """

    def __init__(self, registry: GuardianRegistry):
        """
        Initialize Guardian Assigner

        Args:
            registry: GuardianRegistry instance
        """
        self.registry = registry
        logger.info("GuardianAssigner initialized")

    def choose_guardian(
        self, findings: List[Dict[str, Any]], task_context: Dict[str, Any]
    ) -> str:
        """
        Choose appropriate Guardian based on findings

        MVP Rules:
        1. If RISK_RUNTIME in findings -> smoke_test
        2. If CONFLICT in findings -> smoke_test (diff not yet available)
        3. Default -> smoke_test

        Args:
            findings: List of findings from Lead Agent or other sources
            task_context: Task metadata and context

        Returns:
            Guardian code to use
        """
        # Extract finding categories
        categories = [f.get("category", "") for f in findings]

        logger.debug(f"Choosing Guardian for findings: {categories}")

        # MVP: Simple rule-based selection
        if "RISK_RUNTIME" in categories:
            logger.info("Found RISK_RUNTIME, selecting smoke_test guardian")
            return "smoke_test"

        if "CONFLICT" in categories:
            # In future, this would be 'diff' guardian
            logger.info("Found CONFLICT, selecting smoke_test guardian (diff not yet available)")
            return "smoke_test"

        # Default to smoke_test
        logger.info("No specific finding matched, defaulting to smoke_test guardian")
        return "smoke_test"

    def create_assignment(
        self, task_id: str, guardian_code: str, reason: Dict[str, Any]
    ) -> GuardianAssignment:
        """
        Create a Guardian assignment

        Args:
            task_id: Task to verify
            guardian_code: Guardian to assign
            reason: Reason for assignment (includes findings, context, etc.)

        Returns:
            GuardianAssignment instance

        Raises:
            ValueError: If Guardian code is not registered
        """
        # Validate Guardian exists
        if not self.registry.has(guardian_code):
            raise ValueError(f"Guardian not registered: {guardian_code}")

        assignment = GuardianAssignment.create(
            task_id=task_id,
            guardian_code=guardian_code,
            reason=reason,
        )

        logger.info(
            f"Created assignment {assignment.assignment_id}: "
            f"task={task_id}, guardian={guardian_code}"
        )

        return assignment

    def assign_guardian(
        self, task_id: str, findings: List[Dict[str, Any]], task_context: Dict[str, Any]
    ) -> GuardianAssignment:
        """
        Choose and assign a Guardian in one step

        Convenience method that combines choose_guardian() and create_assignment().

        Args:
            task_id: Task to verify
            findings: List of findings
            task_context: Task metadata

        Returns:
            GuardianAssignment instance
        """
        guardian_code = self.choose_guardian(findings, task_context)

        reason = {
            "findings": findings,
            "selected_guardian": guardian_code,
            "task_context": task_context,
        }

        return self.create_assignment(task_id, guardian_code, reason)
