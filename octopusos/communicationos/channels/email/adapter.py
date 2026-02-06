"""Email Channel Adapter with Polling Mode.

This module implements the EmailAdapter for CommunicationOS, providing asynchronous
email communication through polling. It supports multiple providers (Gmail, Outlook,
SMTP/IMAP) and maintains conversation context using RFC 5322 email threading.

Architecture:
    - EmailAdapter: Main adapter class implementing ChannelAdapter protocol
    - PollingScheduler: Background polling scheduler with configurable interval
    - CursorStore: SQLite-based persistence for last poll position
    - EmailEnvelope → InboundMessage mapping with thread detection
    - OutboundMessage → provider.send() with proper threading headers

Key Features:
    - Configurable polling interval (default: 60 seconds, min: 30s, max: 3600s)
    - Background thread or asyncio task for polling
    - Cursor persistence to track last fetched message
    - Message deduplication based on message_id
    - Thread detection using Message-ID, References, In-Reply-To headers
    - Integration with MessageBus for command processing
    - Error handling and audit logging

Design Patterns:
    - Similar to Telegram/Slack adapters but uses polling instead of webhooks
    - Provider pattern for email provider abstraction
    - Cursor pattern for incremental message fetching
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
)
from agentos.communicationos.providers.email import (
    IEmailProvider,
    EmailEnvelope,
    compute_conversation_key,
    parse_email_address,
)
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


class CursorStore:
    """SQLite-based persistent storage for email polling cursor.

    The cursor tracks the last successfully processed message timestamp,
    enabling incremental polling that only fetches new messages.

    Schema:
        CREATE TABLE email_cursors (
            channel_id TEXT PRIMARY KEY,
            last_poll_time INTEGER NOT NULL,  -- epoch milliseconds
            last_message_id TEXT,              -- last processed message ID
            updated_at INTEGER NOT NULL        -- epoch milliseconds
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize cursor store.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Use default location in user's home directory
            home_dir = Path.home()
            data_dir = home_dir / ".agentos" / "data"
            db_path = str(data_dir / "communicationos" / "email_cursors.db")

        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS email_cursors (
                    channel_id TEXT PRIMARY KEY,
                    last_poll_time INTEGER NOT NULL,
                    last_message_id TEXT,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def get_last_poll_time(self, channel_id: str) -> Optional[datetime]:
        """Get the last poll time for a channel.

        Args:
            channel_id: Channel identifier

        Returns:
            Last poll time as timezone-aware datetime, or None if never polled
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT last_poll_time FROM email_cursors WHERE channel_id = ?",
                (channel_id,)
            )
            row = cursor.fetchone()

            if row:
                epoch_ms = row[0]
                return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
            return None

    def update_cursor(
        self,
        channel_id: str,
        poll_time: datetime,
        last_message_id: Optional[str] = None
    ) -> None:
        """Update the cursor for a channel.

        Args:
            channel_id: Channel identifier
            poll_time: Current poll time
            last_message_id: Last processed message ID (optional)
        """
        epoch_ms = int(poll_time.timestamp() * 1000)
        updated_at_ms = int(utc_now().timestamp() * 1000)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO email_cursors (channel_id, last_poll_time, last_message_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    last_poll_time = excluded.last_poll_time,
                    last_message_id = excluded.last_message_id,
                    updated_at = excluded.updated_at
            """, (channel_id, epoch_ms, last_message_id, updated_at_ms))
            conn.commit()


class EmailAdapter:
    """Channel adapter for Email with polling mode.

    This adapter implements the ChannelAdapter protocol for email communication
    through various providers (Gmail, Outlook, SMTP/IMAP). It uses polling to
    periodically check for new messages and maintains conversation context
    using email threading headers.

    Attributes:
        channel_id: Unique identifier for this channel instance
        provider: Email provider implementation (IEmailProvider)
        poll_interval_seconds: Polling interval in seconds (default: 60)
        mailbox_folder: IMAP folder to monitor (default: "INBOX")
        cursor_store: Persistent storage for polling cursor
        message_bus: MessageBus for routing processed messages
    """

    def __init__(
        self,
        channel_id: str,
        provider: IEmailProvider,
        poll_interval_seconds: int = 60,
        mailbox_folder: str = "INBOX",
        cursor_store: Optional[CursorStore] = None,
        message_bus: Optional[Any] = None
    ):
        """Initialize Email adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "email_gmail_001")
            provider: Email provider implementation
            poll_interval_seconds: Polling interval (30-3600 seconds)
            mailbox_folder: Mailbox folder to monitor (default: "INBOX")
            cursor_store: Cursor store for persistence (creates new if None)
            message_bus: MessageBus for routing messages (optional)
        """
        self.channel_id = channel_id
        self.provider = provider
        self.mailbox_folder = mailbox_folder
        self.message_bus = message_bus

        # Validate and set polling interval
        if poll_interval_seconds < 30:
            logger.warning(
                f"Poll interval {poll_interval_seconds}s too low, using minimum 30s"
            )
            poll_interval_seconds = 30
        elif poll_interval_seconds > 3600:
            logger.warning(
                f"Poll interval {poll_interval_seconds}s too high, using maximum 3600s"
            )
            poll_interval_seconds = 3600

        self.poll_interval_seconds = poll_interval_seconds

        # Initialize cursor store
        self.cursor_store = cursor_store or CursorStore()

        # Deduplication: track recently seen message IDs
        self._seen_message_ids: Set[str] = set()
        self._max_seen_ids = 10000  # Keep last 10k message IDs

        # Polling control
        self._polling_task: Optional[asyncio.Task] = None
        self._polling_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()
        self._is_polling = False

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def _envelope_to_inbound_message(self, envelope: EmailEnvelope) -> InboundMessage:
        """Convert EmailEnvelope to InboundMessage.

        This method maps email-specific fields to the unified InboundMessage format,
        implementing the key mapping rules defined in KEY_MAPPING_RULES.md.

        Mapping:
            - channel_id: self.channel_id
            - user_key: from_address (lowercase normalized)
            - conversation_key: compute_conversation_key(envelope) using thread detection
            - message_id: "email_" + RFC Message-ID (stripped of angle brackets)
            - text: text_body (or html_body if text_body is None)

        Args:
            envelope: EmailEnvelope from provider

        Returns:
            InboundMessage in unified format
        """
        # Normalize sender email address (lowercase)
        from_address = envelope.from_address.lower().strip()

        # Compute conversation key using thread detection algorithm
        conversation_key = compute_conversation_key(envelope)

        # Generate message_id with "email_" prefix
        # Strip angle brackets from Message-ID
        raw_message_id = envelope.message_id.strip('<>')
        message_id = f"email_{raw_message_id}"

        # Use text_body, fall back to html_body if text not available
        text = envelope.text_body
        if not text and envelope.html_body:
            # TODO: Convert HTML to plain text (simple strip for now)
            import re
            text = re.sub(r'<[^>]+>', '', envelope.html_body)

        # Build display name
        display_name = envelope.from_name or from_address

        # Create InboundMessage
        inbound_message = InboundMessage(
            channel_id=self.channel_id,
            user_key=from_address,
            conversation_key=conversation_key,
            message_id=message_id,
            timestamp=envelope.date,
            type=MessageType.TEXT,
            text=text,
            raw={
                "provider_message_id": envelope.provider_message_id,
                "message_id": envelope.message_id,
                "subject": envelope.subject,
                "from_name": envelope.from_name,
                "to_addresses": envelope.to_addresses,
                "cc_addresses": envelope.cc_addresses,
                "in_reply_to": envelope.in_reply_to,
                "references": envelope.references,
                "html_body": envelope.html_body,
                "attachments": envelope.attachments,
                "raw_headers": envelope.raw_headers,
            },
            metadata={
                "from_address": from_address,
                "from_name": envelope.from_name,
                "display_name": display_name,
                "subject": envelope.subject,
                "to_addresses": envelope.to_addresses,
                "cc_addresses": envelope.cc_addresses,
                "thread_root": conversation_key,
                "provider_message_id": envelope.provider_message_id,
            }
        )

        logger.debug(
            f"Converted email to InboundMessage: "
            f"from={from_address}, subject={envelope.subject}, "
            f"thread_root={conversation_key}, message_id={message_id}"
        )

        return inbound_message

    def _is_duplicate(self, message_id: str) -> bool:
        """Check if message has already been processed.

        Args:
            message_id: Message identifier to check

        Returns:
            True if message is duplicate, False otherwise
        """
        if message_id in self._seen_message_ids:
            return True

        # Add to seen set
        self._seen_message_ids.add(message_id)

        # Limit memory usage by pruning old IDs
        if len(self._seen_message_ids) > self._max_seen_ids:
            # Remove oldest half (simple approach)
            ids_to_keep = list(self._seen_message_ids)[self._max_seen_ids // 2:]
            self._seen_message_ids = set(ids_to_keep)

        return False

    async def poll(self) -> List[InboundMessage]:
        """Poll for new email messages and process them.

        This method fetches new messages from the provider since the last poll,
        converts them to InboundMessage format, deduplicates, and routes them
        through the MessageBus if configured.

        Returns:
            List of successfully processed InboundMessage objects

        Raises:
            Exception: If polling fails (provider error, network error, etc.)
        """
        try:
            # Get last poll time from cursor store
            last_poll_time = self.cursor_store.get_last_poll_time(self.channel_id)

            if last_poll_time is None:
                # First poll - fetch messages from last 24 hours
                last_poll_time = utc_now() - timedelta(hours=24)
                logger.info(
                    f"First poll for channel {self.channel_id}, "
                    f"fetching messages since {last_poll_time.isoformat()}"
                )

            # Fetch new messages from provider
            logger.debug(
                f"Polling channel {self.channel_id} for messages since {last_poll_time.isoformat()}"
            )

            envelopes = self.provider.fetch_messages(
                folder=self.mailbox_folder,
                since=last_poll_time,
                limit=100
            )

            logger.info(
                f"Fetched {len(envelopes)} messages from {self.channel_id}"
            )

            # Process each envelope
            processed_messages: List[InboundMessage] = []
            current_poll_time = utc_now()
            last_message_id = None

            for envelope in envelopes:
                try:
                    # Convert to InboundMessage
                    inbound_msg = self._envelope_to_inbound_message(envelope)

                    # Deduplication check
                    if self._is_duplicate(inbound_msg.message_id):
                        logger.debug(
                            f"Skipping duplicate message: {inbound_msg.message_id}"
                        )
                        continue

                    # Route through MessageBus if configured
                    if self.message_bus:
                        await self.message_bus.process_inbound(inbound_msg)

                    processed_messages.append(inbound_msg)
                    last_message_id = inbound_msg.message_id

                    logger.info(
                        f"Processed email: from={inbound_msg.user_key}, "
                        f"subject={inbound_msg.metadata.get('subject')}, "
                        f"thread={inbound_msg.conversation_key}"
                    )

                except Exception as e:
                    logger.exception(
                        f"Failed to process email envelope from {envelope.from_address}: {e}"
                    )
                    # Continue processing other messages
                    continue

            # Update cursor with latest poll time
            self.cursor_store.update_cursor(
                channel_id=self.channel_id,
                poll_time=current_poll_time,
                last_message_id=last_message_id
            )

            return processed_messages

        except Exception as e:
            logger.exception(f"Error polling channel {self.channel_id}: {e}")
            # Don't raise - polling should continue on next interval
            return []

    async def _polling_loop(self) -> None:
        """Background polling loop (asyncio version).

        This coroutine runs continuously, polling for new messages at regular
        intervals until stopped.
        """
        logger.info(
            f"Started email polling loop for {self.channel_id} "
            f"(interval: {self.poll_interval_seconds}s)"
        )

        while not self._stop_polling.is_set():
            try:
                await self.poll()
            except Exception as e:
                logger.exception(
                    f"Error in polling loop for {self.channel_id}: {e}"
                )

            # Wait for next poll interval (check stop flag every second)
            for _ in range(self.poll_interval_seconds):
                if self._stop_polling.is_set():
                    break
                await asyncio.sleep(1)

        logger.info(f"Stopped email polling loop for {self.channel_id}")

    def _polling_loop_threaded(self) -> None:
        """Background polling loop (threaded version).

        This method runs in a separate thread, using asyncio.run() for each
        poll operation.
        """
        logger.info(
            f"Started email polling thread for {self.channel_id} "
            f"(interval: {self.poll_interval_seconds}s)"
        )

        while not self._stop_polling.is_set():
            try:
                # Run poll in asyncio
                asyncio.run(self.poll())
            except Exception as e:
                logger.exception(
                    f"Error in polling thread for {self.channel_id}: {e}"
                )

            # Wait for next poll interval (check stop flag every second)
            for _ in range(self.poll_interval_seconds):
                if self._stop_polling.is_set():
                    break
                self._stop_polling.wait(1)

        logger.info(f"Stopped email polling thread for {self.channel_id}")

    def start_polling(self, use_thread: bool = False) -> None:
        """Start the background polling scheduler.

        Args:
            use_thread: If True, use a background thread instead of asyncio task
        """
        if self._is_polling:
            logger.warning(f"Polling already started for {self.channel_id}")
            return

        self._stop_polling.clear()
        self._is_polling = True

        if use_thread:
            # Start polling in background thread
            self._polling_thread = threading.Thread(
                target=self._polling_loop_threaded,
                daemon=True,
                name=f"email-poll-{self.channel_id}"
            )
            self._polling_thread.start()
            logger.info(
                f"Started polling thread for {self.channel_id} "
                f"(interval: {self.poll_interval_seconds}s)"
            )
        else:
            # Start polling as asyncio task
            loop = asyncio.get_event_loop()
            self._polling_task = loop.create_task(self._polling_loop())
            logger.info(
                f"Started polling task for {self.channel_id} "
                f"(interval: {self.poll_interval_seconds}s)"
            )

    def stop_polling(self) -> None:
        """Stop the background polling scheduler."""
        if not self._is_polling:
            logger.warning(f"Polling not started for {self.channel_id}")
            return

        logger.info(f"Stopping polling for {self.channel_id}")
        self._stop_polling.set()
        self._is_polling = False

        # Wait for thread to finish
        if self._polling_thread:
            self._polling_thread.join(timeout=5)
            self._polling_thread = None

        # Cancel asyncio task
        if self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None

        logger.info(f"Stopped polling for {self.channel_id}")

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through email provider.

        This method converts an OutboundMessage to email format and sends it
        through the provider, including proper threading headers (In-Reply-To,
        References) to maintain conversation context.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Extract reply headers from raw metadata if this is a reply
            in_reply_to = None
            references = None

            if message.reply_to_message_id:
                # Extract original message ID from our prefixed format
                # Format: "email_{message_id}"
                if message.reply_to_message_id.startswith("email_"):
                    original_msg_id = message.reply_to_message_id[6:]  # Strip "email_" prefix
                    in_reply_to = f"<{original_msg_id}>"

                    # Build References header
                    # If original message had references, include them
                    # For simplicity, just use the message we're replying to
                    references = in_reply_to

            # Extract recipient from user_key (should be email address)
            to_addresses = [message.user_key]

            # Generate subject line
            # If replying, prefix with "Re: "
            subject = message.metadata.get("subject", "Message from AgentOS")
            if in_reply_to and not subject.startswith("Re: "):
                subject = f"Re: {subject}"

            # Send message via provider
            result = self.provider.send_message(
                to_addresses=to_addresses,
                subject=subject,
                text_body=message.text,
                html_body=None,  # TODO: Support HTML formatting
                in_reply_to=in_reply_to,
                references=references,
                cc_addresses=None,
                attachments=None  # TODO: Support attachments
            )

            if result.success:
                logger.info(
                    f"Sent email via {self.channel_id}: "
                    f"to={message.user_key}, subject={subject}, "
                    f"message_id={result.message_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to send email via {self.channel_id}: "
                    f"to={message.user_key}, error={result.error_message}"
                )
                return False

        except Exception as e:
            logger.exception(
                f"Exception sending email via {self.channel_id}: {e}"
            )
            return False


__all__ = [
    "EmailAdapter",
    "CursorStore",
]
