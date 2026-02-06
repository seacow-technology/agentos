"""Mode Gateway Registry - Manages mode gateway instances and caching.

This module provides:
1. DefaultModeGateway: A basic implementation that approves all transitions
2. Gateway registry: Maps mode_id -> gateway instance
3. Gateway caching: Reuses gateway instances for performance

The registry supports custom gateway registration and provides a fail-safe
default gateway for unknown modes.

Design Principles:
1. Fail-safe: Unknown modes get a permissive default gateway
2. Cacheable: Gateway instances are cached for performance
3. Extensible: Easy to register custom gateways
4. Type-safe: Uses Protocol for gateway validation

Usage:
    from agentos.core.mode.gateway_registry import get_mode_gateway

    # Get gateway for a mode
    gateway = get_mode_gateway("implementation")
    decision = gateway.validate_transition(
        task_id="task-123",
        mode_id="implementation",
        from_state="QUEUED",
        to_state="RUNNING",
        metadata={}
    )

    # Register custom gateway
    register_mode_gateway("custom_mode", CustomGateway())
"""

from __future__ import annotations
import logging
from typing import Dict, Optional

from .gateway import (
    ModeGatewayProtocol,
    ModeDecision,
    ModeDecisionVerdict,
)

logger = logging.getLogger(__name__)


class DefaultModeGateway:
    """Default mode gateway that approves all transitions.

    This is a permissive gateway used when:
    1. No custom gateway is registered for a mode
    2. System should fail-safe (allow operation if mode check fails)

    The default gateway logs all validation requests for audit purposes
    but does not block any transitions.

    Attributes:
        gateway_id: Identifier for this gateway instance
    """

    def __init__(self, gateway_id: str = "default"):
        """Initialize default gateway.

        Args:
            gateway_id: Identifier for logging and audit
        """
        self.gateway_id = gateway_id

    def validate_transition(
        self,
        task_id: str,
        mode_id: str,
        from_state: str,
        to_state: str,
        metadata: dict
    ) -> ModeDecision:
        """Validate transition (always approves).

        Args:
            task_id: Task ID
            mode_id: Mode ID
            from_state: Current state
            to_state: Target state
            metadata: Task metadata

        Returns:
            ModeDecision with APPROVED verdict
        """
        logger.debug(
            f"DefaultModeGateway: Approving transition for task {task_id} "
            f"in mode '{mode_id}' from '{from_state}' to '{to_state}'"
        )

        return ModeDecision(
            verdict=ModeDecisionVerdict.APPROVED,
            reason=f"Default gateway approves all transitions (mode: {mode_id})",
            metadata={
                "gateway_type": "default",
                "task_id": task_id,
                "transition": f"{from_state} -> {to_state}",
            },
            gateway_id=self.gateway_id,
        )


class RestrictedModeGateway:
    """Restricted mode gateway that blocks certain transitions.

    Used for modes that require additional validation or approval
    before allowing state transitions.

    Example use cases:
    - Autonomous modes requiring approval before RUNNING
    - Production modes requiring approval before DONE
    - Experimental modes requiring monitoring
    """

    def __init__(
        self,
        mode_id: str,
        blocked_transitions: Optional[Dict[str, set]] = None,
        gateway_id: Optional[str] = None
    ):
        """Initialize restricted gateway.

        Args:
            mode_id: Mode this gateway is for
            blocked_transitions: Dict mapping from_state -> set of blocked to_states
            gateway_id: Identifier for logging (defaults to f"restricted_{mode_id}")
        """
        self.mode_id = mode_id
        self.blocked_transitions = blocked_transitions or {}
        self.gateway_id = gateway_id or f"restricted_{mode_id}"

    def validate_transition(
        self,
        task_id: str,
        mode_id: str,
        from_state: str,
        to_state: str,
        metadata: dict
    ) -> ModeDecision:
        """Validate transition with restrictions.

        Args:
            task_id: Task ID
            mode_id: Mode ID
            from_state: Current state
            to_state: Target state
            metadata: Task metadata

        Returns:
            ModeDecision with APPROVED or BLOCKED verdict
        """
        # Check if transition is blocked
        blocked_states = self.blocked_transitions.get(from_state, set())
        if to_state in blocked_states:
            logger.warning(
                f"RestrictedModeGateway: Blocking transition for task {task_id} "
                f"in mode '{mode_id}' from '{from_state}' to '{to_state}'"
            )
            return ModeDecision(
                verdict=ModeDecisionVerdict.BLOCKED,
                reason=f"Transition {from_state} -> {to_state} requires approval in mode {mode_id}",
                metadata={
                    "gateway_type": "restricted",
                    "task_id": task_id,
                    "transition": f"{from_state} -> {to_state}",
                    "requires_approval": True,
                },
                gateway_id=self.gateway_id,
            )

        # Approve if not blocked
        logger.debug(
            f"RestrictedModeGateway: Approving transition for task {task_id} "
            f"in mode '{mode_id}' from '{from_state}' to '{to_state}'"
        )
        return ModeDecision(
            verdict=ModeDecisionVerdict.APPROVED,
            reason=f"Transition approved by restricted gateway (mode: {mode_id})",
            metadata={
                "gateway_type": "restricted",
                "task_id": task_id,
                "transition": f"{from_state} -> {to_state}",
            },
            gateway_id=self.gateway_id,
        )


