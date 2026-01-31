"""Unified message models for CommunicationOS.

⚠️ PROTOCOL FROZEN (v1) - See ADR-014 ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This module defines FROZEN protocol models for CommunicationOS v1.

Changes to InboundMessage, OutboundMessage, MessageType, or related models require:
1. Community RFC submission
2. 14-day review period
3. Backward compatibility analysis
4. Major version bump (v2.0) if breaking

Last frozen: 2026-02-01
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module defines standardized message structures for all communication channels,
ensuring consistent handling of inbound and outbound messages across different
platforms (WhatsApp, Telegram, Email, Slack, etc.).

Design Principles:
- Channel-agnostic: Works with any messaging platform
- Type-safe: Pydantic models ensure data validation
- Extensible: Support for various message types and attachments (via metadata)
- Audit-friendly: All messages include proper timestamps and IDs

Extension Strategy (ADR-014):
- ✅ Extend via metadata dictionary (recommended)
- ✅ Extend via channel manifest configuration
- ✅ Add optional fields with defaults (requires review)
- ❌ Remove or change frozen fields (breaking change)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from agentos.core.time import utc_now


class MessageType(str, Enum):
    """Types of messages supported across all channels.

    ⚠️ FROZEN v1 - See ADR-014
    These 8 message types are frozen. Removing any is a BREAKING CHANGE.
    New types may be added via RFC with proper fallback semantics.

    Attributes:
        TEXT: Plain text messages
        IMAGE: Image attachments (JPEG, PNG, GIF, etc.)
        AUDIO: Audio messages or voice notes
        VIDEO: Video files
        FILE: Document or file attachments
        LOCATION: Geographic location sharing
        INTERACTIVE: Rich interactive messages (buttons, menus, forms)
        SYSTEM: System notifications or events
    """

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    LOCATION = "location"
    INTERACTIVE = "interactive"
    SYSTEM = "system"


class AttachmentType(str, Enum):
    """Types of attachments that can be included in messages.

    Attributes:
        IMAGE: Image file
        AUDIO: Audio file
        VIDEO: Video file
        DOCUMENT: Document file (PDF, DOC, etc.)
        LOCATION: Location data
        CONTACT: Contact card
        STICKER: Sticker or emoji
        INTERACTIVE: Interactive component (button, form, etc.)
    """

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    INTERACTIVE = "interactive"


class Attachment(BaseModel):
    """Attachment data structure.

    Attributes:
        type: Type of attachment
        url: URL to access the attachment (for media files)
        mime_type: MIME type of the attachment
        filename: Original filename (if applicable)
        size_bytes: Size of the attachment in bytes
        metadata: Additional platform-specific metadata
    """

    type: AttachmentType
    url: Optional[str] = None
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "image",
                    "url": "https://example.com/media/image.jpg",
                    "mime_type": "image/jpeg",
                    "filename": "photo.jpg",
                    "size_bytes": 524288,
                    "metadata": {"width": 1920, "height": 1080}
                }
            ]
        }
    }


class Location(BaseModel):
    """Geographic location data.

    Attributes:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        address: Optional human-readable address
        name: Optional location name
    """

    latitude: float
    longitude: float
    address: Optional[str] = None
    name: Optional[str] = None


class InboundMessage(BaseModel):
    """Standardized inbound message from any channel.

    ⚠️ FROZEN v1 - See ADR-014
    Core fields (channel_id, user_key, conversation_key, message_id, timestamp, type,
    text, attachments, metadata) are frozen. Removing or changing semantics is BREAKING.

    Extension Point: Use 'metadata' dict for adapter-specific fields.

    This model represents messages received from external channels (WhatsApp,
    Telegram, Email, etc.) in a unified format. Channel adapters are responsible
    for converting platform-specific messages to this standard format.

    Attributes:
        channel_id: Unique identifier for the channel (e.g., "whatsapp_business", "telegram_bot_123")
        user_key: Unique identifier for the user within the channel (phone number, user ID, email, etc.)
        conversation_key: Unique identifier for the conversation/thread (chat ID, thread ID, etc.)
        message_id: Unique identifier for this specific message (platform-specific ID)
        timestamp: When the message was created/sent (in UTC)
        type: Type of message (text, image, audio, etc.)
        text: Text content of the message (if applicable)
        attachments: List of attachments (images, files, etc.)
        location: Location data (if message contains location)
        raw: Original platform-specific message data (for debugging and platform-specific features)
        metadata: Additional metadata (reply info, forwarded status, etc.)
    """

    channel_id: str = Field(
        ...,
        description="Unique identifier for the channel (e.g., 'whatsapp_business', 'telegram_bot_123')",
        min_length=1,
        max_length=255
    )

    user_key: str = Field(
        ...,
        description="Unique identifier for the user (phone, user ID, email, etc.)",
        min_length=1,
        max_length=255
    )

    conversation_key: str = Field(
        ...,
        description="Unique identifier for the conversation/thread",
        min_length=1,
        max_length=255
    )

    message_id: str = Field(
        ...,
        description="Platform-specific unique message identifier",
        min_length=1,
        max_length=255
    )

    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Message creation timestamp (UTC)"
    )

    type: MessageType = Field(
        default=MessageType.TEXT,
        description="Type of message"
    )

    text: Optional[str] = Field(
        None,
        description="Text content of the message",
        max_length=10000
    )

    attachments: List[Attachment] = Field(
        default_factory=list,
        description="List of attachments"
    )

    location: Optional[Location] = Field(
        None,
        description="Location data if message contains location"
    )

    raw: Dict[str, Any] = Field(
        default_factory=dict,
        description="Original platform-specific message data"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (reply_to, forwarded, etc.)"
    )

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware and in UTC."""
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        # Convert to UTC if not already
        return v.astimezone(tz=None)

    @field_validator('text')
    @classmethod
    def validate_text_presence(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that text is present for TEXT type messages."""
        # Note: This is a simple check. Full validation happens in validate_message_content
        return v

    def validate_message_content(self) -> None:
        """Validate that message has appropriate content based on type.

        Raises:
            ValueError: If message type and content don't match
        """
        if self.type == MessageType.TEXT and not self.text:
            raise ValueError("TEXT type messages must have text content")
        elif self.type == MessageType.LOCATION and not self.location:
            raise ValueError("LOCATION type messages must have location data")
        elif self.type in [MessageType.IMAGE, MessageType.AUDIO, MessageType.VIDEO, MessageType.FILE]:
            if not self.attachments:
                raise ValueError(f"{self.type.value} type messages must have attachments")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "channel_id": "whatsapp_business_001",
                    "user_key": "+1234567890",
                    "conversation_key": "+1234567890",
                    "message_id": "wamid.HBgNMTIzNDU2Nzg5MAA=",
                    "timestamp": "2026-02-01T10:30:00Z",
                    "type": "text",
                    "text": "Hello, how can I help you?",
                    "attachments": [],
                    "raw": {"platform": "whatsapp", "profile_name": "John Doe"},
                    "metadata": {}
                }
            ]
        }
    }


class OutboundMessage(BaseModel):
    """Standardized outbound message to any channel.

    ⚠️ FROZEN v1 - See ADR-014
    Core fields (channel_id, user_key, conversation_key, type, text, attachments,
    metadata) are frozen. Removing or changing semantics is BREAKING.

    Extension Point: Use 'metadata' dict for delivery options and custom fields.

    This model represents messages to be sent to external channels. The system
    will use channel adapters to convert this standard format to platform-specific
    message formats.

    Attributes:
        channel_id: Target channel identifier
        user_key: Target user identifier
        conversation_key: Target conversation/thread identifier
        reply_to_message_id: Optional ID of message being replied to
        type: Type of message to send
        text: Text content to send
        attachments: List of attachments to include
        location: Location data to send
        metadata: Additional metadata (priority, delivery options, etc.)
    """

    channel_id: str = Field(
        ...,
        description="Target channel identifier",
        min_length=1,
        max_length=255
    )

    user_key: str = Field(
        ...,
        description="Target user identifier",
        min_length=1,
        max_length=255
    )

    conversation_key: str = Field(
        ...,
        description="Target conversation/thread identifier",
        min_length=1,
        max_length=255
    )

    reply_to_message_id: Optional[str] = Field(
        None,
        description="Optional ID of message being replied to",
        max_length=255
    )

    type: MessageType = Field(
        default=MessageType.TEXT,
        description="Type of message to send"
    )

    text: Optional[str] = Field(
        None,
        description="Text content to send",
        max_length=10000
    )

    attachments: List[Attachment] = Field(
        default_factory=list,
        description="List of attachments to include"
    )

    location: Optional[Location] = Field(
        None,
        description="Location data to send"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (priority, delivery options, etc.)"
    )

    @field_validator('text')
    @classmethod
    def validate_text_presence(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that text is present for TEXT type messages."""
        return v

    def validate_message_content(self) -> None:
        """Validate that message has appropriate content based on type.

        Raises:
            ValueError: If message type and content don't match
        """
        if self.type == MessageType.TEXT and not self.text:
            raise ValueError("TEXT type messages must have text content")
        elif self.type == MessageType.LOCATION and not self.location:
            raise ValueError("LOCATION type messages must have location data")
        elif self.type in [MessageType.IMAGE, MessageType.AUDIO, MessageType.VIDEO, MessageType.FILE]:
            if not self.attachments:
                raise ValueError(f"{self.type.value} type messages must have attachments")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "channel_id": "whatsapp_business_001",
                    "user_key": "+1234567890",
                    "conversation_key": "+1234567890",
                    "reply_to_message_id": None,
                    "type": "text",
                    "text": "Thank you for your message. How can I assist you?",
                    "attachments": [],
                    "metadata": {"priority": "normal"}
                }
            ]
        }
    }
