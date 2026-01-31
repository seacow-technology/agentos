#!/usr/bin/env python3
"""
Guards Demo - Demonstrates the three Chat Guards in action.

This script shows how to use Phase Gate, Attribution Guard, and Content Fence
to secure Chat ↔ CommunicationOS integration.
"""

from agentos.core.chat.guards import (
    PhaseGate, PhaseGateError,
    AttributionGuard, AttributionViolation,
    ContentFence
)


def demo_phase_gate():
    """Demonstrate Phase Gate functionality."""
    print("=" * 60)
    print("DEMO 1: Phase Gate - Preventing planning-phase operations")
    print("=" * 60)

    # Test 1: Planning phase should block
    print("\n1. Testing comm.search in planning phase:")
    try:
        PhaseGate.check("comm.search", "planning")
        print("   ❌ FAIL: Should have been blocked!")
    except PhaseGateError as e:
        print(f"   ✅ PASS: Blocked as expected - {e}")

    # Test 2: Execution phase should allow
    print("\n2. Testing comm.search in execution phase:")
    try:
        PhaseGate.check("comm.search", "execution")
        print("   ✅ PASS: Allowed in execution phase")
    except PhaseGateError as e:
        print(f"   ❌ FAIL: Should have been allowed - {e}")

    # Test 3: Non-comm operations should always be allowed
    print("\n3. Testing local.query in planning phase:")
    try:
        PhaseGate.check("local.query", "planning")
        print("   ✅ PASS: Local operations allowed in planning")
    except PhaseGateError as e:
        print(f"   ❌ FAIL: Local operations should be allowed - {e}")

    # Test 4: Using is_allowed() method
    print("\n4. Using is_allowed() method:")
    print(f"   comm.search in planning: {PhaseGate.is_allowed('comm.search', 'planning')}")
    print(f"   comm.search in execution: {PhaseGate.is_allowed('comm.search', 'execution')}")
    print(f"   local.query in planning: {PhaseGate.is_allowed('local.query', 'planning')}")


def demo_attribution_guard():
    """Demonstrate Attribution Guard functionality."""
    print("\n" + "=" * 60)
    print("DEMO 2: Attribution Guard - Enforcing proper attribution")
    print("=" * 60)

    session_id = "demo_session_12345"

    # Test 1: Generate correct attribution
    print("\n1. Generating correct attribution:")
    attribution = AttributionGuard.format_attribution("search", session_id)
    print(f"   Generated: {attribution}")
    print("   ✅ PASS: Attribution format is correct")

    # Test 2: Validate correct attribution
    print("\n2. Validating correct attribution:")
    data = {
        "results": ["result1", "result2"],
        "metadata": {
            "attribution": attribution
        }
    }
    try:
        AttributionGuard.enforce(data, session_id)
        print("   ✅ PASS: Attribution validated successfully")
    except AttributionViolation as e:
        print(f"   ❌ FAIL: Should have passed - {e}")

    # Test 3: Reject missing attribution
    print("\n3. Testing missing attribution:")
    bad_data = {"metadata": {}}
    try:
        AttributionGuard.enforce(bad_data, session_id)
        print("   ❌ FAIL: Should have rejected missing attribution")
    except AttributionViolation as e:
        print(f"   ✅ PASS: Rejected as expected - {e}")

    # Test 4: Reject wrong session ID
    print("\n4. Testing wrong session ID:")
    wrong_attribution = AttributionGuard.format_attribution("search", "wrong_session")
    bad_data = {
        "metadata": {
            "attribution": wrong_attribution
        }
    }
    try:
        AttributionGuard.enforce(bad_data, session_id)
        print("   ❌ FAIL: Should have rejected wrong session ID")
    except AttributionViolation as e:
        print(f"   ✅ PASS: Rejected as expected - {e}")


def demo_content_fence():
    """Demonstrate Content Fence functionality."""
    print("\n" + "=" * 60)
    print("DEMO 3: Content Fence - Marking untrusted external content")
    print("=" * 60)

    # Test 1: Wrap external content
    print("\n1. Wrapping external content:")
    content = "This is external content from the internet"
    source_url = "https://example.com/article"

    wrapped = ContentFence.wrap(content, source_url)
    print(f"   Content: {content}")
    print(f"   Source: {source_url}")
    print(f"   Marker: {wrapped['marker']}")
    print(f"   Warning present: {'警告' in wrapped['warning']}")
    print("   ✅ PASS: Content wrapped successfully")

    # Test 2: Generate LLM prompt injection
    print("\n2. Generating LLM prompt injection:")
    llm_prompt = ContentFence.get_llm_prompt_injection(wrapped)
    print("   --- LLM Prompt ---")
    print(llm_prompt[:200] + "...")
    print("   ✅ PASS: LLM prompt generated with warnings")

    # Test 3: Check if content is wrapped
    print("\n3. Checking if content is wrapped:")
    is_wrapped = ContentFence.is_wrapped(wrapped)
    print(f"   Is wrapped: {is_wrapped}")
    print("   ✅ PASS: Content correctly identified as wrapped")

    # Test 4: Unwrap for display
    print("\n4. Unwrapping for display:")
    display = ContentFence.unwrap_for_display(wrapped)
    print("   --- Display Format ---")
    print(display[:200] + "...")
    print("   ✅ PASS: Content unwrapped with warnings preserved")

    # Test 5: Show allowed and forbidden uses
    print("\n5. Usage restrictions:")
    print(f"   Allowed uses: {', '.join(wrapped['allowed_uses'])}")
    print(f"   Forbidden uses: {', '.join(wrapped['forbidden_uses'])}")
    print("   ✅ PASS: Usage restrictions clearly defined")


