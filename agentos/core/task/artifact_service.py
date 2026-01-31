"""Task Artifact Service - Cross-repository artifact tracking

This module provides artifact reference tracking for tasks across multiple repositories.
Artifacts include commits, branches, PRs, patches, files, and tags.

Key Features:
1. Create artifact references (commit, branch, pr, patch, file, tag)
2. Query artifacts by task and/or repository
3. Link task outputs to specific Git refs for traceability
4. Support for cross-repository artifact tracking

Created for Phase 5.2: Cross-repository audit trail
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from agentos.store import get_db
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class ArtifactRefType(str, Enum):
    """Artifact reference type"""

    COMMIT = "commit"
    BRANCH = "branch"
    PR = "pr"
    PATCH = "patch"
    FILE = "file"
    TAG = "tag"


@dataclass
class TaskArtifactRef:
    """Task artifact reference

    Represents a reference to an artifact (commit, PR, file, etc.) produced by a task.

    Attributes:
        artifact_id: Unique artifact ID (auto-generated)
        task_id: Task ID
        repo_id: Repository ID
        ref_type: Reference type (commit, branch, pr, patch, file, tag)
        ref_value: Reference value (commit SHA, branch name, PR number, file path, etc.)
        summary: Brief description of the artifact
        metadata: Additional metadata (JSON)
        created_at: Timestamp
    """

    task_id: str
    repo_id: str
    ref_type: ArtifactRefType
    ref_value: str
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    # Database ID (set after insert)
    artifact_id: Optional[int] = None

    def __post_init__(self):
        """Validate and normalize fields"""
        # Ensure ref_type is ArtifactRefType enum
        if not isinstance(self.ref_type, ArtifactRefType):
            self.ref_type = ArtifactRefType(self.ref_type)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["ref_type"] = self.ref_type.value if isinstance(self.ref_type, ArtifactRefType) else self.ref_type
        return data

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database-compatible dictionary"""
        return {
            "task_id": self.task_id,
            "repo_id": self.repo_id,
            "ref_type": self.ref_type.value if isinstance(self.ref_type, ArtifactRefType) else self.ref_type,
            "ref_value": self.ref_value,
            "summary": self.summary,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at or utc_now_iso(),
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskArtifactRef":
        """Create TaskArtifactRef from database row"""
        # Parse metadata JSON
        metadata = {}
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        return cls(
            artifact_id=row.get("artifact_id"),
            task_id=row["task_id"],
            repo_id=row["repo_id"],
            ref_type=ArtifactRefType(row["ref_type"]),
            ref_value=row["ref_value"],
            summary=row.get("summary", ""),
            metadata=metadata,
            created_at=row.get("created_at"),
        )


class TaskArtifactService:
    """Service for creating and querying task artifact references

    Provides methods to:
    1. Create artifact references (commit, branch, PR, etc.)
    2. Query artifacts by task and/or repository
    3. Get artifact history
    """

    def __init__(self, db=None):
        """Initialize service

        Args:
            db: Database connection (optional, uses default if not provided)
        """
        self.db = db or get_db()

    def create_artifact_ref(
        self,
        task_id: str,
        repo_id: str,
        ref_type: str | ArtifactRefType,
        ref_value: str,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskArtifactRef:
        """Create an artifact reference

        Args:
            task_id: Task ID
            repo_id: Repository ID
            ref_type: Reference type (commit, branch, pr, patch, file, tag)
            ref_value: Reference value (commit SHA, branch name, etc.)
            summary: Brief description
            metadata: Additional metadata (optional)

        Returns:
            Created TaskArtifactRef

        Raises:
            ValueError: If artifact already exists (duplicate)
        """
        # Normalize ref_type
        if not isinstance(ref_type, ArtifactRefType):
            ref_type = ArtifactRefType(ref_type)

        # Check for duplicates
        existing = self._find_artifact(task_id, repo_id, ref_type.value, ref_value)
        if existing:
            logger.warning(
                f"Artifact already exists: task={task_id}, repo={repo_id}, "
                f"type={ref_type.value}, value={ref_value}"
            )
            return existing

        # Create artifact reference
        artifact = TaskArtifactRef(
            task_id=task_id,
            repo_id=repo_id,
            ref_type=ref_type,
            ref_value=ref_value,
            summary=summary,
            metadata=metadata or {},
        )

        # Insert into database
        self._insert_artifact(artifact)

        logger.info(
            f"Created artifact ref: task={task_id}, repo={repo_id}, "
            f"type={ref_type.value}, value={ref_value}"
        )

        return artifact

    def create_commit_ref(
        self,
        task_id: str,
        repo_id: str,
        commit_hash: str,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskArtifactRef:
        """Create a commit artifact reference (convenience method)

        Args:
            task_id: Task ID
            repo_id: Repository ID
            commit_hash: Commit SHA
            summary: Commit message or description
            metadata: Additional metadata (author, timestamp, etc.)

        Returns:
            Created TaskArtifactRef
        """
        return self.create_artifact_ref(
            task_id=task_id,
            repo_id=repo_id,
            ref_type=ArtifactRefType.COMMIT,
            ref_value=commit_hash,
            summary=summary,
            metadata=metadata,
        )

    def create_branch_ref(
        self,
        task_id: str,
        repo_id: str,
        branch_name: str,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskArtifactRef:
        """Create a branch artifact reference (convenience method)

        Args:
            task_id: Task ID
            repo_id: Repository ID
            branch_name: Branch name
            summary: Description
            metadata: Additional metadata

        Returns:
            Created TaskArtifactRef
        """
        return self.create_artifact_ref(
            task_id=task_id,
            repo_id=repo_id,
            ref_type=ArtifactRefType.BRANCH,
            ref_value=branch_name,
            summary=summary,
            metadata=metadata,
        )

    def create_pr_ref(
        self,
        task_id: str,
        repo_id: str,
        pr_number: str | int,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskArtifactRef:
        """Create a PR artifact reference (convenience method)

        Args:
            task_id: Task ID
            repo_id: Repository ID
            pr_number: Pull request number
            summary: PR title or description
            metadata: Additional metadata (url, status, etc.)

        Returns:
            Created TaskArtifactRef
        """
        return self.create_artifact_ref(
            task_id=task_id,
            repo_id=repo_id,
            ref_type=ArtifactRefType.PR,
            ref_value=str(pr_number),
            summary=summary,
            metadata=metadata,
        )

    def get_task_artifacts(
        self,
        task_id: str,
        repo_id: Optional[str] = None,
        ref_type: Optional[str | ArtifactRefType] = None,
    ) -> List[TaskArtifactRef]:
        """Get artifact references for a task

        Args:
            task_id: Task ID
            repo_id: Filter by repository ID (optional)
            ref_type: Filter by reference type (optional)

        Returns:
            List of TaskArtifactRef (ordered by created_at DESC)
        """
        query = "SELECT * FROM task_artifact_ref WHERE task_id = ?"
        params = [task_id]

        if repo_id is not None:
            query += " AND repo_id = ?"
            params.append(repo_id)

        if ref_type is not None:
            # Normalize ref_type to string
            if isinstance(ref_type, ArtifactRefType):
                ref_type = ref_type.value
            query += " AND ref_type = ?"
            params.append(ref_type)

        query += " ORDER BY created_at DESC"

        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()

        return [TaskArtifactRef.from_db_row(dict(row)) for row in rows]

    def get_repo_artifacts(
        self,
        repo_id: str,
        ref_type: Optional[str | ArtifactRefType] = None,
        limit: int = 100,
    ) -> List[TaskArtifactRef]:
        """Get artifact references for a repository (across all tasks)

        Args:
            repo_id: Repository ID
            ref_type: Filter by reference type (optional)
            limit: Maximum number of records (default: 100)

        Returns:
            List of TaskArtifactRef (ordered by created_at DESC)
        """
        query = "SELECT * FROM task_artifact_ref WHERE repo_id = ?"
        params = [repo_id]

        if ref_type is not None:
            # Normalize ref_type to string
            if isinstance(ref_type, ArtifactRefType):
                ref_type = ref_type.value
            query += " AND ref_type = ?"
            params.append(ref_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()

        return [TaskArtifactRef.from_db_row(dict(row)) for row in rows]

    def get_artifact_by_ref(
        self,
        ref_type: str | ArtifactRefType,
        ref_value: str,
    ) -> List[TaskArtifactRef]:
        """Get artifact references by ref type and value

        Useful for finding which tasks modified a specific commit, branch, etc.

        Args:
            ref_type: Reference type
            ref_value: Reference value

        Returns:
            List of TaskArtifactRef (ordered by created_at DESC)
        """
        # Normalize ref_type to string
        if isinstance(ref_type, ArtifactRefType):
            ref_type = ref_type.value

        query = """
            SELECT * FROM task_artifact_ref
            WHERE ref_type = ? AND ref_value = ?
            ORDER BY created_at DESC
        """

        cursor = self.db.execute(query, [ref_type, ref_value])
        rows = cursor.fetchall()

        return [TaskArtifactRef.from_db_row(dict(row)) for row in rows]

    def _find_artifact(
        self,
        task_id: str,
        repo_id: str,
        ref_type: str,
        ref_value: str,
    ) -> Optional[TaskArtifactRef]:
        """Find existing artifact (for duplicate detection)"""
        query = """
            SELECT * FROM task_artifact_ref
            WHERE task_id = ? AND repo_id = ? AND ref_type = ? AND ref_value = ?
            LIMIT 1
        """

        cursor = self.db.execute(query, [task_id, repo_id, ref_type, ref_value])
        row = cursor.fetchone()

        if row:
            return TaskArtifactRef.from_db_row(dict(row))
        return None

    def _insert_artifact(self, artifact: TaskArtifactRef) -> None:
        """Insert artifact reference into database"""
        db_data = artifact.to_db_dict()

        cursor = self.db.execute(
            """
            INSERT INTO task_artifact_ref (task_id, repo_id, ref_type, ref_value, summary, metadata, created_at)
            VALUES (:task_id, :repo_id, :ref_type, :ref_value, :summary, :metadata, :created_at)
            """,
            db_data,
        )

        artifact.artifact_id = cursor.lastrowid
        self.db.commit()
