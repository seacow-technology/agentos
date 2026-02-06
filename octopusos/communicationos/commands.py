"""Unified command processor for CommunicationOS.

This module provides channel-agnostic command handling for all communication
channels. Commands are processed uniformly across WhatsApp, Telegram, Slack, etc.

Design Principles:
- Channel-agnostic: Commands work the same across all channels
- Session-focused: Core commands manage session lifecycle
- Returns OutboundMessage: Responses use standard message format
- No direct channel access: Commands don't know about specific channels

Supported Commands:
- /session new - Create and activate new session
- /session id - Return current active session ID
- /session list - List recent N sessions
- /session use <id> - Switch to specific session
- /session close - Close current session
- /help - Show command help
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from agentos.communicationos.models import OutboundMessage, MessageType
from agentos.communicationos.manifest import SessionScope
from agentos.core.time import utc_now


@dataclass
class SessionInfo:
    """Information about a session (for command responses).

    This is a simplified view of session data for command responses.
    The actual session data is stored in SessionStore.

    Attributes:
        session_id: Unique session identifier
        channel_id: Channel where session was created
        user_key: User who owns the session
        created_at: When session was created (epoch ms)
        updated_at: Last activity timestamp (epoch ms)
        status: Session status (active/inactive/archived)
        title: Optional human-readable title
    """
    session_id: str
    channel_id: str
    user_key: str
    created_at: int
    updated_at: int
    status: str = "active"
    title: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionInfo:
        """Create SessionInfo from dictionary.

        Args:
            data: Session dictionary from SessionStore

        Returns:
            SessionInfo instance
        """
        return cls(
            session_id=data["session_id"],
            channel_id=data["channel_id"],
            user_key=data["user_key"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data.get("status", "active"),
            title=data.get("title")
        )


class CommandProcessor:
    """Unified command processor for all channels.

    This processor handles slash commands uniformly across all communication
    channels. It manages session lifecycle and returns standardized responses.

    The CommandProcessor wraps the SessionStore to provide user-friendly command
    responses while delegating actual storage to the persistent SessionStore.
    """

    def __init__(self, session_store=None):
        """Initialize command processor.

        Args:
            session_store: Session storage backend. If None, creates new SessionStore.
        """
        # Import here to avoid circular dependency
        if session_store is None:
            from agentos.communicationos.session_store import SessionStore as PersistentSessionStore
            session_store = PersistentSessionStore()

        self.session_store = session_store

    def is_command(self, text: str) -> bool:
        """Check if text is a command.

        Args:
            text: Message text to check

        Returns:
            True if text starts with /
        """
        if not text:
            return False
        return text.strip().startswith("/")

    def process_command(
        self,
        text: str,
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Process a command and return response.

        Args:
            text: Command text (e.g., "/session new")
            channel_id: Channel where command was sent
            user_key: User who sent the command
            conversation_key: Conversation/thread identifier

        Returns:
            OutboundMessage with command response
        """
        text = text.strip()

        # Parse command
        parts = text.split(maxsplit=2)
        command = parts[0].lower()

        # Route to appropriate handler
        if command == "/session":
            if len(parts) < 2:
                return self._error_response(
                    channel_id,
                    user_key,
                    conversation_key,
                    "Usage: /session [new|id|list|use|close]"
                )

            subcommand = parts[1].lower()
            args = parts[2] if len(parts) > 2 else None

            return self._handle_session_command(
                subcommand,
                args,
                channel_id,
                user_key,
                conversation_key
            )

        elif command == "/help":
            return self._handle_help_command(
                channel_id,
                user_key,
                conversation_key
            )

        else:
            return self._error_response(
                channel_id,
                user_key,
                conversation_key,
                f"Unknown command: {command}\nType /help for available commands."
            )

    def _handle_session_command(
        self,
        subcommand: str,
        args: Optional[str],
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Handle /session subcommands.

        Args:
            subcommand: Session subcommand (new/id/list/use/close)
            args: Optional command arguments
            channel_id: Channel identifier
            user_key: User identifier
            conversation_key: Conversation identifier

        Returns:
            OutboundMessage with command response
        """
        if subcommand == "new":
            return self._session_new(channel_id, user_key, conversation_key)

        elif subcommand == "id":
            return self._session_id(channel_id, user_key, conversation_key)

        elif subcommand == "list":
            return self._session_list(channel_id, user_key, conversation_key, args)

        elif subcommand == "use":
            if not args:
                return self._error_response(
                    channel_id,
                    user_key,
                    conversation_key,
                    "Usage: /session use <session_id>"
                )
            return self._session_use(channel_id, user_key, conversation_key, args)

        elif subcommand == "close":
            return self._session_close(channel_id, user_key, conversation_key)

        else:
            return self._error_response(
                channel_id,
                user_key,
                conversation_key,
                f"Unknown session command: {subcommand}\n"
                "Available: new, id, list, use, close"
            )

    def _session_new(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Handle /session new command.

        Creates a new session and sets it as active.
        """
        # Create session with USER scope by default
        # The conversation_key is used for routing but scope determines session isolation
        session_id = self.session_store.create_session(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            scope=SessionScope.USER,
            title=None
        )

        response_text = (
            f"✅ New session created: {session_id} (active)\n\n"
            f"All messages will now be associated with this session."
        )

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=response_text,
            metadata={"command": "session_new", "session_id": session_id}
        )

    def _session_id(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Handle /session id command.

        Returns the current active session ID.
        """
        session_data = self.session_store.get_active_session(channel_id, user_key, conversation_key)

        if session_data:
            session_id = session_data["session_id"]
            # Convert epoch ms to datetime for display
            created_at_ms = session_data["created_at"]
            created_dt = datetime.fromtimestamp(created_at_ms / 1000.0, tz=None)

            response_text = (
                f"📋 Current active session: {session_id}\n\n"
                f"Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Status: {session_data.get('status', 'active')}\n"
                f"Messages: {session_data.get('message_count', 0)}"
            )
        else:
            session_id = None
            response_text = (
                "ℹ️ No active session.\n\n"
                "Create one with: /session new"
            )

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=response_text,
            metadata={"command": "session_id", "session_id": session_id}
        )

    def _session_list(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str,
        args: Optional[str]
    ) -> OutboundMessage:
        """Handle /session list command.

        Lists recent sessions (default: 10).
        """
        # Parse limit from args (default: 10)
        limit = 10
        if args:
            try:
                limit = int(args)
                limit = max(1, min(limit, 50))  # Clamp between 1 and 50
            except ValueError:
                pass  # Use default

        sessions_data = self.session_store.list_sessions(channel_id, user_key, limit=limit)
        active_session_data = self.session_store.get_active_session(channel_id, user_key, conversation_key)
        active_id = active_session_data["session_id"] if active_session_data else None

        if not sessions_data:
            response_text = (
                "ℹ️ No sessions found.\n\n"
                "Create one with: /session new"
            )
        else:
            lines = [f"📋 Recent sessions (showing {len(sessions_data)}):\n"]

            for session_data in sessions_data:
                session_id = session_data["session_id"]
                marker = "🟢" if session_id == active_id else "⚪"
                status = "(active)" if session_id == active_id else f"({session_data.get('status', 'active')})"

                # Convert epoch ms to datetime
                created_at_ms = session_data["created_at"]
                created_dt = datetime.fromtimestamp(created_at_ms / 1000.0, tz=None)

                title = session_data.get("title", "")
                title_str = f" - {title}" if title else ""

                lines.append(
                    f"{marker} {session_id} {status}{title_str}\n"
                    f"   Created: {created_dt.strftime('%Y-%m-%d %H:%M')} | "
                    f"Messages: {session_data.get('message_count', 0)}"
                )

            lines.append("\nSwitch with: /session use <session_id>")
            response_text = "\n".join(lines)

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=response_text,
            metadata={"command": "session_list", "count": len(sessions_data)}
        )

    def _session_use(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str,
        session_id: str
    ) -> OutboundMessage:
        """Handle /session use command.

        Switches to a different session.
        """
        session_id = session_id.strip()

        # Check if session exists
        session_data = self.session_store.get_session(session_id)
        if not session_data:
            return self._error_response(
                channel_id,
                user_key,
                conversation_key,
                f"❌ Session not found: {session_id}\n\n"
                f"List available sessions with: /session list"
            )

        # Check if session belongs to this user
        if session_data["channel_id"] != channel_id or session_data["user_key"] != user_key:
            return self._error_response(
                channel_id,
                user_key,
                conversation_key,
                f"❌ Session {session_id} does not belong to you."
            )

        # Set as active
        try:
            self.session_store.switch_session(
                channel_id,
                user_key,
                conversation_key,
                session_id
            )
            response_text = (
                f"✅ Switched to session: {session_id}\n\n"
                f"All messages will now be associated with this session."
            )
        except ValueError as e:
            response_text = f"❌ Failed to switch to session: {str(e)}"

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=response_text,
            metadata={"command": "session_use", "session_id": session_id}
        )

    def _session_close(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Handle /session close command.

        Archives the current active session.
        """
        session_data = self.session_store.get_active_session(channel_id, user_key, conversation_key)

        if not session_data:
            return self._error_response(
                channel_id,
                user_key,
                conversation_key,
                "ℹ️ No active session to close."
            )

        session_id = session_data["session_id"]

        try:
            # Archive the session
            self.session_store.archive_session(session_id)

            response_text = (
                f"✅ Session closed: {session_id}\n\n"
                f"The session has been archived. Create a new session with: /session new"
            )
        except Exception as e:
            response_text = f"❌ Failed to close session: {str(e)}"

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=response_text,
            metadata={"command": "session_close", "session_id": session_id}
        )

    def _handle_help_command(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str
    ) -> OutboundMessage:
        """Handle /help command.

        Returns help text with available commands.
        """
        help_text = """🤖 AgentOS CommunicationOS - Available Commands

📋 Session Management:
  /session new         - Create and activate new session
  /session id          - Show current active session
  /session list [N]    - List recent N sessions (default: 10)
  /session use <id>    - Switch to specific session
  /session close       - Close current session

ℹ️ Help:
  /help                - Show this help message

💡 Tips:
- Sessions keep your conversation context separate
- All messages are associated with your active session
- You can switch between sessions anytime

🔒 Security:
- This channel is configured for chat-only mode
- Execution commands require explicit approval
"""

        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=help_text,
            metadata={"command": "help"}
        )

    def _error_response(
        self,
        channel_id: str,
        user_key: str,
        conversation_key: str,
        error_message: str
    ) -> OutboundMessage:
        """Create an error response message.

        Args:
            channel_id: Channel identifier
            user_key: User identifier
            conversation_key: Conversation identifier
            error_message: Error message to display

        Returns:
            OutboundMessage with error
        """
        return OutboundMessage(
            channel_id=channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            type=MessageType.TEXT,
            text=error_message,
            metadata={"error": True}
        )
