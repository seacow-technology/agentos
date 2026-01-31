#!/usr/bin/env python3
"""
InfoNeedClassifier Interactive Demo

Demonstrates classification behavior for various question types.

Usage:
    # Run demo with all examples
    python3 examples/info_need_classifier_demo.py

    # Interactive mode
    python3 examples/info_need_classifier_demo.py interactive

    # Single classification
    python3 examples/info_need_classifier_demo.py classify "What is the latest AI news?"
"""

import asyncio
import sys
import json
from typing import Dict, List

from agentos.core.chat.info_need_classifier import InfoNeedClassifier
from agentos.core.chat.models.info_need import InfoNeedType, DecisionAction, ConfidenceLevel


# Demo questions organized by expected classification type
DEMO_QUESTIONS: Dict[str, List[str]] = {
    "LOCAL_DETERMINISTIC": [
        "Does the InfoNeedClassifier class exist in this project?",
        "Show me all Python files in the agentos/core/chat directory",
        "What methods does the ChatEngine class have?",
        "Count how many test files exist",
        "Where is the configuration file located?",
        "这个项目中有ChatEngine类吗?",  # Chinese: Does ChatEngine class exist in this project?
    ],
    "LOCAL_KNOWLEDGE": [
        "What is REST API?",
        "Explain the SOLID principles",
        "What's the difference between AI and ML?",
        "How do I use async/await in Python?",
        "What are microservices?",
        "什么是微服务架构?",  # Chinese: What is microservices architecture?
    ],
    "AMBIENT_STATE": [
        "What time is it?",
        "What phase am I in?",
        "What is my session ID?",
        "What mode are we in?",
        "Show me the system status",
        "现在几点?",  # Chinese: What time is it?
        "当前是什么阶段?",  # Chinese: What is the current phase?
    ],
    "EXTERNAL_FACT_UNCERTAIN": [
        "What is the latest Python version?",
        "What are Australia's current AI regulations?",
        "What happened in AI news today?",
        "What is the official stance of the US government on AI safety?",
        "What are the 2026 updates to GDPR?",
        "最新的AI政策是什么?",  # Chinese: What is the latest AI policy?
        "今天有什么AI新闻?",  # Chinese: What AI news today?
    ],
    "OPINION": [
        "What's the best way to learn Python?",
        "Should I use REST or GraphQL?",
        "Is this architecture design good?",
        "What do you recommend for database choice?",
        "What's your opinion on microservices?",
        "你推荐哪个学习路径?",  # Chinese: Which learning path do you recommend?
    ],
}


def print_header(text: str, char: str = "="):
    """Print a formatted header"""
    width = 70
    print()
    print(char * width)
    print(f" {text}")
    print(char * width)
    print()


