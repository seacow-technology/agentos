"""
Router Usage Example

Demonstrates how to use the Task Router to route tasks to provider instances.

PR-1: Router Core - Example usage
"""

import asyncio
import logging
from agentos.router import Router, RouterPersistence, router_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_basic_routing():
    """
    Example 1: Basic routing

    Route a coding task to the best available instance.
    """
    logger.info("=" * 60)
    logger.info("Example 1: Basic Routing")
    logger.info("=" * 60)

    # Create router
    router = Router()

    # Define task specification
    task_spec = {
        "task_id": "task_example_001",
        "title": "Implement user authentication API",
        "description": "Create REST API endpoints for user login, logout, and token refresh using FastAPI",
        "metadata": {
            "priority": "high",
        }
    }

    # Route the task
    try:
        route_plan = await router.route(
            task_id=task_spec["task_id"],
            task_spec=task_spec,
        )

        logger.info(f"\nRoute Plan:")
        logger.info(f"  Task ID: {route_plan.task_id}")
        logger.info(f"  Selected: {route_plan.selected}")
        logger.info(f"  Score: {route_plan.scores.get(route_plan.selected, 0):.2f}")
        logger.info(f"  Fallback: {route_plan.fallback}")
        logger.info(f"  Reasons: {', '.join(route_plan.reasons)}")
        if route_plan.requirements:
            logger.info(f"  Requirements: needs={route_plan.requirements.needs}")

        # Emit routing event
        router_events.emit_task_routed(route_plan)

        # Save to database (optional)
        persistence = RouterPersistence()
        persistence.save_route_plan(route_plan)

        return route_plan

    except RuntimeError as e:
        logger.error(f"Routing failed: {e}")
        return None


async def example_route_verification():
    """
    Example 2: Route verification

    Verify that a routed instance is still available before execution.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Route Verification")
    logger.info("=" * 60)

    # First route a task
    router = Router()
    task_spec = {
        "task_id": "task_example_002",
        "title": "Write unit tests for authentication module",
        "description": "Create pytest tests with fixtures and mocks",
    }

    route_plan = await router.route(
        task_id=task_spec["task_id"],
        task_spec=task_spec,
    )

    logger.info(f"Initial route: {route_plan.selected}")

    # Verify the route (simulate pre-execution check)
    updated_plan, reroute_event = await router.verify_or_reroute(
        task_id=route_plan.task_id,
        current_plan=route_plan,
    )

    if reroute_event:
        logger.info(f"Rerouted: {reroute_event.from_instance} → {reroute_event.to_instance}")
        logger.info(f"Reason: {reroute_event.reason_code.value}")
        router_events.emit_task_rerouted(reroute_event)
    else:
        logger.info(f"Route verified: {updated_plan.selected} is still READY")
        router_events.emit_task_route_verified(
            task_id=updated_plan.task_id,
            instance_id=updated_plan.selected,
            state="READY",
        )

    return updated_plan


async def example_manual_override():
    """
    Example 3: Manual route override

    Manually change the selected instance (user override).
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Manual Override")
    logger.info("=" * 60)

    router = Router()

    # Create a task
    task_spec = {
        "task_id": "task_example_003",
        "title": "Generate landing page with React and Tailwind",
    }

    route_plan = await router.route(
        task_id=task_spec["task_id"],
        task_spec=task_spec,
    )

    logger.info(f"Auto-selected: {route_plan.selected}")

    # Get available instances
    available = await router.get_available_instances()
    logger.info(f"Available instances: {[p.instance_id for p in available]}")

    # User manually selects a different instance
    if len(available) > 1:
        new_instance = available[1].instance_id
        logger.info(f"User overrides to: {new_instance}")

        overridden_plan = router.override_route(
            task_id=route_plan.task_id,
            current_plan=route_plan,
            new_instance_id=new_instance,
        )

        logger.info(f"New selected: {overridden_plan.selected}")
        logger.info(f"New fallback: {overridden_plan.fallback}")

        # Emit override event
        router_events.emit_task_route_overridden(
            task_id=overridden_plan.task_id,
            from_instance=route_plan.selected,
            to_instance=overridden_plan.selected,
            user="demo_user",
        )

        return overridden_plan

    return route_plan


async def example_routing_stats():
    """
    Example 4: Get routing statistics

    Query routing statistics from database.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Routing Statistics")
    logger.info("=" * 60)

    persistence = RouterPersistence()
    stats = persistence.get_routing_stats()

    logger.info(f"Total routed tasks: {stats['total_routed']}")
    logger.info("Tasks by instance:")
    for instance_id, count in stats['by_instance'].items():
        logger.info(f"  {instance_id}: {count}")


async def main():
    """Run all examples"""
    logger.info("\n" + "=" * 60)
    logger.info("Task Router Examples")
    logger.info("=" * 60)

    # Example 1: Basic routing
    await example_basic_routing()

    # Example 2: Route verification
    await example_route_verification()

    # Example 3: Manual override
    await example_manual_override()

    # Example 4: Routing stats
    await example_routing_stats()

    logger.info("\n" + "=" * 60)
    logger.info("Examples completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
