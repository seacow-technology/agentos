"""
Precondition Checker - Validate capability dependencies and preconditions

This module checks:
1. Dependency requirements (`requires` field) - dependent capabilities must be granted
2. State preconditions (e.g., plan must be frozen before Action execution)
3. Cost estimation (tokens, time_ms, API calls)

Design Philosophy:
- Check before execution (fail fast)
- Clear error messages
- Performance: < 10ms per check
"""

import logging
from typing import Dict, List, Optional, Tuple

from agentos.core.capability.models import (
    CapabilityDefinition,
    CostModel,
    SideEffectType,
)
from agentos.core.capability.registry import CapabilityRegistry, get_capability_registry


logger = logging.getLogger(__name__)


class PreconditionError(Exception):
    """
    Raised when a precondition check fails.

    Attributes:
        capability_id: Capability being checked
        missing_requirements: List of missing dependencies
        state_violations: List of state violations
        reason: Human-readable reason
    """

    def __init__(
        self,
        capability_id: str,
        missing_requirements: List[str],
        state_violations: List[str],
        reason: str,
    ):
        self.capability_id = capability_id
        self.missing_requirements = missing_requirements
        self.state_violations = state_violations
        self.reason = reason

        error_parts = [f"Precondition check failed for '{capability_id}'"]

        if missing_requirements:
            error_parts.append(
                f"Missing required capabilities: {', '.join(missing_requirements)}"
            )

        if state_violations:
            error_parts.append(f"State violations: {', '.join(state_violations)}")

        error_parts.append(f"Reason: {reason}")

        super().__init__("\n".join(error_parts))


