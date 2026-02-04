"""Share Links Repository

Provides persistent storage for share links with TTL support and access tracking.
Replaces in-memory shared_previews dict from share.py.

Security features:
- Cryptographically secure token generation (secrets.token_urlsafe)
- Access logging for audit trail
- Automatic expiration handling
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
class ShareLink:
    """Share link data model"""
    token: str
    resource_type: str
    resource_id: str
    creator_id: Optional[str]
    permissions: List[str]
    created_at: int  # epoch ms
    expires_at: Optional[int]  # epoch ms, None = never expires
    access_count: int
    last_accessed_at: Optional[int]  # epoch ms
    metadata: Dict


class ShareRepo:
    """Repository for share_links table"""

    def __init__(self, db_path: str | Path):
        """Initialize ShareRepo

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

    def _generate_token(self) -> str:
        """Generate cryptographically secure token

        Returns:
            URL-safe token (43 characters, 256 bits of entropy)
        """
        return secrets.token_urlsafe(32)

    def create_link(
        self,
        resource_type: str,
        resource_id: str,
        creator_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a new share link

        Args:
            resource_type: Type of resource ('task', 'project', 'code', etc)
            resource_id: Resource identifier
            creator_id: User who created the share link
            ttl_seconds: Time to live in seconds (None = never expires)
            permissions: List of permissions (e.g., ['read', 'comment'])
            metadata: Additional metadata

        Returns:
            token: Generated share token

        Raises:
            sqlite3.IntegrityError: If token collision (very unlikely)
        """
        token = self._generate_token()
        now_ms = int(utc_now().timestamp() * 1000)
        expires_at = None
        if ttl_seconds is not None:
            expires_at = now_ms + (ttl_seconds * 1000)

        permissions_json = json.dumps(permissions or ['read'])
        metadata_json = json.dumps(metadata or {})

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO share_links (
                    token, resource_type, resource_id, creator_id,
                    permissions, created_at, expires_at, access_count,
                    last_accessed_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
            """, (
                token, resource_type, resource_id, creator_id,
                permissions_json, now_ms, expires_at, metadata_json
            ))
            conn.commit()

        logger.info(
            f"Created share link: token={token[:8]}... "
            f"resource={resource_type}:{resource_id} "
            f"ttl={ttl_seconds}s"
        )
        return token

    def get_link(self, token: str) -> Optional[ShareLink]:
        """Get share link by token

        Automatically checks expiration and returns None if expired.

        Args:
            token: Share token

        Returns:
            ShareLink object or None if not found/expired
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT token, resource_type, resource_id, creator_id,
                       permissions, created_at, expires_at, access_count,
                       last_accessed_at, metadata
                FROM share_links
                WHERE token = ?
            """, (token,)).fetchone()

            if not row:
                return None

            # Check expiration
            now_ms = int(utc_now().timestamp() * 1000)
            if row['expires_at'] is not None and now_ms > row['expires_at']:
                logger.info(f"Share link expired: token={token[:8]}...")
                return None

            return ShareLink(
                token=row['token'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                creator_id=row['creator_id'],
                permissions=json.loads(row['permissions'] or '[]'),
                created_at=row['created_at'],
                expires_at=row['expires_at'],
                access_count=row['access_count'],
                last_accessed_at=row['last_accessed_at'],
                metadata=json.loads(row['metadata'] or '{}')
            )

    def increment_access(self, token: str) -> bool:
        """Increment access count and update last_accessed_at

        Args:
            token: Share token

        Returns:
            True if updated, False if not found
        """
        now_ms = int(utc_now().timestamp() * 1000)
        with self._get_conn() as conn:
            cursor = conn.execute("""
                UPDATE share_links
                SET access_count = access_count + 1,
                    last_accessed_at = ?
                WHERE token = ?
            """, (now_ms, token))
            conn.commit()
            return cursor.rowcount > 0

    def revoke_link(self, token: str) -> bool:
        """Revoke (delete) a share link

        Args:
            token: Share token

        Returns:
            True if deleted, False if not found
        """
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM share_links
                WHERE token = ?
            """, (token,))
            conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"Revoked share link: token={token[:8]}...")
            return True
        return False

    def log_access(
        self,
        token: str,
        viewer_ip: Optional[str] = None,
        viewer_agent: Optional[str] = None,
        action: str = 'view',
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log access to a share link

        Args:
            token: Share token
            viewer_ip: Viewer IP address (should be anonymized/hashed)
            viewer_agent: User agent string
            action: Action performed ('view', 'download', 'comment', etc)
            session_id: Preview session ID if applicable
            metadata: Additional metadata
        """
        log_id = secrets.token_urlsafe(16)
        now_ms = int(utc_now().timestamp() * 1000)
        metadata_json = json.dumps(metadata or {})

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO share_access_logs (
                    id, share_token, accessed_at, viewer_ip,
                    viewer_agent, action, session_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id, token, now_ms, viewer_ip,
                viewer_agent, action, session_id, metadata_json
            ))
            conn.commit()

    def cleanup_expired(self) -> int:
        """Clean up expired share links

        Returns:
            Number of links deleted
        """
        now_ms = int(utc_now().timestamp() * 1000)
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM share_links
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (now_ms,))
            conn.commit()
            deleted = cursor.rowcount

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired share links")
        return deleted

    def list_by_creator(
        self,
        creator_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ShareLink]:
        """List share links created by a user

        Args:
            creator_id: Creator user ID
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of ShareLink objects
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT token, resource_type, resource_id, creator_id,
                       permissions, created_at, expires_at, access_count,
                       last_accessed_at, metadata
                FROM share_links
                WHERE creator_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (creator_id, limit, offset)).fetchall()

            links = []
            now_ms = int(utc_now().timestamp() * 1000)
            for row in rows:
                # Skip expired links
                if row['expires_at'] is not None and now_ms > row['expires_at']:
                    continue

                links.append(ShareLink(
                    token=row['token'],
                    resource_type=row['resource_type'],
                    resource_id=row['resource_id'],
                    creator_id=row['creator_id'],
                    permissions=json.loads(row['permissions'] or '[]'),
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    access_count=row['access_count'],
                    last_accessed_at=row['last_accessed_at'],
                    metadata=json.loads(row['metadata'] or '{}')
                ))
            return links

    def get_access_logs(
        self,
        token: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get access logs for a share link

        Args:
            token: Share token
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of access log dictionaries
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT id, share_token, accessed_at, viewer_ip,
                       viewer_agent, action, session_id, metadata
                FROM share_access_logs
                WHERE share_token = ?
                ORDER BY accessed_at DESC
                LIMIT ? OFFSET ?
            """, (token, limit, offset)).fetchall()

            logs = []
            for row in rows:
                logs.append({
                    'id': row['id'],
                    'share_token': row['share_token'],
                    'accessed_at': row['accessed_at'],
                    'viewer_ip': row['viewer_ip'],
                    'viewer_agent': row['viewer_agent'],
                    'action': row['action'],
                    'session_id': row['session_id'],
                    'metadata': json.loads(row['metadata'] or '{}')
                })
            return logs
