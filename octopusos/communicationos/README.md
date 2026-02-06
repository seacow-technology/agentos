# CommunicationOS - Unified Channel Message Specification

## Overview

CommunicationOS provides a **unified message specification** for handling multi-channel communication in AgentOS. This specification enables consistent handling of messages across different platforms (WhatsApp, Telegram, Email, Slack, etc.) through a standardized data model.

## Design Principles

1. **Channel-Agnostic**: Works with any messaging platform through a common interface
2. **Type-Safe**: Uses Pydantic models for robust validation and type checking
3. **Extensible**: Supports various message types (text, image, audio, video, location, etc.)
4. **Audit-Friendly**: All messages include proper timestamps and identifiers for tracking
5. **Metadata-Rich**: Supports platform-specific data through `raw` and `metadata` fields

## Core Models

### MessageType Enum

Defines all supported message types:

```python
class MessageType(str, Enum):
    TEXT = "text"              # Plain text messages
    IMAGE = "image"            # Image attachments
    AUDIO = "audio"            # Audio messages/voice notes
    VIDEO = "video"            # Video files
    FILE = "file"              # Document/file attachments
    LOCATION = "location"      # Geographic location
    INTERACTIVE = "interactive" # Rich interactive messages (buttons, forms)
    SYSTEM = "system"          # System notifications
```

### InboundMessage

Represents messages **received from** external channels.

**Required Fields:**
- `channel_id`: Unique identifier for the channel (e.g., "whatsapp_business_001")
- `user_key`: User identifier (phone number, user ID, email)
- `conversation_key`: Conversation/thread identifier
- `message_id`: Platform-specific message ID

**Optional Fields:**
- `timestamp`: Message timestamp (UTC, auto-generated if not provided)
- `type`: Message type (defaults to TEXT)
- `text`: Text content
- `attachments`: List of attachments
- `location`: Location data
- `raw`: Original platform-specific data
- `metadata`: Additional metadata (reply info, forwarded status, etc.)

**Example:**
```python
from agentos.communicationos import InboundMessage, MessageType

message = InboundMessage(
    channel_id="whatsapp_business_001",
    user_key="+1234567890",
    conversation_key="+1234567890",
    message_id="wamid.HBgNMTIzNDU2Nzg5MAA=",
    type=MessageType.TEXT,
    text="Hello, how can I help you?",
    raw={
        "platform": "whatsapp",
        "profile_name": "John Doe"
    }
)
```

### OutboundMessage

Represents messages to be **sent to** external channels.

**Required Fields:**
- `channel_id`: Target channel identifier
- `user_key`: Target user identifier
- `conversation_key`: Target conversation identifier

**Optional Fields:**
- `reply_to_message_id`: ID of message being replied to
- `type`: Message type (defaults to TEXT)
- `text`: Text content to send
- `attachments`: List of attachments
- `location`: Location data
- `metadata`: Delivery options and metadata

**Example:**
```python
from agentos.communicationos import OutboundMessage, MessageType

message = OutboundMessage(
    channel_id="whatsapp_business_001",
    user_key="+1234567890",
    conversation_key="+1234567890",
    reply_to_message_id="wamid.HBgNMTIzNDU2Nzg5MAA=",
    type=MessageType.TEXT,
    text="Thank you for your message. How can I assist you?",
    metadata={"priority": "normal"}
)
```

### Attachment

Represents file attachments in messages.

**Fields:**
- `type`: AttachmentType (IMAGE, AUDIO, VIDEO, DOCUMENT, etc.)
- `url`: URL to access the attachment
- `mime_type`: MIME type of the file
- `filename`: Original filename
- `size_bytes`: File size in bytes
- `metadata`: Additional metadata (dimensions, duration, etc.)

**Example:**
```python
from agentos.communicationos import Attachment, AttachmentType

attachment = Attachment(
    type=AttachmentType.IMAGE,
    url="https://example.com/media/photo.jpg",
    mime_type="image/jpeg",
    filename="photo.jpg",
    size_bytes=524288,
    metadata={"width": 1920, "height": 1080}
)
```

### Location

Represents geographic location data.

**Fields:**
- `latitude`: Latitude coordinate (required)
- `longitude`: Longitude coordinate (required)
- `address`: Human-readable address (optional)
- `name`: Location name (optional)

