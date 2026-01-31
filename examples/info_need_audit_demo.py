"""
InfoNeed Audit System Demo

This script demonstrates the InfoNeed classification audit system,
showing how classifications are logged and outcomes can be tracked.

Usage:
    python3 examples/info_need_audit_demo.py
"""

import asyncio
import json
from datetime import datetime

from agentos.core.audit import (
    log_info_need_classification,
    log_info_need_outcome,
    get_info_need_classification_events,
    get_info_need_outcomes_for_message,
    find_audit_event_by_metadata,
    INFO_NEED_CLASSIFICATION,
    INFO_NEED_OUTCOME,
)
from agentos.core.chat.info_need_classifier import InfoNeedClassifier


async def demo_basic_classification():
    """Demo: Basic classification with audit logging."""
    print("\n" + "=" * 60)
    print("Demo 1: Basic Classification with Audit")
    print("=" * 60)

    # Create classifier (disable LLM for faster demo)
    classifier = InfoNeedClassifier(
        config={"enable_llm_evaluation": False}
    )

    # Classify a time-sensitive question
    question = "What is the latest Python version?"
    session_id = "demo-session-001"

    print(f"\nQuestion: {question}")
    print("Classifying...")

    result = await classifier.classify(
        message=question,
        session_id=session_id,
    )

    print(f"\nClassification Result:")
    print(f"  Type: {result.info_need_type.value}")
    print(f"  Decision: {result.decision_action.value}")
    print(f"  Confidence: {result.confidence_level.value}")
    print(f"  Message ID: {result.message_id}")

    # Verify it was logged to audit trail
    event = find_audit_event_by_metadata(
        event_type=INFO_NEED_CLASSIFICATION,
        metadata_key="message_id",
        metadata_value=result.message_id,
    )

    print(f"\nAudit Event Created:")
    print(f"  Audit ID: {event['audit_id']}")
    print(f"  Event Type: {event['event_type']}")
    print(f"  Latency: {event['payload']['latency_ms']:.2f}ms")
    print(f"  Signal Strength: {event['payload']['signals']['signal_strength']:.2f}")

    return result.message_id


async def demo_outcome_logging(message_id: str):
    """Demo: Logging classification outcomes."""
    print("\n" + "=" * 60)
    print("Demo 2: Outcome Logging")
    print("=" * 60)

    print(f"\nMessage ID: {message_id}")

    # Simulate user validating the classification by executing /comm
    print("\nScenario: User executes suggested /comm command")
    print("Logging outcome...")

    await log_info_need_outcome(
        message_id=message_id,
        outcome="validated",
        user_action="/comm search latest Python version",
        notes="User followed suggestion immediately",
    )

    print("Outcome logged: validated")

    # Retrieve and display the outcome
    outcomes = get_info_need_outcomes_for_message(message_id)

    print(f"\nOutcome Events for Message:")
    for i, outcome in enumerate(outcomes, 1):
        print(f"  Outcome #{i}:")
        print(f"    Result: {outcome['payload']['outcome']}")
        print(f"    Action: {outcome['payload']['user_action']}")
        print(f"    Latency: {outcome['payload']['latency_ms']:.2f}ms")
        print(f"    Notes: {outcome['payload']['notes']}")


async def demo_manual_classification():
    """Demo: Manual classification event logging."""
    print("\n" + "=" * 60)
    print("Demo 3: Manual Classification Logging")
    print("=" * 60)

    # Manually log a classification event
    print("\nManually logging classification event...")

    message_id = "manual-demo-msg-001"

    await log_info_need_classification(
        message_id=message_id,
        session_id="manual-session-001",
        question="What are the official AI regulations in 2026?",
        classified_type="EXTERNAL_FACT_UNCERTAIN",
        confidence="low",
        decision="REQUIRE_COMM",
        signals={
            "time_sensitive": True,
            "authoritative": True,
            "ambient": False,
            "signal_strength": 0.90
        },
        rule_matches=["official", "regulations", "2026"],
        llm_confidence={
            "confidence": "low",
            "reason": "time-sensitive",
            "reasoning": "Regulatory information changes frequently"
        },
        latency_ms=52.3,
    )

    print("Classification event logged")

    # Simulate user correction
    print("\nScenario: User corrects the classification")
    print("(System said REQUIRE_COMM but user already knows the answer)")

    await log_info_need_outcome(
        message_id=message_id,
        outcome="unnecessary_comm",
        notes="User indicated they already know the regulations",
    )

    print("Outcome logged: unnecessary_comm")

    # Show the correlation
    classification = find_audit_event_by_metadata(
        event_type=INFO_NEED_CLASSIFICATION,
        metadata_key="message_id",
        metadata_value=message_id,
    )

    outcomes = get_info_need_outcomes_for_message(message_id)

    print(f"\nClassification-Outcome Correlation:")
    print(f"  Classification:")
    print(f"    Decision: {classification['payload']['decision']}")
    print(f"    Confidence: {classification['payload']['confidence']}")
    print(f"  Outcome:")
    print(f"    Result: {outcomes[0]['payload']['outcome']}")
    print(f"    Interpretation: System over-estimated need for external info")