# ==============================================================================
# Gateway Registry
# ==============================================================================

# Global registry: mode_id -> gateway instance
_gateway_registry: Dict[str, ModeGatewayProtocol] = {}

# Gateway cache: mode_id -> gateway instance (for performance)
_gateway_cache: Dict[str, ModeGatewayProtocol] = {}

# Default gateway instance (shared across all modes without custom gateway)
_default_gateway = DefaultModeGateway()


def register_mode_gateway(mode_id: str, gateway: ModeGatewayProtocol) -> None:
    """Register a custom gateway for a mode.

    Args:
        mode_id: Mode identifier
        gateway: Gateway instance implementing ModeGatewayProtocol

    Example:
        >>> custom_gateway = RestrictedModeGateway(
        ...     mode_id="autonomous",
        ...     blocked_transitions={"QUEUED": {"RUNNING"}}
        ... )
        >>> register_mode_gateway("autonomous", custom_gateway)
    """
    _gateway_registry[mode_id] = gateway
    # Invalidate cache for this mode
    _gateway_cache.pop(mode_id, None)
    logger.info(f"Registered gateway for mode '{mode_id}': {gateway.__class__.__name__}")


def get_mode_gateway(mode_id: str) -> ModeGatewayProtocol:
    """Get gateway for a mode (with caching).

    Args:
        mode_id: Mode identifier

    Returns:
        Gateway instance for the mode (or default gateway)

    Note:
        - Returns cached instance if available
        - Falls back to default gateway if no custom gateway registered
        - Default gateway is permissive (approves all transitions)
    """
    # Check cache first
    if mode_id in _gateway_cache:
        return _gateway_cache[mode_id]

    # Check registry
    if mode_id in _gateway_registry:
        gateway = _gateway_registry[mode_id]
        _gateway_cache[mode_id] = gateway
        return gateway

    # Fall back to default gateway
    logger.debug(
        f"No custom gateway registered for mode '{mode_id}', using default gateway"
    )
    _gateway_cache[mode_id] = _default_gateway
    return _default_gateway


def clear_gateway_cache() -> None:
    """Clear the gateway cache.

    Useful for testing or when gateway configuration changes.
    """
    _gateway_cache.clear()
    logger.info("Gateway cache cleared")


def clear_gateway_registry() -> None:
    """Clear the gateway registry.

    Warning: This removes all custom gateway registrations.
    Useful for testing but should not be used in production.
    """
    _gateway_registry.clear()
    _gateway_cache.clear()
    logger.warning("Gateway registry cleared (all custom gateways removed)")


def get_registered_modes() -> set:
    """Get all modes with registered gateways.

    Returns:
        Set of mode_ids with custom gateways
    """
    return set(_gateway_registry.keys())


# ==============================================================================
# Pre-configured Gateways
# ==============================================================================

def register_default_gateways() -> None:
    """Register default gateways for built-in modes.

    This function sets up gateways for common modes:
    - implementation: Default (permissive)
    - design, chat, planning: Default (permissive)
    - autonomous: Restricted (requires approval for RUNNING)
    """
    # Most modes use default gateway (no registration needed)

    # Register restricted gateway for autonomous mode
    # (blocks QUEUED -> RUNNING transition)
    autonomous_gateway = RestrictedModeGateway(
        mode_id="autonomous",
        blocked_transitions={
            "QUEUED": {"RUNNING"},  # Require approval before starting
        },
        gateway_id="autonomous_approval_gate"
    )
    register_mode_gateway("autonomous", autonomous_gateway)

    logger.info("Default gateways registered for built-in modes")


__all__ = [
    "DefaultModeGateway",
    "RestrictedModeGateway",
    "register_mode_gateway",
    "get_mode_gateway",
    "clear_gateway_cache",
    "clear_gateway_registry",
    "get_registered_modes",
    "register_default_gateways",
]
