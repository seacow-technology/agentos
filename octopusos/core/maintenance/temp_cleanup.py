"""
Temporary File Cleanup Service

Provides automatic cleanup of temporary files created by AgentOS to prevent
disk space exhaustion and maintain system health.

Features:
- Age-based cleanup (default: 24 hours)
- Size-based cleanup (largest files first)
- Safe deletion (skip active files)
- Detailed logging and statistics
- Background scheduling support

Usage:
    from agentos.core.maintenance import cleanup_old_temp_files
from agentos.core.time import utc_now, utc_now_iso


    # Manual cleanup
    stats = cleanup_old_temp_files(max_age_hours=24)
    print(f"Cleaned {stats['files_deleted']} files, freed {stats['bytes_freed']} bytes")

    # Schedule background cleanup
    from agentos.core.maintenance import schedule_cleanup_task
    task = schedule_cleanup_task(interval_hours=6, max_age_hours=24)
"""

import logging
import os
import tempfile
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TempFileCleanupStats:
    """Statistics for temp file cleanup operations"""

    def __init__(self):
        self.files_scanned = 0
        self.files_deleted = 0
        self.files_skipped = 0
        self.bytes_freed = 0
        self.errors = []
        self.start_time = utc_now()
        self.end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/reporting"""
        duration = 0.0
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "files_scanned": self.files_scanned,
            "files_deleted": self.files_deleted,
            "files_skipped": self.files_skipped,
            "bytes_freed": self.bytes_freed,
            "errors_count": len(self.errors),
            "errors": self.errors[:10],  # First 10 errors
            "duration_seconds": round(duration, 2),
            "started_at": self.start_time.isoformat(),
            "completed_at": self.end_time.isoformat() if self.end_time else None,
        }


def get_temp_dirs() -> List[Path]:
    """
    Get list of temporary directories to clean

    Returns:
        List of Path objects for temp directories
    """
    temp_dirs = []

    # System temp directory
    system_temp = Path(tempfile.gettempdir())
    temp_dirs.append(system_temp)

    # AgentOS-specific temp directories
    agentos_temp = system_temp / "agentos"
    if agentos_temp.exists():
        temp_dirs.append(agentos_temp)

    # Runtime temp directory
    try:
        runtime_temp = Path.home() / ".agentos" / "runtime" / "temp"
        if runtime_temp.exists():
            temp_dirs.append(runtime_temp)
    except Exception as e:
        logger.warning(f"Could not access runtime temp directory: {e}")

    return temp_dirs


def is_file_active(file_path: Path) -> bool:
    """
    Check if a file is currently in use

    Args:
        file_path: Path to check

    Returns:
        True if file appears to be in use, False otherwise
    """
    try:
        # Try to open in exclusive mode
        with open(file_path, 'r+b'):
            pass
        return False
    except (IOError, OSError, PermissionError):
        # File is locked or inaccessible - consider it active
        return True


def cleanup_old_temp_files(
    max_age_hours: int = 24,
    dry_run: bool = False,
    max_files: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Clean up old temporary files

    Args:
        max_age_hours: Delete files older than this many hours (default: 24)
        dry_run: If True, don't actually delete files (default: False)
        max_files: Maximum number of files to delete (None = unlimited)

    Returns:
        Dictionary with cleanup statistics

    Example:
        >>> stats = cleanup_old_temp_files(max_age_hours=48)
        >>> print(f"Freed {stats['bytes_freed'] / 1024 / 1024:.2f} MB")
    """
    stats = TempFileCleanupStats()
    cutoff_timestamp = time.time() - (max_age_hours * 3600)

    logger.info(
        f"Starting temp file cleanup (max_age={max_age_hours}h, dry_run={dry_run})"
    )

    # Get temp directories
    temp_dirs = get_temp_dirs()
    logger.debug(f"Scanning {len(temp_dirs)} temp directories")

    for temp_dir in temp_dirs:
        if not temp_dir.exists():
            continue

        logger.debug(f"Scanning directory: {temp_dir}")

        try:
            # Walk directory tree
            for root, dirs, files in os.walk(temp_dir):
                root_path = Path(root)

                for filename in files:
                    file_path = root_path / filename
                    stats.files_scanned += 1

                    try:
                        # Get file stats
                        file_stat = file_path.stat()

                        # Check age
                        if file_stat.st_mtime >= cutoff_timestamp:
                            stats.files_skipped += 1
                            continue

                        # Check if file is active
                        if is_file_active(file_path):
                            stats.files_skipped += 1
                            logger.debug(f"Skipping active file: {file_path}")
                            continue

                        # Delete file
                        if not dry_run:
                            try:
                                file_path.unlink()
                                stats.files_deleted += 1
                                stats.bytes_freed += file_stat.st_size
                                logger.debug(f"Deleted: {file_path}")
                            except Exception as e:
                                error_msg = f"Failed to delete {file_path}: {e}"
                                logger.warning(error_msg)
                                stats.errors.append(error_msg)
                        else:
                            stats.files_deleted += 1
                            stats.bytes_freed += file_stat.st_size
                            logger.debug(f"Would delete: {file_path}")

                        # Check max_files limit
                        if max_files and stats.files_deleted >= max_files:
                            logger.info(f"Reached max_files limit: {max_files}")
                            break

                    except Exception as e:
                        error_msg = f"Error processing {file_path}: {e}"
                        logger.warning(error_msg)
                        stats.errors.append(error_msg)

                # Break outer loop if max_files reached
                if max_files and stats.files_deleted >= max_files:
                    break

        except Exception as e:
            error_msg = f"Error scanning directory {temp_dir}: {e}"
            logger.error(error_msg, exc_info=True)
            stats.errors.append(error_msg)

    stats.end_time = utc_now()

    # Log summary
    result = stats.to_dict()
    mb_freed = stats.bytes_freed / 1024 / 1024

    logger.info(
        f"Temp file cleanup completed: "
        f"scanned={stats.files_scanned}, "
        f"deleted={stats.files_deleted}, "
        f"skipped={stats.files_skipped}, "
        f"freed={mb_freed:.2f}MB, "
        f"errors={len(stats.errors)}, "
        f"duration={result['duration_seconds']}s"
    )

    if dry_run:
        logger.info("DRY RUN: No files were actually deleted")

    return result


