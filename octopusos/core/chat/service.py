"""Chat service for managing chat sessions and messages"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from agentos.core.chat.models import ChatSession, ChatMessage, ConversationMode
from agentos.core.db import registry_db
from agentos.core.chat.xss_sanitizer import (
    sanitize_session_title,
    sanitize_message_content,
    sanitize_metadata
)

logger = logging.getLogger(__name__)

# Valid message roles (case-insensitive)
VALID_MESSAGE_ROLES = {"user", "assistant", "system"}


def _generate_ulid() -> str:
    """Generate a ULID (Universally Unique Lexicographically Sortable Identifier)"""
    from ulid import ULID
    return str(ULID())


def validate_message_role(role: str) -> str:
    """
    Validate and normalize message role.

    This function provides strict validation to prevent privilege escalation
    and data integrity issues. Only 'user', 'assistant', and 'system' roles
    are allowed (case-insensitive).

    Args:
        role: The role to validate

    Returns:
        Normalized role (lowercase)

    Raises:
        ValueError: If role is invalid, empty, or not a string

    Security Note:
        This validation prevents privilege escalation attacks where malicious
        actors could inject unauthorized roles like "admin", "root", etc.
        All roles are normalized to lowercase to prevent case-based bypasses.
    """
    # Check for empty or non-string roles
    if not role or not isinstance(role, str):
        raise ValueError("Role must be a non-empty string")

    # Normalize to lowercase and strip whitespace
    role_normalized = role.strip().lower()

    # Validate against whitelist
    if role_normalized not in VALID_MESSAGE_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_MESSAGE_ROLES))}"
        )

    return role_normalized


class ChatService:
    """Service for managing chat sessions and messages"""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize ChatService

        Args:
            db_path: Path to database file (defaults to AgentOS registry DB)
                     Note: This parameter is kept for backward compatibility but
                     is ignored. All DB access goes through registry_db.
        """
        # For backward compatibility, accept db_path but use registry_db
        if db_path is not None:
            logger.warning(
                "ChatService: db_path parameter is deprecated and ignored. "
                "All DB access now goes through agentos.core.db.registry_db"
            )

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection via unified registry_db entry point"""
        return registry_db.get_db()

    def _lazy_migrate_session(self, session: ChatSession) -> None:
        """
        Lazy migrate session timestamp to epoch_ms if needed (Task #9: Lazy Migration)

        Called after loading session from database. If epoch_ms fields are NULL,
        this will update them based on the computed values.

        This is a "best effort" operation - failures are logged but don't affect
        the read operation. This ensures graceful degradation.

        Args:
            session: ChatSession object with potential _needs_lazy_migration flag
        """
        # Check if migration is needed (flag set by from_db_row)
        if not getattr(session, '_needs_lazy_migration', False):
            return  # No migration needed

        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Check current state in database
            row = cursor.execute(
                "SELECT created_at_ms, updated_at_ms FROM chat_sessions WHERE session_id = ?",
                (session.session_id,)
            ).fetchone()

            if not row:
                logger.debug(f"Lazy migration skipped: session not found: {session.session_id}")
                return

            # Prepare updates
            needs_update = False
            updates = []
            params = []

            # Check created_at_ms
            if row["created_at_ms"] is None and session.created_at_ms is not None:
                updates.append("created_at_ms = ?")
                params.append(session.created_at_ms)
                needs_update = True

            # Check updated_at_ms
            if row["updated_at_ms"] is None and session.updated_at_ms is not None:
                updates.append("updated_at_ms = ?")
                params.append(session.updated_at_ms)
                needs_update = True

            # Perform update if needed
            if needs_update:
                params.append(session.session_id)
                query = f"UPDATE chat_sessions SET {', '.join(updates)} WHERE session_id = ?"
                cursor.execute(query, params)
                conn.commit()

                logger.debug(
                    f"Lazy migrated session {session.session_id}: "
                    f"created_at_ms={session.created_at_ms}, updated_at_ms={session.updated_at_ms}"
                )

                # Clear the flag to prevent repeated migration attempts
                session._needs_lazy_migration = False

        except Exception as e:
            # Graceful degradation - log but don't raise
            # Migration failure should not break read operations
            logger.warning(f"Lazy migration failed for session {session.session_id}: {e}")

    def _lazy_migrate_message(self, message: ChatMessage) -> None:
        """
        Lazy migrate message timestamp to epoch_ms if needed (Task #9: Lazy Migration)

        Called after loading message from database. If epoch_ms field is NULL,
        this will update it based on the computed value.

        This is a "best effort" operation - failures are logged but don't affect
        the read operation. This ensures graceful degradation.

        Args:
            message: ChatMessage object with potential _needs_lazy_migration flag
        """
        # Check if migration is needed (flag set by from_db_row)
        if not getattr(message, '_needs_lazy_migration', False):
            return  # No migration needed

        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Check current state in database
            row = cursor.execute(
                "SELECT created_at_ms FROM chat_messages WHERE message_id = ?",
                (message.message_id,)
            ).fetchone()

            if not row:
                logger.debug(f"Lazy migration skipped: message not found: {message.message_id}")
                return

            # Perform update if needed
            if row["created_at_ms"] is None and message.created_at_ms is not None:
                cursor.execute(
                    "UPDATE chat_messages SET created_at_ms = ? WHERE message_id = ?",
                    (message.created_at_ms, message.message_id)
                )
                conn.commit()

                logger.debug(
                    f"Lazy migrated message {message.message_id}: "
                    f"created_at_ms={message.created_at_ms}"
                )

                # Clear the flag to prevent repeated migration attempts
                message._needs_lazy_migration = False

        except Exception as e:
            # Graceful degradation - log but don't raise
            # Migration failure should not break read operations
            logger.warning(f"Lazy migration failed for message {message.message_id}: {e}")
    
    # ============================================
    # Session Management
    # ============================================
    
    def create_session(
        self,
        title: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> ChatSession:
        """Create a new chat session

        Args:
            title: Session title (defaults to "New Chat")
            task_id: Optional Task ID to associate with
            metadata: Session metadata (model, provider, context_budget, etc.)
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            Created ChatSession
        """
        from agentos.store.timestamp_utils import now_ms, from_epoch_ms

        session_id = session_id or _generate_ulid()
        title = title or "New Chat"
        metadata = metadata or {}

        # XSS Protection (Task #34): Sanitize title and metadata before storage
        title = sanitize_session_title(title)
        metadata = sanitize_metadata(metadata)

        # Set default metadata
        if "model" not in metadata:
            metadata["model"] = "local"
        if "provider" not in metadata:
            metadata["provider"] = "ollama"
        if "context_budget" not in metadata:
            metadata["context_budget"] = 8000
        if "rag_enabled" not in metadata:
            metadata["rag_enabled"] = True

        # Set default conversation_mode and execution_phase
        # conversation_mode: UI/UX context (default: "chat")
        # execution_phase: Security context (default: "planning" for safety)
        if "conversation_mode" not in metadata:
            metadata["conversation_mode"] = ConversationMode.CHAT.value
        if "execution_phase" not in metadata:
            metadata["execution_phase"] = "planning"  # Safe default

        # Set default project_id for memory context (cross-session sharing)
        if "project_id" not in metadata or not metadata["project_id"]:
            metadata["project_id"] = "default"

        # Task #8: Dual Write - Generate epoch_ms timestamp
        now = now_ms()
        created_at = from_epoch_ms(now)
        updated_at = created_at

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Task #8: Dual Write - Insert both TIMESTAMP and epoch_ms fields
            cursor.execute(
                """
                INSERT INTO chat_sessions
                (session_id, title, task_id, metadata, created_at, updated_at, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    task_id,
                    json.dumps(metadata),
                    created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    now,
                    now
                )
            )
            conn.commit()

            logger.info(f"Created chat session: {session_id} - {title}")

            # Fetch and return the created session
            return self.get_session(session_id)

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create chat session: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def get_session(self, session_id: str) -> ChatSession:
        """Get chat session by ID with lazy migration (Task #9: Lazy Migration)

        Args:
            session_id: Session ID

        Returns:
            ChatSession

        Raises:
            ValueError: If session not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            row = cursor.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Chat session not found: {session_id}")

            session = ChatSession.from_db_row(row)

            # Trigger lazy migration if needed
            self._lazy_migrate_session(session)

            return session

        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        task_id: Optional[str] = None
    ) -> List[ChatSession]:
        """List chat sessions with lazy migration (Task #9: Lazy Migration)

        Args:
            limit: Maximum number of sessions to return
            offset: Offset for pagination
            task_id: Filter by task ID

        Returns:
            List of ChatSession objects
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if task_id:
                rows = cursor.execute(
                    """
                    SELECT * FROM chat_sessions
                    WHERE task_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (task_id, limit, offset)
                ).fetchall()
            else:
                rows = cursor.execute(
                    """
                    SELECT * FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                ).fetchall()

            sessions = [ChatSession.from_db_row(row) for row in rows]

            # Lazy migrate each session (best effort - failures logged but don't block)
            for session in sessions:
                self._lazy_migrate_session(session)

            return sessions

        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Update session metadata

        Args:
            session_id: Session ID
            metadata: New metadata (merges with existing)
        """
        from agentos.store.timestamp_utils import now_ms, from_epoch_ms

        # XSS Protection (Task #34): Sanitize metadata before storage
        metadata = sanitize_metadata(metadata)

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Get current metadata
            session = self.get_session(session_id)
            current_metadata = session.metadata

            # Merge with new metadata
            current_metadata.update(metadata)

            # Task #8: Dual Write - Update both TIMESTAMP and epoch_ms fields
            now = now_ms()
            updated_at = from_epoch_ms(now)

            # Update in database
            cursor.execute(
                """
                UPDATE chat_sessions
                SET metadata = ?,
                    updated_at = ?,
                    updated_at_ms = ?
                WHERE session_id = ?
                """,
                (json.dumps(current_metadata), updated_at.strftime("%Y-%m-%d %H:%M:%S"), now, session_id)
            )
            conn.commit()

            logger.info(f"Updated metadata for session: {session_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update session metadata: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def update_session_title(
        self,
        session_id: str,
        title: str
    ) -> None:
        """Update session title

        Args:
            session_id: Session ID
            title: New title
        """
        from agentos.store.timestamp_utils import now_ms, from_epoch_ms

        # XSS Protection (Task #34): Sanitize title before storage
        title = sanitize_session_title(title)

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Task #8: Dual Write - Update both TIMESTAMP and epoch_ms fields
            now = now_ms()
            updated_at = from_epoch_ms(now)

            cursor.execute(
                """
                UPDATE chat_sessions
                SET title = ?,
                    updated_at = ?,
                    updated_at_ms = ?
                WHERE session_id = ?
                """,
                (title, updated_at.strftime("%Y-%m-%d %H:%M:%S"), now, session_id)
            )
            conn.commit()

            logger.info(f"Updated title for session {session_id}: {title}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update session title: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def delete_session(self, session_id: str) -> None:
        """Delete chat session (and all its messages via CASCADE)
        
        Args:
            session_id: Session ID
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "DELETE FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            
            logger.info(f"Deleted chat session: {session_id}")
        
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to delete session: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    # ============================================
    # Message Management
    # ============================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """Add a message to a chat session

        Args:
            session_id: Session ID
            role: Message role (user/assistant/system only - validated strictly)
            content: Message content
            metadata: Message metadata (tokens_est, source, citations, etc.)

        Returns:
            Created ChatMessage

        Raises:
            ValueError: If role is invalid or session not found
        """
        from agentos.store.timestamp_utils import now_ms, from_epoch_ms

        message_id = _generate_ulid()
        metadata = metadata or {}

        # Role Validation (H-1 to H-7): Validate and normalize role
        # This prevents privilege escalation via invalid roles like "admin", "root", etc.
        role = validate_message_role(role)

        # XSS Protection (Task #34): Sanitize content and metadata before storage
        content = sanitize_message_content(content, preserve_markdown=True)
        metadata = sanitize_metadata(metadata)

        # Auto-estimate tokens if not provided
        if "tokens_est" not in metadata:
            metadata["tokens_est"] = int(len(content) * 1.3)

        # Task #8: Dual Write - Generate epoch_ms timestamp
        now = now_ms()
        created_at = from_epoch_ms(now)

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Idempotency check: Prevent duplicate messages within 1 minute
            # This prevents the same content from being stored multiple times
            # when WebSocket and ChatEngine both try to save user messages
            cursor.execute(
                """
                SELECT message_id FROM chat_messages
                WHERE session_id = ? AND role = ? AND content = ?
                AND created_at > datetime('now', '-1 minute')
                LIMIT 1
                """,
                (session_id, role, content)
            )

            existing = cursor.fetchone()
            if existing:
                existing_id = existing[0]
                logger.warning(
                    f"Duplicate message content detected within 1 minute for session {session_id}. "
                    f"Returning existing message {existing_id} instead of creating new one."
                )
                conn.commit()  # Ensure transaction is completed
                return self.get_message(existing_id)

            # Task #8: Dual Write - Insert both TIMESTAMP and epoch_ms fields
            cursor.execute(
                """
                INSERT INTO chat_messages
                (message_id, session_id, role, content, metadata, created_at, created_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    json.dumps(metadata),
                    created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    now
                )
            )

            # Update session updated_at (both formats)
            cursor.execute(
                """
                UPDATE chat_sessions
                SET updated_at = ?,
                    updated_at_ms = ?
                WHERE session_id = ?
                """,
                (created_at.strftime("%Y-%m-%d %H:%M:%S"), now, session_id)
            )

            conn.commit()

            logger.debug(f"Added {role} message to session {session_id}: {message_id}")

            # Fetch and return the created message
            message = self.get_message(message_id)

            return message

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to add message: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass

            # NEW (Task #5): Trigger memory extraction (async, non-blocking)
            # IMPORTANT: This must be in finally block AFTER return to ensure
            # extraction errors don't affect message saving (graceful degradation)
            try:
                if 'message' in locals() and message.role in ["user", "assistant"]:
                    self._trigger_memory_extraction_async(message)
            except Exception as extraction_err:
                # Suppress extraction errors - they should not affect message flow
                logger.warning(f"Memory extraction trigger failed: {extraction_err}")
    
    def get_message(self, message_id: str) -> ChatMessage:
        """Get message by ID with lazy migration (Task #9: Lazy Migration)

        Args:
            message_id: Message ID

        Returns:
            ChatMessage

        Raises:
            ValueError: If message not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            row = cursor.execute(
                "SELECT * FROM chat_messages WHERE message_id = ?",
                (message_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Chat message not found: {message_id}")

            message = ChatMessage.from_db_row(row)

            # Trigger lazy migration if needed
            self._lazy_migrate_message(message)

            return message

        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a chat session with lazy migration (Task #9: Lazy Migration)

        Args:
            session_id: Session ID
            limit: Maximum number of messages (None = all)
            offset: Offset for pagination

        Returns:
            List of ChatMessage objects (ordered by created_at ASC)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if limit:
                rows = cursor.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?
                    """,
                    (session_id, limit, offset)
                ).fetchall()
            else:
                rows = cursor.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """,
                    (session_id,)
                ).fetchall()

            messages = [ChatMessage.from_db_row(row) for row in rows]

            # Lazy migrate each message (best effort - failures logged but don't block)
            for message in messages:
                self._lazy_migrate_message(message)

            return messages

        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def get_recent_messages(
        self,
        session_id: str,
        count: int = 10
    ) -> List[ChatMessage]:
        """Get recent messages for a session with lazy migration (Task #9: Lazy Migration)

        Args:
            session_id: Session ID
            count: Number of recent messages to get

        Returns:
            List of ChatMessage objects (ordered by created_at DESC, then reversed)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            rows = cursor.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, count)
            ).fetchall()

            # Reverse to get chronological order
            messages = [ChatMessage.from_db_row(row) for row in rows]
            messages.reverse()

            # Lazy migrate each message (best effort - failures logged but don't block)
            for message in messages:
                self._lazy_migrate_message(message)

            return messages

        finally:
            # Connection is thread-local, managed by registry_db
            pass
    
    def count_messages(self, session_id: str) -> int:
        """Count messages in a session

        Args:
            session_id: Session ID

        Returns:
            Number of messages
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            result = cursor.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            return result[0]

        finally:
            # Connection is thread-local, managed by registry_db
            pass

    def delete_message(self, message_id: str) -> None:
        """Delete a single message

        Args:
            message_id: Message ID to delete

        Raises:
            ValueError: If message not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Check if message exists
            row = cursor.execute(
                "SELECT session_id FROM chat_messages WHERE message_id = ?",
                (message_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Message not found: {message_id}")

            session_id = row[0]

            # Delete the message
            cursor.execute(
                "DELETE FROM chat_messages WHERE message_id = ?",
                (message_id,)
            )

            # Update session updated_at
            cursor.execute(
                """
                UPDATE chat_sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,)
            )

            conn.commit()
            logger.debug(f"Deleted message: {message_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to delete message: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass

    def delete_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple messages (batch delete)

        Args:
            message_ids: List of message IDs to delete

        Returns:
            Dict with deleted_count and any failed message IDs
        """
        if not message_ids:
            return {"deleted_count": 0, "failed_ids": []}

        conn = self._get_conn()
        cursor = conn.cursor()

        deleted_count = 0
        failed_ids = []
        session_ids_to_update = set()

        try:
            for message_id in message_ids:
                try:
                    # Get session_id before deletion
                    row = cursor.execute(
                        "SELECT session_id FROM chat_messages WHERE message_id = ?",
                        (message_id,)
                    ).fetchone()

                    if row:
                        session_id = row[0]
                        session_ids_to_update.add(session_id)

                        # Delete the message
                        cursor.execute(
                            "DELETE FROM chat_messages WHERE message_id = ?",
                            (message_id,)
                        )
                        deleted_count += 1
                        logger.debug(f"Deleted message: {message_id}")
                    else:
                        failed_ids.append(message_id)
                        logger.warning(f"Message not found: {message_id}")

                except Exception as e:
                    failed_ids.append(message_id)
                    logger.error(f"Failed to delete message {message_id}: {e}")

            # Update all affected sessions
            for session_id in session_ids_to_update:
                cursor.execute(
                    """
                    UPDATE chat_sessions
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                    """,
                    (session_id,)
                )

            conn.commit()
            logger.info(f"Batch deleted {deleted_count} messages")

            return {
                "deleted_count": deleted_count,
                "failed_ids": failed_ids
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to batch delete messages: {e}")
            raise
        finally:
            # Connection is thread-local, managed by registry_db
            pass

    # ============================================
    # Conversation Mode and Execution Phase Management
    # ============================================

    def get_conversation_mode(self, session_id: str) -> str:
        """Get conversation mode for a session.

        Args:
            session_id: Session ID

        Returns:
            Conversation mode (default: "chat")
        """
        session = self.get_session(session_id)
        return session.metadata.get("conversation_mode", ConversationMode.CHAT.value)

    def update_conversation_mode(self, session_id: str, mode: str) -> None:
        """Update conversation mode for a session.

        This method updates the UI/UX context for the conversation.
        It does NOT affect security controls (execution_phase).

        Args:
            session_id: Session ID
            mode: Conversation mode (chat/discussion/plan/development/task)

        Raises:
            ValueError: If mode is invalid
        """
        # Validate mode
        try:
            ConversationMode(mode)
        except ValueError:
            valid_modes = [m.value for m in ConversationMode]
            raise ValueError(
                f"Invalid conversation mode: {mode}. "
                f"Valid modes: {', '.join(valid_modes)}"
            )

        # Update metadata
        self.update_session_metadata(session_id, {"conversation_mode": mode})
        logger.info(f"Updated conversation_mode for session {session_id}: {mode}")

    def get_execution_phase(self, session_id: str) -> str:
        """Get execution phase for a session.

        Args:
            session_id: Session ID

        Returns:
            Execution phase (default: "planning")
        """
        session = self.get_session(session_id)
        return session.metadata.get("execution_phase", "planning")

    def update_execution_phase(
        self,
        session_id: str,
        phase: str,
        actor: str = "system",
        reason: Optional[str] = None
    ) -> None:
        """Update execution phase for a session with audit logging.

        This method changes the security context for external operations.
        All phase changes are audited for security and compliance.

        Args:
            session_id: Session ID
            phase: Execution phase (planning/execution)
            actor: Who initiated the phase change (default: "system")
            reason: Optional reason for the change

        Raises:
            ValueError: If phase is invalid
        """
        # Validate phase
        valid_phases = ["planning", "execution"]
        if phase not in valid_phases:
            raise ValueError(
                f"Invalid execution phase: {phase}. "
                f"Valid phases: {', '.join(valid_phases)}"
            )

        # Get current phase for audit
        try:
            current_phase = self.get_execution_phase(session_id)
        except Exception:
            current_phase = "unknown"

        # Update metadata
        self.update_session_metadata(session_id, {"execution_phase": phase})

        # Audit log for phase change
        try:
            from agentos.core.capabilities.audit import emit_audit_event

            emit_audit_event(
                event_type="execution_phase_changed",
                details={
                    "session_id": session_id,
                    "old_phase": current_phase,
                    "new_phase": phase,
                    "actor": actor,
                    "reason": reason or "No reason provided"
                },
                task_id=None,  # Chat sessions may not have task_id
                level="info"
            )
        except Exception as e:
            # Graceful degradation - log but don't fail the operation
            logger.warning(f"Failed to emit audit event for phase change: {e}")

        logger.info(
            f"Updated execution_phase for session {session_id}: "
            f"{current_phase} -> {phase} (actor: {actor})"
        )

    def _trigger_memory_extraction_async(self, message: ChatMessage) -> None:
        """Trigger asynchronous memory extraction from message (Task #5)

        This runs in background and does not block the response.
        Memory extraction failures are logged but do not affect the message flow.

        Args:
            message: ChatMessage to extract memories from
        """
        import asyncio
        import threading

        try:
            # Create async task in a separate thread to avoid blocking sync code
            def run_extraction():
                """Run extraction in a new event loop"""
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # Import here to avoid circular dependencies
                        from agentos.core.chat.memory_extractor import extract_and_store_async
                        from agentos.core.memory.service import MemoryService

                        memory_service = MemoryService()

                        # Run extraction
                        count = loop.run_until_complete(extract_and_store_async(
                            message=message,
                            session_id=message.session_id,
                            memory_service=memory_service,
                            project_id=None,  # Could be extracted from session metadata if needed
                            agent_id="webui_chat"
                        ))

                        if count > 0:
                            logger.info(
                                f"Memory extraction completed: "
                                f"message_id={message.message_id}, extracted={count}"
                            )

                            # Emit audit event for observability
                            try:
                                from agentos.core.capabilities.audit import emit_audit_event

                                emit_audit_event(
                                    event_type="memory_extracted",
                                    details={
                                        "session_id": message.session_id,
                                        "message_id": message.message_id,
                                        "memory_count": count,
                                        "role": message.role
                                    },
                                    level="info"
                                )
                            except Exception as audit_err:
                                logger.warning(f"Failed to emit audit event: {audit_err}")

                    finally:
                        loop.close()

                except Exception as e:
                    # Log error but don't propagate - graceful degradation
                    logger.warning(
                        f"Memory extraction failed for message {message.message_id}: {e}",
                        exc_info=True
                    )

            # Start extraction in background thread
            thread = threading.Thread(
                target=run_extraction,
                name=f"memory-extract-{message.message_id[:8]}",
                daemon=True  # Don't block process exit
            )
            thread.start()

            logger.debug(f"Scheduled memory extraction for message {message.message_id}")

        except Exception as e:
            # Graceful degradation - log error but don't fail the message
            logger.warning(f"Failed to schedule memory extraction: {e}")
