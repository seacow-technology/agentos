"""Preview Sessions Repository

Provides persistent storage for preview sessions with TTL support.
Replaces in-memory preview_sessions dict from preview.py.

Features:
- Session persistence across restarts
- Automatic expiration handling
- Activity-based session extension
- Secure session ID generation
"""

import json
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


@dataclass
class PreviewSession:
    """Preview session data model"""
    session_id: str
    share_token: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    html_content: str
    preset: str
    deps_injected: List[str]
    snippet_id: Optional[str]
    viewer_id: Optional[str]
    created_at: int  # epoch ms
    expires_at: int  # epoch ms
    last_activity_at: int  # epoch ms
    metadata: Dict


class PreviewSessionRepo:
    """Repository for preview_sessions table"""

    def __init__(self, db_path: str | Path):
        """Initialize PreviewSessionRepo

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = str(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _generate_session_id(self) -> str:
        """Generate cryptographically secure session ID

        Returns:
            URL-safe session ID
        """
        return secrets.token_urlsafe(24)

    def create(
        self,
        html_content: str,
        resource_type: str = 'html',
        resource_id: Optional[str] = None,
        preset: str = 'html-basic',
        deps_injected: Optional[List[str]] = None,
        snippet_id: Optional[str] = None,
        viewer_id: Optional[str] = None,
        share_token: Optional[str] = None,
        ttl_seconds: int = 3600,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a new preview session

        Args:
            html_content: HTML content to preview
            resource_type: Type of resource ('html', 'code', 'artifact')
            resource_id: Original resource ID if applicable
            preset: Preset name ('html-basic', 'three-webgl-umd')
            deps_injected: List of injected dependencies
            snippet_id: Optional snippet ID
            viewer_id: Anonymous or authenticated viewer ID
            share_token: Associated share token if from share link
            ttl_seconds: Time to live in seconds (default: 3600 = 1 hour)
            metadata: Additional metadata

        Returns:
            session_id: Generated session ID

        Raises:
            sqlite3.IntegrityError: If session_id collision (very unlikely)
        """
        session_id = self._generate_session_id()
        now_ms = int(utc_now().timestamp() * 1000)
        expires_at_ms = now_ms + (ttl_seconds * 1000)

        deps_injected_json = json.dumps(deps_injected or [])
        metadata_json = json.dumps(metadata or {})

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO preview_sessions (
                    session_id, share_token, resource_type, resource_id,
                    html_content, preset, deps_injected, snippet_id,
                    viewer_id, created_at, expires_at, last_activity_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, share_token, resource_type, resource_id,
                html_content, preset, deps_injected_json, snippet_id,
                viewer_id, now_ms, expires_at_ms, now_ms, metadata_json
            ))
            conn.commit()

        logger.info(
            f"Created preview session: session_id={session_id[:8]}... "
            f"preset={preset} ttl={ttl_seconds}s"
        )
        return session_id

    def get(self, session_id: str) -> Optional[PreviewSession]:
        """Get preview session by ID

        Automatically checks expiration and returns None if expired.

        Args:
            session_id: Session identifier

        Returns:
            PreviewSession object or None if not found/expired
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT session_id, share_token, resource_type, resource_id,
                       html_content, preset, deps_injected, snippet_id,
                       viewer_id, created_at, expires_at, last_activity_at, metadata
                FROM preview_sessions
                WHERE session_id = ?
            """, (session_id,)).fetchone()

            if not row:
                return None

            # Check expiration
            now_ms = int(utc_now().timestamp() * 1000)
            if now_ms > row['expires_at']:
                logger.info(f"Preview session expired: session_id={session_id[:8]}...")
                return None

            return PreviewSession(
                session_id=row['session_id'],
                share_token=row['share_token'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                html_content=row['html_content'],
                preset=row['preset'],
                deps_injected=json.loads(row['deps_injected'] or '[]'),
                snippet_id=row['snippet_id'],
                viewer_id=row['viewer_id'],
                created_at=row['created_at'],
                expires_at=row['expires_at'],
                last_activity_at=row['last_activity_at'],
                metadata=json.loads(row['metadata'] or '{}')
            )

    def update_activity(self, session_id: str, extend_ttl_seconds: Optional[int] = None) -> bool:
        """Update last activity time (and optionally extend TTL)

        Args:
            session_id: Session identifier
            extend_ttl_seconds: Optional seconds to extend expiration from now

        Returns:
            True if updated, False if not found
        """
        now_ms = int(utc_now().timestamp() * 1000)

        if extend_ttl_seconds is not None:
            new_expires_at = now_ms + (extend_ttl_seconds * 1000)
            with self._get_conn() as conn:
                cursor = conn.execute("""
                    UPDATE preview_sessions
                    SET last_activity_at = ?,
                        expires_at = ?
                    WHERE session_id = ?
                """, (now_ms, new_expires_at, session_id))
                conn.commit()
                return cursor.rowcount > 0
        else:
            with self._get_conn() as conn:
                cursor = conn.execute("""
                    UPDATE preview_sessions
                    SET last_activity_at = ?
                    WHERE session_id = ?
                """, (now_ms, session_id))
                conn.commit()
                return cursor.rowcount > 0

    def delete(self, session_id: str) -> bool:
        """Delete a preview session

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM preview_sessions
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"Deleted preview session: session_id={session_id[:8]}...")
            return True
        return False

    def cleanup_expired(self) -> int:
        """Clean up expired preview sessions

        Returns:
            Number of sessions deleted
        """
        now_ms = int(utc_now().timestamp() * 1000)
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM preview_sessions
                WHERE expires_at < ?
            """, (now_ms,))
            conn.commit()
            deleted = cursor.rowcount

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired preview sessions")
        return deleted

    def list_by_viewer(
        self,
        viewer_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[PreviewSession]:
        """List preview sessions for a viewer

        Args:
            viewer_id: Viewer ID
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of PreviewSession objects (excluding expired ones)
        """
        now_ms = int(utc_now().timestamp() * 1000)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT session_id, share_token, resource_type, resource_id,
                       html_content, preset, deps_injected, snippet_id,
                       viewer_id, created_at, expires_at, last_activity_at, metadata
                FROM preview_sessions
                WHERE viewer_id = ? AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (viewer_id, now_ms, limit, offset)).fetchall()

            sessions = []
            for row in rows:
                sessions.append(PreviewSession(
                    session_id=row['session_id'],
                    share_token=row['share_token'],
                    resource_type=row['resource_type'],
                    resource_id=row['resource_id'],
                    html_content=row['html_content'],
                    preset=row['preset'],
                    deps_injected=json.loads(row['deps_injected'] or '[]'),
                    snippet_id=row['snippet_id'],
                    viewer_id=row['viewer_id'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    last_activity_at=row['last_activity_at'],
                    metadata=json.loads(row['metadata'] or '{}')
                ))
            return sessions

    def get_metadata(self, session_id: str) -> Optional[Dict]:
        """Get session metadata without HTML content (lighter query)

        Args:
            session_id: Session identifier

        Returns:
            Metadata dictionary or None if not found/expired
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT session_id, preset, deps_injected, snippet_id,
                       created_at, expires_at, last_activity_at
                FROM preview_sessions
                WHERE session_id = ?
            """, (session_id,)).fetchone()

            if not row:
                return None

            # Check expiration
            now_ms = int(utc_now().timestamp() * 1000)
            if now_ms > row['expires_at']:
                return None

            ttl_remaining = (row['expires_at'] - now_ms) // 1000  # Convert to seconds

            return {
                'session_id': row['session_id'],
                'preset': row['preset'],
                'deps_injected': json.loads(row['deps_injected'] or '[]'),
                'snippet_id': row['snippet_id'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'ttl_remaining': ttl_remaining
            }
