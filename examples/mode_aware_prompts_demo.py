#!/usr/bin/env python3
"""Demo script for mode-aware output templates.

This script demonstrates how conversation modes affect AI output style
without changing security boundaries (execution phase).

Usage:
    python examples/mode_aware_prompts_demo.py
"""

from agentos.core.chat.prompts import (
    get_system_prompt,
    get_available_modes,
    get_mode_description,
    ConversationMode
)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def demo_available_modes():
    """Show all available conversation modes"""
    print_section("Available Conversation Modes")

    modes = get_available_modes()
    print(f"Total modes available: {len(modes)}\n")

    for mode in modes:
        description = get_mode_description(mode)
        print(f"  {mode:12} - {description}")


def demo_mode_prompts():
    """Show system prompts for each mode"""
    print_section("Mode-Specific System Prompts")

    for mode in ConversationMode:
        print(f"\n--- {mode.value.upper()} MODE ---\n")
        prompt = get_system_prompt(mode.value)

        # Show first 300 characters
        preview = prompt[:300].replace("\n", "\n  ")
        print(f"  {preview}...")
        print(f"\n  [Full prompt length: {len(prompt)} characters]")


def demo_mode_differences():
    """Highlight key differences between modes"""
    print_section("Mode Characteristics Comparison")

    characteristics = {
        ConversationMode.CHAT: [
            "Conversational tone",
            "Explains reasoning",
            "Asks clarifying questions",
            "Friendly and accessible"
        ],
        ConversationMode.DISCUSSION: [
            "Analytical thinking",
            "Multiple perspectives",
            "Socratic questioning",
            "Structured reasoning"
        ],
        ConversationMode.PLAN: [
            "High-level architecture",
            "Phase breakdown",
            "Risk assessment",
            "No code generation"
        ],
        ConversationMode.DEVELOPMENT: [
            "Code-centric output",
            "Technical precision",
            "Best practices",
            "Implementation details"
        ],
        ConversationMode.TASK: [
            "Direct and concise",
            "Action-oriented",
            "Minimal explanations",
            "Result-focused"
        ]
    }

    for mode, traits in characteristics.items():
        print(f"\n{mode.value.upper()}:")
        for trait in traits:
            print(f"  • {trait}")


def demo_security_independence():
    """Demonstrate that mode doesn't affect security"""
    print_section("Security Independence: Mode vs Phase")

    print("CRITICAL PRINCIPLE:")
    print("  Conversation mode controls HOW the AI communicates (UX)")
    print("  Execution phase controls WHAT the AI can do (Security)\n")

    print("Example Scenarios:")
    print()

    scenarios = [
        {
            "mode": "chat",
            "phase": "planning",
            "description": "Friendly conversation, safe operations only"
        },
        {
            "mode": "development",
            "phase": "planning",
            "description": "Code-focused tone, but still read-only operations"
        },
        {
            "mode": "development",
            "phase": "execution",
            "description": "Code-focused tone, full file operations enabled"
        },
        {
            "mode": "task",
            "phase": "execution",
            "description": "Concise output, full capabilities available"
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. Mode: {scenario['mode']:12} | Phase: {scenario['phase']:10}")
        print(f"   → {scenario['description']}")
        print()

    print("KEY SECURITY RULE:")
    print("  Changing mode from 'chat' to 'development' does NOT grant")
    print("  execution permissions. Phase must be explicitly changed via")
    print("  /execute command with user approval.\n")


def demo_backward_compatibility():
    """Show backward compatibility features"""
    print_section("Backward Compatibility")

    print("Default Behavior:")
    print("  • Sessions without conversation_mode → defaults to 'chat'")
    print("  • Invalid mode values → falls back to 'chat'")
    print("  • No breaking changes to existing API\n")

    print("Testing default behavior:")
    default_prompt = get_system_prompt()
    chat_prompt = get_system_prompt("chat")
    print(f"  get_system_prompt() == get_system_prompt('chat'): {default_prompt == chat_prompt}")

    print("\nTesting invalid mode fallback:")
    invalid_prompt = get_system_prompt("invalid_mode_xyz")
    print(f"  get_system_prompt('invalid_mode_xyz') == get_system_prompt('chat'): {invalid_prompt == chat_prompt}")


def demo_usage_example():
    """Show practical usage example"""
    print_section("Usage Example")

    code = '''
from agentos.core.chat.service import ChatService
from agentos.core.chat.models import ConversationMode

# Create chat service
service = ChatService()

# Create session with development mode
session = service.create_session(
    title="Implement Feature X",
    metadata={
        "conversation_mode": ConversationMode.DEVELOPMENT.value,
        "execution_phase": "planning"  # Still safe!
    }
)

# AI will use development mode tone (code-focused)
# But still respects planning phase restrictions

# To enable code execution, explicitly change phase
service.update_execution_phase(
    session.session_id,
    "execution",
    actor="user",
    reason="Approved for implementation"
)
'''

    print("Python API:")
    print(code)


def main():
    """Run all demos"""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║                                                                       ║")
    print("║             AgentOS Mode-Aware Output Templates Demo                 ║")
    print("║                                                                       ║")
    print("║  Task #6: Conversation modes adjust AI communication style           ║")
    print("║           without affecting capability permissions                   ║")
    print("║                                                                       ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")

    try:
        demo_available_modes()
        demo_mode_differences()
        demo_security_independence()
        demo_mode_prompts()
        demo_backward_compatibility()
        demo_usage_example()

        print("\n" + "=" * 80)
        print("  Demo Complete!")
        print("=" * 80)
        print("\nFor more details, see:")
        print("  • docs/adr/ADR-CHAT-MODE-001-Conversation-Mode-Architecture.md")
        print("  • agentos/core/chat/prompts.py")
        print("  • tests/unit/core/chat/test_mode_aware_prompts.py")
        print()

    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
