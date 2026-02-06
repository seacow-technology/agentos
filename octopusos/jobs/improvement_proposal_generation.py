"""
Improvement Proposal Generation Job - Daily analysis of shadow vs active differences

This job runs periodically (recommended: daily) to:
1. Analyze shadow vs active classifier performance differences
2. Identify patterns where shadow outperforms active
3. Calculate risk levels based on sample size and improvement rate
4. Generate ImprovementProposal objects for human review
5. Store proposals in BrainOS for review queue

Recommended schedule: Daily at 2 AM (low traffic time)

Design Philosophy:
- Conservative: Only generate LOW/MEDIUM risk proposals
- Data-driven: Require minimum sample sizes
- Transparent: Provide clear evidence and reasoning
- Actionable: Generate proposals ready for human review
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from agentos.core.brain.improvement_proposal import (
    ChangeType,
    ImprovementProposal,
    ProposalEvidence,
    RecommendationType,
    RiskLevel,
)
from agentos.core.brain.improvement_proposal_store import get_store
from agentos.core.chat.decision_comparator import get_comparator

logger = logging.getLogger(__name__)


# ============================================
# Risk Assessment Configuration
# ============================================

class RiskAssessmentConfig:
    """Configuration for risk assessment thresholds."""

    # LOW risk thresholds
    LOW_RISK_MIN_SAMPLES = 100
    LOW_RISK_MIN_IMPROVEMENT = 0.15  # 15%

    # MEDIUM risk thresholds
    MEDIUM_RISK_MIN_SAMPLES = 50
    MEDIUM_RISK_MIN_IMPROVEMENT = 0.10  # 10%

    # HIGH risk (will be filtered out)
    HIGH_RISK_THRESHOLD_SAMPLES = 50
    HIGH_RISK_THRESHOLD_IMPROVEMENT = 0.10


# ============================================
# Proposal Generator
# ============================================

class ImprovementProposalGenerator:
    """
    Generates improvement proposals based on shadow vs active analysis.

    Responsibilities:
    - Analyze shadow classifier performance
    - Calculate risk levels
    - Generate proposals for human review
    - Filter out high-risk proposals
    """

    def __init__(
        self,
        time_window_days: int = 7,
        active_version: str = "v1",
        shadow_versions: Optional[List[str]] = None,
        dry_run: bool = False,
    ):
        """
        Initialize proposal generator.

        Args:
            time_window_days: Time window for data analysis (days)
            active_version: Active classifier version ID
            shadow_versions: List of shadow version IDs to analyze
            dry_run: If True, no proposals are saved to database
        """
        self.time_window_days = time_window_days
        self.active_version = active_version
        self.shadow_versions = shadow_versions or []
        self.dry_run = dry_run

        # Components
        self.comparator = get_comparator()
        self.store = get_store()

        # Statistics
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "time_window_days": time_window_days,
            "active_version": active_version,
            "shadow_versions_analyzed": 0,
            "proposals_generated": 0,
            "proposals_low_risk": 0,
            "proposals_medium_risk": 0,
            "proposals_high_risk_filtered": 0,
            "error": None,
        }

    async def run(self) -> Dict[str, Any]:
        """
        Run improvement proposal generation job.

        Returns:
            Statistics dictionary
        """
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["status"] = "running"

        logger.info("=" * 60)
        logger.info("Starting Improvement Proposal Generation Job")
        logger.info("=" * 60)
        logger.info(f"Active version: {self.active_version}")
        logger.info(f"Shadow versions: {self.shadow_versions}")
        logger.info(f"Time window: {self.time_window_days} days")
        if self.dry_run:
            logger.info("DRY RUN MODE - No proposals will be saved")
        logger.info("=" * 60)

        try:
            # Calculate time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=self.time_window_days)
            time_range = (start_time, end_time)

            # Step 1: Analyze each shadow version
            logger.info("\nStep 1: Analyzing shadow vs active performance...")
            all_proposals = []

            for shadow_version in self.shadow_versions:
                logger.info(f"\nAnalyzing shadow version: {shadow_version}")
                proposals = await self._analyze_shadow_version(
                    shadow_version=shadow_version,
                    time_range=time_range,
                )
                all_proposals.extend(proposals)
                self.stats["shadow_versions_analyzed"] += 1

            # Step 2: Filter high-risk proposals
            logger.info("\nStep 2: Filtering proposals by risk level...")
            filtered_proposals = self._filter_proposals_by_risk(all_proposals)

            # Step 3: Save proposals to database
            if not self.dry_run:
                logger.info("\nStep 3: Saving proposals to database...")
                await self._save_proposals(filtered_proposals)
            else:
                logger.info("\nStep 3: Skipping database save (dry run mode)")
                self.stats["proposals_generated"] = len(filtered_proposals)

            # Complete
            self.stats["status"] = "completed"
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info("\n" + "=" * 60)
            logger.info("Improvement Proposal Generation Job Complete")
            logger.info("=" * 60)
            logger.info(f"Shadow versions analyzed: {self.stats['shadow_versions_analyzed']}")
            logger.info(f"Proposals generated: {self.stats['proposals_generated']}")
            logger.info(f"  - LOW risk: {self.stats['proposals_low_risk']}")
            logger.info(f"  - MEDIUM risk: {self.stats['proposals_medium_risk']}")
            logger.info(f"  - HIGH risk (filtered): {self.stats['proposals_high_risk_filtered']}")
            logger.info("=" * 60)

            return self.stats

        except Exception as e:
            logger.error(f"Job failed with error: {e}", exc_info=True)
            self.stats["status"] = "failed"
            self.stats["error"] = str(e)
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
            return self.stats

    async def _analyze_shadow_version(
        self,
        shadow_version: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[ImprovementProposal]:
        """
        Analyze a single shadow version and generate proposals.

        Args:
            shadow_version: Shadow version ID
            time_range: Time range for analysis

        Returns:
            List of ImprovementProposal objects
        """
        proposals = []

        # Overall comparison
        overall_comparison = self.comparator.compare_versions(
            active_version=self.active_version,
            shadow_version=shadow_version,
            time_range=time_range,
            limit=10000,
        )

        # Check if overall improvement is significant
        overall_improvement = overall_comparison["comparison"]["improvement_rate"]
        overall_samples = overall_comparison["comparison"]["sample_count"]

        if overall_improvement is not None and overall_improvement > 0:
            logger.info(
                f"  Overall improvement: {overall_improvement:+.1%} "
                f"({overall_samples} samples)"
            )

            # Generate overall promotion proposal
            proposal = self._create_overall_promotion_proposal(
                shadow_version=shadow_version,
                comparison=overall_comparison,
                time_range=time_range,
            )

            if proposal:
                proposals.append(proposal)

        # Grouped comparison by info_need_type
        grouped_comparisons = self.comparator.compare_by_info_need_type(
            active_version=self.active_version,
            shadow_version=shadow_version,
            time_range=time_range,
            limit=10000,
        )

        # Generate proposals for each info_need_type
        for info_need_type, comparison in grouped_comparisons.items():
            improvement = comparison["comparison"]["improvement_rate"]
            samples = comparison["comparison"]["sample_count"]

            if improvement is not None and improvement > 0:
                logger.info(
                    f"  {info_need_type}: {improvement:+.1%} "
                    f"({samples} samples)"
                )

                # Generate scoped proposal for this info_need_type
                proposal = self._create_scoped_promotion_proposal(
                    shadow_version=shadow_version,
                    info_need_type=info_need_type,
                    comparison=comparison,
                    time_range=time_range,
                )

                if proposal:
                    proposals.append(proposal)

        return proposals

    def _create_overall_promotion_proposal(
        self,
        shadow_version: str,
        comparison: Dict[str, Any],
        time_range: Tuple[datetime, datetime],
    ) -> Optional[ImprovementProposal]:
        """
        Create proposal for overall shadow classifier promotion.

        Args:
            shadow_version: Shadow version ID
            comparison: Comparison result from DecisionComparator
            time_range: Time range for evidence

        Returns:
            ImprovementProposal or None if not qualified
        """
        improvement_rate = comparison["comparison"]["improvement_rate"]
        samples = comparison["comparison"]["sample_count"]
        active_score = comparison["active"].get("avg_score")
        shadow_score = comparison["shadow"].get("avg_score")

        # Assess risk
        risk = self._assess_risk(samples, improvement_rate)

        # Create evidence
        evidence = ProposalEvidence(
            samples=samples,
            improvement_rate=improvement_rate,
            shadow_accuracy=shadow_score,
            active_accuracy=active_score,
            risk=risk,
            confidence_score=self._calculate_confidence(samples, improvement_rate),
            time_range_start=time_range[0],
            time_range_end=time_range[1],
        )

        # Determine recommendation
        recommendation = self._determine_recommendation(risk)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            scope="Overall classifier",
            shadow_version=shadow_version,
            evidence=evidence,
            comparison=comparison,
        )

        # Create proposal
        proposal = ImprovementProposal.create_shadow_promotion_proposal(
            scope="Overall",
            affected_version_id=self.active_version,
            shadow_version_id=shadow_version,
            evidence=evidence,
        )

        # Update reasoning (factory method provides default)
        proposal.reasoning = reasoning

        return proposal

    def _create_scoped_promotion_proposal(
        self,
        shadow_version: str,
        info_need_type: str,
        comparison: Dict[str, Any],
        time_range: Tuple[datetime, datetime],
    ) -> Optional[ImprovementProposal]:
        """
        Create proposal for scoped shadow classifier promotion.

        Args:
            shadow_version: Shadow version ID
            info_need_type: Info need type to scope the proposal
            comparison: Comparison result from DecisionComparator
            time_range: Time range for evidence

        Returns:
            ImprovementProposal or None if not qualified
        """
        improvement_rate = comparison["comparison"]["improvement_rate"]
        samples = comparison["comparison"]["sample_count"]
        active_score = comparison["active"].get("avg_score")
        shadow_score = comparison["shadow"].get("avg_score")

        # Assess risk
        risk = self._assess_risk(samples, improvement_rate)

        # Create evidence
        evidence = ProposalEvidence(
            samples=samples,
            improvement_rate=improvement_rate,
            shadow_accuracy=shadow_score,
            active_accuracy=active_score,
            risk=risk,
            confidence_score=self._calculate_confidence(samples, improvement_rate),
            time_range_start=time_range[0],
            time_range_end=time_range[1],
        )

        # Determine recommendation
        recommendation = self._determine_recommendation(risk)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            scope=info_need_type,
            shadow_version=shadow_version,
            evidence=evidence,
            comparison=comparison,
        )

        # Create proposal
        proposal = ImprovementProposal(
            scope=info_need_type,
            change_type=ChangeType.PROMOTE_SHADOW,
            description=f"Promote shadow classifier {shadow_version} for {info_need_type}",
            evidence=evidence,
            recommendation=recommendation,
            reasoning=reasoning,
            affected_version_id=self.active_version,
            shadow_version_id=shadow_version,
        )

        return proposal

    def _assess_risk(self, samples: int, improvement_rate: float) -> RiskLevel:
        """
        Assess risk level based on samples and improvement rate.

        Args:
            samples: Number of samples
            improvement_rate: Improvement rate (e.g., 0.15 for 15%)

        Returns:
            RiskLevel enum
        """
        if samples >= RiskAssessmentConfig.LOW_RISK_MIN_SAMPLES and \
           improvement_rate >= RiskAssessmentConfig.LOW_RISK_MIN_IMPROVEMENT:
            return RiskLevel.LOW

        if samples >= RiskAssessmentConfig.MEDIUM_RISK_MIN_SAMPLES and \
           improvement_rate >= RiskAssessmentConfig.MEDIUM_RISK_MIN_IMPROVEMENT:
            return RiskLevel.MEDIUM

        return RiskLevel.HIGH

    def _calculate_confidence(self, samples: int, improvement_rate: float) -> float:
        """
        Calculate confidence score based on samples and improvement rate.

        Args:
            samples: Number of samples
            improvement_rate: Improvement rate

        Returns:
            Confidence score (0.0-1.0)
        """
        # Base confidence on sample size
        sample_confidence = min(1.0, samples / 200.0)

        # Boost confidence for higher improvement rates
        improvement_confidence = min(1.0, improvement_rate / 0.3)

        # Weighted average
        confidence = 0.6 * sample_confidence + 0.4 * improvement_confidence

        return round(confidence, 2)

    def _determine_recommendation(self, risk: RiskLevel) -> RecommendationType:
        """
        Determine recommendation based on risk level.

        Args:
            risk: Risk level

        Returns:
            RecommendationType enum
        """
        if risk == RiskLevel.LOW:
            return RecommendationType.PROMOTE
        elif risk == RiskLevel.MEDIUM:
            return RecommendationType.TEST
        else:
            return RecommendationType.DEFER

    def _generate_reasoning(
        self,
        scope: str,
        shadow_version: str,
        evidence: ProposalEvidence,
        comparison: Dict[str, Any],
    ) -> str:
        """
        Generate human-readable reasoning for the proposal.

        Args:
            scope: Proposal scope
            shadow_version: Shadow version ID
            evidence: Evidence supporting the proposal
            comparison: Comparison result

        Returns:
            Reasoning string
        """
        lines = []

        # Summary
        lines.append(
            f"Shadow classifier {shadow_version} shows {evidence.improvement_rate:+.1%} "
            f"improvement over active classifier for scope: {scope}"
        )

        # Sample size
        lines.append(
            f"Based on {evidence.samples} decision samples over "
            f"{self.time_window_days} days."
        )

        # Score details
        if evidence.active_accuracy is not None and evidence.shadow_accuracy is not None:
            lines.append(
                f"Reality Alignment Score: active={evidence.active_accuracy:.2f}, "
                f"shadow={evidence.shadow_accuracy:.2f}"
            )

        # Decision divergence
        divergence_rate = comparison["comparison"].get("divergence_rate", 0)
        if divergence_rate > 0:
            lines.append(
                f"Decision divergence rate: {divergence_rate:.1%} "
                f"({comparison['comparison']['decision_divergence_count']} cases)"
            )

        # Performance breakdown
        better_count = comparison["comparison"].get("better_count", 0)
        worse_count = comparison["comparison"].get("worse_count", 0)
        if better_count > 0 or worse_count > 0:
            lines.append(
                f"Shadow performed better in {better_count} cases, "
                f"worse in {worse_count} cases"
            )

        # Risk assessment
        lines.append(f"Risk level: {evidence.risk.value}")
        lines.append(f"Confidence: {evidence.confidence_score:.0%}")

        return " ".join(lines)

    def _filter_proposals_by_risk(
        self, proposals: List[ImprovementProposal]
    ) -> List[ImprovementProposal]:
        """
        Filter proposals to only include LOW and MEDIUM risk.

        Args:
            proposals: List of all proposals

        Returns:
            Filtered list of proposals
        """
        filtered = []

        for proposal in proposals:
            risk = proposal.evidence.risk

            if risk == RiskLevel.LOW:
                filtered.append(proposal)
                self.stats["proposals_low_risk"] += 1
            elif risk == RiskLevel.MEDIUM:
                filtered.append(proposal)
                self.stats["proposals_medium_risk"] += 1
            else:
                # Filter out HIGH risk
                self.stats["proposals_high_risk_filtered"] += 1
                logger.info(
                    f"  Filtered HIGH risk proposal: {proposal.scope} "
                    f"({proposal.evidence.samples} samples, "
                    f"{proposal.evidence.improvement_rate:+.1%} improvement)"
                )

        return filtered

    async def _save_proposals(self, proposals: List[ImprovementProposal]) -> None:
        """
        Save proposals to database.

        Args:
            proposals: List of proposals to save
        """
        for proposal in proposals:
            try:
                await self.store.save_proposal(proposal)
                self.stats["proposals_generated"] += 1
                logger.info(f"  Saved proposal: {proposal.proposal_id}")
            except Exception as e:
                logger.error(f"  Failed to save proposal {proposal.proposal_id}: {e}")


# ============================================
# CLI Entry Point
# ============================================

async def run_improvement_proposal_generation(
    time_window_days: int = 7,
    active_version: str = "v1",
    shadow_versions: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run improvement proposal generation job.

    Args:
        time_window_days: Time window for data analysis (days)
        active_version: Active classifier version ID
        shadow_versions: List of shadow version IDs to analyze
        dry_run: If True, no proposals are saved to database

    Returns:
        Statistics dictionary
    """
    generator = ImprovementProposalGenerator(
        time_window_days=time_window_days,
        active_version=active_version,
        shadow_versions=shadow_versions or [],
        dry_run=dry_run,
    )

    return await generator.run()


