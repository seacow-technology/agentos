#!/usr/bin/env python3
"""
Classifier Version Management Demo

Demonstrates the complete workflow for managing classifier versions:
1. View current version
2. Create and approve an ImprovementProposal
3. Promote version from proposal
4. List all versions
5. Rollback to previous version
6. View rollback history

Usage:
    python examples/classifier_version_demo.py
"""

import asyncio
from datetime import datetime, timezone

from agentos.core.brain.classifier_version_manager import (
    get_version_manager,
    reset_version_manager,
)
from agentos.core.brain.improvement_proposal import (
    ImprovementProposal,
    ProposalEvidence,
    ChangeType,
    RecommendationType,
    RiskLevel,
)
from agentos.core.brain.improvement_proposal_store import get_store


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_version(version):
    """Pretty print version information."""
    status = "🟢 ACTIVE" if version.is_active else "⚪ Inactive"
    print(f"  Version: {version.version_id} ({version.version_number})")
    print(f"  Status: {status}")
    print(f"  Change Log: {version.change_log}")
    print(f"  Created By: {version.created_by}")
    print(f"  Created At: {version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if version.source_proposal_id:
        print(f"  Source Proposal: {version.source_proposal_id}")
    print()


async def demo():
    """Run the demonstration."""
    print_section("Classifier Version Management Demo")

    # Initialize manager
    manager = get_version_manager()
    store = get_store()

    # Step 1: View current version
    print_section("Step 1: Current Version")
    current = manager.get_active_version()
    if current:
        print_version(current)
    else:
        print("  No active version found!")

    # Step 2: Create and approve an ImprovementProposal
    print_section("Step 2: Create ImprovementProposal")

    proposal = ImprovementProposal(
        proposal_id="BP-DEMO01",
        scope="EXTERNAL_FACT / recency",
        change_type=ChangeType.EXPAND_KEYWORD,
        description="Add time-sensitive keywords for better external fact detection",
        evidence=ProposalEvidence(
            samples=312,
            improvement_rate=0.18,
            shadow_accuracy=0.92,
            active_accuracy=0.78,
            error_reduction=-0.25,
            risk=RiskLevel.LOW,
            confidence_score=0.95,
        ),
        recommendation=RecommendationType.PROMOTE,
        reasoning=(
            "Shadow classifier v2-shadow-keywords shows 18% improvement "
            "over 312 decision samples. Risk is LOW due to stable baseline "
            "and high confidence score (0.95)."
        ),
        affected_version_id=current.version_id if current else "v1",
        shadow_version_id="v2-shadow-keywords",
    )

    print(f"  Proposal ID: {proposal.proposal_id}")
    print(f"  Scope: {proposal.scope}")
    print(f"  Change Type: {proposal.change_type.value}")
    print(f"  Description: {proposal.description}")
    print(f"  Evidence:")
    print(f"    - Samples: {proposal.evidence.samples}")
    print(f"    - Improvement Rate: {proposal.evidence.improvement_rate:+.1%}")
    print(f"    - Risk Level: {proposal.evidence.risk.value}")
    print(f"    - Confidence: {proposal.evidence.confidence_score:.1%}")
    print(f"  Recommendation: {proposal.recommendation.value}")
    print()

    # Save proposal
    await store.save_proposal(proposal)
    print("  ✓ Proposal saved")

    # Approve proposal
    await store.accept_proposal(
        proposal_id=proposal.proposal_id,
        reviewed_by="demo_admin",
        notes="Approved for demo. Improvement rate is significant and risk is low.",
    )
    print("  ✓ Proposal approved by demo_admin")
    print()

    # Step 3: Promote version
    print_section("Step 3: Promote Classifier Version")

    new_version = manager.promote_version(
        proposal_id=proposal.proposal_id,
        change_log=proposal.description,
        created_by="demo_admin",
        is_major=False,  # Minor version bump (v1 -> v1.1)
        metadata={
            "improvement_rate": proposal.evidence.improvement_rate,
            "risk_level": proposal.evidence.risk.value,
            "samples": proposal.evidence.samples,
        }
    )

    print(f"  ✓ Successfully promoted to version {new_version.version_id}")
    print_version(new_version)

    # Mark proposal as implemented
    await store.mark_implemented(proposal.proposal_id)
    print("  ✓ Proposal marked as implemented")
    print()

    # Step 4: List all versions
    print_section("Step 4: Version History")

    versions = manager.list_versions()
    print(f"  Total versions: {len(versions)}")
    print()

    for version in versions:
        print_version(version)

    # Step 5: Create another proposal and promote (Major version)
    print_section("Step 5: Major Version Upgrade")

    proposal2 = ImprovementProposal(
        proposal_id="BP-DEMO02",
        scope="All classifier types",
        change_type=ChangeType.PROMOTE_SHADOW,
        description="Major classifier overhaul with improved rule weights and thresholds",
        evidence=ProposalEvidence(
            samples=500,
            improvement_rate=0.25,
            shadow_accuracy=0.95,
            active_accuracy=0.78,
            error_reduction=-0.30,
            risk=RiskLevel.MEDIUM,
            confidence_score=0.92,
        ),
        recommendation=RecommendationType.PROMOTE,
        reasoning=(
            "Shadow classifier v2-complete shows 25% improvement "
            "across all categories. Risk is MEDIUM but improvement is substantial."
        ),
        affected_version_id=new_version.version_id,
        shadow_version_id="v2-complete",
    )

    await store.save_proposal(proposal2)
    await store.accept_proposal(
        proposal_id=proposal2.proposal_id,
        reviewed_by="demo_admin",
        notes="Major improvement, proceed with promotion.",
    )

    v2 = manager.promote_version(
        proposal_id=proposal2.proposal_id,
        change_log=proposal2.description,
        created_by="demo_admin",
        is_major=True,  # Major version bump (v1.1 -> v2)
    )

    print(f"  ✓ Successfully promoted to version {v2.version_id}")
    print_version(v2)

    await store.mark_implemented(proposal2.proposal_id)

    # Step 6: Simulate performance issue and rollback
    print_section("Step 6: Performance Issue - Rollback")

    print("  ⚠️  Simulated scenario: v2 shows performance regression in production")
    print("  📊 Latency increased by 200%, accuracy dropped to 0.70")
    print()
    print("  Decision: Rollback to v1.1")
    print()

    restored = manager.rollback_version(
        to_version_id=new_version.version_id,
        reason="v2 shows performance regression: latency +200%, accuracy drop to 0.70",
        performed_by="demo_admin",
    )

    print(f"  ✓ Successfully rolled back to version {restored.version_id}")
    print_version(restored)

    # Step 7: View rollback history
    print_section("Step 7: Rollback History")

    history = manager.get_rollback_history()
    print(f"  Total rollbacks: {len(history)}")
    print()

    for record in history:
        print(f"  Rollback: {record.from_version_id} → {record.to_version_id}")
        print(f"  Reason: {record.reason}")
        print(f"  Performed By: {record.performed_by}")
        print(f"  Performed At: {record.performed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print()

    # Final summary
    print_section("Summary")

    active = manager.get_active_version()
    all_versions = manager.list_versions()

    print(f"  ✓ Current Active Version: {active.version_id}")
    print(f"  ✓ Total Versions Created: {len(all_versions)}")
    print(f"  ✓ Total Rollbacks: {len(history)}")
    print()
    print("  Demo completed successfully!")
    print()


if __name__ == "__main__":
    print("\n🚀 Starting Classifier Version Management Demo...")
    print("    This demonstrates the complete workflow for managing classifier versions.\n")

    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("  For production usage, use the CLI commands:")
    print("    - agentos version list")
    print("    - agentos version promote --proposal BP-XXX")
    print("    - agentos version rollback --to v1")
    print("    - agentos version show v2")
    print("    - agentos version history")
    print("="*60 + "\n")
