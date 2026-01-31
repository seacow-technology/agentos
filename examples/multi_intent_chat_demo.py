"""
Multi-Intent Chat Demo (Task #25)

This script demonstrates the multi-intent processing capability of ChatEngine.
It shows how composite questions are automatically detected, split, classified,
and processed to provide comprehensive answers.

Usage:
    python examples/multi_intent_chat_demo.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentos.core.chat.engine import ChatEngine
from agentos.core.chat.service import ChatService
import json


def print_section(title):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_result(result):
    """Print chat result in formatted way"""
    print(f"Role: {result['role']}")
    print(f"Content:\n{result['content']}\n")

    # Print metadata if multi-intent
    metadata = result.get("metadata", {})
    if metadata.get("type") == "multi_intent":
        print("\n--- Multi-Intent Details ---")
        print(f"Sub-Questions: {len(metadata.get('sub_questions', []))}")

        for sq in metadata.get("sub_questions", []):
            print(f"\n  [{sq['index']+1}] {sq['text']}")
            print(f"      Classification: {sq['classification']['type']} → {sq['classification']['action']}")
            print(f"      Success: {sq.get('success', False)}")


def demo_basic_multi_intent():
    """Demo 1: Basic multi-intent with time and phase queries"""
    print_section("Demo 1: Basic Multi-Intent")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Multi-Intent Demo Session",
        metadata={"demo": "basic"}
    )

    print("Question: What time is it? What phase are we in?")
    print("\nExpected: 2 sub-questions, both LOCAL_CAPABILITY\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="What time is it? What phase are we in?",
        stream=False
    )

    print_result(result)


def demo_mixed_classification():
    """Demo 2: Mixed classification types"""
    print_section("Demo 2: Mixed Classification Types")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Mixed Classification Demo",
        metadata={"demo": "mixed"}
    )

    print("Question: What time is it? What is the latest AI policy?")
    print("\nExpected:")
    print("  - Sub-Q1: LOCAL_CAPABILITY (time)")
    print("  - Sub-Q2: REQUIRE_COMM (latest policy)\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="What time is it? What is the latest AI policy?",
        stream=False
    )

    print_result(result)


def demo_enumerated_questions():
    """Demo 3: Enumerated questions"""
    print_section("Demo 3: Enumerated Questions")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Enumerated Demo",
        metadata={"demo": "enumerated"}
    )

    question = """1. What is Python?
2. What is Java?
3. What is Go?"""

    print(f"Question:\n{question}")
    print("\nExpected: 3 sub-questions, enumeration-based split\n")

    result = engine.send_message(
        session_id=session_id,
        user_input=question,
        stream=False
    )

    print_result(result)


def demo_chinese_questions():
    """Demo 4: Chinese language support"""
    print_section("Demo 4: Chinese Language Support")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Chinese Demo",
        metadata={"demo": "chinese"}
    )

    print("Question: 现在几点？今天天气怎么样？")
    print("\nExpected: 2 sub-questions in Chinese\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="现在几点？今天天气怎么样？",
        stream=False
    )

    print_result(result)


def demo_connector_based():
    """Demo 5: Connector-based splitting"""
    print_section("Demo 5: Connector-Based Splitting")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Connector Demo",
        metadata={"demo": "connector"}
    )

    print("Question: 今天天气如何，以及最新的AI政策是什么？")
    print("\nExpected: Split by connector '以及'\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="今天天气如何，以及最新的AI政策是什么？",
        stream=False
    )

    print_result(result)


def demo_single_question():
    """Demo 6: Single question (should NOT split)"""
    print_section("Demo 6: Single Question (No Split)")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Single Question Demo",
        metadata={"demo": "single"}
    )

    print("Question: What is Python?")
    print("\nExpected: NOT split (single intent)\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="What is Python?",
        stream=False
    )

    print_result(result)


def demo_all_local_capability():
    """Demo 7: All local capability questions"""
    print_section("Demo 7: All Local Capability")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="All Local Demo",
        metadata={"demo": "all_local"}
    )

    print("Question: What time is it? What phase am I in? What is my session ID?")
    print("\nExpected: All LOCAL_CAPABILITY, all should succeed\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="What time is it? What phase am I in? What is my session ID?",
        stream=False
    )

    print_result(result)


def demo_audit_trail():
    """Demo 8: Audit trail logging"""
    print_section("Demo 8: Audit Trail Logging")

    from agentos.core.audit import get_audit_events

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Audit Demo",
        metadata={"demo": "audit"}
    )

    print("Question: What time is it? What is Python?")
    print("\nChecking audit trail after processing...\n")

    result = engine.send_message(
        session_id=session_id,
        user_input="What time is it? What is Python?",
        stream=False
    )

    # Check audit trail
    events = get_audit_events(event_type="MULTI_INTENT_SPLIT", limit=5)

    print(f"Recent MULTI_INTENT_SPLIT events: {len(events)}")

    if events:
        latest = events[0]
        print(f"\nLatest event:")
        print(f"  Event ID: {latest['audit_id']}")
        print(f"  Timestamp: {latest['created_at']}")
        print(f"  Payload: {json.dumps(latest['payload'], indent=2)}")


def interactive_mode():
    """Demo 9: Interactive mode"""
    print_section("Demo 9: Interactive Mode")

    engine = ChatEngine(chat_service=ChatService())
    session_id = engine.create_session(
        title="Interactive Demo",
        metadata={"demo": "interactive"}
    )

    print("Interactive Multi-Intent Chat Demo")
    print("Enter composite questions, or 'quit' to exit\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if not user_input:
                continue

            result = engine.send_message(
                session_id=session_id,
                user_input=user_input,
                stream=False
            )

            print(f"\nAssistant: {result['content']}")

            # Show if multi-intent was detected
            metadata = result.get("metadata", {})
            if metadata.get("type") == "multi_intent":
                sub_count = len(metadata.get("sub_questions", []))
                print(f"\n[Multi-intent detected: {sub_count} sub-questions]")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def main():
    """Run all demos"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  Multi-Intent Chat Demo - Task #25".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)

    demos = [
        ("Basic Multi-Intent", demo_basic_multi_intent),
        ("Mixed Classification", demo_mixed_classification),
        ("Enumerated Questions", demo_enumerated_questions),
        ("Chinese Questions", demo_chinese_questions),
        ("Connector-Based", demo_connector_based),
        ("Single Question", demo_single_question),
        ("All Local Capability", demo_all_local_capability),
        ("Audit Trail", demo_audit_trail),
    ]

    print("\nAvailable demos:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print(f"  {len(demos)+1}. Interactive Mode")
    print(f"  {len(demos)+2}. Run All")
    print(f"  0. Exit")

    while True:
        try:
            choice = input("\nSelect demo (0-9): ").strip()

            if choice == "0":
                print("Goodbye!")
                break

            choice_num = int(choice)

            if choice_num == len(demos) + 1:
                interactive_mode()
            elif choice_num == len(demos) + 2:
                # Run all demos
                for name, demo_func in demos:
                    try:
                        demo_func()
                        input("\nPress Enter to continue...")
                    except Exception as e:
                        print(f"\nDemo '{name}' failed: {e}")
                        input("\nPress Enter to continue...")
            elif 1 <= choice_num <= len(demos):
                name, demo_func = demos[choice_num - 1]
                try:
                    demo_func()
                except Exception as e:
                    print(f"\nDemo failed: {e}")
            else:
                print("Invalid choice. Please try again.")

        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


if __name__ == "__main__":
    main()
