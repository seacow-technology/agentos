"""
Answer Packs Repository

Data access layer for answer pack management.
Implements CRUD operations for answer_packs and answer_pack_usage tables (v23 schema).

Created for Agent-DB-Answers integration.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentos.core.db.conn_scope import db_conn_scope

logger = logging.getLogger(__name__)


@dataclass
class AnswerPack:
    """Answer pack data model"""
    id: str  # maps to pack_id
    name: str  # maps to pack_name
    status: str  # maps to validation_status (draft, validated, deprecated, frozen)
    items_json: str  # maps to questions_answers - JSON string of Q&A items
    metadata_json: Optional[str]  # maps to metadata
    created_at: str
    updated_at: str


@dataclass
class AnswerPackLink:
    """Link between answer pack and entity (task/intent)"""
    pack_id: str
    entity_type: str  # task or intent
    entity_id: str
    created_at: str


class AnswersRepo:
    """
    Answer Packs Repository

    Provides database access for answer pack management.
    Maps to v23 schema tables: answer_packs, answer_pack_usage
    """

    def __init__(self, db_path: Path):
        """Initialize repository

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"AnswersRepo initialized with db_path={db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list(
        self,
        status: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[AnswerPack], int]:
        """List answer packs with filtering

        Args:
            status: Filter by validation_status
            q: Search query (searches pack_name and description)
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (packs list, total count)
        """
        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Build query
            where_clauses = []
            params = []

            if status:
                where_clauses.append("validation_status = ?")
                params.append(status)

            if q:
                where_clauses.append("(pack_name LIKE ? OR description LIKE ?)")
                search_pattern = f"%{q}%"
                params.extend([search_pattern, search_pattern])

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get total count
            cursor.execute(
                f"SELECT COUNT(*) FROM answer_packs {where_sql}",
                params
            )
            total = cursor.fetchone()[0]

            # Get paginated results
            query_params = params + [limit, offset]
            cursor.execute(
                f"""
                SELECT pack_id, pack_name, validation_status,
                       questions_answers, metadata,
                       created_at, updated_at
                FROM answer_packs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                query_params
            )

            packs = []
            for row in cursor.fetchall():
                packs.append(AnswerPack(
                    id=row["pack_id"],
                    name=row["pack_name"],
                    status=row["validation_status"],
                    items_json=row["questions_answers"],
                    metadata_json=row["metadata"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                ))

            return packs, total

    def get(self, pack_id: str) -> Optional[AnswerPack]:
        """Get single answer pack by ID

        Args:
            pack_id: Pack ID

        Returns:
            AnswerPack or None if not found
        """
        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT pack_id, pack_name, validation_status,
                       questions_answers, metadata,
                       created_at, updated_at
                FROM answer_packs
                WHERE pack_id = ?
                """,
                [pack_id]
            )

            row = cursor.fetchone()

            if not row:
                return None

            return AnswerPack(
                id=row["pack_id"],
                name=row["pack_name"],
                status=row["validation_status"],
                items_json=row["questions_answers"],
                metadata_json=row["metadata"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def create(self, pack: AnswerPack) -> AnswerPack:
        """Create new answer pack

        Args:
            pack: AnswerPack to create

        Returns:
            Created AnswerPack
        """
        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Calculate pack_size from items_json
            items = json.loads(pack.items_json)
            pack_size = len(items)

            cursor.execute(
                """
                INSERT INTO answer_packs (
                    pack_id, pack_name, description,
                    questions_answers, pack_size,
                    validation_status,
                    metadata,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    pack.id,
                    pack.name,
                    None,  # description (not in current AnswerPack model)
                    pack.items_json,
                    pack_size,
                    pack.status,
                    pack.metadata_json,
                    pack.created_at,
                    pack.updated_at
                ]
            )

            conn.commit()

            logger.info(f"Created answer pack: {pack.id} (name={pack.name}, size={pack_size})")
            return pack

    def update(
        self,
        pack_id: str,
        items_json: str,
        metadata_json: Optional[str]
    ) -> AnswerPack:
        """Update answer pack items and metadata

        Args:
            pack_id: Pack ID
            items_json: Updated items JSON
            metadata_json: Updated metadata JSON

        Returns:
            Updated AnswerPack
        """
        from datetime import datetime, timezone

        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Calculate new pack_size
            items = json.loads(items_json)
            pack_size = len(items)

            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                UPDATE answer_packs
                SET questions_answers = ?,
                    pack_size = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE pack_id = ?
                """,
                [items_json, pack_size, metadata_json, now, pack_id]
            )

            conn.commit()

            logger.info(f"Updated answer pack: {pack_id}")
            return self.get(pack_id)

    def set_status(self, pack_id: str, new_status: str) -> AnswerPack:
        """Change pack validation status

        Args:
            pack_id: Pack ID
            new_status: New status (draft, validated, deprecated, frozen)

        Returns:
            Updated AnswerPack
        """
        from datetime import datetime, timezone

        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                UPDATE answer_packs
                SET validation_status = ?,
                    updated_at = ?,
                    validation_at = ?
                WHERE pack_id = ?
                """,
                [new_status, now, now, pack_id]
            )

            conn.commit()

            logger.info(f"Updated pack status: {pack_id} -> {new_status}")
            return self.get(pack_id)

    def link(
        self,
        pack_id: str,
        entity_type: str,
        entity_id: str
    ) -> AnswerPackLink:
        """Create link between pack and entity (task/intent)

        Args:
            pack_id: Pack ID
            entity_type: Entity type (task or intent)
            entity_id: Entity ID

        Returns:
            Created link
        """
        from datetime import datetime, timezone

        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            now = datetime.now(timezone.utc).isoformat()

            # Use answer_pack_usage table for linking
            cursor.execute(
                """
                INSERT INTO answer_pack_usage (
                    pack_id, task_id, intent, operation, used_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    pack_id,
                    entity_id if entity_type == "task" else None,
                    entity_id if entity_type == "intent" else None,
                    "linked",
                    now
                ]
            )

            conn.commit()

            logger.info(f"Linked pack {pack_id} to {entity_type} {entity_id}")

            return AnswerPackLink(
                pack_id=pack_id,
                entity_type=entity_type,
                entity_id=entity_id,
                created_at=now
            )

    def list_links(self, pack_id: str) -> List[AnswerPackLink]:
        """Get all links for a pack

        Args:
            pack_id: Pack ID

        Returns:
            List of links
        """
        with db_conn_scope(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT pack_id, task_id, intent, used_at
                FROM answer_pack_usage
                WHERE pack_id = ?
                ORDER BY used_at DESC
                """,
                [pack_id]
            )

            links = []
            for row in cursor.fetchall():
                if row["task_id"]:
                    links.append(AnswerPackLink(
                        pack_id=row["pack_id"],
                        entity_type="task",
                        entity_id=row["task_id"],
                        created_at=row["used_at"]
                    ))
                elif row["intent"]:
                    links.append(AnswerPackLink(
                        pack_id=row["pack_id"],
                        entity_type="intent",
                        entity_id=row["intent"],
                        created_at=row["used_at"]
                    ))

            return links
