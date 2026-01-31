"""Content Lineage Tracker - tracks and explains content evolution."""

import json
from typing import Optional
import sqlite3
from pathlib import Path

from agentos.core.content.registry import ContentRegistry
from agentos.store import get_db_path


class ContentLineageTracker:
    """Content Lineage Tracker - tracks content evolution over time.

    This class manages the content_lineage table and provides:
    - Evolution tracking (from_version -> to_version)
    - History queries
    - Version diff
    - Lineage explanation
    """

    def __init__(self, registry: Optional[ContentRegistry] = None, db_path: Optional[Path] = None):
        """Initialize lineage tracker.

        Args:
            registry: ContentRegistry instance (creates new if None)
            db_path: Path to database file (defaults to component_db_path("agentos"))
        """
        self.registry = registry or ContentRegistry()
        self.db_path = db_path or get_db_path()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not initialized. Run 'agentos init' and 'agentos migrate --to 0.5.0' first."
            )
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def track_evolution(
        self, content_id: str, from_version: str, to_version: str, diff: Optional[dict], reason: str
    ) -> int:
        """Track content evolution from one version to another.

        Args:
            content_id: Content ID
            from_version: Source version
            to_version: Target version
            diff: Structured diff (optional)
            reason: Reason for evolution

        Returns:
            Lineage record ID

        Raises:
            ValueError: If versions not found
        """
        # Validate versions exist
        from_content = self.registry.get(content_id, from_version)
        to_content = self.registry.get(content_id, to_version)

        if not from_content:
            raise ValueError(f"Source version not found: {content_id} v{from_version}")
        if not to_content:
            raise ValueError(f"Target version not found: {content_id} v{to_version}")

        # Insert lineage record
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO content_lineage (content_id, from_version, to_version, diff, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (content_id, from_version, to_version, json.dumps(diff) if diff else None, reason),
        )

        lineage_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return lineage_id

    def get_history(self, content_id: str) -> list[dict]:
        """Get evolution history for content.

        Args:
            content_id: Content ID

        Returns:
            List of lineage records (oldest to newest)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM content_lineage
            WHERE content_id = ?
            ORDER BY created_at ASC
            """,
            (content_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "content_id": row["content_id"],
                "from_version": row["from_version"],
                "to_version": row["to_version"],
                "diff": json.loads(row["diff"]) if row["diff"] else None,
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def diff_versions(self, content_id: str, version_a: str, version_b: str) -> dict:
        """Get diff between two versions.

        Args:
            content_id: Content ID
            version_a: First version
            version_b: Second version

        Returns:
            Diff dict with added/removed/changed fields

        Raises:
            ValueError: If versions not found
        """
        content_a = self.registry.get(content_id, version_a)
        content_b = self.registry.get(content_id, version_b)

        if not content_a:
            raise ValueError(f"Version not found: {content_id} v{version_a}")
        if not content_b:
            raise ValueError(f"Version not found: {content_id} v{version_b}")

        # Simple diff: compare specs
        spec_a = content_a.get("spec", {})
        spec_b = content_b.get("spec", {})

        # Find added/removed/changed keys
        keys_a = set(spec_a.keys())
        keys_b = set(spec_b.keys())

        added = {k: spec_b[k] for k in keys_b - keys_a}
        removed = {k: spec_a[k] for k in keys_a - keys_b}
        changed = {
            k: {"from": spec_a[k], "to": spec_b[k]}
            for k in keys_a & keys_b
            if spec_a[k] != spec_b[k]
        }

        return {
            "content_id": content_id,
            "from_version": version_a,
            "to_version": version_b,
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    def explain_version(self, content_id: str, version: str) -> str:
        """Explain how a version came to be (lineage narrative).

        Args:
            content_id: Content ID
            version: Content version

        Returns:
            Human-readable lineage explanation

        Raises:
            ValueError: If version not found
        """
        content = self.registry.get(content_id, version)
        if not content:
            raise ValueError(f"Content not found: {content_id} v{version}")

        metadata = content["metadata"]
        is_root = metadata.get("is_root", False)

        if is_root:
            return (
                f"Content {content_id} v{version} is a ROOT version.\n"
                f"It has no parent and represents the initial creation.\n"
                f"Created at: {metadata.get('created_at', 'unknown')}"
            )

        # Evolved version
        parent_version = metadata.get("parent_version")
        change_reason = metadata.get("change_reason", "No reason provided")

        explanation = (
            f"Content {content_id} v{version} is an EVOLVED version.\n"
            f"Parent: v{parent_version}\n"
            f"Reason: {change_reason}\n"
            f"Created at: {metadata.get('created_at', 'unknown')}\n"
        )

        # Try to get lineage record for more details
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM content_lineage
            WHERE content_id = ? AND to_version = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (content_id, version),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            diff = json.loads(row["diff"]) if row["diff"] else None
            if diff:
                explanation += f"\nChanges:\n"
                if diff.get("added"):
                    explanation += f"  Added: {list(diff['added'].keys())}\n"
                if diff.get("removed"):
                    explanation += f"  Removed: {list(diff['removed'].keys())}\n"
                if diff.get("changed"):
                    explanation += f"  Changed: {list(diff['changed'].keys())}\n"

        # Recursively explain parent (up to 3 levels)
        parent_content = self.registry.get(content_id, parent_version)
        if parent_content and not parent_content["metadata"].get("is_root"):
            grandparent = parent_content["metadata"].get("parent_version")
            if grandparent:
                explanation += f"\n→ Parent v{parent_version} evolved from v{grandparent}"

        return explanation

    def build_lineage_chain(self, content_id: str, version: str) -> list[dict]:
        """Build full lineage chain from root to specified version.

        Args:
            content_id: Content ID
            version: Target version

        Returns:
            List of versions from root to target (ordered)

        Raises:
            ValueError: If version not found
        """
        chain = []
        current_version = version

        while current_version:
            content = self.registry.get(content_id, current_version)
            if not content:
                raise ValueError(f"Version not found in chain: {content_id} v{current_version}")

            chain.append(
                {
                    "version": current_version,
                    "is_root": content["metadata"].get("is_root", False),
                    "parent_version": content["metadata"].get("parent_version"),
                    "change_reason": content["metadata"].get("change_reason"),
                    "created_at": content["metadata"].get("created_at"),
                }
            )

            # Move to parent
            if content["metadata"].get("is_root"):
                break
            current_version = content["metadata"].get("parent_version")

        # Reverse to get root → target order
        return list(reversed(chain))
