"""
Task Router - Core routing engine

Main entry point for task routing decisions.
Orchestrates requirements extraction, instance profiling, scoring, and route planning.

PR-1: Router Core
PR-2: Chat→Task Integration
"""

import logging
from typing import Dict, Any, List, Optional
from agentos.router.models import (
    RoutePlan,
    TaskRequirements,
    InstanceProfile,
    RerouteReason,
    RerouteEvent,
)
from agentos.router.requirements_extractor import RequirementsExtractor
from agentos.router.instance_profiles import InstanceProfileBuilder
from agentos.router.scorer import RouteScorer, RouteScore
from agentos.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class Router:
    """
    Task Router - Intelligent instance selection

    Main workflow:
    1. Extract requirements from task spec
    2. Build instance profiles from provider registry
    3. Score all instances against requirements
    4. Generate routing plan with selected instance and fallback chain
    5. Write audit events

    Supports:
    - Initial routing (route)
    - Route verification (verify_or_reroute)
    - Manual override (override_route)
    """

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        extractor: Optional[RequirementsExtractor] = None,
        profile_builder: Optional[InstanceProfileBuilder] = None,
        scorer: Optional[RouteScorer] = None,
    ):
        """
        Initialize Router

        Args:
            registry: ProviderRegistry (uses singleton if None)
            extractor: RequirementsExtractor (creates new if None)
            profile_builder: InstanceProfileBuilder (creates new if None)
            scorer: RouteScorer (creates new if None)
        """
        self.registry = registry or ProviderRegistry.get_instance()
        self.extractor = extractor or RequirementsExtractor()
        self.profile_builder = profile_builder or InstanceProfileBuilder(self.registry)
        self.scorer = scorer or RouteScorer()

    async def route(
        self,
        task_id: str,
        task_spec: Dict[str, Any],
    ) -> RoutePlan:
        """
        Generate routing plan for a task

        Args:
            task_id: Task ID
            task_spec: Task specification dict (title, description, metadata, etc.)

        Returns:
            RoutePlan with selected instance and fallback chain

        Raises:
            RuntimeError: If no available instances
        """
        logger.info(f"Routing task {task_id}")

        # Step 1: Extract requirements
        requirements = self.extractor.extract(task_spec)
        logger.info(f"Requirements: needs={requirements.needs}, min_ctx={requirements.min_ctx}")

        # Step 2: Build instance profiles
        profiles = await self.profile_builder.build_all_profiles()
        logger.info(f"Found {len(profiles)} provider instances")

        if not profiles:
            raise RuntimeError("No provider instances available")

        # Step 3: Score all instances
        scores = self.scorer.score_all(profiles, requirements)

        # Step 4: Select top instances
        top_scores = self.scorer.select_top_n(scores, n=3)

        if not top_scores:
            # No instances with score > 0
            raise RuntimeError(
                f"No suitable instances found for task requirements: {requirements.needs}"
            )

        # Step 5: Build routing plan
        selected = top_scores[0]
        fallback = [s.instance_id for s in top_scores[1:]]

        scores_dict = {s.instance_id: s.total_score for s in scores}

        plan = RoutePlan(
            task_id=task_id,
            selected=selected.instance_id,
            fallback=fallback,
            scores=scores_dict,
            reasons=selected.reasons,
            requirements=requirements,
        )

        logger.info(
            f"Route plan: selected={plan.selected}, "
            f"fallback={plan.fallback}, "
            f"score={selected.total_score:.2f}"
        )

        return plan

    async def verify_or_reroute(
        self,
        task_id: str,
        current_plan: RoutePlan,
    ) -> tuple[RoutePlan, Optional[RerouteEvent]]:
        """
        Verify current route plan and reroute if necessary

        Called before task execution to ensure selected instance is still available.

        Args:
            task_id: Task ID
            current_plan: Current RoutePlan

        Returns:
            Tuple of (possibly updated RoutePlan, RerouteEvent if rerouted)
        """
        logger.info(f"Verifying route for task {task_id}: {current_plan.selected}")

        # Get profile for current selected instance
        profile = await self.profile_builder.get_profile(current_plan.selected)

        if profile and profile.state == "READY":
            # Instance still ready, no reroute needed
            logger.info(f"Route verified: {current_plan.selected} still READY")
            return current_plan, None

        # Instance not ready, need to reroute
        logger.warning(
            f"Instance {current_plan.selected} not ready (state={profile.state if profile else 'NOT_FOUND'})"
        )

        # Try fallback chain
        for fallback_id in current_plan.fallback:
            fallback_profile = await self.profile_builder.get_profile(fallback_id)
            if fallback_profile and fallback_profile.state == "READY":
                # Found a working fallback
                reroute_event = RerouteEvent(
                    task_id=task_id,
                    from_instance=current_plan.selected,
                    to_instance=fallback_id,
                    reason_code=RerouteReason.INSTANCE_NOT_READY,
                    reason_detail=f"Selected instance not ready (state={profile.state if profile else 'NOT_FOUND'})",
                    timestamp="",  # Will be set in __post_init__
                    fallback_chain=current_plan.fallback,
                )

                # Update plan
                new_plan = RoutePlan(
                    task_id=task_id,
                    selected=fallback_id,
                    fallback=[f for f in current_plan.fallback if f != fallback_id],
                    scores=current_plan.scores,
                    reasons=current_plan.reasons + [f"rerouted_from={current_plan.selected}"],
                    requirements=current_plan.requirements,
                )

                logger.info(f"Rerouted to fallback: {fallback_id}")
                return new_plan, reroute_event

        # No working fallback, need to re-route from scratch
        logger.error("All fallback instances failed, re-routing from scratch")

        try:
            # Re-run full routing
            task_spec = {
                "title": f"Re-route for task {task_id}",
                "metadata": {"requirements": current_plan.requirements.to_dict() if current_plan.requirements else {}},
            }
            new_plan = await self.route(task_id, task_spec)

            reroute_event = RerouteEvent(
                task_id=task_id,
                from_instance=current_plan.selected,
                to_instance=new_plan.selected,
                reason_code=RerouteReason.NO_AVAILABLE_INSTANCE,
                reason_detail="All planned instances unavailable, full re-route performed",
                timestamp="",
                fallback_chain=[],
            )

            return new_plan, reroute_event

        except RuntimeError as e:
            # Complete routing failure
            logger.error(f"Complete routing failure: {e}")
            raise RuntimeError(f"Cannot route task {task_id}: {e}")

    def override_route(
        self,
        task_id: str,
        current_plan: RoutePlan,
        new_instance_id: str,
    ) -> RoutePlan:
        """
        Manually override routing decision

        Used for manual instance selection in UI.

        Args:
            task_id: Task ID
            current_plan: Current RoutePlan
            new_instance_id: New instance to use

        Returns:
            Updated RoutePlan
        """
        logger.info(f"Manual route override for task {task_id}: {current_plan.selected} -> {new_instance_id}")

        # Build new fallback chain (remove new_instance_id if present)
        new_fallback = [current_plan.selected]  # Previous selected becomes first fallback
        new_fallback.extend([f for f in current_plan.fallback if f != new_instance_id])

        new_plan = RoutePlan(
            task_id=task_id,
            selected=new_instance_id,
            fallback=new_fallback,
            scores=current_plan.scores,
            reasons=["manual_override"] + current_plan.reasons,
            requirements=current_plan.requirements,
        )

        return new_plan

    async def get_available_instances(self) -> List[InstanceProfile]:
        """
        Get all available (READY) instance profiles

        Returns:
            List of InstanceProfile with state=READY
        """
        all_profiles = await self.profile_builder.build_all_profiles()
        available = [p for p in all_profiles if p.state == "READY"]
        return available