# ============================================
# Main Entry Point (for standalone execution)
# ============================================

async def main():
    """Main entry point for standalone execution."""
    import sys

    # Simple CLI argument parsing
    dry_run = "--dry-run" in sys.argv
    time_window_days = 7
    active_version = "v1"

    # Extract shadow versions from CLI
    shadow_versions = []
    for arg in sys.argv[1:]:
        if arg.startswith("--shadow="):
            shadow_versions.append(arg.split("=")[1])
        elif arg.startswith("--time-window="):
            time_window_days = int(arg.split("=")[1])
        elif arg.startswith("--active="):
            active_version = arg.split("=")[1]

    print("\n" + "=" * 60)
    print("Improvement Proposal Generation Job")
    print("=" * 60)
    print(f"Active version: {active_version}")
    print(f"Shadow versions: {shadow_versions}")
    print(f"Time window: {time_window_days} days")
    print(f"Dry run: {dry_run}")
    print("=" * 60 + "\n")

    stats = await run_improvement_proposal_generation(
        time_window_days=time_window_days,
        active_version=active_version,
        shadow_versions=shadow_versions,
        dry_run=dry_run,
    )

    # Print results
    print("\n" + "=" * 60)
    print("Job Results")
    print("=" * 60)
    print(f"Status: {stats['status']}")
    print(f"Shadow versions analyzed: {stats['shadow_versions_analyzed']}")
    print(f"Proposals generated: {stats['proposals_generated']}")
    print(f"  - LOW risk: {stats['proposals_low_risk']}")
    print(f"  - MEDIUM risk: {stats['proposals_medium_risk']}")
    print(f"  - HIGH risk (filtered): {stats['proposals_high_risk_filtered']}")

    if stats.get("error"):
        print(f"Error: {stats['error']}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
