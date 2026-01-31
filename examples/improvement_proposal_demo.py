"""
ImprovementProposal Demo

Demonstrates how to use the ImprovementProposal data model for BrainOS v3.
This shows the complete workflow from proposal creation to implementation.
"""

import asyncio
from datetime import datetime, timezone, timedelta

from agentos.core.brain.improvement_proposal import (
    ImprovementProposal,
    ProposalEvidence,
    ProposalStatus,
    ChangeType,
    RiskLevel,
    RecommendationType,
)
from agentos.core.brain.improvement_proposal_store import get_store


async def demo_keyword_expansion():
    """Demo: Create and manage a keyword expansion proposal."""
    print("\n" + "=" * 60)
    print("Demo 1: Keyword Expansion Proposal")
    print("=" * 60)

    # Create evidence from shadow classifier analysis
    evidence = ProposalEvidence(
        samples=500,
        improvement_rate=0.18,  # +18% improvement
        shadow_accuracy=0.92,
        active_accuracy=0.78,
        error_reduction=-0.25,  # 25% fewer errors
        risk=RiskLevel.LOW,
        confidence_score=0.95,
        time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_range_end=datetime.now(timezone.utc),
    )

    # Create proposal using factory method
    proposal = ImprovementProposal.create_keyword_expansion_proposal(
        scope="EXTERNAL_FACT / recency",
        affected_version_id="v1-active",
        keywords=["latest", "current", "now", "recent"],
        evidence=evidence,
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")
    print(f"   Scope: {proposal.scope}")
    print(f"   Change Type: {proposal.change_type.value}")
    print(f"   Status: {proposal.status.value}")
    print(f"   Improvement Rate: {proposal.evidence.improvement_rate:+.1%}")
    print(f"   Risk Level: {proposal.evidence.risk.value}")
    print(f"   Recommendation: {proposal.recommendation.value}")

    # Serialize to dict
    proposal_dict = proposal.to_dict()
    print(f"\n📊 Serialized to dict with {len(proposal_dict)} fields")

    # Demonstrate state transitions
    print("\n📝 State Transitions:")
    print(f"   Initial state: {proposal.status.value}")

    # Accept the proposal
    proposal.accept(
        reviewed_by="engineer@example.com",
        notes="Shadow classifier shows clear improvement. Approved for production.",
    )
    print(f"   After accept(): {proposal.status.value}")
    print(f"   Reviewed by: {proposal.reviewed_by}")
    print(f"   Review notes: {proposal.review_notes}")

    # Mark as implemented
    proposal.mark_implemented()
    print(f"   After mark_implemented(): {proposal.status.value}")
    print(f"   Implemented at: {proposal.implemented_at}")

    return proposal


async def demo_threshold_adjustment():
    """Demo: Create a threshold adjustment proposal."""
    print("\n" + "=" * 60)
    print("Demo 2: Threshold Adjustment Proposal")
    print("=" * 60)

    # Create evidence with moderate risk
    evidence = ProposalEvidence(
        samples=300,
        improvement_rate=0.12,  # +12% improvement
        shadow_accuracy=0.88,
        active_accuracy=0.79,
        error_reduction=-0.15,  # 15% fewer errors
        risk=RiskLevel.MEDIUM,
        confidence_score=0.85,
    )

    # Create proposal
    proposal = ImprovementProposal.create_threshold_adjustment_proposal(
        scope="EXTERNAL_FACT / confidence",
        affected_version_id="v1-active",
        old_threshold=0.7,
        new_threshold=0.65,
        evidence=evidence,
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")
    print(f"   Description: {proposal.description}")
    print(f"   Recommendation: {proposal.recommendation.value}")
    print(f"   (Medium risk → recommended for staging test first)")

    return proposal


async def demo_shadow_promotion():
    """Demo: Create a shadow classifier promotion proposal."""
    print("\n" + "=" * 60)
    print("Demo 3: Shadow Classifier Promotion")
    print("=" * 60)

    # Create evidence for full shadow promotion
    evidence = ProposalEvidence(
        samples=1000,
        improvement_rate=0.22,  # +22% improvement
        shadow_accuracy=0.93,
        active_accuracy=0.76,
        error_reduction=-0.30,  # 30% fewer errors
        risk=RiskLevel.LOW,
        confidence_score=0.98,
    )

    # Create proposal
    proposal = ImprovementProposal.create_shadow_promotion_proposal(
        scope="EXTERNAL_FACT",
        affected_version_id="v1-active",
        shadow_version_id="v2-shadow-expand-keywords",
        evidence=evidence,
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")
    print(f"   Shadow Version: {proposal.shadow_version_id}")
    print(f"   Samples: {proposal.evidence.samples}")
    print(f"   Shadow Accuracy: {proposal.evidence.shadow_accuracy:.1%}")
    print(f"   Active Accuracy: {proposal.evidence.active_accuracy:.1%}")
    print(f"   Improvement: {proposal.evidence.improvement_rate:+.1%}")

    return proposal


async def demo_rejection_workflow():
    """Demo: Reject a proposal workflow."""
    print("\n" + "=" * 60)
    print("Demo 4: Proposal Rejection Workflow")
    print("=" * 60)

    # Create a high-risk proposal
    evidence = ProposalEvidence(
        samples=50,  # Small sample size
        improvement_rate=0.08,  # Marginal improvement
        risk=RiskLevel.HIGH,
        confidence_score=0.65,  # Low confidence
    )

    proposal = ImprovementProposal(
        scope="EXTERNAL_FACT / authority",
        change_type=ChangeType.ADD_SIGNAL,
        description="Add experimental signal based on limited data",
        evidence=evidence,
        recommendation=RecommendationType.DEFER,
        reasoning="Limited sample size, need more data before decision",
        affected_version_id="v1-active",
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")
    print(f"   Samples: {proposal.evidence.samples} (small sample)")
    print(f"   Risk: {proposal.evidence.risk.value}")
    print(f"   Confidence: {proposal.evidence.confidence_score:.1%}")

    # Reject due to insufficient evidence
    proposal.reject(
        reviewed_by="senior-engineer@example.com",
        reason="Insufficient evidence. Sample size too small (n=50). "
               "Recommend collecting at least 500 samples before re-evaluation.",
    )

    print(f"\n❌ Proposal rejected")
    print(f"   Reviewed by: {proposal.reviewed_by}")
    print(f"   Reason: {proposal.review_notes}")
    print(f"   Final status: {proposal.status.value}")

    return proposal


async def demo_deferral_workflow():
    """Demo: Defer a proposal workflow."""
    print("\n" + "=" * 60)
    print("Demo 5: Proposal Deferral Workflow")
    print("=" * 60)

    evidence = ProposalEvidence(
        samples=200,
        improvement_rate=0.10,
        risk=RiskLevel.MEDIUM,
        confidence_score=0.75,
    )

    proposal = ImprovementProposal(
        scope="OPINION / recommendation",
        change_type=ChangeType.REFINE_RULE,
        description="Adjust rule weights for opinion classification",
        evidence=evidence,
        recommendation=RecommendationType.TEST,
        reasoning="Moderate improvement with medium risk",
        affected_version_id="v1-active",
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")

    # Defer for more testing
    proposal.defer(
        reviewed_by="tech-lead@example.com",
        reason="Need to observe performance over longer time period. "
               "Defer decision for 2 weeks to collect more data.",
    )

    print(f"\n⏸️  Proposal deferred")
    print(f"   Reviewed by: {proposal.reviewed_by}")
    print(f"   Reason: {proposal.review_notes}")
    print(f"   Final status: {proposal.status.value}")

    return proposal


async def demo_immutability_protection():
    """Demo: Immutability protection for reviewed proposals."""
    print("\n" + "=" * 60)
    print("Demo 6: Immutability Protection")
    print("=" * 60)

    evidence = ProposalEvidence(
        samples=100,
        improvement_rate=0.15,
        risk=RiskLevel.LOW,
    )

    proposal = ImprovementProposal(
        scope="test",
        change_type=ChangeType.EXPAND_KEYWORD,
        description="Test proposal",
        evidence=evidence,
        recommendation=RecommendationType.PROMOTE,
        reasoning="test",
        affected_version_id="v1",
    )

    print(f"\n✅ Created proposal: {proposal.proposal_id}")
    print(f"   Can be modified: {proposal.can_be_modified()}")

    # Accept the proposal
    proposal.accept(reviewed_by="user@example.com", notes="Approved")
    print(f"\n✅ Proposal accepted")
    print(f"   Can be modified: {proposal.can_be_modified()}")

    # Try to accept again (should fail)
    try:
        proposal.accept(reviewed_by="another-user@example.com")
        print("   ❌ ERROR: Should not be able to accept twice!")
    except ValueError as e:
        print(f"   ✅ Immutability protected: {e}")

    return proposal


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("ImprovementProposal Demo")
    print("=" * 60)
    print("\nThis demo shows how to create and manage improvement proposals")
    print("for BrainOS v3 classifier evolution.")

    # Run all demos
    await demo_keyword_expansion()
    await demo_threshold_adjustment()
    await demo_shadow_promotion()
    await demo_rejection_workflow()
    await demo_deferral_workflow()
    await demo_immutability_protection()

    print("\n" + "=" * 60)
    print("✅ All demos completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
