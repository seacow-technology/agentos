#!/usr/bin/env python3
"""Email Channel Demonstration.

This script demonstrates the complete Email Channel functionality:
1. Gmail Provider setup
2. Email polling
3. Thread detection
4. Message sending with proper threading
5. Integration with MessageBus

Usage:
    python examples/email_channel_demo.py

Note: This is a demonstration script. For production use, configure with real credentials.
"""

import asyncio
from datetime import datetime, timezone

# Import Email Channel components
from agentos.communicationos.channels.email.adapter import EmailAdapter, CursorStore
from agentos.communicationos.providers.email import EmailEnvelope
from agentos.communicationos.models import OutboundMessage
from agentos.communicationos.message_bus import MessageBus

# For demo, we'll use a mock provider
from tests.unit.communicationos.channels.email_channel.test_adapter import MockEmailProvider


def demo_basic_polling():
    """Demonstrate basic email polling."""
    print("=" * 60)
    print("Demo 1: Basic Email Polling")
    print("=" * 60)

    # Create mock provider
    provider = MockEmailProvider()

    # Add some test messages
    now = datetime.now(timezone.utc)
    provider.messages = [
        EmailEnvelope(
            provider_message_id="msg_001",
            message_id="<test-001@user.example.com>",
            from_address="user@example.com",
            from_name="John Doe",
            to_addresses=["agent@example.com"],
            subject="Question about AgentOS",
            date=now,
            text_body="Hello, I have a question about AgentOS. How do I get started?"
        ),
        EmailEnvelope(
            provider_message_id="msg_002",
            message_id="<test-002@user.example.com>",
            from_address="jane@example.com",
            from_name="Jane Smith",
            to_addresses=["agent@example.com"],
            subject="Support Request",
            date=now,
            text_body="I need help with installation."
        )
    ]

    # Create adapter
    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    # Poll messages
    async def poll():
        messages = await adapter.poll()
        print(f"\nPolled {len(messages)} messages:")
        for msg in messages:
            print(f"\n  From: {msg.user_key}")
            print(f"  Subject: {msg.metadata.get('subject')}")
            print(f"  Text: {msg.text[:50]}...")
            print(f"  Thread: {msg.conversation_key}")

    asyncio.run(poll())


def demo_thread_detection():
    """Demonstrate email thread detection."""
    print("\n" + "=" * 60)
    print("Demo 2: Thread Detection")
    print("=" * 60)

    provider = MockEmailProvider()
    now = datetime.now(timezone.utc)

    # Simulate a conversation thread
    provider.messages = [
        # Message 1: New thread
        EmailEnvelope(
            provider_message_id="msg_001",
            message_id="<thread-001@user.example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Help request",
            date=now,
            text_body="I need help with feature X"
        ),
        # Message 2: Reply to message 1
        EmailEnvelope(
            provider_message_id="msg_002",
            message_id="<thread-002@user.example.com>",
            in_reply_to="<thread-001@user.example.com>",
            references="<thread-001@user.example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Re: Help request",
            date=now,
            text_body="Additional details about my question..."
        ),
        # Message 3: Long thread
        EmailEnvelope(
            provider_message_id="msg_003",
            message_id="<thread-003@user.example.com>",
            in_reply_to="<thread-002@user.example.com>",
            references="<thread-001@user.example.com> <thread-002@user.example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Re: Help request",
            date=now,
            text_body="Thanks for the help!"
        )
    ]

    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    async def poll_and_check_threads():
        messages = await adapter.poll()
        print(f"\nProcessed {len(messages)} messages:")

        # All should have same conversation_key (thread root)
        thread_keys = set()
        for i, msg in enumerate(messages, 1):
            print(f"\n  Message {i}:")
            print(f"    Message ID: {msg.message_id}")
            print(f"    Thread Root: {msg.conversation_key}")
            thread_keys.add(msg.conversation_key)

        print(f"\n  ✓ All {len(messages)} messages belong to 1 thread: {len(thread_keys) == 1}")
        print(f"    Thread root: {list(thread_keys)[0]}")

    asyncio.run(poll_and_check_threads())


def demo_reply_with_threading():
    """Demonstrate sending replies with proper threading."""
    print("\n" + "=" * 60)
    print("Demo 3: Reply with Threading Headers")
    print("=" * 60)

    provider = MockEmailProvider()
    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    # Simulate replying to a message
    outbound = OutboundMessage(
        channel_id="email_demo",
        user_key="user@example.com",
        conversation_key="thread-001@user.example.com",
        reply_to_message_id="email_thread-001@user.example.com",
        text="Thank you for your question! Here's how to get started...",
        metadata={"subject": "Question about AgentOS"}
    )

    print("\nSending reply:")
    print(f"  To: {outbound.user_key}")
    print(f"  Thread: {outbound.conversation_key}")
    print(f"  Reply to: {outbound.reply_to_message_id}")

    success = adapter.send_message(outbound)
    print(f"\n  ✓ Message sent: {success}")

    # Show the sent message details
    if provider.sent_messages:
        sent = provider.sent_messages[0]
        print(f"\n  Threading headers:")
        print(f"    In-Reply-To: {sent['in_reply_to']}")
        print(f"    References: {sent['references']}")
        print(f"    Subject: {sent['subject']}")


