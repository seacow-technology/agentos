"""Example integrations demonstrating CommunicationOS security features.

This module provides complete examples of how to use the security system
in different scenarios.

Examples:
1. Basic security policy setup
2. Multi-channel with different security levels
3. Admin token management
4. Violation monitoring
5. Remote exposure handling
"""

import asyncio
import logging
from datetime import datetime, timezone

from agentos.communicationos import (
    InboundMessage,
    MessageBus,
    MessageType,
    OutboundMessage,
    PolicyEnforcer,
    ProcessingContext,
    SecurityMode,
    SecurityPolicy,
    generate_admin_token,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example 1: Basic Security Setup
# ================================

def example_basic_security():
    """Example 1: Basic security policy setup with default restrictions."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Security Setup")
    print("=" * 60)

    # Create default policy (most restrictive)
    policy = SecurityPolicy.default_policy()

    print("\nDefault Policy Configuration:")
    print(f"  Mode: {policy.mode.value}")
    print(f"  Chat Only: {policy.chat_only}")
    print(f"  Allow Execute: {policy.allow_execute}")
    print(f"  Allowed Commands: {policy.allowed_commands}")
    print(f"  Rate Limit: {policy.rate_limit_per_minute} req/min")

    # Test command validation
    print("\nCommand Validation Tests:")
    test_commands = [
        "/session new",
        "/help",
        "/execute script.sh",
        "/admin delete",
    ]

    for cmd in test_commands:
        allowed = policy.is_command_allowed(cmd)
        status = "✓ ALLOWED" if allowed else "✗ BLOCKED"
        print(f"  {cmd:30s} -> {status}")


# Example 2: Multi-Channel Security
# ==================================

async def example_multi_channel_security():
    """Example 2: Different security policies for different channels."""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Channel Security")
    print("=" * 60)

    # Create policies
    public_policy = SecurityPolicy(
        mode=SecurityMode.CHAT_ONLY,
        chat_only=True,
        allow_execute=False,
        allowed_commands=["/help", "/session"],
        rate_limit_per_minute=10,
    )

    internal_policy = SecurityPolicy(
        mode=SecurityMode.CHAT_EXEC_RESTRICTED,
        chat_only=False,
        allow_execute=True,
        allowed_commands=["/help", "/session", "/status", "/execute"],
        rate_limit_per_minute=60,
    )

    # Setup enforcer
    enforcer = PolicyEnforcer(default_policy=public_policy)
    enforcer.set_channel_policy("slack_internal", internal_policy)

    print("\nChannel Policies:")
    print("  Public Channels (default):")
    print(f"    Mode: {public_policy.mode.value}")
    print(f"    Execute: {public_policy.allow_execute}")
    print(f"    Commands: {public_policy.allowed_commands}")

    print("\n  Internal Channel (slack_internal):")
    print(f"    Mode: {internal_policy.mode.value}")
    print(f"    Execute: {internal_policy.allow_execute}")
    print(f"    Commands: {internal_policy.allowed_commands}")

    # Test messages
    print("\nMessage Processing Tests:")

    # Test 1: Public channel with execute command (should be blocked)
    public_msg = InboundMessage(
        channel_id="whatsapp_public",
        user_key="user_123",
        conversation_key="conv_123",
        message_id="msg_1",
        timestamp=datetime.now(timezone.utc),
        type=MessageType.TEXT,
        text="/execute dangerous.sh",
    )

    context = ProcessingContext(
        message_id="msg_1",
        channel_id="whatsapp_public",
        metadata={},
    )

    result = await enforcer.process_inbound(public_msg, context)
    print(f"\n  Public channel execute: {result.status.value}")
    if result.error:
        print(f"    Error: {result.error}")

    # Test 2: Internal channel with execute command (should be allowed)
    internal_msg = InboundMessage(
        channel_id="slack_internal",
        user_key="admin_001",
        conversation_key="thread_456",
        message_id="msg_2",
        timestamp=datetime.now(timezone.utc),
        type=MessageType.TEXT,
        text="/execute safe_script.sh",
    )

    context = ProcessingContext(
        message_id="msg_2",
        channel_id="slack_internal",
        metadata={},
    )

    result = await enforcer.process_inbound(internal_msg, context)
    print(f"\n  Internal channel execute: {result.status.value}")


# Example 3: Admin Token Management
# ==================================

def example_admin_tokens():
    """Example 3: Admin token generation and validation."""
    print("\n" + "=" * 60)
    print("Example 3: Admin Token Management")
    print("=" * 60)

    # Generate admin token
    admin_token, token_hash = generate_admin_token()

    print("\nGenerated Admin Token:")
    print(f"  Token (save securely): {admin_token[:20]}...{admin_token[-10:]}")
    print(f"  Hash (store in config): {token_hash[:20]}...{token_hash[-10:]}")

    # Create policy with admin token requirement
    policy = SecurityPolicy(
        mode=SecurityMode.CHAT_EXEC_RESTRICTED,
        allow_execute=True,
        require_admin_token=True,
        admin_token_hash=token_hash,
        allowed_commands=["/help", "/session", "/execute"],
    )

    print("\nToken Validation Tests:")

    # Test valid token
    is_valid = policy.validate_admin_token(admin_token)
    print(f"  Valid token: {'✓ PASS' if is_valid else '✗ FAIL'}")

    # Test invalid token
    is_valid = policy.validate_admin_token("wrong_token")
    print(f"  Invalid token: {'✗ FAIL' if not is_valid else '✓ PASS (should fail)'}")

    # Test missing token
    is_valid = policy.validate_admin_token(None)
    print(f"  Missing token: {'✗ FAIL' if not is_valid else '✓ PASS (should fail)'}")


# Example 4: Violation Monitoring
# ================================

async def example_violation_monitoring():
    """Example 4: Monitoring and querying security violations."""
    print("\n" + "=" * 60)
    print("Example 4: Violation Monitoring")
    print("=" * 60)

    # Setup enforcer
    policy = SecurityPolicy.default_policy()
    enforcer = PolicyEnforcer(default_policy=policy)

    print("\nSimulating security violations...")

    # Simulate various violations
    test_cases = [
        {
            "channel": "whatsapp_001",
            "user": "user_123",
            "text": "/execute hack.sh",
            "expected": "blocked",
        },
        {
            "channel": "telegram_001",
            "user": "user_456",
            "text": "/admin delete_all",
            "expected": "blocked",
        },
        {
            "channel": "whatsapp_001",
            "user": "user_789",
            "text": "/session new",
            "expected": "allowed",
        },
    ]

    for i, test in enumerate(test_cases):
        msg = InboundMessage(
            channel_id=test["channel"],
            user_key=test["user"],
            conversation_key=f"conv_{i}",
            message_id=f"msg_{i}",
            timestamp=datetime.now(timezone.utc),
            type=MessageType.TEXT,
            text=test["text"],
        )

        context = ProcessingContext(
            message_id=f"msg_{i}",
            channel_id=test["channel"],
            metadata={},
        )

        result = await enforcer.process_inbound(msg, context)
        actual = "blocked" if result.status.value == "reject" else "allowed"

        status = "✓" if actual == test["expected"] else "✗"
        print(f"\n  {status} Test {i+1}:")
        print(f"    Command: {test['text']}")
        print(f"    Expected: {test['expected']}")
        print(f"    Actual: {actual}")

    # Query violations
    print("\n\nViolation Summary:")
    violations = enforcer.get_violations()
    print(f"  Total violations: {len(violations)}")

    for violation in violations:
        print(f"\n  Violation:")
        print(f"    Type: {violation['violation_type']}")
        print(f"    Channel: {violation['channel_id']}")
        print(f"    User: {violation['user_key']}")
        print(f"    Command: {violation.get('command', 'N/A')}")

    # Get statistics
    stats = enforcer.get_stats()
    print("\n\nSecurity Statistics:")
    print(f"  Total violations: {stats['total_violations']}")
    print(f"  Blocked count: {stats['blocked_count']}")
    print(f"  By type: {stats['by_type']}")
    print(f"  By channel: {stats['by_channel']}")


# Example 5: Remote Exposure Handling
# ====================================

def example_remote_exposure():
    """Example 5: Detecting and handling remote exposure."""
    print("\n" + "=" * 60)
    print("Example 5: Remote Exposure Handling")
    print("=" * 60)

    from agentos.communicationos.security import RemoteExposureDetector

    # Check if remote exposed
    is_remote = RemoteExposureDetector.is_remote_exposed()

    print(f"\nRemote Exposure Status: {'YES' if is_remote else 'NO'}")

    if is_remote:
        print("\n" + RemoteExposureDetector.get_exposure_warning())

        print("\nRecommended Actions:")
        print("  1. Use CHAT_ONLY mode for all public channels")
        print("  2. Enable admin token validation")
        print("  3. Set conservative rate limits")
        print("  4. Monitor violation logs regularly")
        print("  5. Use webhook signature validation")
    else:
        print("\nSystem appears to be running locally.")
        print("Enhanced security measures may not be necessary.")

    # Create appropriate policy based on exposure
    if is_remote:
        policy = SecurityPolicy(
            mode=SecurityMode.CHAT_ONLY,
            chat_only=True,
            allow_execute=False,
            allowed_commands=["/help", "/session"],
            rate_limit_per_minute=10,
            block_on_violation=True,
        )
        print("\n✓ Created strict policy for remote environment")
    else:
        policy = SecurityPolicy(
            mode=SecurityMode.CHAT_EXEC_RESTRICTED,
            chat_only=False,
            allow_execute=True,
            allowed_commands=["/help", "/session", "/execute", "/status"],
            rate_limit_per_minute=60,
            block_on_violation=True,
        )
        print("\n✓ Created permissive policy for local environment")

    print(f"\nPolicy Configuration:")
    print(f"  Mode: {policy.mode.value}")
    print(f"  Allow Execute: {policy.allow_execute}")
    print(f"  Rate Limit: {policy.rate_limit_per_minute} req/min")


# Example 6: Complete Integration
# ================================

async def example_complete_integration():
    """Example 6: Complete integration with MessageBus."""
    print("\n" + "=" * 60)
    print("Example 6: Complete MessageBus Integration")
    print("=" * 60)

    # Create message bus
    bus = MessageBus()

    # Setup security
    policy = SecurityPolicy.default_policy()
    enforcer = PolicyEnforcer(default_policy=policy, enable_remote_warnings=True)
    bus.add_middleware(enforcer)

    print("\n✓ MessageBus configured with security enforcement")
    print(f"  Default Policy: {policy.mode.value}")
    print(f"  Remote Warnings: Enabled")

    # Simulate message flow
    print("\n\nSimulating message flow:")

    # Create test message
    msg = InboundMessage(
        channel_id="test_channel",
        user_key="test_user",
        conversation_key="test_conv",
        message_id="msg_test",
        timestamp=datetime.now(timezone.utc),
        type=MessageType.TEXT,
        text="Hello, AgentOS!",
    )

    print(f"\n  Processing message: '{msg.text}'")

    # Process through bus
    result = await bus.process_inbound(msg)

    print(f"  Result: {result.status.value}")
    print(f"  Security policy applied: {result.metadata.get('security_policy', {}).get('mode')}")

    print("\n✓ Complete integration successful")


# Main execution
# ==============

def main():
    """Run all examples."""
    print("\n")
    print("=" * 60)
    print("CommunicationOS Security Examples")
    print("=" * 60)

    # Synchronous examples
    example_basic_security()
    example_admin_tokens()
    example_remote_exposure()

    # Asynchronous examples
    print("\n\nRunning async examples...")
    asyncio.run(example_multi_channel_security())
    asyncio.run(example_violation_monitoring())
    asyncio.run(example_complete_integration())

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
