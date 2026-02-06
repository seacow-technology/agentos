"""
Decision Comparator - Generates comparison metrics for active vs shadow decisions

This module provides the core engine for comparing active and shadow classifier
decisions to help humans evaluate which shadow version is worth migrating to production.

Key Features:
- Compare decision actions between active and shadow
- Aggregate metrics by info_need_type, time period, and classifier version
- Calculate improvement rates based on Reality Alignment Scores
- Support filtering and grouping across multiple dimensions

Design Philosophy:
- Data-driven: All comparisons based on actual recorded decisions
- Transparent: Clear metrics for human judgment
- Flexible: Support multiple aggregation and filtering dimensions
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agentos.core.audit import (
    get_decision_sets,
    get_shadow_evaluations_for_decision_set,
    get_user_behavior_signals_for_message,
)

logger = logging.getLogger(__name__)


class DecisionComparator:
    """
    Generates comparison metrics for active vs shadow decisions.

    Responsibilities:
    - Aggregate decision data from audit logs
    - Compute decision distribution statistics
    - Calculate improvement rates when scores are available
    - Support multi-dimensional filtering and grouping

    Usage:
        comparator = DecisionComparator()
        comparison = comparator.compare_versions(
            active_version="v1",
            shadow_version="v2-shadow-a",
            time_range=(start_time, end_time)
        )
    """

    def __init__(self):
        """Initialize decision comparator."""
        pass

    def compare_versions(
        self,
        active_version: str,
        shadow_version: str,
        session_id: Optional[str] = None,
        info_need_type: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Compare active and shadow classifier versions.

        Args:
            active_version: Active classifier version ID (e.g., "v1")
            shadow_version: Shadow classifier version ID (e.g., "v2-shadow-a")
            session_id: Optional session filter
            info_need_type: Optional info need type filter
            time_range: Optional time range (start, end)
            limit: Maximum number of decision sets to analyze

        Returns:
            Comparison result dictionary with structure:
            {
                "active": {
                    "version": "v1",
                    "avg_score": -0.5,  # If scores available
                    "decision_distribution": {
                        "REQUIRE_COMM": 120,
                        "DIRECT_ANSWER": 80,
                        ...
                    },
                    "info_need_distribution": {
                        "EXTERNAL_FACT_UNCERTAIN": 100,
                        "LOCAL_KNOWLEDGE": 90,
                        ...
                    }
                },
                "shadow": {
                    "version": "v2-shadow-a",
                    "avg_score": 0.2,
                    "decision_distribution": {...},
                    "info_need_distribution": {...}
                },
                "comparison": {
                    "improvement_rate": 0.7,  # If scores available
                    "sample_count": 312,
                    "decision_divergence_count": 150,
                    "decision_agreement_count": 162,
                    "divergence_rate": 0.48,
                    "better_count": 220,  # Shadow performed better
                    "worse_count": 50,    # Shadow performed worse
                    "neutral_count": 42,  # Same performance
                    "decision_action_comparison": {
                        "REQUIRE_COMM": {
                            "active_count": 120,
                            "shadow_count": 95,
                            "delta": -25
                        },
                        ...
                    }
                },
                "filters": {
                    "session_id": session_id,
                    "info_need_type": info_need_type,
                    "time_range": [start.isoformat(), end.isoformat()] if time_range else None
                }
            }
        """
        # Fetch decision sets
        decision_sets = self._fetch_decision_sets(
            session_id=session_id,
            active_version=active_version,
            limit=limit
        )

        # Filter by time range if specified
        if time_range:
            decision_sets = [
                ds for ds in decision_sets
                if time_range[0] <= datetime.fromtimestamp(ds["created_at"], tz=timezone.utc) <= time_range[1]
            ]

        # Filter decision sets that have the target shadow version
        filtered_sets = []
        for ds in decision_sets:
            payload = ds["payload"]
            if shadow_version in payload.get("shadow_versions", []):
                # Apply info_need_type filter if specified
                if info_need_type:
                    active_decision = payload.get("active_decision", {})
                    if active_decision.get("info_need_type") != info_need_type:
                        continue
                filtered_sets.append(ds)

        if not filtered_sets:
            logger.warning(
                f"No decision sets found for active={active_version}, shadow={shadow_version}"
            )
            return self._empty_comparison_result(
                active_version, shadow_version, session_id, info_need_type, time_range
            )

        # Aggregate active and shadow decisions
        active_stats = self._aggregate_decisions(filtered_sets, "active")
        shadow_stats = self._aggregate_shadow_decisions(filtered_sets, shadow_version)

        # Calculate comparison metrics
        comparison = self._calculate_comparison(
            filtered_sets, active_stats, shadow_stats, shadow_version
        )

        # Build result
        result = {
            "active": {
                "version": active_version,
                **active_stats,
            },
            "shadow": {
                "version": shadow_version,
                **shadow_stats,
            },
            "comparison": comparison,
            "filters": {
                "session_id": session_id,
                "info_need_type": info_need_type,
                "time_range": [time_range[0].isoformat(), time_range[1].isoformat()]
                if time_range
                else None,
            },
        }

        logger.info(
            f"Comparison complete: {comparison['sample_count']} samples, "
            f"divergence_rate={comparison['divergence_rate']:.2f}"
        )

        return result

    def _fetch_decision_sets(
        self,
        session_id: Optional[str],
        active_version: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch decision sets from audit logs.

        Args:
            session_id: Optional session filter
            active_version: Active version filter
            limit: Maximum results

        Returns:
            List of decision set audit events
        """
        decision_sets = get_decision_sets(
            session_id=session_id,
            active_version=active_version,
            has_shadow=True,  # Only sets with shadow decisions
            limit=limit,
        )
        return decision_sets

    def _aggregate_decisions(
        self, decision_sets: List[Dict[str, Any]], role: str
    ) -> Dict[str, Any]:
        """
        Aggregate decision statistics for a specific role (active/shadow).

        Args:
            decision_sets: List of decision set audit events
            role: "active" or "shadow"

        Returns:
            Aggregated statistics dictionary
        """
        decision_actions = []
        info_need_types = []
        confidence_levels = []
        scores = []

        for ds in decision_sets:
            payload = ds["payload"]

            if role == "active":
                decision = payload.get("active_decision", {})
            else:
                # For shadow, we aggregate all shadow decisions
                shadow_decisions = payload.get("shadow_decisions", [])
                if not shadow_decisions:
                    continue
                decision = shadow_decisions[0]  # Take first shadow for now

            # Extract decision fields
            decision_action = decision.get("decision_action")
            info_need_type = decision.get("info_need_type")
            confidence_level = decision.get("confidence_level")

            if decision_action:
                decision_actions.append(decision_action)
            if info_need_type:
                info_need_types.append(info_need_type)
            if confidence_level:
                confidence_levels.append(confidence_level)

            # Try to get score from shadow evaluation (if available)
            decision_set_id = payload.get("decision_set_id")
            if decision_set_id:
                evaluations = get_shadow_evaluations_for_decision_set(decision_set_id)
                if evaluations:
                    eval_payload = evaluations[0]["payload"]
                    if role == "active":
                        score = eval_payload.get("active_score")
                        if score is not None:
                            scores.append(score)

        # Build distribution statistics
        decision_distribution = self._count_distribution(decision_actions)
        info_need_distribution = self._count_distribution(info_need_types)
        confidence_distribution = self._count_distribution(confidence_levels)

        # Calculate average score if available
        avg_score = None
        if scores:
            avg_score = sum(scores) / len(scores)

        return {
            "sample_count": len(decision_actions),
            "avg_score": avg_score,
            "decision_distribution": decision_distribution,
            "info_need_distribution": info_need_distribution,
            "confidence_distribution": confidence_distribution,
        }

    def _aggregate_shadow_decisions(
        self, decision_sets: List[Dict[str, Any]], shadow_version: str
    ) -> Dict[str, Any]:
        """
        Aggregate shadow decision statistics for a specific shadow version.

        Args:
            decision_sets: List of decision set audit events
            shadow_version: Shadow version ID to aggregate

        Returns:
            Aggregated statistics dictionary
        """
        decision_actions = []
        info_need_types = []
        confidence_levels = []
        scores = []

        for ds in decision_sets:
            payload = ds["payload"]
            shadow_decisions = payload.get("shadow_decisions", [])
            shadow_versions = payload.get("shadow_versions", [])

            # Find the shadow decision matching our target version
            shadow_decision = None
            for i, version in enumerate(shadow_versions):
                if version == shadow_version and i < len(shadow_decisions):
                    shadow_decision = shadow_decisions[i]
                    break

            if not shadow_decision:
                continue

            # Extract decision fields
            decision_action = shadow_decision.get("decision_action")
            info_need_type = shadow_decision.get("info_need_type")
            confidence_level = shadow_decision.get("confidence_level")

            if decision_action:
                decision_actions.append(decision_action)
            if info_need_type:
                info_need_types.append(info_need_type)
            if confidence_level:
                confidence_levels.append(confidence_level)

            # Try to get score from shadow evaluation (if available)
            decision_set_id = payload.get("decision_set_id")
            if decision_set_id:
                evaluations = get_shadow_evaluations_for_decision_set(decision_set_id)
                if evaluations:
                    eval_payload = evaluations[0]["payload"]
                    shadow_scores = eval_payload.get("shadow_scores", {})
                    score = shadow_scores.get(shadow_version)
                    if score is not None:
                        scores.append(score)

        # Build distribution statistics
        decision_distribution = self._count_distribution(decision_actions)
        info_need_distribution = self._count_distribution(info_need_types)
        confidence_distribution = self._count_distribution(confidence_levels)

        # Calculate average score if available
        avg_score = None
        if scores:
            avg_score = sum(scores) / len(scores)

        return {
            "sample_count": len(decision_actions),
            "avg_score": avg_score,
            "decision_distribution": decision_distribution,
            "info_need_distribution": info_need_distribution,
            "confidence_distribution": confidence_distribution,
        }

    def _count_distribution(self, items: List[str]) -> Dict[str, int]:
        """
        Count distribution of items.

        Args:
            items: List of items to count

        Returns:
            Dictionary mapping item to count
        """
        distribution = defaultdict(int)
        for item in items:
            distribution[item] += 1
        return dict(distribution)

    def _calculate_comparison(
        self,
        decision_sets: List[Dict[str, Any]],
        active_stats: Dict[str, Any],
        shadow_stats: Dict[str, Any],
        shadow_version: str,
    ) -> Dict[str, Any]:
        """
        Calculate comparison metrics between active and shadow.

        Args:
            decision_sets: List of decision set audit events
            active_stats: Active decision statistics
            shadow_stats: Shadow decision statistics
            shadow_version: Shadow version ID

        Returns:
            Comparison metrics dictionary
        """
        sample_count = len(decision_sets)
        decision_divergence_count = 0
        decision_agreement_count = 0
        better_count = 0
        worse_count = 0
        neutral_count = 0

        # Compare decisions pairwise
        for ds in decision_sets:
            payload = ds["payload"]
            active_decision = payload.get("active_decision", {})
            shadow_decisions = payload.get("shadow_decisions", [])
            shadow_versions = payload.get("shadow_versions", [])

            # Find matching shadow decision
            shadow_decision = None
            for i, version in enumerate(shadow_versions):
                if version == shadow_version and i < len(shadow_decisions):
                    shadow_decision = shadow_decisions[i]
                    break

            if not shadow_decision:
                continue

            # Compare decision actions
            active_action = active_decision.get("decision_action")
            shadow_action = shadow_decision.get("decision_action")

            if active_action and shadow_action:
                if active_action == shadow_action:
                    decision_agreement_count += 1
                else:
                    decision_divergence_count += 1

            # Compare scores if available (for better/worse/neutral counts)
            decision_set_id = payload.get("decision_set_id")
            if decision_set_id:
                evaluations = get_shadow_evaluations_for_decision_set(decision_set_id)
                if evaluations:
                    eval_payload = evaluations[0]["payload"]
                    active_score = eval_payload.get("active_score")
                    shadow_scores = eval_payload.get("shadow_scores", {})
                    shadow_score = shadow_scores.get(shadow_version)

                    if active_score is not None and shadow_score is not None:
                        score_delta = shadow_score - active_score
                        if score_delta > 0.05:  # Threshold for "better"
                            better_count += 1
                        elif score_delta < -0.05:  # Threshold for "worse"
                            worse_count += 1
                        else:
                            neutral_count += 1

        # Calculate divergence rate
        total_compared = decision_divergence_count + decision_agreement_count
        divergence_rate = (
            decision_divergence_count / total_compared if total_compared > 0 else 0.0
        )

        # Calculate improvement rate (if scores available)
        improvement_rate = None
        if active_stats["avg_score"] is not None and shadow_stats["avg_score"] is not None:
            active_avg = active_stats["avg_score"]
            shadow_avg = shadow_stats["avg_score"]
            if active_avg != 0:
                improvement_rate = (shadow_avg - active_avg) / abs(active_avg)
            else:
                improvement_rate = shadow_avg  # If active is 0, use shadow as improvement

        # Calculate decision action comparison
        decision_action_comparison = self._compare_distributions(
            active_stats["decision_distribution"],
            shadow_stats["decision_distribution"],
        )

        return {
            "improvement_rate": improvement_rate,
            "sample_count": sample_count,
            "decision_divergence_count": decision_divergence_count,
            "decision_agreement_count": decision_agreement_count,
            "divergence_rate": divergence_rate,
            "better_count": better_count,
            "worse_count": worse_count,
            "neutral_count": neutral_count,
            "decision_action_comparison": decision_action_comparison,
        }

    def _compare_distributions(
        self, active_dist: Dict[str, int], shadow_dist: Dict[str, int]
    ) -> Dict[str, Dict[str, int]]:
        """
        Compare two distributions.

        Args:
            active_dist: Active decision distribution
            shadow_dist: Shadow decision distribution

        Returns:
            Comparison dictionary mapping action to counts
        """
        all_actions = set(active_dist.keys()) | set(shadow_dist.keys())
        comparison = {}

        for action in all_actions:
            active_count = active_dist.get(action, 0)
            shadow_count = shadow_dist.get(action, 0)
            delta = shadow_count - active_count

            comparison[action] = {
                "active_count": active_count,
                "shadow_count": shadow_count,
                "delta": delta,
            }

        return comparison

    def _empty_comparison_result(
        self,
        active_version: str,
        shadow_version: str,
        session_id: Optional[str],
        info_need_type: Optional[str],
        time_range: Optional[Tuple[datetime, datetime]],
    ) -> Dict[str, Any]:
        """
        Generate empty comparison result when no data is found.

        Args:
            active_version: Active version ID
            shadow_version: Shadow version ID
            session_id: Session filter
            info_need_type: Info need type filter
            time_range: Time range filter

        Returns:
            Empty comparison result dictionary
        """
        return {
            "active": {
                "version": active_version,
                "sample_count": 0,
                "avg_score": None,
                "decision_distribution": {},
                "info_need_distribution": {},
                "confidence_distribution": {},
            },
            "shadow": {
                "version": shadow_version,
                "sample_count": 0,
                "avg_score": None,
                "decision_distribution": {},
                "info_need_distribution": {},
                "confidence_distribution": {},
            },
            "comparison": {
                "improvement_rate": None,
                "sample_count": 0,
                "decision_divergence_count": 0,
                "decision_agreement_count": 0,
                "divergence_rate": 0.0,
                "better_count": 0,
                "worse_count": 0,
                "neutral_count": 0,
                "decision_action_comparison": {},
            },
            "filters": {
                "session_id": session_id,
                "info_need_type": info_need_type,
                "time_range": [time_range[0].isoformat(), time_range[1].isoformat()]
                if time_range
                else None,
            },
        }

    def compare_by_info_need_type(
        self,
        active_version: str,
        shadow_version: str,
        session_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare versions grouped by info_need_type.

        Args:
            active_version: Active classifier version ID
            shadow_version: Shadow classifier version ID
            session_id: Optional session filter
            time_range: Optional time range filter
            limit: Maximum results per group

        Returns:
            Dictionary mapping info_need_type to comparison result
        """
        # Get all info need types
        decision_sets = self._fetch_decision_sets(session_id, active_version, limit)

        if time_range:
            decision_sets = [
                ds for ds in decision_sets
                if time_range[0] <= datetime.fromtimestamp(ds["created_at"], tz=timezone.utc) <= time_range[1]
            ]

        # Extract unique info need types
        info_need_types = set()
        for ds in decision_sets:
            payload = ds["payload"]
            active_decision = payload.get("active_decision", {})
            info_need_type = active_decision.get("info_need_type")
            if info_need_type:
                info_need_types.add(info_need_type)

        # Generate comparison for each info need type
        results = {}
        for info_need_type in info_need_types:
            comparison = self.compare_versions(
                active_version=active_version,
                shadow_version=shadow_version,
                session_id=session_id,
                info_need_type=info_need_type,
                time_range=time_range,
                limit=limit,
            )
            results[info_need_type] = comparison

        logger.info(
            f"Generated comparisons for {len(results)} info need types"
        )

        return results

    def get_summary_statistics(
        self,
        active_version: str,
        shadow_versions: List[str],
        session_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Get summary statistics comparing one active to multiple shadow versions.

        Args:
            active_version: Active classifier version ID
            shadow_versions: List of shadow version IDs to compare
            session_id: Optional session filter
            time_range: Optional time range filter
            limit: Maximum results

        Returns:
            Summary statistics dictionary
        """
        summaries = []

        for shadow_version in shadow_versions:
            comparison = self.compare_versions(
                active_version=active_version,
                shadow_version=shadow_version,
                session_id=session_id,
                time_range=time_range,
                limit=limit,
            )

            # Extract key metrics
            summary = {
                "shadow_version": shadow_version,
                "sample_count": comparison["comparison"]["sample_count"],
                "divergence_rate": comparison["comparison"]["divergence_rate"],
                "improvement_rate": comparison["comparison"]["improvement_rate"],
                "better_count": comparison["comparison"]["better_count"],
                "worse_count": comparison["comparison"]["worse_count"],
                "neutral_count": comparison["comparison"]["neutral_count"],
            }
            summaries.append(summary)

        # Sort by improvement rate (descending)
        summaries.sort(
            key=lambda x: x["improvement_rate"] if x["improvement_rate"] is not None else -float("inf"),
            reverse=True,
        )

        return {
            "active_version": active_version,
            "shadow_comparisons": summaries,
            "filters": {
                "session_id": session_id,
                "time_range": [time_range[0].isoformat(), time_range[1].isoformat()]
                if time_range
                else None,
            },
        }


# Singleton instance
_comparator: Optional[DecisionComparator] = None


def get_comparator() -> DecisionComparator:
    """
    Get singleton DecisionComparator instance.

    Returns:
        Global DecisionComparator instance
    """
    global _comparator
    if _comparator is None:
        _comparator = DecisionComparator()
    return _comparator
