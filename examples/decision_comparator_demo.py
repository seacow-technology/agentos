"""
Decision Comparator Demo

This demo shows how to use the Decision Comparator to generate
comparison metrics between active and shadow classifier versions.

Usage:
    python examples/decision_comparator_demo.py
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from agentos.core.audit import (
    log_decision_set,
    log_shadow_evaluation,
    log_user_behavior_signal,
)
from agentos.core.chat.decision_comparator import get_comparator


async def setup_demo_data():
    """
    Create demo decision sets and evaluations.

    Simulates a scenario where:
    - Active classifier (v1) uses conservative REQUIRE_COMM strategy
    - Shadow classifier (v2-shadow-a) uses more aggressive DIRECT_ANSWER strategy
    - Shadow classifier (v2-shadow-b) balances between the two
    """
    print("🔧 Setting up demo data...")

    session_id = f"demo-session-{uuid.uuid4()}"

    # Scenario 1: Active is too conservative (should use DIRECT_ANSWER)
    scenarios = [
        {
            "question": "What is Python?",
            "info_type": "LOCAL_KNOWLEDGE",
            "active_action": "REQUIRE_COMM",
            "shadow_a_action": "DIRECT_ANSWER",
            "shadow_b_action": "DIRECT_ANSWER",
            "active_score": 0.3,
            "shadow_a_score": 0.9,
            "shadow_b_score": 0.85,
            "signal": "user_followup_override",
        },
        {
            "question": "How do I use Python decorators?",
            "info_type": "LOCAL_KNOWLEDGE",
            "active_action": "REQUIRE_COMM",
            "shadow_a_action": "DIRECT_ANSWER",
            "shadow_b_action": "DIRECT_ANSWER",
            "active_score": 0.4,
            "shadow_a_score": 0.85,
            "shadow_b_score": 0.8,
            "signal": "smooth_completion",
        },
        {
            "question": "What is the latest Python version?",
            "info_type": "EXTERNAL_FACT_UNCERTAIN",
            "active_action": "REQUIRE_COMM",
            "shadow_a_action": "DIRECT_ANSWER",
            "shadow_b_action": "REQUIRE_COMM",
            "active_score": 0.8,
            "shadow_a_score": 0.3,
            "shadow_b_score": 0.75,
            "signal": "smooth_completion",
        },
        {
            "question": "What is machine learning?",
            "info_type": "LOCAL_KNOWLEDGE",
            "active_action": "DIRECT_ANSWER",
            "shadow_a_action": "DIRECT_ANSWER",
            "shadow_b_action": "DIRECT_ANSWER",
            "active_score": 0.9,
            "shadow_a_score": 0.9,
            "shadow_b_score": 0.85,
            "signal": "smooth_completion",
        },
        {
            "question": "What is the weather today?",
            "info_type": "EXTERNAL_FACT_UNCERTAIN",
            "active_action": "DIRECT_ANSWER",
            "shadow_a_action": "REQUIRE_COMM",
            "shadow_b_action": "REQUIRE_COMM",
            "active_score": 0.2,
            "shadow_a_score": 0.95,
            "shadow_b_score": 0.9,
            "signal": "user_followup_override",
        },
        {
            "question": "Should I use React or Vue?",
            "info_type": "OPINION",
            "active_action": "REQUIRE_COMM",
            "shadow_a_action": "DIRECT_ANSWER",
            "shadow_b_action": "SUGGEST_COMM",
            "active_score": 0.6,
            "shadow_a_score": 0.5,
            "shadow_b_score": 0.85,
            "signal": "smooth_completion",
        },
    ]

    decision_sets = []

    for scenario in scenarios:
        decision_set_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # Log decision set
        await log_decision_set(
            decision_set_id=decision_set_id,
            message_id=message_id,
            session_id=session_id,
            question_text=scenario["question"],
            active_version="v1",
            shadow_versions=["v2-shadow-a", "v2-shadow-b"],
            active_decision={
                "info_need_type": scenario["info_type"],
                "decision_action": scenario["active_action"],
                "confidence_level": "medium",
            },
            shadow_decisions=[
                {
                    "info_need_type": scenario["info_type"],
                    "decision_action": scenario["shadow_a_action"],
                    "confidence_level": "high",
                },
                {
                    "info_need_type": scenario["info_type"],
                    "decision_action": scenario["shadow_b_action"],
                    "confidence_level": "high",
                },
            ],
        )

        # Log evaluation with scores
        await log_shadow_evaluation(
            evaluation_id=str(uuid.uuid4()),
            decision_set_id=decision_set_id,
            message_id=message_id,
            session_id=session_id,
            active_score=scenario["active_score"],
            shadow_scores={
                "v2-shadow-a": scenario["shadow_a_score"],
                "v2-shadow-b": scenario["shadow_b_score"],
            },
            signals_used=[scenario["signal"]],
            evaluation_time_ms=50.0,
        )

        # Log user behavior signal
        await log_user_behavior_signal(
            message_id=message_id,
            session_id=session_id,
            signal_type=scenario["signal"],
            signal_data={},
        )

        decision_sets.append({
            "decision_set_id": decision_set_id,
            "message_id": message_id,
        })

    print(f"✅ Created {len(scenarios)} decision sets")
    return session_id


async def demo_basic_comparison(session_id):
    """Demo basic version comparison."""
    print("\n" + "=" * 60)
    print("1. BASIC COMPARISON: v1 (active) vs v2-shadow-a")
    print("=" * 60)

    comparator = get_comparator()

    result = comparator.compare_versions(
        active_version="v1",
        shadow_version="v2-shadow-a",
        session_id=session_id,
    )

    print(f"\n📊 Sample Count: {result['comparison']['sample_count']}")
    print(f"📈 Divergence Rate: {result['comparison']['divergence_rate']:.1%}")

    if result['comparison']['improvement_rate'] is not None:
        print(f"🚀 Improvement Rate: {result['comparison']['improvement_rate']:.1%}")

    print(f"\n📋 Active Decision Distribution:")
    for action, count in result['active']['decision_distribution'].items():
        print(f"   {action}: {count}")

    print(f"\n📋 Shadow Decision Distribution:")
    for action, count in result['shadow']['decision_distribution'].items():
        print(f"   {action}: {count}")

    print(f"\n⚖️  Decision Action Comparison:")
    for action, comp in result['comparison']['decision_action_comparison'].items():
        delta = comp['delta']
        symbol = "+" if delta > 0 else ""
        print(f"   {action}: "
              f"active={comp['active_count']}, "
              f"shadow={comp['shadow_count']} "
              f"({symbol}{delta})")

    if result['active']['avg_score'] is not None:
        print(f"\n⭐ Active Avg Score: {result['active']['avg_score']:.2f}")
        print(f"⭐ Shadow Avg Score: {result['shadow']['avg_score']:.2f}")
        print(f"\n🎯 Better Count: {result['comparison']['better_count']}")
        print(f"❌ Worse Count: {result['comparison']['worse_count']}")
        print(f"➖ Neutral Count: {result['comparison']['neutral_count']}")


async def demo_multi_shadow_comparison(session_id):
    """Demo comparing multiple shadow versions."""
    print("\n" + "=" * 60)
    print("2. MULTI-SHADOW COMPARISON: Ranking shadow versions")
    print("=" * 60)

    comparator = get_comparator()

    result = comparator.get_summary_statistics(
        active_version="v1",
        shadow_versions=["v2-shadow-a", "v2-shadow-b"],
        session_id=session_id,
    )

    print(f"\n🏆 Shadow Version Ranking (by improvement rate):\n")

    for i, shadow in enumerate(result['shadow_comparisons'], 1):
        print(f"{i}. {shadow['shadow_version']}")
        print(f"   📊 Sample Count: {shadow['sample_count']}")
        print(f"   📈 Divergence Rate: {shadow['divergence_rate']:.1%}")

        if shadow['improvement_rate'] is not None:
            print(f"   🚀 Improvement Rate: {shadow['improvement_rate']:.1%}")
            print(f"   ✅ Better: {shadow['better_count']}, "
                  f"❌ Worse: {shadow['worse_count']}, "
                  f"➖ Neutral: {shadow['neutral_count']}")
        print()


async def demo_grouped_comparison(session_id):
    """Demo comparison grouped by info need type."""
    print("\n" + "=" * 60)
    print("3. GROUPED COMPARISON: By Info Need Type")
    print("=" * 60)

    comparator = get_comparator()

    result = comparator.compare_by_info_need_type(
        active_version="v1",
        shadow_version="v2-shadow-b",
        session_id=session_id,
    )

    print(f"\n📁 Comparisons grouped by info need type:\n")

    for info_type, comparison in result.items():
        print(f"▶ {info_type}")
        print(f"   Sample Count: {comparison['comparison']['sample_count']}")
        print(f"   Divergence Rate: {comparison['comparison']['divergence_rate']:.1%}")

        if comparison['comparison']['improvement_rate'] is not None:
            print(f"   Improvement Rate: {comparison['comparison']['improvement_rate']:.1%}")
        print()


async def demo_filtered_comparison(session_id):
    """Demo comparison with time range filter."""
    print("\n" + "=" * 60)
    print("4. FILTERED COMPARISON: Last 1 hour")
    print("=" * 60)

    comparator = get_comparator()

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(hours=1)

    result = comparator.compare_versions(
        active_version="v1",
        shadow_version="v2-shadow-a",
        session_id=session_id,
        time_range=(start_time, end_time),
    )

    print(f"\n⏰ Time Range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"📊 Sample Count: {result['comparison']['sample_count']}")
    print(f"📈 Divergence Rate: {result['comparison']['divergence_rate']:.1%}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("DECISION COMPARATOR DEMO")
    print("=" * 60)
    print("\nThis demo shows how to compare active and shadow classifier")
    print("versions to evaluate which shadow is worth migrating to production.")

    # Setup demo data
    session_id = await setup_demo_data()

    # Wait for audit logs to be written
    await asyncio.sleep(0.1)

    # Run demos
    await demo_basic_comparison(session_id)
    await demo_multi_shadow_comparison(session_id)
    await demo_grouped_comparison(session_id)
    await demo_filtered_comparison(session_id)

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\n📝 Key Takeaways:")
    print("   1. v2-shadow-b shows best overall performance")
    print("   2. Active v1 is too conservative on LOCAL_KNOWLEDGE")
    print("   3. Active v1 is too aggressive on EXTERNAL_FACT_UNCERTAIN")
    print("   4. Shadow comparisons provide clear migration guidance")
    print("\n✅ Decision Comparator is ready for production use!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
