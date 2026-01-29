"""Command history service for tracking and replaying commands."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from agentos.core.command.types import CommandStatus
from agentos.store import get_db_path


@dataclass
class CommandHistoryEntry:
    """A single command history entry."""
    id: str
    command_id: str
    args: dict
    executed_at: str
    duration_ms: Optional[int]
    status: str
    result_summary: Optional[str]
    error: Optional[str]
    task_id: Optional[str]
    session_id: Optional[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class CommandHistoryService:
    """Service for managing command history."""
    
    def __init__(self, db_path: Path | None = None):
        """Initialize history service.
        
        Args:
            db_path: Database path (default: ~/.agentos/store.db)
        """
        self.db_path = Path(db_path or get_db_path())
        self._ensure_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_schema(self):
        """Ensure command_history tables exist."""
        migration_path = (
            Path(__file__).parent.parent.parent
            / "store"
            / "migrations"
            / "v14_command_history.sql"
        )
        
        if migration_path.exists():
            conn = self._get_connection()
            with open(migration_path, "r", encoding="utf-8") as f:
                migration_sql = f.read()
            conn.executescript(migration_sql)
            conn.commit()
            conn.close()
    
    def record(
        self,
        command_id: str,
        args: dict,
        status: CommandStatus,
        duration_ms: int | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Record a command execution.
        
        Args:
            command_id: Command ID (e.g., "kb:search")
            args: Command arguments
            status: Execution status
            duration_ms: Duration in milliseconds
            result_summary: Human-readable summary
            error: Error message if failed
            task_id: Associated task ID
            session_id: Session ID
            
        Returns:
            History entry ID
        """
        history_id = f"hist_{uuid.uuid4().hex[:12]}"
        executed_at = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO command_history 
            (id, command_id, args, executed_at, duration_ms, status, result_summary, error, task_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                command_id,
                json.dumps(args),
                executed_at,
                duration_ms,
                status.value if isinstance(status, CommandStatus) else status,
                result_summary,
                error,
                task_id,
                session_id,
            ),
        )
        
        conn.commit()
        conn.close()
        
        return history_id
    
    def get(self, history_id: str) -> Optional[CommandHistoryEntry]:
        """Get a history entry by ID.
        
        Args:
            history_id: History entry ID
            
        Returns:
            CommandHistoryEntry or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM command_history WHERE id = ?",
            (history_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return CommandHistoryEntry(
            id=row["id"],
            command_id=row["command_id"],
            args=json.loads(row["args"]) if row["args"] else {},
            executed_at=row["executed_at"],
            duration_ms=row["duration_ms"],
            status=row["status"],
            result_summary=row["result_summary"],
            error=row["error"],
            task_id=row["task_id"],
            session_id=row["session_id"],
        )
    
    def list(
        self,
        command_id: str | None = None,
        status: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[CommandHistoryEntry]:
        """List history entries with filters.
        
        Args:
            command_id: Filter by command ID
            status: Filter by status
            task_id: Filter by task ID
            limit: Maximum number of entries
            
        Returns:
            List of CommandHistoryEntry
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM command_history WHERE 1=1"
        params = []
        
        if command_id:
            query += " AND command_id = ?"
            params.append(command_id)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        
        query += " ORDER BY executed_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            CommandHistoryEntry(
                id=row["id"],
                command_id=row["command_id"],
                args=json.loads(row["args"]) if row["args"] else {},
                executed_at=row["executed_at"],
                duration_ms=row["duration_ms"],
                status=row["status"],
                result_summary=row["result_summary"],
                error=row["error"],
                task_id=row["task_id"],
                session_id=row["session_id"],
            )
            for row in rows
        ]
    
    def pin(self, history_id: str, note: str | None = None) -> str:
        """Pin a history entry.
        
        Args:
            history_id: History entry ID
            note: Optional note about why it's pinned
            
        Returns:
            Pin ID
        """
        pin_id = f"pin_{uuid.uuid4().hex[:12]}"
        pinned_at = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO pinned_commands (id, history_id, pinned_at, note)
            VALUES (?, ?, ?, ?)
            """,
            (pin_id, history_id, pinned_at, note),
        )
        
        conn.commit()
        conn.close()
        
        return pin_id
    
    def unpin(self, history_id: str):
        """Unpin a history entry.
        
        Args:
            history_id: History entry ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM pinned_commands WHERE history_id = ?",
            (history_id,)
        )
        
        conn.commit()
        conn.close()
    
    def list_pinned(self) -> List[CommandHistoryEntry]:
        """List all pinned commands.
        
        Returns:
            List of pinned CommandHistoryEntry
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT h.* FROM command_history h
            JOIN pinned_commands p ON h.id = p.history_id
            ORDER BY p.pinned_at DESC
            """
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            CommandHistoryEntry(
                id=row["id"],
                command_id=row["command_id"],
                args=json.loads(row["args"]) if row["args"] else {},
                executed_at=row["executed_at"],
                duration_ms=row["duration_ms"],
                status=row["status"],
                result_summary=row["result_summary"],
                error=row["error"],
                task_id=row["task_id"],
                session_id=row["session_id"],
            )
            for row in rows
        ]
    
    def clear(self, older_than_days: int | None = None):
        """Clear history entries.
        
        Args:
            older_than_days: Only clear entries older than N days (None = clear all)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if older_than_days:
            # Calculate cutoff date
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
            cursor.execute(
                "DELETE FROM command_history WHERE executed_at < ?",
                (cutoff,)
            )
        else:
            cursor.execute("DELETE FROM command_history")
        
        conn.commit()
        conn.close()
    
    def export(self, output_path: Path):
        """Export history to JSON file.
        
        Args:
            output_path: Output file path
        """
        entries = self.list(limit=10000)  # Export up to 10k entries
        
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(entries),
            "entries": [entry.to_dict() for entry in entries],
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
