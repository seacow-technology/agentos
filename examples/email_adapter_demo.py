#!/usr/bin/env python3
"""Email Adapter Demo Script.

This script demonstrates how to use the Email Channel Adapter with a mock provider.
For production use, replace MockProvider with a real provider (Gmail, Outlook, SMTP/IMAP).

Usage:
    python3 examples/email_adapter_demo.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.communicationos.channels.email import EmailAdapter, CursorStore
from agentos.communicationos.providers.email import (
    EmailEnvelope,
    ValidationResult,
    SendResult,
)
from agentos.communicationos.models import OutboundMessage


class MockEmailProvider:
    """Mock email provider for demonstration purposes."""

    def __init__(self):
        """Initialize mock provider."""
        self.messages = []
        self.sent_messages = []
        print("[Provider] Mock email provider initialized")

    def validate_credentials(self) -> ValidationResult:
        """Validate credentials (always returns success for demo)."""
        print("[Provider] Validating credentials...")
        return ValidationResult(valid=True, metadata={"provider": "mock"})

    def fetch_messages(self, folder="INBOX", since=None, limit=100):
        """Fetch messages (returns mock messages)."""
        print(f"[Provider] Fetching messages from {folder} (since={since}, limit={limit})")
        return self.messages

    def send_message(
        self,
        to_addresses,
        subject,
        text_body=None,
        html_body=None,
        in_reply_to=None,
        references=None,
        cc_addresses=None,
        attachments=None
    ):
        """Send message (stores in mock list)."""
        message_id = f"<sent-{len(self.sent_messages) + 1}@mock.example.com>"
        self.sent_messages.append({
            "to": to_addresses,
            "subject": subject,
            "text": text_body,
            "in_reply_to": in_reply_to,
            "references": references,
        })
        print(f"[Provider] Sent message: to={to_addresses}, subject={subject}")
        return SendResult(
            success=True,
            provider_message_id=f"sent-{len(self.sent_messages)}",
            message_id=message_id
        )

    def mark_as_read(self, provider_message_id):
        """Mark message as read."""
        return True


async def demo_basic_polling():
    """Demonstrate basic polling functionality."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Polling")
    print("="*70)

    # Create mock provider
    provider = MockEmailProvider()

    # Add some mock messages
    now = datetime.now(timezone.utc)
    provider.messages = [
        EmailEnvelope(
            provider_message_id="mock-001",
            message_id="<test-001@user.example.com>",
            from_address="user@example.com",
            from_name="John Doe",
            to_addresses=["agent@example.com"],
            subject="Question about AgentOS",
            date=now,
            text_body="Hello, I have a question about AgentOS features.",
        ),
        EmailEnvelope(
            provider_message_id="mock-002",
            message_id="<test-002@user.example.com>",
            in_reply_to="<test-001@user.example.com>",
            references="<test-001@user.example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Re: Question about AgentOS",
            date=now,
            text_body="Following up on my previous question...",
        ),
    ]

    # Create adapter
    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    print("\n[Adapter] Created with channel_id='email_demo'")
    print(f"[Adapter] Poll interval: {adapter.poll_interval_seconds}s")

    # Perform manual poll
    print("\n[Adapter] Polling for messages...")
    messages = await adapter.poll()

    print(f"\n[Results] Fetched {len(messages)} messages:")
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}:")
        print(f"  From: {msg.user_key}")
        print(f"  Subject: {msg.metadata.get('subject')}")
        print(f"  Thread: {msg.conversation_key}")
        print(f"  Message ID: {msg.message_id}")
        print(f"  Text: {msg.text[:50]}...")

    # Verify thread detection
    if len(messages) >= 2:
        print("\n[Thread Detection]")
        print(f"  Message 1 thread: {messages[0].conversation_key}")
        print(f"  Message 2 thread: {messages[1].conversation_key}")
        if messages[0].conversation_key == messages[1].conversation_key:
            print("  ✓ Thread detection working! Both messages in same thread.")
        else:
            print("  ✗ Thread mismatch - check implementation")


