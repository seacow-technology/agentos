"""Usage examples for CommunicationOS unified message models and commands.

This file demonstrates common usage patterns for InboundMessage, OutboundMessage,
and CommandProcessor.
"""

from datetime import datetime, timezone

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
    Attachment,
    AttachmentType,
    Location,
)
from agentos.communicationos.commands import CommandProcessor, SessionStore


def example_text_message():
    """Example: Basic text message."""
    message = InboundMessage(
        channel_id="whatsapp_business_001",
        user_key="+1234567890",
        conversation_key="+1234567890",
        message_id="wamid.HBgNMTIzNDU2Nzg5MAA=",
        type=MessageType.TEXT,
        text="Hello, how can I help you today?",
    )
    print(f"Received text message: {message.text}")
    return message


def example_image_message():
    """Example: Image message with attachment."""
    attachment = Attachment(
        type=AttachmentType.IMAGE,
        url="https://example.com/media/photo.jpg",
        mime_type="image/jpeg",
        filename="photo.jpg",
        size_bytes=524288,
        metadata={"width": 1920, "height": 1080},
    )

    message = InboundMessage(
        channel_id="telegram_bot_123",
        user_key="user_456",
        conversation_key="chat_789",
        message_id="msg_001",
        type=MessageType.IMAGE,
        text="Check out this photo!",
        attachments=[attachment],
    )
    print(f"Received image: {message.attachments[0].filename}")
    return message


def example_location_message():
    """Example: Location sharing."""
    location = Location(
        latitude=37.7749,
        longitude=-122.4194,
        address="San Francisco, CA 94102",
        name="Golden Gate Bridge",
    )

    message = InboundMessage(
        channel_id="whatsapp_business_001",
        user_key="+1234567890",
        conversation_key="+1234567890",
        message_id="msg_002",
        type=MessageType.LOCATION,
        location=location,
    )
    print(f"Received location: {message.location.name}")
    return message


def example_reply_message():
    """Example: Replying to a message."""
    # Received message
    inbound = InboundMessage(
        channel_id="telegram_bot_123",
        user_key="user_456",
        conversation_key="chat_789",
        message_id="msg_003",
        text="What's the weather today?",
    )

    # Create reply
    outbound = OutboundMessage(
        channel_id=inbound.channel_id,
        user_key=inbound.user_key,
        conversation_key=inbound.conversation_key,
        reply_to_message_id=inbound.message_id,
        type=MessageType.TEXT,
        text="The weather is sunny today with a high of 75°F!",
    )
    print(f"Replying to {inbound.message_id}: {outbound.text}")
    return outbound


def example_file_attachment():
    """Example: Sending a file attachment."""
    attachment = Attachment(
        type=AttachmentType.DOCUMENT,
        url="https://example.com/reports/monthly_report.pdf",
        mime_type="application/pdf",
        filename="monthly_report.pdf",
        size_bytes=1048576,
    )

    message = OutboundMessage(
        channel_id="email_smtp_001",
        user_key="user@example.com",
        conversation_key="thread_123",
        type=MessageType.FILE,
        text="Please find attached the monthly report.",
        attachments=[attachment],
    )
    print(f"Sending file: {message.attachments[0].filename}")
    return message


def example_with_metadata():
    """Example: Message with metadata."""
    message = InboundMessage(
        channel_id="slack_workspace_001",
        user_key="U12345",
        conversation_key="C67890",
        message_id="1234567890.123456",
        text="This is an edited message",
        metadata={
            "reply_to": "1234567889.123456",
            "edited": True,
            "edit_timestamp": "2026-02-01T10:35:00Z",
            "thread_ts": "1234567880.123456",
        },
    )
    print(f"Message metadata: {message.metadata}")
    return message


def example_message_validation():
    """Example: Message validation."""
    # Valid message
    valid_message = InboundMessage(
        channel_id="whatsapp_001",
        user_key="+1234567890",
        conversation_key="chat_123",
        message_id="msg_004",
        type=MessageType.TEXT,
        text="Hello!",
    )
    try:
        valid_message.validate_message_content()
        print("Message validation passed")
    except ValueError as e:
        print(f"Validation error: {e}")

    # Invalid message (TEXT without text content)
    invalid_message = InboundMessage(
        channel_id="whatsapp_001",
        user_key="+1234567890",
        conversation_key="chat_123",
        message_id="msg_005",
        type=MessageType.TEXT,
        text=None,
    )
    try:
        invalid_message.validate_message_content()
        print("Message validation passed")
    except ValueError as e:
        print(f"Validation error: {e}")


def example_json_serialization():
    """Example: JSON serialization."""
    message = InboundMessage(
        channel_id="whatsapp_001",
        user_key="+1234567890",
        conversation_key="chat_123",
        message_id="msg_006",
        text="Hello, world!",
    )

    # Convert to dictionary
    data = message.model_dump()
    print(f"Message as dict: {data}")

    # Convert to JSON string
    json_str = message.model_dump_json()
    print(f"Message as JSON: {json_str}")

    # Parse from dictionary
    restored = InboundMessage(**data)
    print(f"Restored message: {restored.text}")