def get_temp_dir_stats() -> Dict[str, Any]:
    """
    Get statistics about temporary directories

    Returns:
        Dictionary with temp directory statistics

    Example:
        >>> stats = get_temp_dir_stats()
        >>> print(f"Total size: {stats['total_size_mb']:.2f} MB")
    """
    temp_dirs = get_temp_dirs()

    total_files = 0
    total_size = 0
    old_files = 0  # Older than 24 hours
    very_old_files = 0  # Older than 7 days

    cutoff_24h = time.time() - (24 * 3600)
    cutoff_7d = time.time() - (7 * 24 * 3600)

    for temp_dir in temp_dirs:
        if not temp_dir.exists():
            continue

        try:
            for root, dirs, files in os.walk(temp_dir):
                root_path = Path(root)
                for filename in files:
                    try:
                        file_path = root_path / filename
                        file_stat = file_path.stat()

                        total_files += 1
                        total_size += file_stat.st_size

                        if file_stat.st_mtime < cutoff_24h:
                            old_files += 1

                        if file_stat.st_mtime < cutoff_7d:
                            very_old_files += 1

                    except Exception:
                        pass  # Skip files we can't access

        except Exception as e:
            logger.warning(f"Error scanning {temp_dir}: {e}")

    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "old_files_24h": old_files,
        "very_old_files_7d": very_old_files,
        "temp_dirs": [str(d) for d in temp_dirs],
        "timestamp": utc_now_iso(),
    }


# Background cleanup task management
_cleanup_task: Optional[asyncio.Task] = None


async def _cleanup_loop(interval_hours: int, max_age_hours: int):
    """
    Background cleanup loop

    Args:
        interval_hours: Hours between cleanup runs
        max_age_hours: Age threshold for file deletion
    """
    logger.info(
        f"Starting background cleanup task "
        f"(interval={interval_hours}h, max_age={max_age_hours}h)"
    )

    while True:
        try:
            # Wait for interval
            await asyncio.sleep(interval_hours * 3600)

            # Run cleanup
            logger.info("Running scheduled temp file cleanup")
            stats = cleanup_old_temp_files(max_age_hours=max_age_hours)

            # Log results
            mb_freed = stats["bytes_freed"] / 1024 / 1024
            logger.info(
                f"Scheduled cleanup completed: "
                f"deleted={stats['files_deleted']}, freed={mb_freed:.2f}MB"
            )

        except asyncio.CancelledError:
            logger.info("Background cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background cleanup task: {e}", exc_info=True)
            # Continue running despite errors


def schedule_cleanup_task(
    interval_hours: int = 6,
    max_age_hours: int = 24,
) -> asyncio.Task:
    """
    Schedule background cleanup task

    Args:
        interval_hours: Hours between cleanup runs (default: 6)
        max_age_hours: Age threshold for file deletion (default: 24)

    Returns:
        asyncio.Task for the background cleanup

    Example:
        >>> task = schedule_cleanup_task(interval_hours=12, max_age_hours=48)
        >>> # Later: task.cancel() to stop
    """
    global _cleanup_task

    # Cancel existing task if any
    if _cleanup_task and not _cleanup_task.done():
        logger.warning("Cancelling existing cleanup task")
        _cleanup_task.cancel()

    # Create new task
    _cleanup_task = asyncio.create_task(
        _cleanup_loop(interval_hours, max_age_hours)
    )

    logger.info(
        f"Scheduled background cleanup task "
        f"(interval={interval_hours}h, max_age={max_age_hours}h)"
    )

    return _cleanup_task


def cancel_cleanup_task():
    """Cancel the background cleanup task if running"""
    global _cleanup_task

    if _cleanup_task and not _cleanup_task.done():
        logger.info("Cancelling background cleanup task")
        _cleanup_task.cancel()
        _cleanup_task = None
    else:
        logger.debug("No active cleanup task to cancel")
