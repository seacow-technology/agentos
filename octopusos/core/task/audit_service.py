"""Task Audit Service - Cross-repository audit trail recording

This module provides audit recording for task operations across multiple repositories.
It captures Git changes, file modifications, and operations for complete traceability.

Key Features:
1. Record operations (read, write, commit, push) per repository
2. Capture Git change summaries (status, diff stats)
3. Size-limited storage (avoid bloat with large diffs)
4. Query audits by task and/or repository
5. Integration with TaskArtifactService for commit tracking

Created for Phase 5.2: Cross-repository audit trail
"""

import json
import logging
import sqlite3
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.task.repo_context import TaskRepoContext
from agentos.store import get_db, get_writer
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


# Maximum size for git diff summary (10KB)
MAX_DIFF_SIZE = 10 * 1024

# Maximum size for git status summary (5KB)
MAX_STATUS_SIZE = 5 * 1024


@dataclass
class TaskAudit:
    """Task audit record

    Represents a single audit event for a task, potentially associated with a repository.

    Attributes:
        audit_id: Unique audit record ID (auto-generated)
        task_id: Task ID
        repo_id: Repository ID (optional, None for task-level audits)
        level: Log level (info, warn, error)
        event_type: Event type (repo_read, repo_write, repo_commit, etc.)
        operation: Operation name (read, write, commit, push)
        status: Operation status (success, failed, partial)

        # Git information
        git_status_summary: Git status output (porcelain format)
        git_diff_summary: Git diff --stat output
        commit_hash: Git commit hash (if applicable)

        # Change metrics
        files_changed: List of changed file paths
        lines_added: Number of lines added
        lines_deleted: Number of lines deleted

        # Metadata
        error_message: Error message (if failed)
        payload: Additional event data (JSON)
        created_at: Timestamp
    """

    task_id: str
    event_type: str
    level: str = "info"
    repo_id: Optional[str] = None
    operation: Optional[str] = None
    status: str = "success"

    # Git information
    git_status_summary: Optional[str] = None
    git_diff_summary: Optional[str] = None
    commit_hash: Optional[str] = None

    # Change metrics
    files_changed: List[str] = field(default_factory=list)
    lines_added: int = 0
    lines_deleted: int = 0

    # Metadata
    error_message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    # Database ID (set after insert)
    audit_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Ensure payload is a dict
        if not isinstance(data.get("payload"), dict):
            data["payload"] = {}
        return data

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database-compatible dictionary

        Combines fields into payload JSON for storage.
        """
        # Build payload
        payload = {
            "operation": self.operation,
            "status": self.status,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "git_status_summary": self.git_status_summary,
            "git_diff_summary": self.git_diff_summary,
            "commit_hash": self.commit_hash,
            "error_message": self.error_message,
            **self.payload,  # Merge any additional payload data
        }

        return {
            "task_id": self.task_id,
            "repo_id": self.repo_id,
            "level": self.level,
            "event_type": self.event_type,
            "payload": json.dumps(payload),
            "created_at": self.created_at or utc_now_iso(),
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskAudit":
        """Create TaskAudit from database row"""
        # Parse payload JSON
        payload = {}
        if row.get("payload"):
            try:
                payload = json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                payload = {}

        return cls(
            audit_id=row.get("audit_id"),
            task_id=row["task_id"],
            repo_id=row.get("repo_id"),
            level=row.get("level", "info"),
            event_type=row["event_type"],
            operation=payload.get("operation"),
            status=payload.get("status", "success"),
            git_status_summary=payload.get("git_status_summary"),
            git_diff_summary=payload.get("git_diff_summary"),
            commit_hash=payload.get("commit_hash"),
            files_changed=payload.get("files_changed", []),
            lines_added=payload.get("lines_added", 0),
            lines_deleted=payload.get("lines_deleted", 0),
            error_message=payload.get("error_message"),
            payload=payload,
            created_at=row.get("created_at"),
        )


class TaskAuditService:
    """Service for recording and querying task audits

    Provides methods to:
    1. Record operations (read, write, commit, push)
    2. Capture Git change summaries
    3. Query audits by task and/or repository
    """

    def __init__(self, db=None):
        """Initialize service

        Args:
            db: Database connection (optional, uses default if not provided)
        """
        self.db = db or get_db()

    def record_operation(
        self,
        task_id: str,
        operation: str,
        repo_id: Optional[str] = None,
        status: str = "success",
        event_type: Optional[str] = None,
        level: str = "info",
        **kwargs
    ) -> TaskAudit:
        """Record a task operation

        Args:
            task_id: Task ID
            operation: Operation name (read, write, commit, push)
            repo_id: Repository ID (optional)
            status: Operation status (success, failed, partial)
            event_type: Event type (optional, defaults to repo_{operation})
            level: Log level (info, warn, error)
            **kwargs: Additional metadata (files_changed, error_message, etc.)

        Returns:
            Created TaskAudit record
        """
        # Default event type
        if event_type is None:
            event_type = f"repo_{operation}" if repo_id else operation

        # Create audit record
        audit = TaskAudit(
            task_id=task_id,
            repo_id=repo_id,
            event_type=event_type,
            operation=operation,
            status=status,
            level=level,
            files_changed=kwargs.get("files_changed", []),
            lines_added=kwargs.get("lines_added", 0),
            lines_deleted=kwargs.get("lines_deleted", 0),
            commit_hash=kwargs.get("commit_hash"),
            error_message=kwargs.get("error_message"),
            payload=kwargs.get("payload", {}),
        )

        # Insert into database
        self._insert_audit(audit)

        logger.info(
            f"Recorded audit: task={task_id}, repo={repo_id}, operation={operation}, status={status}"
        )

        return audit

    def record_git_changes(
        self,
        task_id: str,
        repo_context: TaskRepoContext,
        operation: str = "write",
        commit_hash: Optional[str] = None,
    ) -> TaskAudit:
        """Record Git changes for a repository

        Captures:
        - Git status summary (porcelain format)
        - Git diff summary (--stat format, size-limited)
        - Changed files list
        - Lines added/deleted

        Args:
            task_id: Task ID
            repo_context: Repository context
            operation: Operation name (default: write)
            commit_hash: Commit hash (optional)

        Returns:
            Created TaskAudit record
        """
        # Get Git summaries
        git_status = self._get_git_status_summary(repo_context.path)
        git_diff = self._get_git_diff_summary(repo_context.path)

        # Parse changed files and line counts
        files_changed, lines_added, lines_deleted = self._parse_diff_summary(git_diff)

        # Create audit record
        audit = TaskAudit(
            task_id=task_id,
            repo_id=repo_context.repo_id,
            event_type=f"repo_{operation}",
            operation=operation,
            status="success",
            level="info",
            git_status_summary=git_status,
            git_diff_summary=git_diff,
            commit_hash=commit_hash,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )

        # Insert into database
        self._insert_audit(audit)

        logger.info(
            f"Recorded Git changes: task={task_id}, repo={repo_context.repo_id}, "
            f"files={len(files_changed)}, +{lines_added}/-{lines_deleted}"
        )

        return audit

    def get_task_audits(
        self,
        task_id: str,
        repo_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TaskAudit]:
        """Get audit records for a task

        Args:
            task_id: Task ID
            repo_id: Filter by repository ID (optional)
            event_type: Filter by event type (optional)
            limit: Maximum number of records (default: 100)

        Returns:
            List of TaskAudit records (ordered by created_at DESC)
        """
        query = "SELECT * FROM task_audits WHERE task_id = ?"
        params = [task_id]

        if repo_id is not None:
            query += " AND repo_id = ?"
            params.append(repo_id)

        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()

        return [TaskAudit.from_db_row(dict(row)) for row in rows]

    def get_repo_audits(
        self,
        repo_id: str,
        limit: int = 100,
    ) -> List[TaskAudit]:
        """Get audit records for a repository (across all tasks)

        Args:
            repo_id: Repository ID
            limit: Maximum number of records (default: 100)

        Returns:
            List of TaskAudit records (ordered by created_at DESC)
        """
        query = """
            SELECT * FROM task_audits
            WHERE repo_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """

        cursor = self.db.execute(query, [repo_id, limit])
        rows = cursor.fetchall()

        return [TaskAudit.from_db_row(dict(row)) for row in rows]

    def _insert_audit(self, audit: TaskAudit) -> None:
        """Insert audit record into database

        使用 SQLiteWriter 串行化写入，避免并发锁冲突。
        如果遇到外键约束失败（task_id 不存在），则降级处理：
        - 记录警告日志
        - 不抛出异常（best-effort）
        """
        db_data = audit.to_db_dict()
        writer = get_writer()

        def _do_insert(conn):
            """在 writer 线程中执行插入"""
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO task_audits (task_id, repo_id, level, event_type, payload, created_at)
                    VALUES (:task_id, :repo_id, :level, :event_type, :payload, :created_at)
                    """,
                    db_data,
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError as e:
                # 外键约束失败：task_id 不存在
                if "FOREIGN KEY constraint" in str(e):
                    logger.warning(
                        f"Audit dropped: task_id={audit.task_id} not found in tasks table. "
                        f"This is expected if task creation failed or audit arrived before task. "
                        f"Event: {audit.event_type}"
                    )
                    # 返回 None 表示写入失败，但不抛异常
                    return None
                else:
                    # 其他完整性错误，继续抛出
                    raise

        try:
            audit_id = writer.submit(_do_insert, timeout=5.0)
            if audit_id is not None:
                audit.audit_id = audit_id
        except Exception as e:
            # Best-effort：audit 失败不应该影响业务
            logger.warning(f"Failed to insert audit (best-effort): {e}")

    def _get_git_status_summary(self, repo_path: Path, max_size: int = MAX_STATUS_SIZE) -> Optional[str]:
        """Get git status --porcelain output

        Args:
            repo_path: Repository path
            max_size: Maximum output size in bytes (default: 5KB)

        Returns:
            Git status output (porcelain format), or None if error
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning(f"Git status failed: {result.stderr}")
                return None

            output = result.stdout

            # Truncate if too large
            if len(output) > max_size:
                output = output[:max_size] + f"\n... (truncated, total {len(result.stdout)} bytes)"

            return output if output.strip() else None

        except subprocess.TimeoutExpired:
            logger.warning(f"Git status timeout for {repo_path}")
            return None
        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            return None

    def _get_git_diff_summary(self, repo_path: Path, max_size: int = MAX_DIFF_SIZE) -> Optional[str]:
        """Get git diff --stat output (size-limited)

        Args:
            repo_path: Repository path
            max_size: Maximum output size in bytes (default: 10KB)

        Returns:
            Git diff --stat output, or None if error
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "diff", "--stat", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning(f"Git diff failed: {result.stderr}")
                return None

            output = result.stdout

            # Truncate if too large
            if len(output) > max_size:
                lines = output.split("\n")
                truncated_lines = []
                current_size = 0

                for line in lines:
                    if current_size + len(line) + 1 > max_size:
                        break
                    truncated_lines.append(line)
                    current_size += len(line) + 1

                output = "\n".join(truncated_lines)
                output += f"\n... (truncated, total {len(lines)} lines)"

            return output if output.strip() else None

        except subprocess.TimeoutExpired:
            logger.warning(f"Git diff timeout for {repo_path}")
            return None
        except Exception as e:
            logger.error(f"Error getting git diff: {e}")
            return None

    def _parse_diff_summary(self, diff_summary: Optional[str]) -> tuple[List[str], int, int]:
        """Parse git diff --stat output to extract files and line counts

        Example input:
            src/main.py  | 30 +++++-----
            tests/test.py | 20 +++++++++++
            2 files changed, 40 insertions(+), 10 deletions(-)

        Args:
            diff_summary: Git diff --stat output

        Returns:
            (files_changed, lines_added, lines_deleted)
        """
        if not diff_summary:
            return [], 0, 0

        files_changed = []
        lines_added = 0
        lines_deleted = 0

        try:
            lines = diff_summary.strip().split("\n")

            for line in lines:
                # Parse file lines (format: "filename | changes ++++----")
                if "|" in line and not line.strip().startswith("..."):
                    parts = line.split("|")
                    if len(parts) >= 2:
                        filename = parts[0].strip()
                        if filename:
                            files_changed.append(filename)

            # Parse summary line (last line)
            # Format: "2 files changed, 40 insertions(+), 10 deletions(-)"
            summary_line = lines[-1] if lines else ""
            if "insertion" in summary_line or "deletion" in summary_line:
                # Extract insertions
                if "insertion" in summary_line:
                    import re
                    match = re.search(r"(\d+) insertion", summary_line)
                    if match:
                        lines_added = int(match.group(1))

                # Extract deletions
                if "deletion" in summary_line:
                    import re
                    match = re.search(r"(\d+) deletion", summary_line)
                    if match:
                        lines_deleted = int(match.group(1))

        except Exception as e:
            logger.warning(f"Error parsing diff summary: {e}")

        return files_changed, lines_added, lines_deleted
