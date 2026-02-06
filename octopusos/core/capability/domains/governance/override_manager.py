"""
Override Manager - Emergency governance override system

Implements GC-004: governance.override.admin

Design Philosophy:
- Emergency overrides should be rare and heavily audited
- All overrides require:
  * Admin ID (who is overriding)
  * Reason (minimum 100 characters)
  * Expiration (time-limited)
- Overrides are single-use (cannot be reused)
- All override usage is logged to audit trail

Security Features:
- Time-limited tokens (default: 24 hours)
- Single-use enforcement
- Comprehensive audit logging
- Optional 2FA verification (future)
"""

import logging
import sqlite3
import secrets
from typing import Optional

from agentos.core.time import utc_now_ms
from agentos.core.capability.domains.governance.models import OverrideToken


logger = logging.getLogger(__name__)


class OverrideManager:
    """
    Manager for emergency governance overrides.

    Overrides allow admins to bypass governance checks in emergency
    situations. All overrides are:
    - Time-limited
    - Single-use
    - Fully audited
    - Require justification

    Usage:
        manager = OverrideManager(db_path)

        # Create override
        token = manager.create_override(
            admin_id="user:alice",
            blocked_operation="state.memory.write for critical data",
            reason="Emergency fix for production data corruption...",
            duration_hours=2
        )

        # Validate override
        if manager.validate_override(token.override_id):
            # Proceed with blocked operation
            pass
    """

    MIN_REASON_LENGTH = 100  # Minimum characters for override reason

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize override manager.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        logger.info(f"OverrideManager initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # Override Creation
    # ===================================================================

    def create_override(
        self,
        admin_id: str,
        blocked_operation: str,
        reason: str,
        duration_hours: int = 24,
    ) -> OverrideToken:
        """
        Create emergency override token.

        Args:
            admin_id: Admin creating override
            blocked_operation: Description of operation being overridden
            reason: Detailed justification (min 100 chars)
            duration_hours: How long override is valid (default: 24h)

        Returns:
            OverrideToken

        Raises:
            ValueError: If reason is too short or duration invalid
        """
        # Validate reason length
        if len(reason) < self.MIN_REASON_LENGTH:
            raise ValueError(
                f"Override reason must be at least {self.MIN_REASON_LENGTH} characters. "
                f"Got {len(reason)} characters."
            )

        # Validate duration
        if duration_hours < 1 or duration_hours > 168:  # Max 1 week
            raise ValueError("Duration must be between 1 and 168 hours")

        # Generate secure token
        override_id = f"override-{secrets.token_urlsafe(32)}"

        # Calculate expiration
        now_ms = utc_now_ms()
        duration_ms = duration_hours * 60 * 60 * 1000
        expires_at_ms = now_ms + duration_ms

        # Create override token
        token = OverrideToken(
            override_id=override_id,
            admin_id=admin_id,
            blocked_operation=blocked_operation,
            override_reason=reason,
            expires_at_ms=expires_at_ms,
            used=False,
            used_at_ms=None,
            created_at_ms=now_ms,
            metadata={
                "duration_hours": duration_hours,
            },
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO governance_overrides (
                override_id, admin_id, blocked_operation, override_reason,
                expires_at_ms, used, used_at_ms, created_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token.override_id,
                token.admin_id,
                token.blocked_operation,
                token.override_reason,
                token.expires_at_ms,
                int(token.used),
                token.used_at_ms,
                token.created_at_ms,
            ),
        )

        conn.commit()
        conn.close()

        logger.warning(
            f"Override token created by {admin_id} for: {blocked_operation[:100]}... "
            f"(expires in {duration_hours}h)"
        )

        # Send security notification (in production)
        self._send_override_notification(token)

        return token

    def _send_override_notification(self, token: OverrideToken):
        """
        Send notification about override creation.

        In production, this would send alerts to security team.
        """
        logger.info(
            f"SECURITY ALERT: Override created\n"
            f"  Admin: {token.admin_id}\n"
            f"  Operation: {token.blocked_operation}\n"
            f"  Expires: {token.expires_at_ms}\n"
            f"  Reason: {token.override_reason[:200]}..."
        )

    # ===================================================================
    # Override Validation
    # ===================================================================

    def validate_override(self, override_token: str) -> bool:
        """
        Validate and consume override token.

        This method:
        1. Checks if token exists
        2. Checks if token has expired
        3. Checks if token has already been used
        4. Marks token as used (single-use enforcement)
        5. Logs usage to audit trail

        Args:
            override_token: Override token string

        Returns:
            True if valid and consumed, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Query override
        cursor.execute(
            """
            SELECT override_id, admin_id, blocked_operation, override_reason,
                   expires_at_ms, used, used_at_ms, created_at_ms
            FROM governance_overrides
            WHERE override_id = ?
            """,
            (override_token,),
        )
        row = cursor.fetchone()

        if row is None:
            conn.close()
            logger.warning(f"Override token not found: {override_token}")
            return False

        # Parse override
        token = OverrideToken(
            override_id=row["override_id"],
            admin_id=row["admin_id"],
            blocked_operation=row["blocked_operation"],
            override_reason=row["override_reason"],
            expires_at_ms=row["expires_at_ms"],
            used=bool(row["used"]),
            used_at_ms=row["used_at_ms"],
            created_at_ms=row["created_at_ms"],
        )

        # Check if already used
        if token.used:
            conn.close()
            logger.warning(
                f"Override token already used: {override_token} (used at {token.used_at_ms})"
            )
            return False

        # Check if expired
        if token.is_expired:
            conn.close()
            logger.warning(
                f"Override token expired: {override_token} (expired at {token.expires_at_ms})"
            )
            return False

        # Mark as used
        now_ms = utc_now_ms()
        cursor.execute(
            """
            UPDATE governance_overrides
            SET used = 1, used_at_ms = ?
            WHERE override_id = ?
            """,
            (now_ms, override_token),
        )

        conn.commit()
        conn.close()

        logger.warning(
            f"Override token consumed: {override_token}\n"
            f"  Admin: {token.admin_id}\n"
            f"  Operation: {token.blocked_operation}\n"
            f"  Reason: {token.override_reason[:200]}..."
        )

        # Send security notification
        self._send_override_usage_notification(token)

        return True

    def _send_override_usage_notification(self, token: OverrideToken):
        """Send notification about override usage"""
        logger.info(
            f"SECURITY ALERT: Override token used\n"
            f"  Token: {token.override_id}\n"
            f"  Admin: {token.admin_id}\n"
            f"  Operation: {token.blocked_operation}"
        )

    # ===================================================================
    # Override Query
    # ===================================================================

    def get_override(self, override_id: str) -> Optional[OverrideToken]:
        """
        Get override token by ID.

        Args:
            override_id: Override identifier

        Returns:
            OverrideToken or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT override_id, admin_id, blocked_operation, override_reason,
                   expires_at_ms, used, used_at_ms, created_at_ms
            FROM governance_overrides
            WHERE override_id = ?
            """,
            (override_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return OverrideToken(
            override_id=row["override_id"],
            admin_id=row["admin_id"],
            blocked_operation=row["blocked_operation"],
            override_reason=row["override_reason"],
            expires_at_ms=row["expires_at_ms"],
            used=bool(row["used"]),
            used_at_ms=row["used_at_ms"],
            created_at_ms=row["created_at_ms"],
        )

    def list_active_overrides(self) -> list[OverrideToken]:
        """
        List all active (unused, unexpired) overrides.

        Returns:
            List of active OverrideToken objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now_ms = utc_now_ms()

        cursor.execute(
            """
            SELECT override_id, admin_id, blocked_operation, override_reason,
                   expires_at_ms, used, used_at_ms, created_at_ms
            FROM governance_overrides
            WHERE used = 0 AND expires_at_ms > ?
            ORDER BY created_at_ms DESC
            """,
            (now_ms,),
        )
        rows = cursor.fetchall()
        conn.close()

        tokens = []
        for row in rows:
            token = OverrideToken(
                override_id=row["override_id"],
                admin_id=row["admin_id"],
                blocked_operation=row["blocked_operation"],
                override_reason=row["override_reason"],
                expires_at_ms=row["expires_at_ms"],
                used=bool(row["used"]),
                used_at_ms=row["used_at_ms"],
                created_at_ms=row["created_at_ms"],
            )
            tokens.append(token)

        return tokens

    # ===================================================================
    # Cleanup
    # ===================================================================

    def expire_old_overrides(self, older_than_days: int = 90):
        """
        Delete expired override records older than specified days.

        This is for housekeeping - removes old override records from database.

        Args:
            older_than_days: Delete records older than this many days
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_ms = utc_now_ms() - (older_than_days * 24 * 60 * 60 * 1000)

        cursor.execute(
            """
            DELETE FROM governance_overrides
            WHERE expires_at_ms < ?
            """,
            (cutoff_ms,),
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Expired {deleted_count} old override records (older than {older_than_days}d)")

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> dict:
        """Get override statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total overrides
        cursor.execute("SELECT COUNT(*) as count FROM governance_overrides")
        stats["total_overrides"] = cursor.fetchone()["count"]

        # Active overrides
        now_ms = utc_now_ms()
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM governance_overrides
            WHERE used = 0 AND expires_at_ms > ?
            """,
            (now_ms,),
        )
        stats["active_overrides"] = cursor.fetchone()["count"]

        # Used overrides
        cursor.execute("SELECT COUNT(*) as count FROM governance_overrides WHERE used = 1")
        stats["used_overrides"] = cursor.fetchone()["count"]

        # Expired overrides
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM governance_overrides
            WHERE used = 0 AND expires_at_ms <= ?
            """,
            (now_ms,),
        )
        stats["expired_overrides"] = cursor.fetchone()["count"]

        conn.close()

        return stats
