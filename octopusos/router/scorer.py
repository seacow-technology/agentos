"""
Route Scorer - Score and rank provider instances for routing

Implements the scoring formula from router.md MVP specification:
- READY state is mandatory
- Capability match scoring
- Context window requirements
- Latency scoring
- Local preference

PR-1: Router Core
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from agentos.router.models import InstanceProfile, TaskRequirements

logger = logging.getLogger(__name__)


@dataclass
class RouteScore:
    """
    Routing score with breakdown
    """
    instance_id: str
    total_score: float
    reasons: List[str] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "instance_id": self.instance_id,
            "total_score": self.total_score,
            "reasons": self.reasons,
            "breakdown": self.breakdown,
        }


class RouteScorer:
    """
    Score provider instances for task routing

    MVP Scoring Formula:
    - READY state: mandatory (else score=0)
    - Tags match: +0.2 per match
    - Context window: +0.1 if ctx >= min_ctx
    - Latency: +0.0~0.1 (normalized, lower is better)
    - Local preference: +0.05 for local, -0.02 for cloud
    """

    def score_all(
        self,
        profiles: List[InstanceProfile],
        requirements: TaskRequirements,
    ) -> List[RouteScore]:
        """
        Score all instance profiles against task requirements

        Args:
            profiles: List of InstanceProfile
            requirements: TaskRequirements

        Returns:
            List of RouteScore objects (sorted by score descending)
        """
        scores = []

        for profile in profiles:
            score = self.score_single(profile, requirements)
            scores.append(score)

        # Sort by total score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        logger.debug(f"Scored {len(scores)} instances")
        return scores

    def score_single(
        self,
        profile: InstanceProfile,
        requirements: TaskRequirements,
    ) -> RouteScore:
        """
        Score a single instance profile

        Args:
            profile: InstanceProfile
            requirements: TaskRequirements

        Returns:
            RouteScore
        """
        reasons = []
        breakdown = {}
        total_score = 0.0

        # Hard requirement: READY state
        if profile.state != "READY":
            return RouteScore(
                instance_id=profile.instance_id,
                total_score=0.0,
                reasons=[f"NOT_READY (state={profile.state})"],
                breakdown={"state": 0.0},
            )

        reasons.append("READY")
        breakdown["state"] = 1.0

        # Capability tags matching
        tags_score, tags_reasons = self._score_tags(profile.tags, requirements.needs)
        total_score += tags_score
        breakdown["tags"] = tags_score
        reasons.extend(tags_reasons)

        # Context window requirement
        ctx_score, ctx_reason = self._score_context_window(profile.ctx, requirements.min_ctx)
        total_score += ctx_score
        breakdown["ctx"] = ctx_score
        if ctx_reason:
            reasons.append(ctx_reason)

        # Latency scoring
        latency_score, latency_reason = self._score_latency(
            profile.latency_ms, requirements.latency_class
        )
        total_score += latency_score
        breakdown["latency"] = latency_score
        if latency_reason:
            reasons.append(latency_reason)

        # Preference scoring
        pref_score, pref_reason = self._score_preference(
            profile.cost_category, requirements.prefer
        )
        total_score += pref_score
        breakdown["preference"] = pref_score
        if pref_reason:
            reasons.append(pref_reason)

        return RouteScore(
            instance_id=profile.instance_id,
            total_score=total_score,
            reasons=reasons,
            breakdown=breakdown,
        )

    def _score_tags(self, profile_tags: List[str], required_needs: List[str]) -> Tuple[float, List[str]]:
        """
        Score capability tags match

        Args:
            profile_tags: Instance capability tags
            required_needs: Required capabilities

        Returns:
            (score, reasons)
        """
        score = 0.0
        reasons = []

        # Match each required capability
        matched = []
        for need in required_needs:
            if need in profile_tags:
                score += 0.2
                matched.append(need)

        if matched:
            reasons.append(f"tags_match={','.join(matched)}")
        else:
            # No specific match, but allow general tasks
            if "general" in required_needs:
                reasons.append("general_task")

        return score, reasons

    def _score_context_window(self, profile_ctx: int | None, min_ctx: int) -> Tuple[float, str]:
        """
        Score context window requirement

        Args:
            profile_ctx: Instance context window size (None if unknown)
            min_ctx: Minimum required context

        Returns:
            (score, reason)
        """
        if profile_ctx is None:
            # Unknown context, give small penalty
            return 0.02, "ctx_unknown"

        if profile_ctx >= min_ctx:
            return 0.1, f"ctx>={min_ctx}"
        else:
            return 0.0, f"ctx<{min_ctx}"

    def _score_latency(self, latency_ms: float | None, latency_class: str) -> Tuple[float, str]:
        """
        Score latency performance

        Args:
            latency_ms: Last probe latency
            latency_class: Required latency class (fast/normal/batch)

        Returns:
            (score, reason)
        """
        if latency_ms is None:
            return 0.0, "latency_unknown"

        # Normalize latency to 0-0.1 score
        # Best: < 50ms = 0.1
        # Good: < 200ms = 0.05
        # OK: < 500ms = 0.02
        # Slow: >= 500ms = 0.0

        if latency_ms < 50:
            score = 0.1
            reason = "latency_best"
        elif latency_ms < 200:
            score = 0.05
            reason = "latency_good"
        elif latency_ms < 500:
            score = 0.02
            reason = "latency_ok"
        else:
            score = 0.0
            reason = "latency_slow"

        # Adjust for latency class requirement
        if latency_class == "fast" and latency_ms > 200:
            score *= 0.5  # Penalty for slow instance on fast task

        return score, reason

    def _score_preference(self, cost_category: str, preferences: List[str]) -> Tuple[float, str]:
        """
        Score preference match

        Args:
            cost_category: Instance cost category (local/cloud)
            preferences: Preferred categories

        Returns:
            (score, reason)
        """
        # Local preference
        if "local" in preferences and cost_category == "local":
            return 0.05, "local_preferred"

        # Cloud preference
        if "cloud" in preferences and cost_category == "cloud":
            return 0.05, "cloud_preferred"

        # Default: slight penalty for cloud (assuming local is default preference)
        if cost_category == "cloud":
            return -0.02, "cloud_fallback"

        return 0.0, ""

    def select_top_n(self, scores: List[RouteScore], n: int = 3) -> List[RouteScore]:
        """
        Select top N scored instances

        Args:
            scores: List of RouteScore (should be sorted)
            n: Number to select

        Returns:
            Top N RouteScore objects
        """
        # Filter out zero scores
        valid_scores = [s for s in scores if s.total_score > 0.0]
        return valid_scores[:n]
