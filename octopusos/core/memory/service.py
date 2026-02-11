"""Memory Service for external memory storage and retrieval."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from octopusos.core.memory.budgeter import ContextBudget, ContextBudgeter
from octopusos.core.memory.permission import MemoryPermissionService
from octopusos.core.storage.paths import component_db_path
from octopusos.core.time import utc_now_iso


console = Console()
logger = logging.getLogger(__name__)


def _trace_log(event: str, **fields: object) -> None:
    payload = {"event": event, **fields}
    logger.info("memory_store_trace %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))


class MemoryService:
    """External memory service for storing and retrieving agent memories."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize memory service with database connection."""
        if db_path is None:
            db_path = component_db_path("memoryos")
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Use the same db_path for permission service
        self.permission_service = MemoryPermissionService(db_path=self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_memory_columns(self, cursor: sqlite3.Cursor) -> set[str]:
        rows = cursor.execute("PRAGMA table_info(memory_items)").fetchall()
        columns: set[str] = set()
        for row in rows:
            try:
                columns.add(row["name"])
            except Exception:
                columns.add(row[1])
        return columns

    def upsert(self, *args, **kwargs) -> str:
        """
        Insert or update memory item with conflict resolution.

        Conflict Strategy:
        - Same (scope, type, key) = potential conflict
        - Resolution: Mark old as superseded, insert new
        - Keep version chain for audit

        Args:
            agent_id: Agent performing the operation (requires WRITE capability)
            memory_item: MemoryItem dict (must conform to schema)

        Returns:
            memory_id: The ID of the inserted/updated memory

        Raises:
            PermissionDenied: If agent lacks WRITE capability
        """
        agent_id = kwargs.pop("agent_id", "system")
        memory_item = kwargs.pop("memory_item", None)

        if len(args) == 1:
            memory_item = args[0]
        elif len(args) >= 2:
            if isinstance(args[0], dict):
                memory_item = args[0]
                agent_id = args[1]
            else:
                agent_id = args[0]
                memory_item = args[1]

        if memory_item is None:
            raise ValueError("memory_item required")

        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="upsert",
            context={
                "method": "upsert",
                "memory_type": memory_item.get("type"),
                "scope": memory_item.get("scope")
            }
        )
        conn = self._get_connection()
        cursor = conn.cursor()
        columns = self._get_memory_columns(cursor)
        store_path = str(Path(self.db_path).resolve())

        # Extract conflict detection key
        scope = memory_item["scope"]
        mem_type = memory_item["type"]
        content = memory_item["content"]
        key = content.get("key")  # For preference/fact types

        # Check for existing memory with same (scope, type, key)
        if key:
            existing = self._find_conflicting_memory(
                scope=scope,
                mem_type=mem_type,
                key=key,
                project_id=memory_item.get("project_id"),
                cursor=cursor
            )

            if existing:
                # Conflict detected!
                logger.info(
                    f"Memory conflict detected: {mem_type}/{key} "
                    f"(old: {existing['id']}, new value: {content.get('value')})"
                )

                # Apply conflict resolution strategy
                resolved_id = self._resolve_conflict(
                    existing=existing,
                    new_item=memory_item,
                    cursor=cursor,
                    conn=conn
                )
                conn.close()
                return resolved_id

        # No conflict, standard upsert
        memory_id = memory_item.get("id")
        if not memory_id:
            # Generate ID if not provided
            memory_id = f"mem-{uuid.uuid4().hex[:12]}"
            memory_item["id"] = memory_id

        # Set timestamps
        now = utc_now_iso()
        if "created_at" not in memory_item:
            memory_item["created_at"] = now
        memory_item["updated_at"] = now

        # Set conflict resolution defaults
        if "version" not in memory_item:
            memory_item["version"] = 1
        if "is_active" not in memory_item:
            memory_item["is_active"] = 1

        # Extract fields
        content_json = json.dumps(memory_item["content"])
        tags = json.dumps(memory_item.get("tags", []))
        sources = json.dumps(memory_item.get("sources", []))
        confidence = memory_item.get("confidence", 0.5)
        project_id = memory_item.get("project_id")

        columns = self._get_memory_columns(cursor)
        base_columns = [
            "id",
            "scope",
            "type",
            "content",
            "tags",
            "sources",
            "confidence",
            "project_id",
            "created_at",
            "updated_at",
        ]
        optional_columns = ["version", "is_active", "superseded_by", "supersedes"]
        insert_columns = [col for col in base_columns if col in columns]
        insert_columns += [col for col in optional_columns if col in columns]

        values_map = {
            "id": memory_id,
            "scope": scope,
            "type": mem_type,
            "content": content_json,
            "tags": tags,
            "sources": sources,
            "confidence": confidence,
            "project_id": project_id,
            "created_at": memory_item["created_at"],
            "updated_at": memory_item["updated_at"],
            "version": memory_item["version"],
            "is_active": memory_item["is_active"],
            "superseded_by": memory_item.get("superseded_by"),
            "supersedes": memory_item.get("supersedes"),
        }

        placeholders = ", ".join(["?"] * len(insert_columns))
        update_columns = [col for col in insert_columns if col not in ("id", "created_at")]
        update_clause = ", ".join([f"{col} = excluded.{col}" for col in update_columns])

        cursor.execute(
            f"""
            INSERT INTO memory_items ({", ".join(insert_columns)})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET
                {update_clause}
            """,
            [values_map[col] for col in insert_columns],
        )

        _trace_log(
            "memory_write_before_commit",
            memory_id=memory_id,
            scope=scope,
            memory_type=mem_type,
            store_path=store_path,
            write_count=1,
        )
        try:
            conn.commit()
            _trace_log(
                "memory_write_after_commit",
                memory_id=memory_id,
                scope=scope,
                memory_type=mem_type,
                store_path=store_path,
                write_count=1,
                commit_result="success",
            )
        except Exception as commit_error:
            conn.rollback()
            _trace_log(
                "memory_write_after_commit",
                memory_id=memory_id,
                scope=scope,
                memory_type=mem_type,
                store_path=store_path,
                write_count=1,
                commit_result="failed",
                error=str(commit_error),
            )
            logger.error(
                "Memory commit failed: memory_id=%s store_path=%s error=%s",
                memory_id,
                store_path,
                commit_error,
                exc_info=True,
            )
            raise
        conn.close()

        return memory_id

    def get(self, *args, **kwargs) -> Optional[dict]:
        """
        Get memory item by ID.

        Args:
            agent_id: Agent performing the operation (requires READ capability)
            memory_id: Memory ID to retrieve

        Returns:
            Memory item dict or None if not found

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        agent_id = kwargs.pop("agent_id", "system")
        memory_id = kwargs.pop("memory_id", None)

        if len(args) == 1:
            memory_id = args[0]
        elif len(args) >= 2:
            first, second = args[0], args[1]
            if isinstance(first, str) and isinstance(second, str):
                if first.startswith("mem-") or not second.startswith("mem-"):
                    memory_id = first
                    agent_id = second
                else:
                    agent_id = first
                    memory_id = second
            else:
                memory_id = first
                agent_id = second

        if memory_id is None:
            raise ValueError("memory_id required")

        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="get",
            context={"method": "get", "memory_id": memory_id}
        )
        conn = self._get_connection()
        cursor = conn.cursor()
        columns = self._get_memory_columns(cursor)

        cursor.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_dict(row)

    def list(
        self,
        agent_id: str = "system",
        scope: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        mem_type: Optional[str] = None,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[dict]:
        """
        List memory items with filters (only active by default).

        Args:
            agent_id: Agent performing the operation (requires READ capability)
            scope: Filter by scope (global|project|repo|task|agent)
            project_id: Filter by project ID
            tags: Filter by tags (returns items with ANY of these tags)
            mem_type: Filter by memory type
            limit: Maximum results to return
            include_inactive: Include superseded/inactive memories

        Returns:
            List of memory items

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="list",
            context={
                "method": "list",
                "scope": scope,
                "project_id": project_id
            }
        )
        conn = self._get_connection()
        cursor = conn.cursor()
        columns = self._get_memory_columns(cursor)

        query = "SELECT * FROM memory_items WHERE 1=1"
        params = []

        # Only return active memories by default
        if not include_inactive:
            if "is_active" in columns:
                query += " AND (is_active IS NULL OR is_active = 1)"

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if mem_type:
            query += " AND type = ?"
            params.append(mem_type)

        if tags:
            # Filter by tags (JSON contains any of the tags)
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
            query += " AND (" + " OR ".join(tag_conditions) + ")"

        query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def search(
        self, agent_id: str, query: str, scope: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        """
        Full-text search memories.

        Args:
            agent_id: Agent performing the operation (requires READ capability)
            query: Search query string
            scope: Optional scope filter
            limit: Maximum results

        Returns:
            List of matching memory items

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="search",
            context={"method": "search", "query": query, "scope": scope}
        )
        conn = self._get_connection()
        cursor = conn.cursor()
        columns = self._get_memory_columns(cursor)

        # FTS search
        sql = """
            SELECT m.*
            FROM memory_items m
            JOIN memory_fts fts ON m.rowid = fts.rowid
            WHERE memory_fts MATCH ?
        """
        params = [query]

        if scope:
            sql += " AND m.scope = ?"
            params.append(scope)

        sql += " ORDER BY m.confidence DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def build_context(self, *args, **kwargs) -> dict:
        """
        Build MemoryPack context for agent execution.

        Args:
            agent_id: Agent performing the operation (requires READ capability)
            project_id: Target project ID (can be None for global-only context)
            agent_type: Target agent type
            task_id: Optional task ID
            confidence_threshold: Minimum confidence score
            budget: Context budget (defaults to ContextBudget())

        Returns:
            MemoryPack dict

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        agent_id = kwargs.pop("agent_id", "system")
        project_id = kwargs.pop("project_id", None)
        agent_type = kwargs.pop("agent_type", None)
        task_id = kwargs.pop("task_id", None)
        confidence_threshold = kwargs.pop("confidence_threshold", 0.3)
        budget = kwargs.pop("budget", None)

        if args:
            if len(args) >= 3:
                agent_id = args[0]
                project_id = args[1]
                agent_type = args[2]
                if len(args) > 3:
                    task_id = args[3]
                if len(args) > 4:
                    confidence_threshold = args[4]
                if len(args) > 5:
                    budget = args[5]
            elif len(args) == 2:
                project_id = args[0]
                agent_type = args[1]
            elif len(args) == 1:
                project_id = args[0]

        if agent_type is None:
            raise ValueError("agent_type required")

        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="build_context",
            context={
                "method": "build_context",
                "project_id": project_id,
                "agent_type": agent_type
            }
        )
        conn = self._get_connection()
        cursor = conn.cursor()
        columns = self._get_memory_columns(cursor)

        # Query memories by scope hierarchy
        scopes = ["global"]
        if project_id:
            scopes.extend(["project", "repo"])
        if task_id:
            scopes.extend(["task"])
        scopes.append("agent")

        memories = []

        for scope in scopes:
            query = """
                SELECT * FROM memory_items
                WHERE scope = ?
                AND confidence >= ?
            """
            params = [scope, confidence_threshold]

            if "is_active" in columns:
                query += " AND (is_active IS NULL OR is_active = 1)"

            if scope in ["project", "repo", "task", "agent"]:
                if project_id:
                    # Filter by project_id when provided
                    query += " AND (project_id = ? OR project_id IS NULL)"
                    params.append(project_id)
                else:
                    # When project_id is None, only load global/agent scope items without project_id
                    query += " AND project_id IS NULL"

            query += " ORDER BY confidence DESC, created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            memories.extend([self._row_to_dict(row) for row in rows])

        conn.close()

        # Apply budget trimming
        budgeter = ContextBudgeter(budget=budget)
        trimmed_memories, budget_stats = budgeter.trim_context(memories)

        # Build summary
        by_type = {}
        by_scope = {}
        for mem in trimmed_memories:
            mem_type = mem["type"]
            mem_scope = mem["scope"]
            by_type[mem_type] = by_type.get(mem_type, 0) + 1
            by_scope[mem_scope] = by_scope.get(mem_scope, 0) + 1

        memory_pack = {
            "schema_version": "1.0.0",
            "project_id": project_id,
            "agent_type": agent_type,
            "task_id": task_id,
            "memories": trimmed_memories,
            "summary": {
                "total_memories": len(trimmed_memories),
                "by_type": by_type,
                "by_scope": by_scope,
            },
            "generated_at": utc_now_iso(),
            "metadata": {
                "confidence_threshold": confidence_threshold,
                "filters_applied": [f"scope in {scopes}", f"confidence >= {confidence_threshold}"],
                "budget": {
                    "max_tokens": budget.max_tokens if budget else 4000,
                    "max_memories": budget.max_memories if budget else 100,
                    "utilized_tokens": budget_stats["total_tokens"],
                    "utilized_memories": budget_stats["total_memories"],
                    "trimmed": budget_stats["trimmed"],
                    "removed_count": budget_stats.get("removed_count", 0)
                }
            },
        }

        return memory_pack

    def delete(self, agent_id: str, memory_id: str) -> bool:
        """
        Delete memory item by ID.

        Args:
            agent_id: Agent performing the operation (requires ADMIN capability)
            memory_id: Memory ID to delete

        Returns:
            True if deleted

        Raises:
            PermissionDenied: If agent lacks ADMIN capability
        """
        # Permission check
        self.permission_service.check_capability(
            agent_id=agent_id,
            operation="delete",
            context={"method": "delete", "memory_id": memory_id}
        )
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def propose(
        self,
        agent_id: str,
        memory_item: dict,
        reason: Optional[str] = None
    ) -> str:
        """
        Propose a memory (requires PROPOSE capability).

        This is an alternative to upsert() for agents with PROPOSE capability.
        The memory enters approval queue instead of being written directly.

        This is the key anti-hallucination mechanism: chat agents can propose
        memories but cannot pollute the Memory system until a human reviews.

        Args:
            agent_id: Agent proposing
            memory_item: MemoryItem to propose
            reason: Optional reason for the proposal

        Returns:
            proposal_id (not memory_id - use approve_proposal to get memory_id)

        Raises:
            PermissionDenied: If agent lacks PROPOSE capability

        Example:
            >>> service.propose(
            ...     agent_id="chat_agent",
            ...     memory_item={
            ...         "scope": "global",
            ...         "type": "preference",
            ...         "content": {"key": "preferred_name", "value": "Alice"}
            ...     },
            ...     reason="User said: 'call me Alice'"
            ... )
            '01HX123ABC...'
        """
        from octopusos.core.memory.proposals import get_proposal_service

        proposal_service = get_proposal_service()
        return proposal_service.propose_memory(
            agent_id=agent_id,
            memory_item=memory_item,
            reason=reason
        )

    def get_version_history(self, memory_id: str) -> list[dict]:
        """
        Get version history for a memory item.

        Returns all versions in the conflict resolution chain, from oldest to newest.

        Args:
            memory_id: Memory ID to get history for

        Returns:
            List of memory items in version order
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get the current memory
        cursor.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return []

        current = self._row_to_dict(row)
        versions = [current]

        # Follow supersedes chain backwards to find older versions
        predecessor_id = current.get("supersedes")
        while predecessor_id:
            cursor.execute("SELECT * FROM memory_items WHERE id = ?", (predecessor_id,))
            row = cursor.fetchone()
            if not row:
                break

            predecessor = self._row_to_dict(row)
            versions.insert(0, predecessor)  # Insert at beginning
            predecessor_id = predecessor.get("supersedes")

        # Follow superseded_by chain forwards to find newer versions
        successor_id = current.get("superseded_by")
        while successor_id:
            cursor.execute("SELECT * FROM memory_items WHERE id = ?", (successor_id,))
            row = cursor.fetchone()
            if not row:
                break

            successor = self._row_to_dict(row)
            versions.append(successor)
            successor_id = successor.get("superseded_by")

        conn.close()
        return versions

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to MemoryItem dict."""
        row_keys = set(row.keys())
        result = {
            "id": row["id"],
            "scope": row["scope"],
            "type": row["type"],
            "content": json.loads(row["content"]),
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            # Backward/partial schema compatibility: old rows may not have sources.
            "sources": json.loads(row["sources"]) if "sources" in row_keys and row["sources"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "confidence": row["confidence"],
            "project_id": row["project_id"],
        }

        # Add conflict resolution fields if they exist
        if "version" in row.keys():
            result["version"] = row["version"]
        if "is_active" in row.keys():
            result["is_active"] = bool(row["is_active"])
        if "superseded_by" in row.keys():
            result["superseded_by"] = row["superseded_by"]
        if "supersedes" in row.keys():
            result["supersedes"] = row["supersedes"]
        if "superseded_at" in row.keys():
            result["superseded_at"] = row["superseded_at"]

        return result

    def _find_conflicting_memory(
        self,
        scope: str,
        mem_type: str,
        key: str,
        project_id: Optional[str],
        cursor
    ) -> Optional[dict]:
        """
        Find existing active memory with same (scope, type, key).

        Args:
            scope: Memory scope
            mem_type: Memory type
            key: Content key to check for conflicts
            project_id: Optional project ID filter
            cursor: Database cursor

        Returns:
            Existing MemoryItem dict if found, None otherwise
        """
        columns = self._get_memory_columns(cursor)

        query = """
            SELECT *
            FROM memory_items
            WHERE scope = ?
              AND type = ?
              AND json_extract(content, '$.key') = ?
        """
        params = [scope, mem_type, key]

        if "is_active" in columns:
            query += " AND is_active = 1"

        # Add project_id filter if provided
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        else:
            query += " AND project_id IS NULL"

        query += " ORDER BY created_at DESC LIMIT 1"

        cursor.execute(query, params)
        row = cursor.fetchone()

        if row:
            return self._row_to_dict(row)
        return None

    def _resolve_conflict(
        self,
        existing: dict,
        new_item: dict,
        cursor,
        conn
    ) -> str:
        """
        Resolve memory conflict using strategy:
        1. Latest + Highest Confidence wins
        2. Mark old as superseded
        3. Link version chain

        Args:
            existing: Existing memory item
            new_item: New memory item
            cursor: Database cursor
            conn: Database connection

        Returns:
            ID of the winning memory
        """
        # Strategy 1: Compare confidence
        old_confidence = existing.get("confidence", 0.5)
        new_confidence = new_item.get("confidence", 0.5)

        # Strategy 2: Latest wins if confidence is close
        confidence_diff = abs(new_confidence - old_confidence)

        if confidence_diff < 0.1:
            # Confidences are similar, latest wins
            winner = "new"
        else:
            # Use higher confidence
            winner = "new" if new_confidence > old_confidence else "old"

        if winner == "new":
            # New item wins: mark old as superseded
            old_id = existing["id"]
            new_id = new_item.get("id") or f"mem-{uuid.uuid4().hex[:12]}"
            new_item["id"] = new_id

            # Update old item to mark as superseded
            superseded_at = utc_now_iso()
            cursor.execute("""
                UPDATE memory_items
                SET is_active = 0,
                    superseded_by = ?,
                    superseded_at = ?
                WHERE id = ?
            """, (new_id, superseded_at, old_id))

            # Set new item's metadata
            now = utc_now_iso()
            if "created_at" not in new_item:
                new_item["created_at"] = now
            new_item["updated_at"] = now
            new_item["is_active"] = 1
            new_item["supersedes"] = old_id
            new_item["version"] = existing.get("version", 1) + 1
            new_item["superseded_by"] = None

            # Extract fields for new item
            content_json = json.dumps(new_item["content"])
            tags = json.dumps(new_item.get("tags", []))
            sources = json.dumps(new_item.get("sources", []))
            confidence = new_item.get("confidence", 0.5)
            project_id = new_item.get("project_id")

            # Insert new item
            cursor.execute(
                """
                INSERT INTO memory_items (
                    id, scope, type, content, tags, sources, confidence, project_id,
                    created_at, updated_at, version, is_active, superseded_by, supersedes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    new_id,
                    new_item["scope"],
                    new_item["type"],
                    content_json,
                    tags,
                    sources,
                    confidence,
                    project_id,
                    new_item["created_at"],
                    new_item["updated_at"],
                    new_item["version"],
                    new_item["is_active"],
                    new_item.get("superseded_by"),
                    new_item["supersedes"],
                ),
            )

            store_path = str(Path(self.db_path).resolve())
            _trace_log(
                "memory_write_before_commit",
                memory_id=new_id,
                scope=new_item["scope"],
                memory_type=new_item["type"],
                store_path=store_path,
                write_count=1,
                conflict_resolution="supersede_old",
            )
            try:
                conn.commit()
                _trace_log(
                    "memory_write_after_commit",
                    memory_id=new_id,
                    scope=new_item["scope"],
                    memory_type=new_item["type"],
                    store_path=store_path,
                    write_count=1,
                    conflict_resolution="supersede_old",
                    commit_result="success",
                )
            except Exception as commit_error:
                conn.rollback()
                _trace_log(
                    "memory_write_after_commit",
                    memory_id=new_id,
                    scope=new_item["scope"],
                    memory_type=new_item["type"],
                    store_path=store_path,
                    write_count=1,
                    conflict_resolution="supersede_old",
                    commit_result="failed",
                    error=str(commit_error),
                )
                logger.error(
                    "Memory conflict commit failed: memory_id=%s store_path=%s error=%s",
                    new_id,
                    store_path,
                    commit_error,
                    exc_info=True,
                )
                raise

            logger.info(
                f"Conflict resolved: new value wins "
                f"(old: {old_id}, new: {new_id}, version: {new_item['version']})"
            )

            return new_id

        else:
            # Old item wins: don't insert new
            logger.info(
                f"Conflict resolved: old value retained "
                f"(higher confidence: {old_confidence} > {new_confidence})"
            )
            return existing["id"]
