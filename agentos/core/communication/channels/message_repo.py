"""Channel Message Repository - Persistence and Audit Trail.

This module provides database persistence for all inbound and outbound channel messages.
It implements complete audit trail tracking for channel communications across
multiple platforms (SMS, Slack, Discord, etc.).

Architecture:
    - ChannelMessageRepo: Main repository class for CRUD operations
    - UUID v7 generation for time-ordered message IDs
    - Epoch millisecond timestamps for consistency with v44+
    - JSON metadata storage for channel-specific fields
    - Status lifecycle tracking (pending → delivered/failed)

Design Principles:
    - Every message MUST be persisted (audit requirement)
    - Timestamps use epoch_ms (consistency with existing schemas)
    - Metadata is JSON-encoded (flexible, extensible)
    - Session linking enables conversation context
    - Status tracking enables delivery confirmation and retry logic

References:
    - agentos/store/migrations/schema_v65_channel_messages.sql - Table schema
    - agentos/store/migrations/v61_twilio_sessions.sql - Similar audit pattern
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


def generate_message_id() -> str:
    """Generate a time-ordered message ID using UUID v7.

    UUID v7 provides:
    - Time-ordered sorting (timestamp prefix)
    - Unique across all messages
    - Compatible with TEXT primary key

    Returns:
        Message ID string in format: "msg-<uuid7>"

    Example:
        >>> msg_id = generate_message_id()
        >>> msg_id.startswith('msg-')
        True
    """
    # Use UUID v4 (Python standard library doesn't have v7 yet)
    # For production, consider using a library with UUID v7 support
    # Format: msg-<uuid> for easy identification
    return f"msg-{uuid.uuid4().hex}"


@dataclass
class ChannelMessage:
    """Data class representing a channel message record.

    Attributes:
        message_id: Unique message identifier (UUID v7)
        channel_type: Channel platform (twilio_sms, slack, discord)
        channel_id: Channel instance identifier
        direction: Message flow direction (inbound/outbound)
        from_identifier: Sender identifier
        to_identifier: Recipient identifier
        content: Message text content
        metadata: JSON metadata dict
        received_at: Inbound receive timestamp (epoch_ms)
        sent_at: Outbound send timestamp (epoch_ms)
        delivered_at: Delivery confirmation timestamp (epoch_ms)
        status: Message status (pending/delivered/failed)
        error_message: Error details if failed
        session_id: Linked chat session ID
        created_at: Record creation timestamp (epoch_ms)
        updated_at: Last update timestamp (epoch_ms)
    """

    message_id: str
    channel_type: str
    channel_id: str
    direction: str
    from_identifier: str
    to_identifier: str
    content: str
    metadata: Optional[Dict[str, Any]]
    received_at: Optional[int]
    sent_at: Optional[int]
    delivered_at: Optional[int]
    status: str
    error_message: Optional[str]
    session_id: Optional[str]
    created_at: int
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all message fields
        """
        return {
            "message_id": self.message_id,
            "channel_type": self.channel_type,
            "channel_id": self.channel_id,
            "direction": self.direction,
            "from_identifier": self.from_identifier,
            "to_identifier": self.to_identifier,
            "content": self.content,
            "metadata": self.metadata,
            "received_at": self.received_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "status": self.status,
            "error_message": self.error_message,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ChannelMessageRepo:
    """Repository for channel message persistence and audit trail.

    This class provides CRUD operations for channel messages, enabling:
    - Complete audit trail for all inbound/outbound messages
    - Message history queries
    - Session linking for conversation context
    - Delivery status tracking

    Thread Safety:
        Uses connection-per-operation pattern for SQLite safety.
        For concurrent writes, consider using agentos.store.get_writer().

    Attributes:
        db_path: Path to SQLite database file
    """

    def __init__(self, db_path: str | Path):
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database (str or Path)

        Raises:
            ValueError: If db_path is invalid
        """
        if not db_path:
            raise ValueError("db_path cannot be empty")

        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path

        if not self.db_path.exists():
            raise ValueError(f"Database not found: {self.db_path}")

        logger.debug(f"Initialized ChannelMessageRepo: db_path={self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create database connection.

        Returns:
            SQLite connection object

        Raises:
            sqlite3.Error: If connection fails
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    def create_inbound(
        self,
        channel_type: str,
        channel_id: str,
        from_identifier: str,
        to_identifier: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Create inbound message record.

        Inbound messages are received from external users/systems.
        The message is recorded with:
        - direction = 'inbound'
        - status = 'delivered' (already received)
        - received_at = current timestamp

        Args:
            channel_type: Channel platform (e.g., 'twilio_sms', 'slack')
            channel_id: Channel instance ID (e.g., phone number, channel ID)
            from_identifier: Sender identifier (e.g., user phone number)
            to_identifier: Recipient identifier (e.g., bot phone number)
            content: Message text content
            metadata: Optional JSON metadata dict

        Returns:
            message_id: Unique message identifier

        Raises:
            ValueError: If required fields are invalid
            sqlite3.Error: If database operation fails

        Example:
            >>> repo = ChannelMessageRepo('/path/to/db.sqlite')
            >>> msg_id = repo.create_inbound(
            ...     channel_type='twilio_sms',
            ...     channel_id='+15551234567',
            ...     from_identifier='+15559876543',
            ...     to_identifier='+15551234567',
            ...     content='Hello AgentOS!'
            ... )
            >>> print(f"Message ID: {msg_id}")
        """
        # Validate required fields
        if not all([channel_type, channel_id, from_identifier, to_identifier]):
            raise ValueError(
                "All identifier fields are required: "
                "channel_type, channel_id, from_identifier, to_identifier"
            )

        # Generate message ID and timestamps
        message_id = generate_message_id()
        now_ms = utc_now_ms()

        # Prepare metadata JSON
        metadata_json = json.dumps(metadata) if metadata else None

        # Insert into database
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO channel_messages (
                    message_id, channel_type, channel_id, direction,
                    from_identifier, to_identifier, content, metadata,
                    received_at, sent_at, delivered_at,
                    status, error_message, session_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    channel_type,
                    channel_id,
                    "inbound",  # direction
                    from_identifier,
                    to_identifier,
                    content,
                    metadata_json,
                    now_ms,  # received_at
                    None,  # sent_at (NULL for inbound)
                    None,  # delivered_at (NULL for inbound)
                    "delivered",  # status (already received)
                    None,  # error_message
                    None,  # session_id (to be linked later)
                    now_ms,  # created_at
                    now_ms,  # updated_at
                ),
            )
            conn.commit()

            logger.info(
                f"Created inbound message: id={message_id}, "
                f"channel={channel_type}:{channel_id}, from={from_identifier}"
            )

            return message_id

        except sqlite3.Error as e:
            logger.error(f"Failed to create inbound message: {e}")
            raise
        finally:
            conn.close()

    def create_outbound(
        self,
        channel_type: str,
        channel_id: str,
        from_identifier: str,
        to_identifier: str,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Create outbound message record.

        Outbound messages are sent to external users/systems.
        The message is recorded with:
        - direction = 'outbound'
        - status = 'pending' (to be confirmed)
        - sent_at = current timestamp

        Args:
            channel_type: Channel platform (e.g., 'twilio_sms', 'slack')
            channel_id: Channel instance ID (e.g., phone number, channel ID)
            from_identifier: Sender identifier (e.g., bot phone number)
            to_identifier: Recipient identifier (e.g., user phone number)
            content: Message text content
            session_id: Optional chat session ID for conversation linking
            metadata: Optional JSON metadata dict

        Returns:
            message_id: Unique message identifier

        Raises:
            ValueError: If required fields are invalid
            sqlite3.Error: If database operation fails

        Example:
            >>> repo = ChannelMessageRepo('/path/to/db.sqlite')
            >>> msg_id = repo.create_outbound(
            ...     channel_type='twilio_sms',
            ...     channel_id='+15551234567',
            ...     from_identifier='+15551234567',
            ...     to_identifier='+15559876543',
            ...     content='Thanks for your message!',
            ...     session_id='ses-abc123'
            ... )
        """
        # Validate required fields
        if not all([channel_type, channel_id, from_identifier, to_identifier]):
            raise ValueError(
                "All identifier fields are required: "
                "channel_type, channel_id, from_identifier, to_identifier"
            )

        # Generate message ID and timestamps
        message_id = generate_message_id()
        now_ms = utc_now_ms()

        # Prepare metadata JSON
        metadata_json = json.dumps(metadata) if metadata else None

        # Insert into database
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO channel_messages (
                    message_id, channel_type, channel_id, direction,
                    from_identifier, to_identifier, content, metadata,
                    received_at, sent_at, delivered_at,
                    status, error_message, session_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    channel_type,
                    channel_id,
                    "outbound",  # direction
                    from_identifier,
                    to_identifier,
                    content,
                    metadata_json,
                    None,  # received_at (NULL for outbound)
                    now_ms,  # sent_at
                    None,  # delivered_at (to be updated on confirmation)
                    "pending",  # status (awaiting delivery)
                    None,  # error_message
                    session_id,  # session_id (optional)
                    now_ms,  # created_at
                    now_ms,  # updated_at
                ),
            )
            conn.commit()

            logger.info(
                f"Created outbound message: id={message_id}, "
                f"channel={channel_type}:{channel_id}, to={to_identifier}, "
                f"session={session_id}"
            )

            return message_id

        except sqlite3.Error as e:
            logger.error(f"Failed to create outbound message: {e}")
            raise
        finally:
            conn.close()

    def update_status(
        self,
        message_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update message delivery status.

        This method updates the status field and optionally records error details.
        For 'delivered' status, it also sets delivered_at timestamp.

        Args:
            message_id: Message identifier to update
            status: New status ('pending', 'delivered', 'failed', 'read')
            error_message: Optional error details (for 'failed' status)

        Raises:
            ValueError: If message_id or status is invalid
            sqlite3.Error: If database operation fails

        Example:
            >>> repo.update_status('msg-abc123', 'delivered')
            >>> repo.update_status('msg-xyz789', 'failed', error_message='Network timeout')
        """
        # Validate inputs
        if not message_id:
            raise ValueError("message_id is required")

        valid_statuses = {"pending", "delivered", "failed", "read"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        now_ms = utc_now_ms()

        # Determine if we should set delivered_at
        delivered_at = now_ms if status == "delivered" else None

        # Update database
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                UPDATE channel_messages
                SET status = ?,
                    error_message = ?,
                    delivered_at = COALESCE(?, delivered_at),
                    updated_at = ?
                WHERE message_id = ?
                """,
                (status, error_message, delivered_at, now_ms, message_id),
            )

            if cursor.rowcount == 0:
                logger.warning(f"No message found with id: {message_id}")
            else:
                logger.info(
                    f"Updated message status: id={message_id}, "
                    f"status={status}, error={error_message}"
                )

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to update message status: {e}")
            raise
        finally:
            conn.close()

    def link_to_session(self, message_id: str, session_id: str) -> None:
        """Link message to chat session.

        This enables conversation context by linking channel messages
        to their corresponding chat sessions.

        Args:
            message_id: Message identifier to link
            session_id: Chat session identifier

        Raises:
            ValueError: If message_id or session_id is invalid
            sqlite3.Error: If database operation fails

        Example:
            >>> repo.link_to_session('msg-abc123', 'ses-xyz789')
        """
        # Validate inputs
        if not message_id:
            raise ValueError("message_id is required")
        if not session_id:
            raise ValueError("session_id is required")

        now_ms = utc_now_ms()

        # Update database
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                UPDATE channel_messages
                SET session_id = ?,
                    updated_at = ?
                WHERE message_id = ?
                """,
                (session_id, now_ms, message_id),
            )

            if cursor.rowcount == 0:
                logger.warning(f"No message found with id: {message_id}")
            else:
                logger.info(
                    f"Linked message to session: message={message_id}, session={session_id}"
                )

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to link message to session: {e}")
            raise
        finally:
            conn.close()

    def get_history(
        self, channel_type: str, channel_id: str, limit: int = 50
    ) -> List[Dict]:
        """Get message history for a channel.

        Returns recent messages for a specific channel, ordered by creation time
        (most recent first).

        Args:
            channel_type: Channel platform (e.g., 'twilio_sms', 'slack')
            channel_id: Channel instance ID (e.g., phone number, channel ID)
            limit: Maximum number of messages to return (default: 50)

        Returns:
            List of message dictionaries, ordered by created_at DESC

        Raises:
            ValueError: If parameters are invalid
            sqlite3.Error: If database operation fails

        Example:
            >>> repo = ChannelMessageRepo('/path/to/db.sqlite')
            >>> history = repo.get_history('twilio_sms', '+15551234567', limit=10)
            >>> for msg in history:
            ...     print(f"{msg['direction']}: {msg['content']}")
        """
        # Validate inputs
        if not channel_type:
            raise ValueError("channel_type is required")
        if not channel_id:
            raise ValueError("channel_id is required")
        if limit <= 0:
            raise ValueError("limit must be positive")

        # Query database
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT
                    message_id, channel_type, channel_id, direction,
                    from_identifier, to_identifier, content, metadata,
                    received_at, sent_at, delivered_at,
                    status, error_message, session_id,
                    created_at, updated_at
                FROM channel_messages
                WHERE channel_type = ? AND channel_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (channel_type, channel_id, limit),
            )

            rows = cursor.fetchall()

            # Convert rows to dictionaries
            messages = []
            for row in rows:
                msg_dict = dict(row)
                # Parse JSON metadata
                if msg_dict.get("metadata"):
                    try:
                        msg_dict["metadata"] = json.loads(msg_dict["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON metadata for message {msg_dict['message_id']}"
                        )
                        msg_dict["metadata"] = None
                messages.append(msg_dict)

            logger.debug(
                f"Retrieved {len(messages)} messages for "
                f"channel={channel_type}:{channel_id}"
            )

            return messages

        except sqlite3.Error as e:
            logger.error(f"Failed to get message history: {e}")
            raise
        finally:
            conn.close()

    def get_by_id(self, message_id: str) -> Optional[Dict]:
        """Get a single message by ID.

        Args:
            message_id: Message identifier

        Returns:
            Message dictionary if found, None otherwise

        Raises:
            ValueError: If message_id is invalid
            sqlite3.Error: If database operation fails
        """
        if not message_id:
            raise ValueError("message_id is required")

        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT
                    message_id, channel_type, channel_id, direction,
                    from_identifier, to_identifier, content, metadata,
                    received_at, sent_at, delivered_at,
                    status, error_message, session_id,
                    created_at, updated_at
                FROM channel_messages
                WHERE message_id = ?
                """,
                (message_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Convert to dictionary
            msg_dict = dict(row)

            # Parse JSON metadata
            if msg_dict.get("metadata"):
                try:
                    msg_dict["metadata"] = json.loads(msg_dict["metadata"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON metadata for message {message_id}")
                    msg_dict["metadata"] = None

            return msg_dict

        except sqlite3.Error as e:
            logger.error(f"Failed to get message by ID: {e}")
            raise
        finally:
            conn.close()

    def get_by_session(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get all messages for a specific session.

        Args:
            session_id: Chat session identifier
            limit: Maximum number of messages to return (default: 50)

        Returns:
            List of message dictionaries, ordered by created_at DESC

        Raises:
            ValueError: If parameters are invalid
            sqlite3.Error: If database operation fails
        """
        if not session_id:
            raise ValueError("session_id is required")
        if limit <= 0:
            raise ValueError("limit must be positive")

        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT
                    message_id, channel_type, channel_id, direction,
                    from_identifier, to_identifier, content, metadata,
                    received_at, sent_at, delivered_at,
                    status, error_message, session_id,
                    created_at, updated_at
                FROM channel_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            )

            rows = cursor.fetchall()

            # Convert rows to dictionaries
            messages = []
            for row in rows:
                msg_dict = dict(row)
                # Parse JSON metadata
                if msg_dict.get("metadata"):
                    try:
                        msg_dict["metadata"] = json.loads(msg_dict["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON metadata for message {msg_dict['message_id']}"
                        )
                        msg_dict["metadata"] = None
                messages.append(msg_dict)

            logger.debug(
                f"Retrieved {len(messages)} messages for session={session_id}"
            )

            return messages

        except sqlite3.Error as e:
            logger.error(f"Failed to get messages by session: {e}")
            raise
        finally:
            conn.close()
