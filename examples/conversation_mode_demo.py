#!/usr/bin/env python3
"""
Conversation Mode and Execution Phase Demo

This example demonstrates:
1. Creating sessions with different conversation modes
2. Managing execution phases with audit logging
3. Independence between mode and phase
4. Validation and error handling
"""

from agentos.core.chat.service import ChatService
from agentos.core.chat.models import ConversationMode


def main():
    print("=" * 60)
    print("Conversation Mode & Execution Phase Demo")
    print("=" * 60)

    service = ChatService()

    # ========================================
    # Demo 1: Default Values
    # ========================================
    print("\n1. Creating session with defaults:")
    session1 = service.create_session(title="Default Session")
    print(f"   Session ID: {session1.session_id}")
    print(f"   conversation_mode: {session1.metadata['conversation_mode']} (default)")
    print(f"   execution_phase: {session1.metadata['execution_phase']} (safe default)")

    # ========================================
    # Demo 2: Custom Conversation Modes
    # ========================================
    print("\n2. Creating sessions with different conversation modes:")

    modes_examples = [
        ("chat", "General Q&A session"),
        ("discussion", "Team brainstorming"),
        ("plan", "System design planning"),
        ("development", "Active coding session"),
        ("task", "Task-focused work")
    ]

    sessions = {}
    for mode, description in modes_examples:
        session = service.create_session(
            title=f"{mode.capitalize()} Session",
            metadata={"conversation_mode": mode}
        )
        sessions[mode] = session
        print(f"   [{mode}] {description}")
        print(f"       → conversation_mode: {session.metadata['conversation_mode']}")
        print(f"       → execution_phase: {session.metadata['execution_phase']}")

    # ========================================
    # Demo 3: Execution Phase Management
    # ========================================
    print("\n3. Managing execution phases:")

    test_session = service.create_session(title="Phase Test")
    print(f"   Initial phase: {service.get_execution_phase(test_session.session_id)}")

    # Switch to execution phase (with audit)
    print("   Switching to execution phase...")
    service.update_execution_phase(
        test_session.session_id,
        phase="execution",
        actor="demo_user",
        reason="User requested web search capability"
    )
    print(f"   New phase: {service.get_execution_phase(test_session.session_id)}")

    # Switch back to planning
    print("   Switching back to planning phase...")
    service.update_execution_phase(
        test_session.session_id,
        phase="planning",
        actor="demo_user",
        reason="External operations completed"
    )
    print(f"   Final phase: {service.get_execution_phase(test_session.session_id)}")

    # ========================================
    # Demo 4: Independence Verification
    # ========================================
    print("\n4. Verifying independence between mode and phase:")

    independent_session = service.create_session(
        title="Independence Test",
        metadata={
            "conversation_mode": "chat",
            "execution_phase": "planning"
        }
    )

    print(f"   Initial state:")
    print(f"      mode: {service.get_conversation_mode(independent_session.session_id)}")
    print(f"      phase: {service.get_execution_phase(independent_session.session_id)}")

    # Change mode - phase should remain unchanged
    print("   Changing mode to 'development'...")
    service.update_conversation_mode(independent_session.session_id, "development")
    print(f"      mode: {service.get_conversation_mode(independent_session.session_id)}")
    print(f"      phase: {service.get_execution_phase(independent_session.session_id)} (unchanged)")

    # Change phase - mode should remain unchanged
    print("   Changing phase to 'execution'...")
    service.update_execution_phase(
        independent_session.session_id,
        "execution",
        actor="demo_user"
    )
    print(f"      mode: {service.get_conversation_mode(independent_session.session_id)} (unchanged)")
    print(f"      phase: {service.get_execution_phase(independent_session.session_id)}")

    # ========================================
    # Demo 5: Validation
    # ========================================
    print("\n5. Validation examples:")

    validation_session = service.create_session(title="Validation Test")

    # Valid mode update
    print("   Valid mode update (plan):")
    try:
        service.update_conversation_mode(validation_session.session_id, "plan")
        print("      ✓ Success")
    except ValueError as e:
        print(f"      ✗ Error: {e}")

    # Invalid mode update
    print("   Invalid mode update (invalid_mode):")
    try:
        service.update_conversation_mode(validation_session.session_id, "invalid_mode")
        print("      ✓ Success")
    except ValueError as e:
        print(f"      ✗ Error: {e}")

    # Valid phase update
    print("   Valid phase update (execution):")
    try:
        service.update_execution_phase(
            validation_session.session_id,
            "execution",
            actor="demo_user"
        )
        print("      ✓ Success")
    except ValueError as e:
        print(f"      ✗ Error: {e}")

    # Invalid phase update
    print("   Invalid phase update (invalid_phase):")
    try:
        service.update_execution_phase(
            validation_session.session_id,
            "invalid_phase",
            actor="demo_user"
        )
        print("      ✓ Success")
    except ValueError as e:
        print(f"      ✗ Error: {e}")

    # ========================================
    # Demo 6: All Valid Combinations
    # ========================================
    print("\n6. All valid mode/phase combinations:")
    print("   Creating sessions with all combinations...")

    modes = [m.value for m in ConversationMode]
    phases = ["planning", "execution"]

    print(f"\n   {'Mode':<15} {'Phase':<15} Status")
    print(f"   {'-'*15} {'-'*15} ------")

    for mode in modes:
        for phase in phases:
            try:
                session = service.create_session(
                    title=f"{mode}/{phase}",
                    metadata={
                        "conversation_mode": mode,
                        "execution_phase": phase
                    }
                )
                print(f"   {mode:<15} {phase:<15} ✓")
            except Exception as e:
                print(f"   {mode:<15} {phase:<15} ✗ {e}")

    # ========================================
    # Demo 7: Real-World Scenario
    # ========================================
    print("\n7. Real-world scenario: Research & Development session:")

    # Start with planning mode (brainstorming)
    rd_session = service.create_session(
        title="Research: AI Agent Architecture",
        metadata={
            "conversation_mode": "discussion",
            "execution_phase": "planning"
        }
    )
    print(f"   Step 1: Brainstorming phase")
    print(f"      mode: {service.get_conversation_mode(rd_session.session_id)}")
    print(f"      phase: {service.get_execution_phase(rd_session.session_id)}")

    # User wants to search for papers - enable execution
    print(f"\n   Step 2: User requests web search")
    service.update_execution_phase(
        rd_session.session_id,
        "execution",
        actor="user",
        reason="Need to search for research papers"
    )
    print(f"      phase: {service.get_execution_phase(rd_session.session_id)} (enabled)")

    # Search complete, switch to development mode
    print(f"\n   Step 3: Moving to implementation")
    service.update_conversation_mode(rd_session.session_id, "development")
    print(f"      mode: {service.get_conversation_mode(rd_session.session_id)}")
    print(f"      phase: {service.get_execution_phase(rd_session.session_id)} (still enabled)")

    # Disable external ops for coding phase
    print(f"\n   Step 4: Disable external ops for coding")
    service.update_execution_phase(
        rd_session.session_id,
        "planning",
        actor="user",
        reason="Focus on implementation without distractions"
    )
    print(f"      mode: {service.get_conversation_mode(rd_session.session_id)} (unchanged)")
    print(f"      phase: {service.get_execution_phase(rd_session.session_id)} (disabled)")

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. conversation_mode and execution_phase are independent")
    print("2. Mode affects UI/UX, phase affects security")
    print("3. Phase changes are audited, mode changes are not")
    print("4. Always use safe defaults (mode: chat, phase: planning)")
    print("5. Validate all inputs before updating")


if __name__ == "__main__":
    main()