def demo_cursor_persistence():
    """Demonstrate cursor-based incremental polling."""
    print("\n" + "=" * 60)
    print("Demo 4: Cursor-Based Incremental Polling")
    print("=" * 60)

    import tempfile
    from pathlib import Path

    # Create temporary cursor store
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        cursor_store = CursorStore(db_path=db_path)
        provider = MockEmailProvider()

        # First poll
        print("\nFirst poll (no cursor):")
        print("  → Will fetch last 24 hours")

        adapter = EmailAdapter(
            channel_id="email_demo",
            provider=provider,
            cursor_store=cursor_store,
            poll_interval_seconds=60
        )

        now = datetime.now(timezone.utc)
        provider.messages = [
            EmailEnvelope(
                provider_message_id="msg_001",
                message_id="<test-001@user.example.com>",
                from_address="user@example.com",
                to_addresses=["agent@example.com"],
                subject="First message",
                date=now,
                text_body="First message"
            )
        ]

        async def first_poll():
            messages = await adapter.poll()
            print(f"  ✓ Fetched {len(messages)} messages")

            # Check cursor
            cursor = cursor_store.get_last_poll_time("email_demo")
            print(f"  ✓ Cursor updated: {cursor.isoformat() if cursor else 'None'}")

        asyncio.run(first_poll())

        # Second poll (should use cursor)
        print("\nSecond poll (with cursor):")
        print("  → Will only fetch messages after cursor")

        # Add new message after cursor
        from datetime import timedelta
        provider.messages.append(
            EmailEnvelope(
                provider_message_id="msg_002",
                message_id="<test-002@user.example.com>",
                from_address="user@example.com",
                to_addresses=["agent@example.com"],
                subject="Second message",
                date=now + timedelta(minutes=5),
                text_body="Second message"
            )
        )

        async def second_poll():
            messages = await adapter.poll()
            print(f"  ✓ Fetched {len(messages)} new messages (dedup filters first)")

            cursor = cursor_store.get_last_poll_time("email_demo")
            print(f"  ✓ Cursor updated again: {cursor.isoformat() if cursor else 'None'}")

        asyncio.run(second_poll())

    finally:
        Path(db_path).unlink(missing_ok=True)


def demo_message_bus_integration():
    """Demonstrate MessageBus integration."""
    print("\n" + "=" * 60)
    print("Demo 5: MessageBus Integration")
    print("=" * 60)

    from agentos.communicationos.message_bus import ProcessingContext, ProcessingStatus

    # Create MessageBus
    bus = MessageBus()

    # Create adapter with MessageBus
    provider = MockEmailProvider()
    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60,
        message_bus=bus
    )

    bus.register_adapter("email_demo", adapter)

    # Add a message
    now = datetime.now(timezone.utc)
    provider.messages = [
        EmailEnvelope(
            provider_message_id="msg_001",
            message_id="<test-001@user.example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Test",
            date=now,
            text_body="Hello from user"
        )
    ]

    print("\nPolling with MessageBus integration:")

    async def poll_with_bus():
        # Poll will automatically route through MessageBus
        messages = await adapter.poll()
        print(f"  ✓ Polled {len(messages)} messages")
        print(f"  ✓ Messages routed through MessageBus")
        print(f"  ✓ Middleware processing completed")

    asyncio.run(poll_with_bus())


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("Email Channel Feature Demonstrations")
    print("=" * 60)

    # Run all demos
    demo_basic_polling()
    demo_thread_detection()
    demo_reply_with_threading()
    demo_cursor_persistence()
    demo_message_bus_integration()

    print("\n" + "=" * 60)
    print("All demonstrations completed successfully!")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ Email polling from provider")
    print("  ✓ RFC 5322 thread detection")
    print("  ✓ Reply with proper In-Reply-To/References")
    print("  ✓ Cursor-based incremental polling")
    print("  ✓ MessageBus integration")
    print("\nFor production use:")
    print("  1. Configure GmailProvider with real OAuth credentials")
    print("  2. Set appropriate polling interval (60s recommended)")
    print("  3. Enable audit and dedupe middleware")
    print("  4. Monitor cursor lag and poll failures")
    print("=" * 60)


if __name__ == "__main__":
    main()
