"""
InfoNeed Memory System - Usage Examples

This file demonstrates how to use the InfoNeed judgment memory system
for pattern analysis, deduplication, and user feedback tracking.

Task #22: MemoryOS judgment history storage
"""

import asyncio
from datetime import timedelta
from agentos.core.chat.info_need_classifier import InfoNeedClassifier
from agentos.core.memory.info_need_writer import InfoNeedMemoryWriter
from agentos.core.memory.schema import InfoNeedJudgment


async def example_1_basic_classification_with_memory():
    """Example 1: Basic classification with automatic memory storage."""
    print("\n=== Example 1: Basic Classification with Memory ===")

    classifier = InfoNeedClassifier()
    session_id = "demo-session-1"

    # Classify a question (automatically writes to MemoryOS)
    result = await classifier.classify(
        message="What is the latest Python version?",
        session_id=session_id
    )

    print(f"Classification Result:")
    print(f"  Type: {result.info_need_type.value}")
    print(f"  Action: {result.decision_action.value}")
    print(f"  Confidence: {result.confidence_level.value}")
    print(f"  Message ID: {result.message_id}")

    # Query the judgment from memory
    writer = InfoNeedMemoryWriter()
    judgments = await writer.query_recent_judgments(
        session_id=session_id,
        time_range="1h"
    )

    print(f"\nJudgments in memory: {len(judgments)}")
    if judgments:
        j = judgments[0]
        print(f"  Question: {j.question_text}")
        print(f"  Type: {j.classified_type.value}")
        print(f"  Outcome: {j.outcome.value}")


async def example_2_outcome_feedback():
    """Example 2: Update judgment with user feedback."""
    print("\n=== Example 2: Outcome Feedback ===")

    classifier = InfoNeedClassifier()
    writer = InfoNeedMemoryWriter()

    # Classify question
    result = await classifier.classify(
        message="How do I implement authentication?",
        session_id="demo-session-2"
    )

    message_id = result.message_id
    print(f"Classification: {result.decision_action.value}")

    # Simulate user proceeding with the decision
    await writer.update_judgment_outcome_by_message_id(
        message_id=message_id,
        outcome="user_proceeded",
        user_action="followed_llm_answer"
    )

    print("Updated outcome: user_proceeded")

    # Retrieve and verify
    judgment = await writer.get_judgment_by_id(result.message_id)
    if judgment:
        print(f"Outcome recorded: {judgment.outcome.value}")
        print(f"User action: {judgment.user_action}")


async def example_3_deduplication():
    """Example 3: Deduplication - detect similar questions."""
    print("\n=== Example 3: Deduplication ===")

    writer = InfoNeedMemoryWriter()
    classifier = InfoNeedClassifier()

    # Ask first question
    q1 = "What is the latest Python version?"
    result1 = await classifier.classify(q1, session_id="demo-session-3")
    print(f"Classified: {q1}")

    # Ask similar question with different formatting
    q2 = "  WHAT IS THE LATEST PYTHON VERSION?  "
    question_hash = InfoNeedJudgment.create_question_hash(q2)

    # Check for similar judgment before classifying
    similar = await writer.find_similar_judgment(
        question_hash=question_hash,
        time_window=timedelta(hours=1)
    )

    if similar:
        print(f"\nFound similar question!")
        print(f"  Original: {similar.question_text}")
        print(f"  Previous decision: {similar.decision_action.value}")
        print(f"  Can reuse this judgment instead of re-classifying")
    else:
        print("No similar question found, would classify normally")


async def example_4_pattern_analysis():
    """Example 4: Analyze patterns in user questions."""
    print("\n=== Example 4: Pattern Analysis ===")

    classifier = InfoNeedClassifier()
    writer = InfoNeedMemoryWriter()

    session_id = "demo-session-4"

    # Simulate a user session with various questions
    questions = [
        "What is the latest React version?",
        "How do I sort a Python list?",
        "Where is the User model defined?",
        "What are the current running processes?",
        "Who is the CEO of Microsoft?",
    ]

    print("Classifying multiple questions...")
    for q in questions:
        await classifier.classify(q, session_id=session_id)

    # Analyze patterns
    judgments = await writer.query_recent_judgments(
        session_id=session_id,
        time_range="1h"
    )

    print(f"\nPattern Analysis for {len(judgments)} judgments:")

    # Count by type
    type_counts = {}
    for j in judgments:
        type_name = j.classified_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    for type_name, count in type_counts.items():
        print(f"  {type_name}: {count}")