async def demo_query_patterns():
    """Demo: Querying classification events."""
    print("\n" + "=" * 60)
    print("Demo 4: Querying Classification Events")
    print("=" * 60)

    # Log several test events
    print("\nCreating test classification events...")

    test_session = "query-demo-session"

    for i in range(3):
        await log_info_need_classification(
            message_id=f"query-demo-msg-{i}",
            session_id=test_session,
            question=f"Test question {i}",
            classified_type="EXTERNAL_FACT_UNCERTAIN" if i % 2 == 0 else "LOCAL_KNOWLEDGE",
            confidence="low" if i % 2 == 0 else "high",
            decision="REQUIRE_COMM" if i % 2 == 0 else "DIRECT_ANSWER",
            signals={
                "time_sensitive": i % 2 == 0,
                "authoritative": False,
                "ambient": False,
                "signal_strength": 0.8 if i % 2 == 0 else 0.5
            },
            rule_matches=[],
            llm_confidence=None,
            latency_ms=30.0,
        )

    print(f"Created 3 test events for session: {test_session}")

    # Query by session
    print(f"\nQuerying events by session...")
    events = get_info_need_classification_events(
        session_id=test_session,
        limit=10,
    )

    print(f"Found {len(events)} events:")
    for event in events:
        payload = event["payload"]
        print(f"  - {payload['classified_type']} -> {payload['decision']}")

    # Query by decision type
    print(f"\nQuerying events by decision type (REQUIRE_COMM)...")
    require_comm_events = get_info_need_classification_events(
        decision="REQUIRE_COMM",
        limit=5,
    )

    print(f"Found {len(require_comm_events)} REQUIRE_COMM decisions")


async def demo_quality_metrics():
    """Demo: Computing quality metrics from audit trail."""
    print("\n" + "=" * 60)
    print("Demo 5: Quality Metrics (Preview)")
    print("=" * 60)

    print("\nThis demonstrates the data foundation for quality metrics...")

    # Create test scenario: correct classification
    msg1 = "metrics-demo-msg-correct"
    await log_info_need_classification(
        message_id=msg1,
        session_id="metrics-session",
        question="What is the current weather?",
        classified_type="EXTERNAL_FACT_UNCERTAIN",
        confidence="low",
        decision="REQUIRE_COMM",
        signals={
            "time_sensitive": True,
            "authoritative": False,
            "ambient": False,
            "signal_strength": 0.85
        },
        rule_matches=["current", "weather"],
        llm_confidence={"confidence": "low", "reason": "time-sensitive"},
        latency_ms=40.0,
    )

    await log_info_need_outcome(
        message_id=msg1,
        outcome="validated",
        user_action="/comm search weather",
        notes="Correct classification",
    )

    # Create test scenario: incorrect classification
    msg2 = "metrics-demo-msg-incorrect"
    await log_info_need_classification(
        message_id=msg2,
        session_id="metrics-session",
        question="What is Python?",
        classified_type="EXTERNAL_FACT_UNCERTAIN",
        confidence="low",
        decision="REQUIRE_COMM",
        signals={
            "time_sensitive": False,
            "authoritative": False,
            "ambient": False,
            "signal_strength": 0.4
        },
        rule_matches=[],
        llm_confidence=None,
        latency_ms=35.0,
    )

    await log_info_need_outcome(
        message_id=msg2,
        outcome="user_corrected",
        notes="Should have been LOCAL_KNOWLEDGE",
    )

    print("\nQuality Metrics (computed from audit trail):")

    # Get all classifications
    all_events = get_info_need_classification_events(
        session_id="metrics-session",
        limit=100,
    )

    print(f"\n  Total Classifications: {len(all_events)}")

    # Count outcomes
    validated = 0
    corrected = 0

    for event in all_events:
        message_id = event["payload"]["message_id"]
        outcomes = get_info_need_outcomes_for_message(message_id)

        if outcomes:
            outcome_type = outcomes[0]["payload"]["outcome"]
            if outcome_type == "validated":
                validated += 1
            elif outcome_type == "user_corrected":
                corrected += 1

    if len(all_events) > 0:
        accuracy = (validated / len(all_events)) * 100
        print(f"  Validated: {validated}")
        print(f"  Corrected: {corrected}")
        print(f"  Accuracy: {accuracy:.1f}%")

    print("\n  Note: Full quality metrics implementation in Task #20")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("InfoNeed Audit System Demo")
    print("=" * 60)
    print("\nThis demo shows how InfoNeed classifications are audited.")
    print("Audit events enable quality metrics and system improvement.")

    # Run demos
    message_id = await demo_basic_classification()
    await demo_outcome_logging(message_id)
    await demo_manual_classification()
    await demo_query_patterns()
    await demo_quality_metrics()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  1. Classifications are automatically logged to audit trail")
    print("  2. Outcomes can be recorded to validate classifications")
    print("  3. Audit data enables quality metrics computation")
    print("  4. Audit logging is non-blocking and never breaks main flow")
    print("  5. All events are queryable via session, decision, or message_id")
    print("\nFor more details, see:")
    print("  - agentos/core/audit.py (audit functions)")
    print("  - agentos/core/chat/info_need_classifier.py (integration)")
    print("  - tests/unit/core/test_info_need_audit.py (test examples)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
