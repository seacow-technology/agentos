"""
Session Store Abstractions

⚠️ DEPRECATED (PR-2):
This module is deprecated as of PR-2. All session management has been
unified to use ChatService (agentos.core.chat.service.ChatService).

New sessions are stored in chat_sessions table, not webui_sessions.
This module is kept for backward compatibility during migration (PR-3).

Use ChatService instead:
    from agentos.core.chat.service import ChatService
    chat_service = ChatService()
    session = chat_service.create_session(title="My Session")

---

Provides pluggable storage backends for WebUI sessions and messages.

Architecture Decision:
- WebUI storage is independent of Core storage (task/run tables)
- Allows different cleanup policies, scaling strategies, and backup schedules
- Memory store for testing/fallback, SQLite store for production
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
import sqlite3
import json
import ulid

from .models import Session, Message


class SessionStore(ABC):
    """
    Abstract Session Store Interface

    Implementations:
    - MemorySessionStore: In-memory (testing, fallback)
    - SQLiteSessionStore: Persistent (production)
    """

    @abstractmethod
    def create_session(
        self,
        user_id: str = "default",
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None
    ) -> Session:
        """Create a new session (optionally with specific session_id for backward compatibility)"""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        pass

    @abstractmethod
    def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Session]:
        """List sessions (paginated, ordered by updated_at DESC)"""
        pass

    @abstractmethod
    def update_session(self, session_id: str, metadata: dict) -> bool:
        """Update session metadata and updated_at"""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete session and all its messages"""
        pass

    @abstractmethod
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Message:
        """Add message to session"""
        pass

    @abstractmethod
    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Message]:
        """Get messages for session (paginated, ordered by created_at ASC)"""
        pass

    @abstractmethod
    def count_messages(self, session_id: str) -> int:
        """Count messages in session"""
        pass


class MemorySessionStore(SessionStore):
    """
    In-Memory Session Store

    Use cases:
    - Unit tests
    - Development fallback
    - Degraded mode (when DB unavailable)

    Limitations:
    - Data lost on restart
    - No cross-process sharing
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._messages: dict[str, list[Message]] = {}  # session_id -> messages

    def create_session(
        self,
        user_id: str = "default",
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None
    ) -> Session:
        if session_id is None:
            session_id = str(ulid.ULID())
        session = Session(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {}
        )
        self._sessions[session_id] = session
        self._messages[session_id] = []
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Session]:
        sessions = list(self._sessions.values())

        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]

        # Sort by updated_at DESC
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[offset:offset + limit]

    def update_session(self, session_id: str, metadata: dict) -> bool:
        if session_id not in self._sessions:
            return False

        self._sessions[session_id].metadata.update(metadata)
        self._sessions[session_id].updated_at = datetime.now(timezone.utc)
        return True

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False

        del self._sessions[session_id]
        self._messages.pop(session_id, None)
        return True

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Message:
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")

        message_id = str(ulid.ULID())
        message = Message(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )

        # Validate before adding
        is_valid, error = message.validate()
        if not is_valid:
            raise ValueError(f"Invalid message: {error}")

        self._messages[session_id].append(message)

        # Update session timestamp
        self._sessions[session_id].updated_at = datetime.now(timezone.utc)

        return message

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Message]:
        messages = self._messages.get(session_id, [])
        return messages[offset:offset + limit]

    def count_messages(self, session_id: str) -> int:
        return len(self._messages.get(session_id, []))


class SQLiteSessionStore(SessionStore):
    """
    SQLite Session Store

    Production implementation with:
    - Persistent storage
    - Transaction support
    - Efficient indexing
    - Cascading deletes

    Schema: store/webui_schema.sql
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure tables exist (idempotent)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 统一数据库配置 (与主库保持一致)
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webui_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webui_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES webui_sessions(session_id)
                        ON DELETE CASCADE
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
                ON webui_sessions(user_id, updated_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                ON webui_messages(session_id, created_at ASC)
            """)

            conn.commit()

    def create_session(
        self,
        user_id: str = "default",
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None
    ) -> Session:
        if session_id is None:
            session_id = str(ulid.ULID())
        now = datetime.now(timezone.utc).isoformat()

        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            metadata=metadata or {}
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO webui_sessions
                (session_id, user_id, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    now,
                    now,
                    json.dumps(metadata or {})
                )
            )
            conn.commit()

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, user_id, created_at, updated_at, metadata "
                "FROM webui_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Session.from_db_row(row)

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Session]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if user_id:
                cursor.execute(
                    "SELECT session_id, user_id, created_at, updated_at, metadata "
                    "FROM webui_sessions WHERE user_id = ? "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (user_id, limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT session_id, user_id, created_at, updated_at, metadata "
                    "FROM webui_sessions "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )

            rows = cursor.fetchall()
            return [Session.from_db_row(row) for row in rows]

    def update_session(self, session_id: str, metadata: dict) -> bool:
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get current metadata
            cursor.execute(
                "SELECT metadata FROM webui_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if not row:
                return False

            current_metadata = json.loads(row[0]) if row[0] else {}
            current_metadata.update(metadata)

            cursor.execute(
                "UPDATE webui_sessions SET metadata = ?, updated_at = ? "
                "WHERE session_id = ?",
                (json.dumps(current_metadata), now, session_id)
            )
            conn.commit()

            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # PRAGMA 已在 _ensure_schema 中统一配置,无需重复设置

            cursor.execute(
                "DELETE FROM webui_sessions WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()

            return cursor.rowcount > 0

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Message:
        message_id = str(ulid.ULID())
        now = datetime.now(timezone.utc).isoformat()

        message = Message(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.fromisoformat(now),
            metadata=metadata or {}
        )

        # Validate
        is_valid, error = message.validate()
        if not is_valid:
            raise ValueError(f"Invalid message: {error}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Verify session exists
            cursor.execute(
                "SELECT 1 FROM webui_sessions WHERE session_id = ?",
                (session_id,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Session not found: {session_id}")

            # Insert message
            cursor.execute(
                """
                INSERT INTO webui_messages
                (message_id, session_id, role, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    now,
                    json.dumps(metadata or {})
                )
            )

            # Update session timestamp
            cursor.execute(
                "UPDATE webui_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id)
            )

            conn.commit()

        return message

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Message]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT message_id, session_id, role, content, created_at, metadata "
                "FROM webui_messages WHERE session_id = ? "
                "ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (session_id, limit, offset)
            )

            rows = cursor.fetchall()
            return [Message.from_db_row(row) for row in rows]

    def count_messages(self, session_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM webui_messages WHERE session_id = ?",
                (session_id,)
            )
            return cursor.fetchone()[0]