async def example_5_performance_monitoring():
    """Example 5: Monitor classification performance."""
    print("\n=== Example 5: Performance Monitoring ===")

    classifier = InfoNeedClassifier()
    writer = InfoNeedMemoryWriter()

    session_id = "demo-session-5"

    # Classify some questions
    questions = [
        "What is the latest news?",
        "How do I use async/await?",
        "Where is config.py?",
    ]

    for q in questions:
        await classifier.classify(q, session_id=session_id)

    # Get statistics
    stats = await writer.get_judgment_stats(
        session_id=session_id,
        time_range="1h"
    )

    print(f"Performance Statistics:")
    print(f"  Total judgments: {stats['total_judgments']}")
    print(f"  Average latency: {stats['avg_latency_ms']:.2f}ms")
    print(f"\n  By type:")
    for type_name, count in stats['by_type'].items():
        print(f"    {type_name}: {count}")
    print(f"\n  By action:")
    for action, count in stats['by_action'].items():
        print(f"    {action}: {count}")
    print(f"\n  By outcome:")
    for outcome, count in stats['by_outcome'].items():
        print(f"    {outcome}: {count}")


async def example_6_session_replay():
    """Example 6: Replay a user's information need history."""
    print("\n=== Example 6: Session Replay ===")

    classifier = InfoNeedClassifier()
    writer = InfoNeedMemoryWriter()

    session_id = "demo-session-6"

    # Simulate a conversation
    conversation = [
        ("What is the latest TypeScript version?", "user_proceeded"),
        ("How do I implement OAuth?", "user_declined"),
        ("Where is the auth middleware?", "user_proceeded"),
    ]

    print("Simulating conversation...")
    for question, outcome in conversation:
        result = await classifier.classify(question, session_id=session_id)
        await asyncio.sleep(0.1)  # Brief delay
        await writer.update_judgment_outcome_by_message_id(
            message_id=result.message_id,
            outcome=outcome
        )

    # Replay session
    print("\nSession Replay:")
    history = await writer.query_recent_judgments(
        session_id=session_id,
        time_range="1h"
    )

    for i, judgment in enumerate(reversed(history), 1):
        print(f"\n{i}. {judgment.question_text}")
        print(f"   Decision: {judgment.decision_action.value}")
        print(f"   Outcome: {judgment.outcome.value}")
        print(f"   Latency: {judgment.decision_latency_ms:.1f}ms")


async def example_7_user_feedback_analysis():
    """Example 7: Analyze user feedback on decisions."""
    print("\n=== Example 7: User Feedback Analysis ===")

    classifier = InfoNeedClassifier()
    writer = InfoNeedMemoryWriter()

    session_id = "demo-session-7"

    # Classify and get different outcomes
    test_cases = [
        ("What is the latest news?", "require_comm", "user_proceeded"),
        ("How do I sort a list?", "direct_answer", "user_proceeded"),
        ("What is the weather?", "require_comm", "user_declined"),
    ]

    for question, expected_action, outcome in test_cases:
        result = await classifier.classify(question, session_id=session_id)
        await writer.update_judgment_outcome_by_message_id(
            message_id=result.message_id,
            outcome=outcome,
            user_action=f"response_to_{expected_action}"
        )

    # Analyze declined decisions
    print("Analyzing user-declined decisions...")
    declined = await writer.query_recent_judgments(
        session_id=session_id,
        outcome="user_declined"
    )

    print(f"\nUser declined {len(declined)} decisions:")
    for judgment in declined:
        print(f"  Question: {judgment.question_text}")
        print(f"  Our decision: {judgment.decision_action.value}")
        print(f"  User feedback: {judgment.user_action}")


async def example_8_ttl_cleanup():
    """Example 8: TTL-based cleanup of old judgments."""
    print("\n=== Example 8: TTL Cleanup ===")

    # Create writer with short TTL for demo
    writer = InfoNeedMemoryWriter(ttl_days=30)

    # Get current count
    judgments_before = await writer.query_recent_judgments(
        time_range="365d",  # All judgments
        limit=10000
    )

    print(f"Judgments before cleanup: {len(judgments_before)}")

    # Run cleanup (removes judgments older than 30 days)
    deleted = await writer.cleanup_old_judgments()

    print(f"Deleted {deleted} old judgments")

    # Get count after cleanup
    judgments_after = await writer.query_recent_judgments(
        time_range="365d",
        limit=10000
    )

    print(f"Judgments after cleanup: {len(judgments_after)}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("InfoNeed Memory System - Usage Examples")
    print("=" * 60)

    try:
        await example_1_basic_classification_with_memory()
        await example_2_outcome_feedback()
        await example_3_deduplication()
        await example_4_pattern_analysis()
        await example_5_performance_monitoring()
        await example_6_session_replay()
        await example_7_user_feedback_analysis()
        await example_8_ttl_cleanup()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Note: This requires a properly initialized database
    # Run: agentos init (if not already done)
    asyncio.run(main())
