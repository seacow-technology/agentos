"""
Router Event Emitters - Emit routing events to event bus

Provides convenience functions for emitting router-related events
with proper formatting and auditability.

PR-1: Router Core - Event integration
"""

import logging
from typing import Optional, Dict, Any

from agentos.router.models import RoutePlan, RerouteEvent
from agentos.core.events import Event, get_event_bus

logger = logging.getLogger(__name__)


def emit_task_routed(route_plan: RoutePlan) -> None:
    """
    Emit task.routed event

    Args:
        route_plan: RoutePlan to emit
    """
    try:
        event = Event.task_routed(
            task_id=route_plan.task_id,
            selected=route_plan.selected,
            fallback=route_plan.fallback,
            scores=route_plan.scores,
            reasons=route_plan.reasons,
            requirements=route_plan.requirements.to_dict() if route_plan.requirements else None,
        )

        bus = get_event_bus()
        bus.emit(event)

        logger.info(f"Emitted task.routed event for task {route_plan.task_id}")
    except Exception as e:
        logger.error(f"Failed to emit task.routed event: {e}", exc_info=True)


def emit_task_route_verified(task_id: str, instance_id: str, state: str) -> None:
    """
    Emit task.route_verified event

    Args:
        task_id: Task identifier
        instance_id: Verified instance ID
        state: Instance state
    """
    try:
        event = Event.task_route_verified(
            task_id=task_id,
            instance_id=instance_id,
            state=state,
        )

        bus = get_event_bus()
        bus.emit(event)

        logger.info(f"Emitted task.route_verified event for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to emit task.route_verified event: {e}", exc_info=True)


def emit_task_rerouted(reroute_event: RerouteEvent) -> None:
    """
    Emit task.rerouted event

    Args:
        reroute_event: RerouteEvent to emit
    """
    try:
        event = Event.task_rerouted(
            task_id=reroute_event.task_id,
            from_instance=reroute_event.from_instance,
            to_instance=reroute_event.to_instance,
            reason_code=reroute_event.reason_code.value,
            reason_detail=reroute_event.reason_detail,
            fallback_chain=reroute_event.fallback_chain,
        )

        bus = get_event_bus()
        bus.emit(event)

        logger.info(
            f"Emitted task.rerouted event for task {reroute_event.task_id}: "
            f"{reroute_event.from_instance} → {reroute_event.to_instance}"
        )
    except Exception as e:
        logger.error(f"Failed to emit task.rerouted event: {e}", exc_info=True)


def emit_task_route_overridden(
    task_id: str,
    from_instance: str,
    to_instance: str,
    user: Optional[str] = None,
) -> None:
    """
    Emit task.route_overridden event

    Args:
        task_id: Task identifier
        from_instance: Original instance
        to_instance: New instance
        user: User who performed override (optional)
    """
    try:
        event = Event.task_route_overridden(
            task_id=task_id,
            from_instance=from_instance,
            to_instance=to_instance,
            user=user,
        )

        bus = get_event_bus()
        bus.emit(event)

        logger.info(
            f"Emitted task.route_overridden event for task {task_id}: "
            f"{from_instance} → {to_instance} (user: {user or 'unknown'})"
        )
    except Exception as e:
        logger.error(f"Failed to emit task.route_overridden event: {e}", exc_info=True)
