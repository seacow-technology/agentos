"""
Demonstration of Task #8: Enhanced Memory Injection in System Prompt

This script shows the difference between the old and new memory injection approach.

Before (Task #8):
- Memory facts buried in the middle of prompt
- No strong enforcement instructions
- No visual emphasis on preferred_name

After (Task #8):
- Memory section at the top with high visibility
- Strong "MUST" instructions for LLM compliance
- Visual separators (===) for emphasis
- preferred_name highlighted prominently
- Categorized sections: Identity, Preferences, Facts
"""

from agentos.core.chat.context_builder import ContextBuilder, ContextBudget
from agentos.core.chat.service import ChatService
from agentos.core.memory.service import MemoryService
from agentos.core.project_kb.service import ProjectKBService


def demo_enhanced_memory_injection():
    """Demonstrate the enhanced memory injection in system prompt."""

    # Create sample memory facts
    memory_facts = [
        {
            "id": "mem-001",
            "scope": "global",
            "type": "preference",
            "content": {
                "key": "preferred_name",
                "value": "胖哥"
            },
            "confidence": 0.9,
            "tags": ["user", "identity"]
        },
        {
            "id": "mem-002",
            "scope": "global",
            "type": "preference",
            "content": {
                "key": "language",
                "value": "zh-CN"
            },
            "confidence": 0.85,
            "tags": ["language"]
        },
        {
            "id": "mem-003",
            "scope": "project",
            "type": "project_fact",
            "content": {
                "summary": "This is an AgentOS project focused on AI agent orchestration"
            },
            "confidence": 0.8,
            "tags": ["project"]
        }
    ]

    # Create context parts
    context_parts = {
        "memory": memory_facts,
        "rag": [
            {
                "chunk_id": "chunk-001",
                "path": "README.md",
                "heading": "Getting Started",
                "content": "AgentOS is a flexible agent operating system..."
            }
        ],
        "summaries": [],
        "window": []
    }

    # Create context builder (with mocked services for demo)
    try:
        builder = ContextBuilder(
            budget=ContextBudget(
                max_tokens=8000,
                system_tokens=1000,
                window_tokens=4000,
                rag_tokens=2000,
                memory_tokens=1000
            )
        )

        # Build system prompt
        prompt = builder._build_system_prompt(context_parts, session_id="demo-session")

        print("=" * 80)
        print("ENHANCED MEMORY INJECTION DEMO (Task #8)")
        print("=" * 80)
        print()
        print("Generated System Prompt:")
        print("-" * 80)
        print(prompt)
        print("-" * 80)
        print()
        print("Key Improvements:")
        print("  ✓ Memory section positioned at top (highest priority)")
        print("  ✓ Visual separators (===) for emphasis")
        print("  ✓ Strong enforcement instructions (MUST)")
        print("  ✓ Preferred name (胖哥) highlighted prominently")
        print("  ✓ Categorized sections (Identity, Preferences, Facts)")
        print("  ✓ Explicit instructions to use preferred name")
        print()
        print("Result: LLM is much more likely to use '胖哥' in responses!")
        print("=" * 80)

    except Exception as e:
        print(f"Demo error: {e}")
        print("This is expected if running outside of full AgentOS environment.")
        print("The key changes are in the prompt structure shown above.")


def show_before_after_comparison():
    """Show before/after comparison of prompt structure."""

    print("\n" + "=" * 80)
    print("BEFORE vs AFTER COMPARISON")
    print("=" * 80)
    print()

    print("BEFORE (Task #8):")
    print("-" * 80)
    print("""
You are an AI assistant in AgentOS.

Your capabilities:
- Answer questions about the codebase
- Access project memory for long-term facts
- Execute slash commands

Project Memory:
1. preferred_name: 胖哥

Relevant Documentation:
1. README.md - Getting Started

Respond concisely and helpfully.
""")
    print("-" * 80)
    print()
    print("Issues:")
    print("  ✗ Memory buried in middle of prompt")
    print("  ✗ No strong enforcement instructions")
    print("  ✗ preferred_name not emphasized")
    print("  ✗ LLM may ignore or forget to use it")
    print()

    print("AFTER (Task #8):")
    print("-" * 80)
    print("""
You are an AI assistant in AgentOS.

============================================================
⚠️  CRITICAL USER CONTEXT (MUST FOLLOW)
============================================================

👤 USER IDENTITY:
   The user prefers to be called: "胖哥"
   ⚠️  You MUST address the user as "胖哥" in all responses.
   ⚠️  Do NOT use generic terms like "user" or "you" - use "胖哥".

============================================================

Your capabilities:
- Answer questions about the codebase
- Access project memory for long-term facts
- Execute slash commands

Relevant Documentation:
1. README.md - Getting Started

Respond concisely and helpfully.
""")
    print("-" * 80)
    print()
    print("Improvements:")
    print("  ✓ Memory at top (highest priority)")
    print("  ✓ Visual separators increase visibility")
    print("  ✓ Strong 'MUST' instructions")
    print("  ✓ Explicit directive to use preferred name")
    print("  ✓ Warning against generic terms")
    print()
    print("=" * 80)


if __name__ == "__main__":
    print("\n")
    show_before_after_comparison()
    print("\n")
    demo_enhanced_memory_injection()