class PreconditionChecker:
    """
    Precondition checker for capability invocations.

    This class verifies:
    1. All `requires` dependencies are granted to the agent
    2. State preconditions are met (e.g., frozen plan)
    3. Cost budgets are not exceeded

    Usage:
        checker = PreconditionChecker()

        # Check before invoking capability
        checker.check_preconditions(
            agent_id="executor_agent",
            capability_id="action.execute",
            context={"task_id": "task-123", "plan_frozen": True}
        )

        # Estimate cost
        cost = checker.estimate_cost(capability_id="action.llm.call")
        print(f"Estimated tokens: {cost.estimated_tokens}")
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None):
        """
        Initialize precondition checker.

        Args:
            registry: CapabilityRegistry instance (default: use global singleton)
        """
        self.registry = registry or get_capability_registry()
        logger.debug("PreconditionChecker initialized")

    # ===================================================================
    # Precondition Checks
    # ===================================================================

    def check_preconditions(
        self,
        agent_id: str,
        capability_id: str,
        context: Optional[Dict] = None,
    ):
        """
        Check all preconditions for a capability invocation.

        This is the main entry point called BEFORE executing a capability.

        Args:
            agent_id: Agent invoking the capability
            capability_id: Capability to check
            context: Execution context (for state preconditions)

        Raises:
            PreconditionError: If any precondition fails
            ValueError: If capability not found
        """
        context = context or {}

        # Get capability definition
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            raise ValueError(f"Capability not found: {capability_id}")

        missing_requirements = []
        state_violations = []

        # Check dependency requirements
        for required_cap_id in cap_def.requires:
            if not self.registry.has_capability(agent_id, required_cap_id):
                missing_requirements.append(required_cap_id)

        # Check state preconditions
        state_checks = self._check_state_preconditions(cap_def, context)
        if not state_checks[0]:
            state_violations.append(state_checks[1])

        # Raise error if any check failed
        if missing_requirements or state_violations:
            reason = self._build_precondition_failure_reason(
                cap_def, missing_requirements, state_violations
            )
            raise PreconditionError(
                capability_id=capability_id,
                missing_requirements=missing_requirements,
                state_violations=state_violations,
                reason=reason,
            )

        logger.debug(f"Preconditions passed for {capability_id}")

    def _check_state_preconditions(
        self, cap_def: CapabilityDefinition, context: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Check state-specific preconditions.

        These are domain-specific rules, e.g.:
        - Action domain requires frozen plan
        - Memory write requires governance approval
        - Task state write requires frozen plan

        Args:
            cap_def: Capability definition
            context: Execution context

        Returns:
            (is_valid, error_message)
        """
        capability_id = cap_def.capability_id

        # Action capabilities require frozen plan
        if capability_id.startswith("action."):
            if "plan_frozen" not in context or not context["plan_frozen"]:
                return False, "Action execution requires a frozen plan (decision.plan.freeze must be called first)"

        # Task state write requires frozen plan
        if capability_id == "state.task.write":
            if "plan_frozen" not in context or not context["plan_frozen"]:
                return False, "Task state modification requires a frozen plan"

        # Decision rollback requires special approval
        if capability_id == "decision.rollback":
            if "emergency_approved" not in context or not context["emergency_approved"]:
                return False, "Decision rollback requires emergency approval from governance"

        # File delete requires explicit confirmation
        if capability_id == "action.file.delete":
            if "delete_confirmed" not in context or not context["delete_confirmed"]:
                return False, "File deletion requires explicit confirmation flag"

        # All checks passed
        return True, None

    def _build_precondition_failure_reason(
        self,
        cap_def: CapabilityDefinition,
        missing_requirements: List[str],
        state_violations: List[str],
    ) -> str:
        """Build detailed failure reason"""
        parts = []

        if missing_requirements:
            parts.append(
                f"Agent must first be granted these capabilities: {', '.join(missing_requirements)}"
            )

        if state_violations:
            parts.append(f"State preconditions not met: {'; '.join(state_violations)}")

        parts.append(f"See capability definition for '{cap_def.capability_id}' for details.")

        return " | ".join(parts)

    # ===================================================================
    # Dependency Validation
    # ===================================================================

    def validate_dependencies(
        self, agent_id: str, capability_id: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all dependency capabilities are granted.

        This checks the `requires` field of the capability definition.

        Args:
            agent_id: Agent identifier
            capability_id: Capability to check

        Returns:
            (all_granted, missing_capabilities)
        """
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            return False, [f"Capability not found: {capability_id}"]

        missing = []
        for required_cap_id in cap_def.requires:
            if not self.registry.has_capability(agent_id, required_cap_id):
                missing.append(required_cap_id)

        return (len(missing) == 0, missing)

    def get_dependency_tree(
        self, capability_id: str, max_depth: int = 10
    ) -> Dict[str, List[str]]:
        """
        Get full dependency tree for a capability.

        This recursively resolves all `requires` dependencies.

        Args:
            capability_id: Capability to analyze
            max_depth: Maximum recursion depth

        Returns:
            Dict mapping capability_id → list of direct dependencies
        """
        if max_depth <= 0:
            logger.warning(f"Max depth reached resolving dependencies for {capability_id}")
            return {}

        tree = {}
        visited = set()

        def _resolve(cap_id: str, depth: int):
            if depth >= max_depth or cap_id in visited:
                return

            visited.add(cap_id)
            cap_def = self.registry.get_capability(cap_id)
            if cap_def is None:
                return

            tree[cap_id] = cap_def.requires

            # Recurse into dependencies
            for dep_cap_id in cap_def.requires:
                _resolve(dep_cap_id, depth + 1)

        _resolve(capability_id, 0)
        return tree

    # ===================================================================
    # Cost Estimation
    # ===================================================================

    def estimate_cost(self, capability_id: str) -> Optional[CostModel]:
        """
        Get cost estimate for a capability.

        Returns:
            CostModel with estimates, or None if not available
        """
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            return None

        return cap_def.cost_model

    def estimate_total_cost(
        self, capability_id: str, include_dependencies: bool = True
    ) -> CostModel:
        """
        Estimate total cost including dependencies.

        Args:
            capability_id: Capability to estimate
            include_dependencies: Include cost of dependencies

        Returns:
            Aggregated CostModel
        """
        total_tokens = 0
        total_time_ms = 0
        total_api_calls = 0

        # Get direct cost
        cap_def = self.registry.get_capability(capability_id)
        if cap_def and cap_def.cost_model:
            total_tokens += cap_def.cost_model.estimated_tokens or 0
            total_time_ms += cap_def.cost_model.estimated_time_ms or 0
            total_api_calls += cap_def.cost_model.estimated_api_calls or 0

        # Add dependency costs
        if include_dependencies and cap_def:
            for dep_cap_id in cap_def.requires:
                dep_cost = self.estimate_cost(dep_cap_id)
                if dep_cost:
                    total_tokens += dep_cost.estimated_tokens or 0
                    total_time_ms += dep_cost.estimated_time_ms or 0
                    total_api_calls += dep_cost.estimated_api_calls or 0

        return CostModel(
            estimated_tokens=total_tokens if total_tokens > 0 else None,
            estimated_time_ms=total_time_ms if total_time_ms > 0 else None,
            estimated_api_calls=total_api_calls if total_api_calls > 0 else None,
        )

    # ===================================================================
    # Batch Operations
    # ===================================================================

    def check_batch_preconditions(
        self, agent_id: str, capability_ids: List[str], context: Optional[Dict] = None
    ) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Check preconditions for multiple capabilities.

        Args:
            agent_id: Agent identifier
            capability_ids: List of capabilities to check
            context: Shared context

        Returns:
            Dict mapping capability_id → (is_valid, error_message)
        """
        results = {}

        for capability_id in capability_ids:
            try:
                self.check_preconditions(agent_id, capability_id, context)
                results[capability_id] = (True, None)
            except PreconditionError as e:
                results[capability_id] = (False, str(e))
            except Exception as e:
                results[capability_id] = (False, f"Unexpected error: {e}")

        return results

    def validate_agent_can_execute(
        self, agent_id: str, capability_id: str
    ) -> Tuple[bool, List[str]]:
        """
        Check if agent can execute capability (quick check without state).

        This only checks:
        1. Capability exists
        2. Agent has direct grant
        3. All dependencies are granted

        Does NOT check state preconditions.

        Args:
            agent_id: Agent identifier
            capability_id: Capability to check

        Returns:
            (can_execute, reasons_if_not)
        """
        reasons = []

        # Check capability exists
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            reasons.append(f"Capability '{capability_id}' does not exist")
            return False, reasons

        # Check agent has grant
        if not self.registry.has_capability(agent_id, capability_id):
            reasons.append(f"Agent does not have capability '{capability_id}'")

        # Check dependencies
        is_valid, missing = self.validate_dependencies(agent_id, capability_id)
        if not is_valid:
            reasons.append(f"Missing dependencies: {', '.join(missing)}")

        return (len(reasons) == 0, reasons)


# Global singleton
_checker_instance: Optional[PreconditionChecker] = None


def get_precondition_checker(
    registry: Optional[CapabilityRegistry] = None,
) -> PreconditionChecker:
    """
    Get global precondition checker singleton.

    Args:
        registry: Optional CapabilityRegistry instance

    Returns:
        Singleton PreconditionChecker instance
    """
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = PreconditionChecker(registry=registry)
    return _checker_instance
