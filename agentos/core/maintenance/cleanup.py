"""Database maintenance and cleanup utilities.

This module provides utilities for maintaining database health, including:
- Orphan record cleanup
- Stale session cleanup
- Database statistics and health checks

M-23: Orphan record cleanup for NULL session_id tasks
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from agentos.store import get_db, get_writer
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class DatabaseCleaner:
    """Database maintenance and cleanup operations."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database cleaner.

        Args:
            db_path: Optional database path (defaults to registry DB)
        """
        self.db_path = db_path

    def cleanup_orphan_tasks(
        self,
        days_old: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Clean up orphan task records (NULL session_id).

        Orphan tasks are tasks with NULL session_id that are old and in
        terminal states (completed, cancelled, failed). These tasks are safe
        to delete as they're not associated with any active session.

        Args:
            days_old: Delete tasks older than this many days
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics:
            - deleted_count: Number of tasks deleted
            - candidate_count: Number of tasks eligible for deletion
            - dry_run: Whether this was a dry run
            - cutoff_date: ISO timestamp of cutoff date

        Example:
            >>> cleaner = DatabaseCleaner()
            >>> result = cleaner.cleanup_orphan_tasks(days_old=30)
            >>> print(f"Cleaned up {result['deleted_count']} orphan tasks")
        """
        cutoff = utc_now() - timedelta(days=days_old)
        cutoff_iso = cutoff.isoformat()

        logger.info(f"Starting orphan task cleanup (dry_run={dry_run}, cutoff={cutoff_iso})")

        # First, find candidates
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE session_id IS NULL
              AND created_at < ?
              AND status IN ('completed', 'cancelled', 'failed', 'orphan')
        """, (cutoff_iso,))

        candidate_count = cursor.fetchone()[0]

        if dry_run:
            logger.info(f"[DRY RUN] Would delete {candidate_count} orphan tasks")
            return {
                'deleted_count': 0,
                'candidate_count': candidate_count,
                'dry_run': True,
                'cutoff_date': cutoff_iso,
            }

        # Perform actual deletion using SQLiteWriter for safe concurrent execution
        writer = get_writer()

        def delete_orphans(conn: sqlite3.Connection) -> int:
            """Delete orphan tasks in a transaction."""
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM tasks
                WHERE session_id IS NULL
                  AND created_at < ?
                  AND status IN ('completed', 'cancelled', 'failed', 'orphan')
            """, (cutoff_iso,))

            deleted = cursor.rowcount
            logger.info(f"Deleted {deleted} orphan tasks")
            return deleted

        try:
            deleted_count = writer.submit(delete_orphans, timeout=30.0)

            return {
                'deleted_count': deleted_count,
                'candidate_count': candidate_count,
                'dry_run': False,
                'cutoff_date': cutoff_iso,
            }
        except Exception as e:
            logger.error(f"Failed to delete orphan tasks: {e}", exc_info=True)
            raise

    def cleanup_stale_sessions(
        self,
        days_inactive: int = 90,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Clean up stale chat sessions with no recent activity.

        Args:
            days_inactive: Delete sessions with no activity for this many days
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        cutoff = utc_now() - timedelta(days=days_inactive)
        cutoff_iso = cutoff.isoformat()

        logger.info(f"Starting stale session cleanup (dry_run={dry_run}, cutoff={cutoff_iso})")

        conn = get_db()
        cursor = conn.cursor()

        # Find sessions with no recent activity
        cursor.execute("""
            SELECT COUNT(*) FROM chat_sessions
            WHERE last_activity < ?
              OR last_activity IS NULL
        """, (cutoff_iso,))

        candidate_count = cursor.fetchone()[0]

        if dry_run:
            logger.info(f"[DRY RUN] Would delete {candidate_count} stale sessions")
            return {
                'deleted_count': 0,
                'candidate_count': candidate_count,
                'dry_run': True,
                'cutoff_date': cutoff_iso,
            }

        writer = get_writer()

        def delete_stale_sessions(conn: sqlite3.Connection) -> int:
            """Delete stale sessions in a transaction."""
            cursor = conn.cursor()

            # Get session IDs to delete
            cursor.execute("""
                SELECT session_id FROM chat_sessions
                WHERE last_activity < ?
                  OR last_activity IS NULL
            """, (cutoff_iso,))

            session_ids = [row[0] for row in cursor.fetchall()]

            if not session_ids:
                return 0

            # Delete associated messages first (if messages table exists)
            try:
                placeholders = ','.join('?' * len(session_ids))
                cursor.execute(f"""
                    DELETE FROM chat_messages
                    WHERE session_id IN ({placeholders})
                """, session_ids)
                logger.info(f"Deleted {cursor.rowcount} messages from stale sessions")
            except sqlite3.OperationalError:
                # Messages table might not exist
                pass

            # Delete sessions
            cursor.execute(f"""
                DELETE FROM chat_sessions
                WHERE session_id IN ({placeholders})
            """, session_ids)

            deleted = cursor.rowcount
            logger.info(f"Deleted {deleted} stale sessions")
            return deleted

        try:
            deleted_count = writer.submit(delete_stale_sessions, timeout=30.0)

            return {
                'deleted_count': deleted_count,
                'candidate_count': candidate_count,
                'dry_run': False,
                'cutoff_date': cutoff_iso,
            }
        except Exception as e:
            logger.error(f"Failed to delete stale sessions: {e}", exc_info=True)
            raise

    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics.

        Returns:
            Dictionary with database statistics:
            - table_counts: Row counts for main tables
            - orphan_tasks: Count of tasks with NULL session_id
            - old_orphans: Count of old orphan tasks (>30 days)
            - stale_sessions: Count of inactive sessions (>90 days)
            - database_size_mb: Database file size in MB
        """
        conn = get_db()
        cursor = conn.cursor()

        stats: Dict[str, Any] = {}

        # Table row counts
        tables = ['tasks', 'chat_sessions', 'task_lineage', 'task_audits', 'task_agents']
        table_counts = {}

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                table_counts[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                table_counts[table] = None  # Table doesn't exist

        stats['table_counts'] = table_counts

        # Orphan task statistics
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE session_id IS NULL")
        stats['orphan_tasks'] = cursor.fetchone()[0]

        cutoff_30d = (utc_now() - timedelta(days=30)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE session_id IS NULL
              AND created_at < ?
              AND status IN ('completed', 'cancelled', 'failed', 'orphan')
        """, (cutoff_30d,))
        stats['old_orphans'] = cursor.fetchone()[0]

        # Stale session statistics
        cutoff_90d = (utc_now() - timedelta(days=90)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM chat_sessions
            WHERE last_activity < ? OR last_activity IS NULL
        """, (cutoff_90d,))
        stats['stale_sessions'] = cursor.fetchone()[0]

        # Database file size (if accessible)
        try:
            from agentos.store import get_db_path
            db_path = get_db_path()
            if db_path.exists():
                size_bytes = db_path.stat().st_size
                stats['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
        except Exception:
            stats['database_size_mb'] = None

        return stats

    def vacuum_database(self) -> Dict[str, Any]:
        """Run VACUUM to reclaim disk space and optimize database.

        VACUUM rebuilds the database file, repacking it into a minimal amount
        of disk space. This is useful after large deletions.

        Returns:
            Dictionary with vacuum results:
            - size_before_mb: Size before VACUUM
            - size_after_mb: Size after VACUUM
            - space_reclaimed_mb: Space reclaimed

        Note:
            VACUUM requires exclusive access to the database and can take
            time on large databases.
        """
        from agentos.store import get_db_path

        db_path = get_db_path()

        # Get size before
        size_before = db_path.stat().st_size if db_path.exists() else 0

        logger.info(f"Running VACUUM on {db_path} (size: {size_before / (1024*1024):.2f} MB)")

        # VACUUM cannot be run in a transaction, must be direct connection
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("VACUUM")
            conn.close()
            logger.info("VACUUM completed")
        except Exception as e:
            conn.close()
            logger.error(f"VACUUM failed: {e}", exc_info=True)
            raise

        # Get size after
        size_after = db_path.stat().st_size if db_path.exists() else 0
        space_reclaimed = size_before - size_after

        return {
            'size_before_mb': round(size_before / (1024 * 1024), 2),
            'size_after_mb': round(size_after / (1024 * 1024), 2),
            'space_reclaimed_mb': round(space_reclaimed / (1024 * 1024), 2),
        }


def cleanup_orphans(days_old: int = 30, dry_run: bool = False) -> int:
    """Convenience function to clean up orphan tasks.

    Args:
        days_old: Delete tasks older than this many days
        dry_run: If True, only report what would be deleted

    Returns:
        Number of tasks deleted (0 if dry_run)
    """
    cleaner = DatabaseCleaner()
    result = cleaner.cleanup_orphan_tasks(days_old=days_old, dry_run=dry_run)
    return result['deleted_count']
