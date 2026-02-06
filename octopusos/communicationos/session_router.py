"""Session routing for CommunicationOS.

⚠️ PROTOCOL FROZEN (v1) - See ADR-014 ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SessionRouter logic and key formats are FROZEN v1.

Frozen Key Formats:
- USER scope: "{channel_id}:{user_key}"
- USER_CONVERSATION scope: "{channel_id}:{user_key}:{conversation_key}"

Changing these formats is a BREAKING CHANGE requiring RFC and v2.0.
Last frozen: 2026-02-01
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module provides session resolution and routing functionality that maps
inbound messages to AgentOS sessions based on channel scope configuration.

Design Principles:
- Channel-driven: Session mapping based on channel manifest session_scope
- Deterministic: Same inputs always produce same session mapping
- Flexible: Support both USER and USER_CONVERSATION scopes
- Audit-friendly: Clear mapping logic for debugging
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agentos.communicationos.models import InboundMessage
from agentos.communicationos.manifest import SessionScope
from agentos.communicationos.registry import ChannelRegistry


@dataclass
class ResolvedContext:
    """Resolved context for message routing.

    This represents the complete routing context after analyzing an inbound
    message and channel configuration.

    Attributes:
        channel_id: Channel identifier
        user_key: User identifier within the channel
        conversation_key: Conversation/thread identifier
        session_scope: Resolved session scope from channel manifest
        session_lookup_key: Key used to look up the active session
        title_hint: Suggested session title (e.g., first message text)
    """

    channel_id: str
    user_key: str
    conversation_key: str
    session_scope: SessionScope
    session_lookup_key: str
    title_hint: Optional[str] = None

    def __post_init__(self):
        """Validate the resolved context."""
        if not self.channel_id:
            raise ValueError("channel_id cannot be empty")
        if not self.user_key:
            raise ValueError("user_key cannot be empty")
        if not self.conversation_key:
            raise ValueError("conversation_key cannot be empty")
        if not self.session_lookup_key:
            raise ValueError("session_lookup_key cannot be empty")


class SessionRouter:
    """Routes inbound messages to sessions based on channel scope.

    The SessionRouter resolves which session an inbound message should be
    routed to by:
    1. Looking up the channel manifest to get session_scope
    2. Computing the session lookup key based on scope
    3. Providing context for session creation/lookup

    Example:
        >>> registry = ChannelRegistry()
        >>> router = SessionRouter(registry)
        >>> message = InboundMessage(
        ...     channel_id="whatsapp_business",
        ...     user_key="+1234567890",
        ...     conversation_key="+1234567890",
        ...     message_id="msg_001",
        ...     text="Hello"
        ... )
        >>> context = router.resolve(message)
        >>> print(context.session_scope)
        SessionScope.USER
        >>> print(context.session_lookup_key)
        whatsapp_business:+1234567890
    """

    def __init__(self, channel_registry: ChannelRegistry):
        """Initialize the session router.

        Args:
            channel_registry: Registry to look up channel manifests
        """
        self._registry = channel_registry

    def resolve(self, message: InboundMessage) -> ResolvedContext:
        """Resolve session context for an inbound message.

        This method determines which session the message belongs to based on:
        - Channel manifest session_scope configuration
        - Message identifiers (channel_id, user_key, conversation_key)

        Args:
            message: Inbound message to resolve context for

        Returns:
            ResolvedContext with routing information

        Raises:
            ValueError: If channel is not found or message is invalid
        """
        # Look up channel manifest
        manifest = self._registry.get_manifest(message.channel_id)
        if not manifest:
            raise ValueError(f"Channel not found: {message.channel_id}")

        # Get session scope from manifest
        session_scope = manifest.session_scope

        # Compute session lookup key based on scope
        if session_scope == SessionScope.USER:
            # One session per user across all conversations
            session_lookup_key = f"{message.channel_id}:{message.user_key}"
        elif session_scope == SessionScope.USER_CONVERSATION:
            # One session per user-conversation pair
            session_lookup_key = (
                f"{message.channel_id}:{message.user_key}:{message.conversation_key}"
            )
        else:
            raise ValueError(f"Unsupported session scope: {session_scope}")

        # Extract title hint (first 50 chars of text message)
        title_hint = None
        if message.text:
            title_hint = message.text[:50].strip()
            if len(message.text) > 50:
                title_hint += "..."

        return ResolvedContext(
            channel_id=message.channel_id,
            user_key=message.user_key,
            conversation_key=message.conversation_key,
            session_scope=session_scope,
            session_lookup_key=session_lookup_key,
            title_hint=title_hint,
        )

    def compute_lookup_key(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: Optional[str] = None
    ) -> str:
        """Compute session lookup key for given identifiers.

        This is a utility method for computing lookup keys without a full message.

        Args:
            channel_id: Channel identifier
            user_key: User identifier
            conversation_key: Optional conversation identifier

        Returns:
            Session lookup key

        Raises:
            ValueError: If channel is not found
        """
        manifest = self._registry.get_manifest(channel_id)
        if not manifest:
            raise ValueError(f"Channel not found: {channel_id}")

        session_scope = manifest.session_scope

        if session_scope == SessionScope.USER:
            return f"{channel_id}:{user_key}"
        elif session_scope == SessionScope.USER_CONVERSATION:
            if not conversation_key:
                raise ValueError(
                    "conversation_key required for USER_CONVERSATION scope"
                )
            return f"{channel_id}:{user_key}:{conversation_key}"
        else:
            raise ValueError(f"Unsupported session scope: {session_scope}")

    def parse_lookup_key(self, lookup_key: str) -> tuple[str, str, Optional[str]]:
        """Parse a session lookup key back into components.

        Args:
            lookup_key: Session lookup key to parse

        Returns:
            Tuple of (channel_id, user_key, conversation_key)
            conversation_key will be None for USER scope

        Raises:
            ValueError: If lookup_key format is invalid
        """
        parts = lookup_key.split(":", maxsplit=2)
        if len(parts) < 2:
            raise ValueError(f"Invalid lookup key format: {lookup_key}")

        channel_id = parts[0]
        user_key = parts[1]
        conversation_key = parts[2] if len(parts) == 3 else None

        return channel_id, user_key, conversation_key