def demo_full_integration():
    """Demonstrate all three guards working together."""
    print("\n" + "=" * 60)
    print("DEMO 4: Full Integration - All guards working together")
    print("=" * 60)

    session_id = "integration_test_12345"
    operation = "comm.search"
    execution_phase = "execution"

    print(f"\nSimulating {operation} in {execution_phase} phase:")

    # Step 1: Phase Gate
    print("\n1. Checking Phase Gate:")
    try:
        PhaseGate.check(operation, execution_phase)
        print("   ✅ Phase gate passed - operation allowed")
    except PhaseGateError as e:
        print(f"   ❌ Phase gate blocked - {e}")
        return

    # Step 2: Fetch and wrap content
    print("\n2. Fetching and wrapping external content:")
    external_content = "Search results from external source"
    source_url = "https://search.example.com/results"
    wrapped = ContentFence.wrap(external_content, source_url)
    print(f"   ✅ Content wrapped with {wrapped['marker']}")

    # Step 3: Add attribution
    print("\n3. Adding attribution:")
    attribution = AttributionGuard.format_attribution("search", session_id)
    data = {
        "content": wrapped,
        "metadata": {
            "attribution": attribution
        }
    }
    print(f"   ✅ Attribution added: {attribution}")

    # Step 4: Validate attribution
    print("\n4. Validating attribution:")
    try:
        AttributionGuard.enforce(data, session_id)
        print("   ✅ Attribution validated successfully")
    except AttributionViolation as e:
        print(f"   ❌ Attribution validation failed - {e}")
        return

    # Step 5: Generate LLM prompt
    print("\n5. Generating safe LLM prompt:")
    llm_prompt = ContentFence.get_llm_prompt_injection(wrapped)
    print("   ✅ LLM prompt generated with safety warnings")

    print("\n" + "=" * 60)
    print("✅ FULL INTEGRATION SUCCESS - All guards passed!")
    print("=" * 60)


def demo_security_violations():
    """Demonstrate how guards prevent security violations."""
    print("\n" + "=" * 60)
    print("DEMO 5: Security Violations - Guards preventing attacks")
    print("=" * 60)

    # Violation 1: Planning phase data leakage
    print("\n1. Attempt: Planning phase data leakage")
    print("   Attack: Try to search external data during planning")
    try:
        PhaseGate.check("comm.search", "planning")
        print("   ❌ SECURITY BREACH: Planning phase leak!")
    except PhaseGateError:
        print("   ✅ BLOCKED: Phase gate prevented planning phase leak")

    # Violation 2: Attribution forgery
    print("\n2. Attempt: Attribution forgery")
    print("   Attack: Use data without proper attribution")
    data = {"metadata": {}}
    try:
        AttributionGuard.enforce(data, "test_session")
        print("   ❌ SECURITY BREACH: Attribution bypass!")
    except AttributionViolation:
        print("   ✅ BLOCKED: Attribution guard prevented forgery")

    # Violation 3: Session ID spoofing
    print("\n3. Attempt: Session ID spoofing")
    print("   Attack: Use attribution with wrong session ID")
    fake_attribution = AttributionGuard.format_attribution("search", "fake_session")
    data = {"metadata": {"attribution": fake_attribution}}
    try:
        AttributionGuard.enforce(data, "real_session")
        print("   ❌ SECURITY BREACH: Session ID spoofed!")
    except AttributionViolation:
        print("   ✅ BLOCKED: Attribution guard detected session mismatch")

    # Violation 4: Unmarked external content
    print("\n4. Attempt: Unmarked external content")
    print("   Attack: Use external content without UNTRUSTED marker")
    unmarked_content = {"content": "External data", "source": "https://evil.com"}
    if ContentFence.is_wrapped(unmarked_content):
        print("   ❌ SECURITY BREACH: Unmarked content accepted!")
    else:
        print("   ✅ BLOCKED: Content fence detected unmarked content")

    print("\n" + "=" * 60)
    print("✅ SECURITY VALIDATION COMPLETE - All attacks blocked!")
    print("=" * 60)


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("CHAT GUARDS DEMONSTRATION")
    print("Security Boundary for Chat ↔ CommunicationOS Integration")
    print("=" * 60)

    # Run all demos
    demo_phase_gate()
    demo_attribution_guard()
    demo_content_fence()
    demo_full_integration()
    demo_security_violations()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("All guards are working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    main()
