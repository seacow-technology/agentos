"""
Task Routing Service - Handles routing for task creation

Integrates Router with Task creation pipeline (PR-2: Chat→Task Integration)

Key functionality:
- Route new tasks based on task spec
- Save routing information to task
- Write audit events
- Support manual route override
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from agentos.router import Router, RoutePlan
from agentos.core.task.manager import TaskManager

logger = logging.getLogger(__name__)


class TaskRoutingService:
    """
    Service layer for task routing operations

    Coordinates between Router and TaskManager to handle:
    - Initial routing when creating tasks
    - Route verification before execution
    - Manual route overrides
    - Audit event writing
    """

    def __init__(
        self,
        router: Optional[Router] = None,
        task_manager: Optional[TaskManager] = None,
    ):
        """
        Initialize service

        Args:
            router: Router instance (creates new if None)
            task_manager: TaskManager instance (creates new if None)
        """
        self.router = router or Router()
        self.task_manager = task_manager or TaskManager()

    async def route_new_task(
        self,
        task_id: str,
        task_spec: Dict[str, Any],
    ) -> RoutePlan:
        """
        Route a newly created task

        Called during task creation to determine which provider instance to use.

        Args:
            task_id: Task ID
            task_spec: Task specification (title, description, metadata, etc.)

        Returns:
            RoutePlan

        Raises:
            RuntimeError: If routing fails
        """
        logger.info(f"Routing new task {task_id}")

        try:
            # Call router to generate plan
            plan = await self.router.route(task_id, task_spec)

            # Save routing info to task
            self.task_manager.update_task_routing(
                task_id=task_id,
                route_plan_json=json.dumps(plan.to_dict()),
                requirements_json=json.dumps(plan.requirements.to_dict()) if plan.requirements else "{}",
                selected_instance_id=plan.selected,
                router_version=plan.router_version,
            )

            # Write audit event
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="TASK_ROUTED",
                level="info",
                payload={
                    "selected": plan.selected,
                    "fallback": plan.fallback,
                    "reasons": plan.reasons,
                    "scores": plan.scores,
                    "router_version": plan.router_version,
                },
            )

            logger.info(f"Task {task_id} routed to {plan.selected}")
            return plan

        except Exception as e:
            logger.error(f"Routing failed for task {task_id}: {e}", exc_info=True)
            # Write error audit
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="TASK_ROUTING_FAILED",
                level="error",
                payload={"error": str(e)},
            )
            raise RuntimeError(f"Failed to route task {task_id}: {e}")

    async def verify_route(
        self,
        task_id: str,
    ) -> RoutePlan:
        """
        Verify task routing before execution

        Checks if selected instance is still available, reroutes if needed.

        Args:
            task_id: Task ID

        Returns:
            Current or updated RoutePlan

        Raises:
            RuntimeError: If task not found or routing info missing
        """
        logger.info(f"Verifying route for task {task_id}")

        # Get task from database
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RuntimeError(f"Task not found: {task_id}")

        if not task.route_plan_json:
            raise RuntimeError(f"Task {task_id} has no routing information")

        # Parse current plan
        plan_dict = json.loads(task.route_plan_json)
        current_plan = RoutePlan.from_dict(plan_dict)

        # Verify or reroute
        new_plan, reroute_event = await self.router.verify_or_reroute(task_id, current_plan)

        # If rerouted, update task and write audit
        if reroute_event:
            self.task_manager.update_task_routing(
                task_id=task_id,
                route_plan_json=json.dumps(new_plan.to_dict()),
                requirements_json=task.requirements_json or "{}",  # Keep existing requirements
                selected_instance_id=new_plan.selected,
                router_version=new_plan.router_version,
            )

            # Write reroute audit event
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="TASK_REROUTED",
                level="warn",
                payload=reroute_event.to_dict(),
            )

            logger.warning(f"Task {task_id} rerouted: {reroute_event.from_instance} -> {reroute_event.to_instance}")
        else:
            # Write verification audit
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="TASK_ROUTE_VERIFIED",
                level="info",
                payload={"selected": new_plan.selected},
            )

        return new_plan

    def override_route(
        self,
        task_id: str,
        new_instance_id: str,
    ) -> RoutePlan:
        """
        Manually override task routing

        Used when user selects a different instance in UI.

        Args:
            task_id: Task ID
            new_instance_id: New instance to use

        Returns:
            Updated RoutePlan

        Raises:
            RuntimeError: If task not found or routing info missing
        """
        logger.info(f"Manual route override for task {task_id}: -> {new_instance_id}")

        # Get task from database
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RuntimeError(f"Task not found: {task_id}")

        if not task.route_plan_json:
            raise RuntimeError(f"Task {task_id} has no routing information")

        # Parse current plan
        plan_dict = json.loads(task.route_plan_json)
        current_plan = RoutePlan.from_dict(plan_dict)

        # Override route
        new_plan = self.router.override_route(task_id, current_plan, new_instance_id)

        # Update task
        self.task_manager.update_task_routing(
            task_id=task_id,
            route_plan_json=json.dumps(new_plan.to_dict()),
            requirements_json=task.requirements_json or "{}",
            selected_instance_id=new_plan.selected,
            router_version=new_plan.router_version,
        )

        # Write audit event
        self.task_manager.add_audit(
            task_id=task_id,
            event_type="TASK_ROUTE_OVERRIDDEN",
            level="info",
            payload={
                "previous_instance": current_plan.selected,
                "new_instance": new_instance_id,
                "method": "manual_ui",
            },
        )

        logger.info(f"Task {task_id} route overridden: {current_plan.selected} -> {new_instance_id}")
        return new_plan

    def get_route_plan(self, task_id: str) -> Optional[RoutePlan]:
        """
        Get current routing plan for a task

        Args:
            task_id: Task ID

        Returns:
            RoutePlan or None if not found/not routed
        """
        task = self.task_manager.get_task(task_id)
        if not task or not task.route_plan_json:
            return None

        try:
            plan_dict = json.loads(task.route_plan_json)
            return RoutePlan.from_dict(plan_dict)
        except Exception as e:
            logger.error(f"Failed to parse route plan for task {task_id}: {e}")
            return None


# Helper function for sync contexts (e.g., task_handler.py)
def route_task_sync(task_id: str, task_spec: Dict[str, Any]) -> RoutePlan:
    """
    Synchronous wrapper for routing a task

    Use this in non-async contexts like task_handler.

    Args:
        task_id: Task ID
        task_spec: Task specification

    Returns:
        RoutePlan
    """
    service = TaskRoutingService()
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If event loop is running, use run_until_complete
        # This works in most cases except nested async calls
        return loop.run_until_complete(service.route_new_task(task_id, task_spec))
    else:
        # Create new event loop
        return asyncio.run(service.route_new_task(task_id, task_spec))
