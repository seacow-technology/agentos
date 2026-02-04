"""Twilio Session Repository - Persistent Storage for Twilio Voice Sessions.

Task #12 (Wave A2): Replace in-memory _twilio_sessions dict with database storage.

This repository provides:
- Create, read, update operations for Twilio sessions
- Event logging for call lifecycle tracking
- Query support for session management
- Automatic timestamp management
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now, to_epoch_ms
from agentos.core.communication.voice.models import VoiceSession, VoiceSessionState

logger = logging.getLogger(__name__)


class TwilioSessionRepo:
    """Repository for managing Twilio voice sessions in persistent storage.

    This class provides database operations for Twilio voice sessions,
    replacing the in-memory _twilio_sessions dict with persistent storage.

    Thread Safety:
        - Read operations are thread-safe (SQLite handles concurrent reads)
        - Write operations should use SQLiteWriter for serialization
        - For MVP, using direct connection (will migrate to SQLiteWriter if needed)
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize repository with database connection.

        Args:
            db_path: Path to database file. If None, uses default AgentOS database.
        """
        if db_path is None:
            db_path = str(component_db_path("agentos"))

        self.db_path = db_path
        logger.info(f"TwilioSessionRepo initialized with database: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection.

        Returns:
            SQLite connection with row factory enabled
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, session: VoiceSession) -> str:
        """Create a new Twilio session in database.

        Args:
            session: VoiceSession object to persist

        Returns:
            session_id of the created session

        Raises:
            sqlite3.IntegrityError: If session_id or call_sid already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now_ms = to_epoch_ms(utc_now())

            # Extract call_sid from transport_metadata
            call_sid = session.transport_metadata.get("call_sid")
            from_number = session.transport_metadata.get("from_number", "")
            to_number = session.transport_metadata.get("to_number", "")
            stream_sid = session.transport_metadata.get("stream_sid")

            if not call_sid:
                raise ValueError("call_sid is required in transport_metadata")

            cursor.execute("""
                INSERT INTO twilio_sessions (
                    session_id, call_sid, from_number, to_number,
                    status, state,
                    started_at, last_activity_at, created_at, updated_at,
                    project_id, stream_sid, transport_metadata,
                    stt_provider, tts_provider,
                    risk_tier, policy_verdict, audit_trace_id,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                call_sid,
                from_number,
                to_number,
                session.state.value,
                session.state.value,  # status = state (compatibility)
                to_epoch_ms(session.created_at),
                to_epoch_ms(session.last_activity_at),
                now_ms,
                now_ms,
                session.project_id,
                stream_sid,
                json.dumps(session.transport_metadata),
                session.stt_provider.value,
                session.tts_provider.value if session.tts_provider else None,
                session.risk_tier,
                session.policy_verdict,
                session.audit_trace_id,
                json.dumps(session.metadata) if session.metadata else None,
            ))

            conn.commit()
            logger.info(f"Created Twilio session: {session.session_id} (call_sid={call_sid})")

            # Log creation event
            self.log_event(
                session_id=session.session_id,
                event_type="incoming",
                event_data={
                    "call_sid": call_sid,
                    "from_number": from_number,
                    "to_number": to_number,
                },
            )

            return session.session_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error(f"Failed to create session (integrity error): {e}")
            raise
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create session: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get Twilio session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session data, or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM twilio_sessions WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Convert Row to dict
            session_dict = dict(row)

            # Parse JSON fields
            if session_dict.get("transport_metadata"):
                session_dict["transport_metadata"] = json.loads(session_dict["transport_metadata"])
            else:
                session_dict["transport_metadata"] = {}

            if session_dict.get("metadata"):
                session_dict["metadata"] = json.loads(session_dict["metadata"])
            else:
                session_dict["metadata"] = {}

            return session_dict

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def get_by_call_sid(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Get Twilio session by Twilio Call SID.

        Args:
            call_sid: Twilio Call SID

        Returns:
            Dictionary with session data, or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM twilio_sessions WHERE call_sid = ?
            """, (call_sid,))

            row = cursor.fetchone()
            if not row:
                return None

            session_dict = dict(row)

            # Parse JSON fields
            if session_dict.get("transport_metadata"):
                session_dict["transport_metadata"] = json.loads(session_dict["transport_metadata"])
            else:
                session_dict["transport_metadata"] = {}

            if session_dict.get("metadata"):
                session_dict["metadata"] = json.loads(session_dict["metadata"])
            else:
                session_dict["metadata"] = {}

            return session_dict

        except Exception as e:
            logger.error(f"Failed to get session by call_sid {call_sid}: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def update(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update Twilio session fields.

        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update

        Returns:
            True if update succeeded, False otherwise

        Note:
            - Automatically updates 'updated_at' timestamp
            - JSON fields (metadata, transport_metadata) are automatically serialized
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build dynamic UPDATE query
            set_clauses = []
            values = []

            for key, value in updates.items():
                if key in ("session_id", "call_sid"):
                    # Don't allow updating primary/unique keys
                    continue

                # JSON-encode complex types
                if key in ("metadata", "transport_metadata") and isinstance(value, dict):
                    value = json.dumps(value)

                # Convert datetime to epoch_ms
                if key in ("last_activity_at", "ended_at") and isinstance(value, datetime):
                    value = to_epoch_ms(value)

                # Convert VoiceSessionState enum to string
                if key in ("status", "state") and hasattr(value, "value"):
                    value = value.value

                set_clauses.append(f"{key} = ?")
                values.append(value)

            if not set_clauses:
                logger.warning(f"No valid fields to update for session {session_id}")
                return False

            # Add updated_at timestamp
            set_clauses.append("updated_at = ?")
            values.append(to_epoch_ms(utc_now()))

            # Execute update
            values.append(session_id)
            query = f"UPDATE twilio_sessions SET {', '.join(set_clauses)} WHERE session_id = ?"

            cursor.execute(query, values)
            conn.commit()

            rows_affected = cursor.rowcount
            if rows_affected > 0:
                logger.info(f"Updated session {session_id}: {list(updates.keys())}")
                return True
            else:
                logger.warning(f"No session found to update: {session_id}")
                return False

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update session {session_id}: {e}", exc_info=True)
            return False
        finally:
            conn.close()

    def update_activity(self, session_id: str) -> bool:
        """Update session's last_activity_at timestamp.

        Convenience method for frequent activity updates.

        Args:
            session_id: Session identifier

        Returns:
            True if update succeeded, False otherwise
        """
        return self.update(session_id, {
            "last_activity_at": utc_now(),
        })

    def log_event(
        self,
        session_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a call event for audit trail.

        Args:
            session_id: Session identifier
            event_type: Type of event (e.g., 'incoming', 'stream_started', 'transcript')
            event_data: Optional event data payload

        Returns:
            event_id of the logged event
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            event_id = str(uuid.uuid4())
            now_ms = to_epoch_ms(utc_now())

            cursor.execute("""
                INSERT INTO twilio_call_logs (
                    id, session_id, event_type, event_data, timestamp
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                event_id,
                session_id,
                event_type,
                json.dumps(event_data) if event_data else None,
                now_ms,
            ))

            conn.commit()
            logger.debug(f"Logged event {event_type} for session {session_id}")

            return event_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to log event: {e}", exc_info=True)
            return ""
        finally:
            conn.close()

    def list(
        self,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List Twilio sessions with optional filters.

        Args:
            status: Filter by status (e.g., 'active', 'stopped')
            project_id: Filter by project ID
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of session dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM twilio_sessions WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                session_dict = dict(row)

                # Parse JSON fields
                if session_dict.get("transport_metadata"):
                    session_dict["transport_metadata"] = json.loads(session_dict["transport_metadata"])
                else:
                    session_dict["transport_metadata"] = {}

                if session_dict.get("metadata"):
                    session_dict["metadata"] = json.loads(session_dict["metadata"])
                else:
                    session_dict["metadata"] = {}

                sessions.append(session_dict)

            return sessions

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def get_events(
        self,
        session_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get call events for a session.

        Args:
            session_id: Session identifier
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM twilio_call_logs WHERE session_id = ?"
            params = [session_id]

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            events = []
            for row in rows:
                event_dict = dict(row)

                # Parse JSON event_data
                if event_dict.get("event_data"):
                    event_dict["event_data"] = json.loads(event_dict["event_data"])
                else:
                    event_dict["event_data"] = {}

                events.append(event_dict)

            return events

        except Exception as e:
            logger.error(f"Failed to get events for session {session_id}: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old completed sessions.

        Args:
            days_old: Delete sessions older than this many days

        Returns:
            Number of sessions deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_ms = to_epoch_ms(utc_now()) - (days_old * 24 * 60 * 60 * 1000)

            cursor.execute("""
                DELETE FROM twilio_sessions
                WHERE status IN ('stopped', 'completed', 'failed')
                AND created_at < ?
            """, (cutoff_ms,))

            conn.commit()
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old Twilio sessions (>{days_old} days)")

            return deleted_count

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to cleanup old sessions: {e}", exc_info=True)
            return 0
        finally:
            conn.close()