**Example:**
```python
from agentos.communicationos import Location

location = Location(
    latitude=37.7749,
    longitude=-122.4194,
    address="San Francisco, CA",
    name="Golden Gate Bridge"
)
```

## Message Validation

Both `InboundMessage` and `OutboundMessage` include a `validate_message_content()` method that ensures message content matches the message type:

```python
message = InboundMessage(
    channel_id="whatsapp_001",
    user_key="+1234567890",
    conversation_key="chat_123",
    message_id="msg_456",
    type=MessageType.TEXT,
    text=None  # Invalid!
)

message.validate_message_content()  # Raises ValueError
```

**Validation Rules:**
- TEXT messages must have `text` content
- IMAGE/AUDIO/VIDEO/FILE messages must have `attachments`
- LOCATION messages must have `location` data

## Usage Patterns

### Creating a Reply

```python
# Received inbound message
inbound = InboundMessage(
    channel_id="telegram_001",
    user_key="user123",
    conversation_key="chat456",
    message_id="msg789",
    text="What's the weather?"
)

# Create reply using inbound context
outbound = OutboundMessage(
    channel_id=inbound.channel_id,
    user_key=inbound.user_key,
    conversation_key=inbound.conversation_key,
    reply_to_message_id=inbound.message_id,
    text="The weather is sunny today!"
)
```

### Sending Media

```python
from agentos.communicationos import OutboundMessage, Attachment, AttachmentType

message = OutboundMessage(
    channel_id="whatsapp_001",
    user_key="+1234567890",
    conversation_key="chat_123",
    type=MessageType.IMAGE,
    text="Here's your report",
    attachments=[
        Attachment(
            type=AttachmentType.IMAGE,
            url="https://example.com/report.png",
            filename="monthly_report.png"
        )
    ]
)
```

### Sharing Location

```python
from agentos.communicationos import OutboundMessage, Location, MessageType

message = OutboundMessage(
    channel_id="whatsapp_001",
    user_key="+1234567890",
    conversation_key="chat_123",
    type=MessageType.LOCATION,
    location=Location(
        latitude=40.7128,
        longitude=-74.0060,
        name="Meeting Point"
    )
)
```

## JSON Serialization

All models support JSON serialization:

```python
# Convert to dictionary
data = message.model_dump()

# Convert to JSON string
json_str = message.model_dump_json()

# Parse from dictionary
message = InboundMessage(**data)

# Parse from JSON string
message = InboundMessage.model_validate_json(json_str)
```

## Integration with Channel Adapters

Channel adapters are responsible for:

1. **Inbound**: Converting platform-specific messages to `InboundMessage`
2. **Outbound**: Converting `OutboundMessage` to platform-specific format

```python
# Example WhatsApp adapter (pseudo-code)
class WhatsAppAdapter:
    def parse_inbound(self, whatsapp_webhook_data):
        """Convert WhatsApp webhook to InboundMessage."""
        return InboundMessage(
            channel_id=self.channel_id,
            user_key=whatsapp_webhook_data["from"],
            conversation_key=whatsapp_webhook_data["from"],
            message_id=whatsapp_webhook_data["id"],
            text=whatsapp_webhook_data["text"]["body"],
            raw=whatsapp_webhook_data
        )

    def format_outbound(self, message: OutboundMessage):
        """Convert OutboundMessage to WhatsApp API format."""
        return {
            "messaging_product": "whatsapp",
            "to": message.user_key,
            "type": "text",
            "text": {"body": message.text}
        }
```

## Testing

Run the test suite:

```bash
python3 -m pytest tests/unit/communicationos/test_models.py -v
```

All 37 tests should pass, covering:
- Model creation and validation
- Field constraints
- Message type validation
- JSON serialization
- Edge cases and error handling
- Unicode support
- Message interoperability

## Next Steps

This unified message specification provides the foundation for:

1. **Session Management**: Track conversations across channels
2. **Command Processing**: Parse and route commands from any channel
3. **Channel Registry**: Manage multiple channel instances
4. **Middleware Pipeline**: Process messages with unified middleware
5. **Channel Adapters**: Implement platform-specific adapters

## References

- **Pydantic Documentation**: https://docs.pydantic.dev/
- **WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **RFC 5322 (Email)**: https://tools.ietf.org/html/rfc5322