def example_multi_attachment():
    """Example: Message with multiple attachments."""
    attachments = [
        Attachment(
            type=AttachmentType.IMAGE,
            url="https://example.com/photo1.jpg",
            filename="photo1.jpg",
        ),
        Attachment(
            type=AttachmentType.IMAGE,
            url="https://example.com/photo2.jpg",
            filename="photo2.jpg",
        ),
        Attachment(
            type=AttachmentType.IMAGE,
            url="https://example.com/photo3.jpg",
            filename="photo3.jpg",
        ),
    ]

    message = OutboundMessage(
        channel_id="telegram_bot_123",
        user_key="user_456",
        conversation_key="chat_789",
        type=MessageType.IMAGE,
        text="Here are the photos you requested",
        attachments=attachments,
    )
    print(f"Sending {len(message.attachments)} attachments")
    return message


def example_command_processor():
    """Example: Using CommandProcessor for session management."""
    processor = CommandProcessor()

    # User sends /session new command
    response1 = processor.process_command(
        "/session new",
        channel_id="whatsapp",
        user_key="+1234567890",
        conversation_key="chat_123"
    )
    print(f"Response: {response1.text}")
    session_id = response1.metadata.get("session_id")
    print(f"Created session: {session_id}\n")

    # User sends /session id command
    response2 = processor.process_command(
        "/session id",
        channel_id="whatsapp",
        user_key="+1234567890",
        conversation_key="chat_123"
    )
    print(f"Response: {response2.text}\n")

    # User sends /help command
    response3 = processor.process_command(
        "/help",
        channel_id="whatsapp",
        user_key="+1234567890",
        conversation_key="chat_123"
    )
    print(f"Help response:\n{response3.text}\n")


def example_session_lifecycle():
    """Example: Complete session lifecycle."""
    processor = CommandProcessor()
    channel_id = "whatsapp"
    user_key = "+1234567890"
    conversation_key = "chat_123"

    # 1. Create first session
    print("1. Creating first session...")
    response1 = processor.process_command("/session new", channel_id, user_key, conversation_key)
    session1_id = response1.metadata["session_id"]
    print(f"   Created: {session1_id}\n")

    # 2. Create second session
    print("2. Creating second session...")
    response2 = processor.process_command("/session new", channel_id, user_key, conversation_key)
    session2_id = response2.metadata["session_id"]
    print(f"   Created: {session2_id} (now active)\n")

    # 3. List sessions
    print("3. Listing sessions...")
    response3 = processor.process_command("/session list", channel_id, user_key, conversation_key)
    print(f"   {response3.text}\n")

    # 4. Switch to first session
    print("4. Switching to first session...")
    response4 = processor.process_command(f"/session use {session1_id}", channel_id, user_key, conversation_key)
    print(f"   {response4.text}\n")

    # 5. Close current session
    print("5. Closing current session...")
    response5 = processor.process_command("/session close", channel_id, user_key, conversation_key)
    print(f"   {response5.text}\n")


def example_multi_user_sessions():
    """Example: Multiple users with isolated sessions."""
    processor = CommandProcessor()

    # User 1 creates session
    print("User 1 (+1111111111) creates session:")
    response1 = processor.process_command(
        "/session new",
        channel_id="whatsapp",
        user_key="+1111111111",
        conversation_key="chat_1"
    )
    user1_session = response1.metadata["session_id"]
    print(f"  Session ID: {user1_session}\n")

    # User 2 creates session
    print("User 2 (+2222222222) creates session:")
    response2 = processor.process_command(
        "/session new",
        channel_id="whatsapp",
        user_key="+2222222222",
        conversation_key="chat_2"
    )
    user2_session = response2.metadata["session_id"]
    print(f"  Session ID: {user2_session}\n")

    # Verify isolation
    print("Verifying isolation:")
    print(f"  User 1 session: {user1_session}")
    print(f"  User 2 session: {user2_session}")
    print(f"  Sessions are isolated: {user1_session != user2_session}\n")


def example_command_detection():
    """Example: Detecting commands vs normal messages."""
    processor = CommandProcessor()

    messages = [
        "/session new",
        "/help",
        "Hello, how are you?",
        "What is /help?",
        "/unknown command",
    ]

    print("Testing command detection:")
    for msg in messages:
        is_cmd = processor.is_command(msg)
        print(f"  '{msg}' -> {'COMMAND' if is_cmd else 'MESSAGE'}")
    print()


if __name__ == "__main__":
    print("=== CommunicationOS Message Examples ===\n")

    print("1. Text Message")
    example_text_message()
    print()

    print("2. Image Message")
    example_image_message()
    print()

    print("3. Location Message")
    example_location_message()
    print()

    print("4. Reply Message")
    example_reply_message()
    print()

    print("5. File Attachment")
    example_file_attachment()
    print()

    print("6. Message with Metadata")
    example_with_metadata()
    print()

    print("7. Message Validation")
    example_message_validation()
    print()

    print("8. JSON Serialization")
    example_json_serialization()
    print()

    print("9. Multi-Attachment Message")
    example_multi_attachment()
    print()

    print("=== All examples completed ===")
