"""
Voice Session persistent storage.

Provides database-backed storage for voice sessions and transcripts,
replacing the in-memory _sessions dict.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from agentos.core.time import utc_now
from agentos.core.storage.paths import component_db_path
from agentos.core.db.registry_db import get_db, transaction

logger = logging.getLogger(__name__)


class VoiceSessionStore:
    """
    Persistent storage for voice sessions and transcripts.

    Features:
    - Database-backed session persistence
    - Transaction support for data integrity
    - Query methods for sessions and transcripts
    - Automatic cleanup of old sessions
    """

    def __init__(self):
        """Initialize voice session store."""
        self.db_path = component_db_path("agentos")
        logger.debug(f"VoiceSessionStore initialized with db: {self.db_path}")

    def create_session(
        self,
        project_id: Optional[str],
        provider: str,
        stt_provider: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new voice session.

        Args:
            project_id: Optional project ID for context.
            provider: Voice provider name (local, openai, azure).
            stt_provider: STT provider name (whisper_local, openai, azure, mock).
            metadata: Optional session metadata.

        Returns:
            session_id: Unique session identifier.
        """
        session_id = f"voice-{uuid.uuid4().hex[:12]}"
        now_ms = int(utc_now().timestamp() * 1000)

        metadata_json = json.dumps(metadata) if metadata else None

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO voice_sessions (
                    session_id, project_id, provider, stt_provider, state,
                    created_at_ms, updated_at_ms, metadata,
                    total_bytes_received, total_transcripts
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, 0, 0)
                """,
                (session_id, project_id, provider, stt_provider, now_ms, now_ms, metadata_json),
            )

        logger.info(
            f"Created voice session: {session_id} "
            f"(project: {project_id}, STT: {stt_provider})"
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get voice session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session data dict or None if not found.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                session_id, project_id, provider, stt_provider, state,
                created_at_ms, updated_at_ms, stopped_at_ms, metadata,
                total_bytes_received, total_transcripts
            FROM voice_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_session_dict(row)

    def update_session_state(
        self,
        session_id: str,
        state: str,
        stopped_at_ms: Optional[int] = None,
    ) -> bool:
        """
        Update session state.

        Args:
            session_id: Session identifier.
            state: New state (ACTIVE, STOPPED, ERROR).
            stopped_at_ms: Timestamp when stopped (epoch ms).

        Returns:
            True if updated, False if session not found.
        """
        now_ms = int(utc_now().timestamp() * 1000)

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE voice_sessions
                SET state = ?, updated_at_ms = ?, stopped_at_ms = ?
                WHERE session_id = ?
                """,
                (state, now_ms, stopped_at_ms, session_id),
            )
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated session {session_id} state to {state}")
        else:
            logger.warning(f"Session {session_id} not found for state update")

        return updated

    def update_session_stats(
        self,
        session_id: str,
        bytes_received: Optional[int] = None,
        transcript_count: Optional[int] = None,
    ) -> bool:
        """
        Update session statistics.

        Args:
            session_id: Session identifier.
            bytes_received: Total bytes received (incremental).
            transcript_count: Total transcripts (incremental).

        Returns:
            True if updated, False if session not found.
        """
        now_ms = int(utc_now().timestamp() * 1000)

        updates = ["updated_at_ms = ?"]
        params = [now_ms]

        if bytes_received is not None:
            updates.append("total_bytes_received = total_bytes_received + ?")
            params.append(bytes_received)

        if transcript_count is not None:
            updates.append("total_transcripts = total_transcripts + ?")
            params.append(transcript_count)

        params.append(session_id)

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE voice_sessions
                SET {', '.join(updates)}
                WHERE session_id = ?
                """,
                params,
            )
            updated = cursor.rowcount > 0

        return updated

    def list_sessions(
        self,
        state: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List voice sessions with optional filters.

        Args:
            state: Filter by state (ACTIVE, STOPPED, ERROR).
            project_id: Filter by project ID.
            limit: Maximum number of results.
            offset: Result offset for pagination.

        Returns:
            List of session dicts.
        """
        conditions = []
        params = []

        if state:
            conditions.append("state = ?")
            params.append(state)

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                session_id, project_id, provider, stt_provider, state,
                created_at_ms, updated_at_ms, stopped_at_ms, metadata,
                total_bytes_received, total_transcripts
            FROM voice_sessions
            {where_clause}
            ORDER BY created_at_ms DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
        rows = cursor.fetchall()

        return [self._row_to_session_dict(row) for row in rows]

    def add_transcript(
        self,
        session_id: str,
        transcript: str,
        audio_timestamp_ms: int,
        confidence: Optional[float] = None,
        language: Optional[str] = None,
        audio_duration_ms: Optional[int] = None,
        audio_bytes: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> str:
        """
        Add a transcript record for a session.

        Args:
            session_id: Session identifier.
            transcript: Transcribed text.
            audio_timestamp_ms: Client-side audio timestamp.
            confidence: Transcription confidence (0.0 - 1.0).
            language: Detected or specified language code.
            audio_duration_ms: Duration of audio segment.
            audio_bytes: Size of audio data.
            provider: STT provider used.

        Returns:
            transcript_id: Unique transcript identifier.
        """
        transcript_id = f"trans-{uuid.uuid4().hex[:12]}"
        now_ms = int(utc_now().timestamp() * 1000)

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO voice_transcripts (
                    id, session_id, transcript, confidence, language,
                    audio_timestamp_ms, created_at_ms, audio_duration_ms,
                    audio_bytes, provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript_id,
                    session_id,
                    transcript,
                    confidence,
                    language,
                    audio_timestamp_ms,
                    now_ms,
                    audio_duration_ms,
                    audio_bytes,
                    provider,
                ),
            )

        # Update session transcript count
        self.update_session_stats(session_id, transcript_count=1)

        logger.debug(f"Added transcript {transcript_id} to session {session_id}")
        return transcript_id

    def get_session_transcripts(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get transcripts for a session.

        Args:
            session_id: Session identifier.
            limit: Maximum number of results.
            offset: Result offset for pagination.

        Returns:
            List of transcript dicts.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, session_id, transcript, confidence, language,
                audio_timestamp_ms, created_at_ms, audio_duration_ms,
                audio_bytes, provider
            FROM voice_transcripts
            WHERE session_id = ?
            ORDER BY audio_timestamp_ms ASC
            LIMIT ? OFFSET ?
            """,
            (session_id, limit, offset),
        )
        rows = cursor.fetchall()

        return [self._row_to_transcript_dict(row) for row in rows]

    def _row_to_session_dict(self, row) -> Dict[str, Any]:
        """Convert database row to session dict."""
        metadata = json.loads(row[8]) if row[8] else None

        return {
            "session_id": row[0],
            "project_id": row[1],
            "provider": row[2],
            "stt_provider": row[3],
            "state": row[4],
            "created_at_ms": row[5],
            "updated_at_ms": row[6],
            "stopped_at_ms": row[7],
            "metadata": metadata,
            "total_bytes_received": row[9],
            "total_transcripts": row[10],
        }

    def _row_to_transcript_dict(self, row) -> Dict[str, Any]:
        """Convert database row to transcript dict."""
        return {
            "id": row[0],
            "session_id": row[1],
            "transcript": row[2],
            "confidence": row[3],
            "language": row[4],
            "audio_timestamp_ms": row[5],
            "created_at_ms": row[6],
            "audio_duration_ms": row[7],
            "audio_bytes": row[8],
            "provider": row[9],
        }


# Global instance (singleton)
_store_instance: Optional[VoiceSessionStore] = None


def get_voice_session_store() -> VoiceSessionStore:
    """
    Get or create global voice session store instance.

    Returns:
        VoiceSessionStore instance.
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = VoiceSessionStore()
    return _store_instance
