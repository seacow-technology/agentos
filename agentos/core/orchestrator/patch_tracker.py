"""Patch tracking for audit trail."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


class PatchTracker:
    """Tracks code change patches for audit purposes."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize patch tracker."""
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("agentos")
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_patch(
        self,
        run_id: int,
        intent: str,
        files: list[str],
        step_id: Optional[int] = None,
    ) -> str:
        """
        Create a new patch record.

        Args:
            run_id: Task run ID
            intent: Why this change was made (human-readable)
            files: List of file paths affected
            step_id: Optional step ID

        Returns:
            patch_id: Unique patch identifier
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Generate patch ID
        patch_id = f"p{uuid.uuid4().hex[:8]}"

        # Compute diff hash (placeholder - in real impl would hash actual diff content)
        diff_hash = self._compute_diff_hash(files)

        # Insert patch
        cursor.execute(
            """
            INSERT INTO patches (patch_id, run_id, step_id, intent, files, diff_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (patch_id, run_id, step_id, intent, json.dumps(files), diff_hash),
        )

        conn.commit()
        conn.close()

        return patch_id

    def link_commit(
        self,
        patch_id: str,
        commit_hash: str,
        commit_message: str,
        repo_root: Optional[str] = None,
    ):
        """
        Link a git commit to a patch.

        Args:
            patch_id: Patch ID to link
            commit_hash: Git commit hash
            commit_message: Commit message
            repo_root: Repository root path
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO commit_links (patch_id, commit_hash, commit_message, committed_at, repo_root)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
            (patch_id, commit_hash, commit_message, repo_root),
        )

        conn.commit()
        conn.close()

    def get_patches_for_run(self, run_id: int) -> list[dict]:
        """Get all patches for a run."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM patches WHERE run_id = ? ORDER BY created_at
        """,
            (run_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_commits_for_patch(self, patch_id: str) -> list[dict]:
        """Get all commits linked to a patch."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM commit_links WHERE patch_id = ? ORDER BY committed_at
        """,
            (patch_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_commits_for_run(self, run_id: int) -> list[dict]:
        """Get all commits for a run (via patches)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT cl.*
            FROM commit_links cl
            JOIN patches p ON cl.patch_id = p.patch_id
            WHERE p.run_id = ?
            ORDER BY cl.committed_at
        """,
            (run_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _compute_diff_hash(self, files: list[str]) -> str:
        """
        Compute hash for diff content.

        In production, this would read actual file diffs.
        For now, we hash the file list as a placeholder.
        """
        content = "\n".join(sorted(files))
        return hashlib.sha256(content.encode()).hexdigest()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to dict."""
        return {
            "id": row["id"],
            "patch_id": row["patch_id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "intent": row["intent"],
            "files": json.loads(row["files"]),
            "diff_hash": row["diff_hash"],
            "created_at": row["created_at"],
        }