async def demo_send_reply():
    """Demonstrate sending a reply with proper threading."""
    print("\n" + "="*70)
    print("DEMO 2: Sending Reply")
    print("="*70)

    provider = MockEmailProvider()
    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    # Create outbound reply message
    reply = OutboundMessage(
        channel_id="email_demo",
        user_key="user@example.com",
        conversation_key="test-001@user.example.com",
        reply_to_message_id="email_test-001@user.example.com",
        text="Thank you for your question! AgentOS provides...",
        metadata={"subject": "Question about AgentOS"}
    )

    print("\n[Adapter] Sending reply...")
    print(f"  To: {reply.user_key}")
    print(f"  Thread: {reply.conversation_key}")
    print(f"  Reply to: {reply.reply_to_message_id}")

    # Send message
    success = adapter.send_message(reply)

    if success:
        print("\n[Result] ✓ Message sent successfully")
        sent = provider.sent_messages[0]
        print(f"  To: {sent['to']}")
        print(f"  Subject: {sent['subject']}")
        print(f"  In-Reply-To: {sent['in_reply_to']}")
        print(f"  References: {sent['references']}")
    else:
        print("\n[Result] ✗ Message send failed")


async def demo_deduplication():
    """Demonstrate message deduplication."""
    print("\n" + "="*70)
    print("DEMO 3: Message Deduplication")
    print("="*70)

    provider = MockEmailProvider()

    now = datetime.now(timezone.utc)
    # Same message in list twice
    message = EmailEnvelope(
        provider_message_id="mock-001",
        message_id="<test-001@user.example.com>",
        from_address="user@example.com",
        to_addresses=["agent@example.com"],
        subject="Test",
        date=now,
        text_body="Test message",
    )
    provider.messages = [message, message]  # Duplicate

    adapter = EmailAdapter(
        channel_id="email_demo",
        provider=provider,
        poll_interval_seconds=60
    )

    print("\n[Provider] Added 2 identical messages (duplicate)")

    # First poll
    print("\n[Adapter] First poll...")
    messages1 = await adapter.poll()
    print(f"[Result] Processed {len(messages1)} messages (expected: 1)")

    # Second poll (same messages)
    print("\n[Adapter] Second poll (same messages)...")
    messages2 = await adapter.poll()
    print(f"[Result] Processed {len(messages2)} messages (expected: 0 - deduplicated)")

    if len(messages1) == 1 and len(messages2) == 0:
        print("\n✓ Deduplication working correctly!")
    else:
        print("\n✗ Deduplication issue detected")


async def demo_cursor_persistence():
    """Demonstrate cursor persistence."""
    print("\n" + "="*70)
    print("DEMO 4: Cursor Persistence")
    print("="*70)

    import tempfile
    db_path = tempfile.mktemp(suffix=".db")
    print(f"\n[CursorStore] Using temp database: {db_path}")

    cursor_store = CursorStore(db_path=db_path)

    # Check initial state
    last_poll = cursor_store.get_last_poll_time("test_channel")
    print(f"[Initial] Last poll time: {last_poll} (expected: None)")

    # Update cursor
    now = datetime.now(timezone.utc)
    cursor_store.update_cursor(
        channel_id="test_channel",
        poll_time=now,
        last_message_id="email_test-123@example.com"
    )
    print(f"\n[Updated] Cursor set to: {now.isoformat()}")

    # Retrieve cursor
    retrieved = cursor_store.get_last_poll_time("test_channel")
    print(f"[Retrieved] Last poll time: {retrieved.isoformat()}")

    # Verify
    if retrieved and abs((retrieved - now).total_seconds()) < 0.01:
        print("\n✓ Cursor persistence working!")
    else:
        print("\n✗ Cursor persistence issue")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


async def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("EMAIL CHANNEL ADAPTER - DEMO SCRIPT")
    print("="*70)
    print("\nThis script demonstrates the Email Channel Adapter functionality")
    print("using a mock email provider.\n")

    try:
        # Run demos
        await demo_basic_polling()
        await demo_send_reply()
        await demo_deduplication()
        await demo_cursor_persistence()

        print("\n" + "="*70)
        print("ALL DEMOS COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nNext steps:")
        print("1. Implement real provider (Gmail, Outlook, or SMTP/IMAP)")
        print("2. Configure credentials in manifest.json")
        print("3. Start polling: adapter.start_polling(use_thread=True)")
        print("4. Integrate with MessageBus for routing")
        print("\nSee ADAPTER_USAGE.md for detailed documentation.")

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
