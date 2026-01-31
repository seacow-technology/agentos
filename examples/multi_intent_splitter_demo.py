#!/usr/bin/env python3
"""
Multi-Intent Question Splitter Demo

This script demonstrates the capabilities of the MultiIntentSplitter,
showing how it handles various question patterns and edge cases.

Run:
    python examples/multi_intent_splitter_demo.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.chat.multi_intent_splitter import MultiIntentSplitter, split_question


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print('=' * 80)


def demo_split(splitter: MultiIntentSplitter, question: str, description: str = ""):
    """Demonstrate splitting a question."""
    print(f"\n📝 Input: {question}")
    if description:
        print(f"   ({description})")

    if splitter.should_split(question):
        result = splitter.split(question)
        if result:
            print(f"✅ Split into {len(result)} sub-questions:")
            for sub_q in result:
                print(f"   [{sub_q.index}] {sub_q.text}")
                if sub_q.needs_context:
                    print(f"       ⚠️  Needs context: {sub_q.context_hint}")
        else:
            print("❌ Split check failed (validation rejected)")
    else:
        print("➡️  No split needed")


def main():
    """Run the demo."""
    print("\n" + "=" * 80)
    print("  Multi-Intent Question Splitter Demo")
    print("=" * 80)

    # Create splitter with default config
    splitter = MultiIntentSplitter()

    # =========================================================================
    # 1. Connector-based splitting
    # =========================================================================
    print_section("1. Connector-Based Splitting")

    demo_split(
        splitter,
        "现在几点？以及最新AI政策",
        "Chinese connector '以及'"
    )

    demo_split(
        splitter,
        "What's the time? And also the latest AI policy",
        "English connector 'and also'"
    )

    demo_split(
        splitter,
        "告诉我Python是什么？还有它的主要特性",
        "Chinese connector '还有' with pronoun reference"
    )

    demo_split(
        splitter,
        "Show me the config, additionally display the current mode",
        "English connector 'additionally'"
    )

    # =========================================================================
    # 2. Punctuation-based splitting
    # =========================================================================
    print_section("2. Punctuation-Based Splitting")

    demo_split(
        splitter,
        "谁是当前总统；他的政策是什么？",
        "Chinese semicolon with pronoun reference"
    )

    demo_split(
        splitter,
        "What is Docker; How to install it?",
        "English semicolon with pronoun reference"
    )

    demo_split(
        splitter,
        "检查系统状态；显示当前phase",
        "Chinese semicolon separating commands"
    )

    # =========================================================================
    # 3. Enumeration-based splitting
    # =========================================================================
    print_section("3. Enumeration-Based Splitting")

    demo_split(
        splitter,
        "1. 现在几点 2. 今天天气 3. 最新新闻",
        "Numeric enumeration (space-separated)"
    )

    demo_split(
        splitter,
        "1. What time is it\n2. What's the weather\n3. Latest news",
        "Numeric enumeration (newline-separated)"
    )

    demo_split(
        splitter,
        "（1）解释AI概念\n（2）说明应用场景",
        "Chinese parenthesized numbers"
    )

    demo_split(
        splitter,
        "First, check the logs. Second, restart the service.",
        "English ordinal enumeration"
    )

    # =========================================================================
    # 4. Conservative non-split cases
    # =========================================================================
    print_section("4. Conservative Non-Split Cases")

    demo_split(
        splitter,
        "最新的AI政策以及实施细节是什么？",
        "Connector links parallel components (NOT independent questions)"
    )

    demo_split(
        splitter,
        "什么是人工智能？",
        "Single simple question"
    )

    demo_split(
        splitter,
        "Explain REST API and its use cases",
        "Single question with compound object"
    )

    demo_split(
        splitter,
        "Show me files with .py and .js extensions",
        "'and' connects file extensions (NOT questions)"
    )

    demo_split(
        splitter,
        "比较Python和Java的性能以及语法差异",
        "Single comparison with multiple aspects"
    )

    # =========================================================================
    # 5. Context preservation
    # =========================================================================
    print_section("5. Context Preservation (Pronoun References)")

    demo_split(
        splitter,
        "谁是现任总统？以及他的主要政策",
        "Second question uses '他' referring to president"
    )

    demo_split(
        splitter,
        "What is Docker? And how to use it?",
        "Second question uses 'it' referring to Docker"
    )

    demo_split(
        splitter,
        "Who is the CEO of OpenAI? And what are his recent statements?",
        "Second question uses 'his' referring to CEO"
    )

    # =========================================================================
    # 6. Multiple question marks
    # =========================================================================
    print_section("6. Multiple Question Marks")

    demo_split(
        splitter,
        "现在几点？今天天气如何？",
        "Two complete questions back-to-back"
    )

    demo_split(
        splitter,
        "What's the time? What's the weather?",
        "Two English questions with question marks"
    )

    # =========================================================================
    # 7. Edge cases
    # =========================================================================
    print_section("7. Edge Cases")

    demo_split(
        splitter,
        "以及",
        "Only connector, no content"
    )

    demo_split(
        splitter,
        "",
        "Empty string"
    )

    demo_split(
        splitter,
        "短",
        "Single character (too short)"
    )

    demo_split(
        splitter,
        "问题A以及问题B还有问题C",
        "Multiple connectors"
    )

    # =========================================================================
    # 8. Configuration demo
    # =========================================================================
    print_section("8. Custom Configuration")

    # Create splitter with custom config
    custom_splitter = MultiIntentSplitter(config={
        'min_length': 3,
        'max_splits': 2,  # Only allow up to 2 splits
        'enable_context': True,
    })

    print("\nConfiguration: min_length=3, max_splits=2, enable_context=True")

    demo_split(
        custom_splitter,
        "1. A 2. B 3. C",
        "Should split (within max_splits=2) - WAIT, has 3 items, should NOT split"
    )

    demo_split(
        custom_splitter,
        "1. First 2. Second",
        "Should split (exactly max_splits=2)"
    )

    # =========================================================================
    # 9. Performance demo
    # =========================================================================
    print_section("9. Performance Test")

    import time

    test_questions = [
        "现在几点？以及最新AI政策",
        "1. First\n2. Second\n3. Third",
        "What is Docker; How to install it?",
        "问题A还有问题B同时问题C",
    ]

    iterations = 1000
    print(f"\nRunning {iterations} iterations on {len(test_questions)} questions...")

    start = time.perf_counter()
    for _ in range(iterations):
        for question in test_questions:
            splitter.split(question)
    elapsed = time.perf_counter() - start

    total_ops = iterations * len(test_questions)
    avg_time_ms = (elapsed / total_ops) * 1000

    print(f"✅ Total time: {elapsed:.3f}s")
    print(f"✅ Average time per split: {avg_time_ms:.4f}ms")
    print(f"✅ Target: <5ms (p95)")

    if avg_time_ms < 5.0:
        print("🎉 Performance target MET!")
    else:
        print("⚠️  Performance target not met")

    # =========================================================================
    # 10. Convenience function demo
    # =========================================================================
    print_section("10. Convenience Function")

    print("\nUsing split_question() convenience function:")
    result = split_question("问题A以及问题B")

    if result:
        print(f"✅ Split into {len(result)} questions:")
        for sub_q in result:
            print(f"   [{sub_q.index}] {sub_q.text}")
    else:
        print("➡️  No split needed")

    # =========================================================================
    # Summary
    # =========================================================================
    print_section("Summary")

    print("""
The MultiIntentSplitter provides:
  ✅ Rule-based splitting (no LLM, low latency)
  ✅ Conservative approach (when uncertain, don't split)
  ✅ Context preservation (detects pronoun references)
  ✅ Bilingual support (Chinese and English)
  ✅ Multiple strategies (connectors, punctuation, enumeration)
  ✅ Configurable behavior (min_length, max_splits, context detection)
  ✅ High performance (<5ms p95)

Use cases:
  • Chat systems handling composite questions
  • Question preprocessing pipelines
  • Multi-intent detection in conversational AI
  • Batch question processing

Documentation: docs/chat/MULTI_INTENT_SPLITTER.md
    """)

    print("\n" + "=" * 80 + "\n")


if __name__ == '__main__':
    main()