def print_classification_result(question: str, result, show_details: bool = True):
    """Print classification result in a formatted way"""
    # Color codes for terminal output
    TYPE_COLORS = {
        "local_deterministic": "\033[94m",  # Blue
        "local_knowledge": "\033[92m",  # Green
        "ambient_state": "\033[96m",  # Cyan
        "external_fact_uncertain": "\033[93m",  # Yellow
        "opinion": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    type_color = TYPE_COLORS.get(result.info_need_type.value, "")

    print(f"\n{'─' * 70}")
    print(f"Question: {question}")
    print(f"{'─' * 70}")
    print(f"Type:       {type_color}{result.info_need_type.value}{RESET}")
    print(f"Action:     {result.decision_action.value}")
    print(f"Confidence: {result.confidence_level.value}")

    if show_details:
        print(f"\nRule Signals:")
        print(f"  Signal strength:     {result.rule_signals.signal_strength:.2f}")
        print(f"  Time-sensitive:      {result.rule_signals.has_time_sensitive_keywords}")
        print(f"  Authoritative:       {result.rule_signals.has_authoritative_keywords}")
        print(f"  Ambient state:       {result.rule_signals.has_ambient_state_keywords}")

        if result.rule_signals.matched_keywords:
            keywords = ", ".join(result.rule_signals.matched_keywords[:5])
            if len(result.rule_signals.matched_keywords) > 5:
                keywords += f" (+ {len(result.rule_signals.matched_keywords) - 5} more)"
            print(f"  Matched keywords:    {keywords}")

        if result.llm_confidence:
            print(f"\nLLM Assessment:")
            print(f"  Confidence:          {result.llm_confidence.confidence.value}")
            print(f"  Reason:              {result.llm_confidence.reason}")

        print(f"\nReasoning:")
        print(f"  {result.reasoning}")


async def demo_classification(show_details: bool = True):
    """Run classification demo on all example questions"""
    print_header("InfoNeedClassifier Interactive Demo")

    classifier = InfoNeedClassifier()

    for category, questions in DEMO_QUESTIONS.items():
        print_header(f"Category: {category}", char="-")

        for question in questions:
            try:
                result = await classifier.classify(question)
                print_classification_result(question, result, show_details)

            except Exception as e:
                print(f"\n❌ Classification failed: {str(e)}")

    print("\n" + "=" * 70)
    print(" Demo Complete!")
    print("=" * 70)


async def interactive_mode():
    """Interactive mode where user can enter questions"""
    print_header("InfoNeedClassifier - Interactive Mode")
    print("Enter questions to classify. Type 'quit' or 'exit' to stop.\n")

    classifier = InfoNeedClassifier()

    while True:
        try:
            # Get user input
            question = input("\n\033[1mQuestion:\033[0m ").strip()

            if question.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            if not question:
                continue

            # Classify
            result = await classifier.classify(question)

            # Display result
            print_classification_result(question, result, show_details=True)

            # Suggest action based on classification
            print(f"\n\033[1mSuggested Action:\033[0m")
            if result.decision_action == DecisionAction.LOCAL_CAPABILITY:
                print("  → Use local tools (file system, status checks, etc.)")
            elif result.decision_action == DecisionAction.DIRECT_ANSWER:
                print("  → Answer directly from LLM knowledge")
            elif result.decision_action == DecisionAction.REQUIRE_COMM:
                print("  → Requires external information via /comm command")
                print(f"     Example: /comm search {question[:40]}")
            elif result.decision_action == DecisionAction.SUGGEST_COMM:
                print("  → Can answer, but suggest verification via /comm")
                print(f"     Example: /comm search {question[:40]}")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


async def classify_single(question: str):
    """Classify a single question and display result"""
    classifier = InfoNeedClassifier()

    print_header(f"Classifying: {question}")

    try:
        result = await classifier.classify(question)
        print_classification_result(question, result, show_details=True)

        # Export to JSON
        print(f"\n\033[1mJSON Export:\033[0m")
        json_output = json.dumps(result.to_dict(), indent=2, default=str)
        print(json_output)

    except Exception as e:
        print(f"\n❌ Classification failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def batch_classify(questions: List[str]):
    """Classify multiple questions and show summary"""
    print_header("Batch Classification")

    classifier = InfoNeedClassifier()

    results = []
    for question in questions:
        try:
            result = await classifier.classify(question)
            results.append((question, result))
        except Exception as e:
            print(f"❌ Failed to classify: {question[:50]}")
            print(f"   Error: {str(e)}")

    # Display summary table
    print(f"\n{'Question':<45} {'Type':<25} {'Action':<20} {'Conf':<8}")
    print("─" * 100)

    for question, result in results:
        q_display = question[:42] + "..." if len(question) > 45 else question
        print(
            f"{q_display:<45} "
            f"{result.info_need_type.value:<25} "
            f"{result.decision_action.value:<20} "
            f"{result.confidence_level.value:<8}"
        )

    # Display distribution
    print("\n" + "─" * 70)
    print("Distribution:")

    type_counts = {}
    action_counts = {}

    for _, result in results:
        type_counts[result.info_need_type.value] = \
            type_counts.get(result.info_need_type.value, 0) + 1
        action_counts[result.decision_action.value] = \
            action_counts.get(result.decision_action.value, 0) + 1

    print(f"\nTypes:")
    for type_name, count in sorted(type_counts.items()):
        pct = count / len(results) * 100
        print(f"  {type_name:<25} {count:3d} ({pct:5.1f}%)")

    print(f"\nActions:")
    for action_name, count in sorted(action_counts.items()):
        pct = count / len(results) * 100
        print(f"  {action_name:<25} {count:3d} ({pct:5.1f}%)")


async def compare_with_without_llm():
    """Compare classification with and without LLM assessment"""
    print_header("Comparison: With vs Without LLM Assessment")

    questions = [
        "What is the latest Python version?",
        "What is Python?",
        "Should I use Flask or Django?",
    ]

    # Classifier with LLM
    classifier_with_llm = InfoNeedClassifier(config={
        "enable_llm_evaluation": True
    })

    # Classifier without LLM (rule-based only)
    classifier_without_llm = InfoNeedClassifier(config={
        "enable_llm_evaluation": False
    })

    for question in questions:
        print(f"\n{'─' * 70}")
        print(f"Question: {question}")
        print(f"{'─' * 70}")

        # With LLM
        result_with = await classifier_with_llm.classify(question)
        print(f"\n\033[1mWith LLM:\033[0m")
        print(f"  Type:       {result_with.info_need_type.value}")
        print(f"  Action:     {result_with.decision_action.value}")
        print(f"  Confidence: {result_with.confidence_level.value}")
        if result_with.llm_confidence:
            print(f"  LLM reason: {result_with.llm_confidence.reason}")

        # Without LLM
        result_without = await classifier_without_llm.classify(question)
        print(f"\n\033[1mWithout LLM (rule-based only):\033[0m")
        print(f"  Type:       {result_without.info_need_type.value}")
        print(f"  Action:     {result_without.decision_action.value}")
        print(f"  Confidence: {result_without.confidence_level.value}")

        # Comparison
        if result_with.info_need_type != result_without.info_need_type:
            print(f"\n⚠️  Different type classification!")
        if result_with.decision_action != result_without.decision_action:
            print(f"⚠️  Different action recommendation!")


def print_usage():
    """Print usage information"""
    print("""
InfoNeedClassifier Demo

Usage:
    python3 examples/info_need_classifier_demo.py [command] [args]

Commands:
    (no args)              Run full demo with all example questions
    interactive            Enter interactive mode for custom questions
    classify <question>    Classify a single question
    batch <file>           Classify questions from a file (one per line)
    compare                Compare classification with/without LLM
    help                   Show this help message

Examples:
    python3 examples/info_need_classifier_demo.py
    python3 examples/info_need_classifier_demo.py interactive
    python3 examples/info_need_classifier_demo.py classify "What is the latest AI news?"
    python3 examples/info_need_classifier_demo.py batch questions.txt
    python3 examples/info_need_classifier_demo.py compare

Options:
    --no-details           Hide detailed classification information
    --help, -h             Show this help message
    """)


def main():
    """Main entry point"""
    # Parse command line arguments
    if len(sys.argv) < 2:
        # Default: run demo
        asyncio.run(demo_classification(show_details=True))
        return

    command = sys.argv[1].lower()

    if command in ["help", "--help", "-h"]:
        print_usage()

    elif command == "interactive":
        asyncio.run(interactive_mode())

    elif command == "classify":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide a question to classify")
            print("Usage: python3 examples/info_need_classifier_demo.py classify <question>")
            sys.exit(1)

        question = " ".join(sys.argv[2:])
        asyncio.run(classify_single(question))

    elif command == "batch":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide a file path")
            print("Usage: python3 examples/info_need_classifier_demo.py batch <file>")
            sys.exit(1)

        file_path = sys.argv[2]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                questions = [line.strip() for line in f if line.strip()]

            asyncio.run(batch_classify(questions))

        except FileNotFoundError:
            print(f"❌ Error: File not found: {file_path}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading file: {str(e)}")
            sys.exit(1)

    elif command == "compare":
        asyncio.run(compare_with_without_llm())

    elif command == "demo":
        # Explicit demo command
        show_details = "--no-details" not in sys.argv
        asyncio.run(demo_classification(show_details=show_details))

    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'help' to see available commands")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
