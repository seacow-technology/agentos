"""SQLite implementation of MemoryStore."""

from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memoryos.core.store import MemoryStore

class SqliteMemoryStore(MemoryStore):
    """SQLite-based memory store with FTS5."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("memoryos")
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create memory_items table (simplified version)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                project_id TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create FTS5 virtual table (no external content, store directly)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
                id UNINDEXED,
                summary
            )
        """)
        
        # Triggers for FTS5
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_items_ai AFTER INSERT ON memory_items BEGIN
                INSERT INTO memory_items_fts(rowid, id, summary)
                VALUES (new.rowid, new.id, json_extract(new.content, '$.summary'));
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_items_ad AFTER DELETE ON memory_items BEGIN
                DELETE FROM memory_items_fts WHERE rowid = old.rowid;
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_items_au AFTER UPDATE ON memory_items BEGIN
                DELETE FROM memory_items_fts WHERE rowid = old.rowid;
                INSERT INTO memory_items_fts(rowid, id, summary)
                VALUES (new.rowid, new.id, json_extract(new.content, '$.summary'));
            END
        """)
        
        conn.commit()
        conn.close()
    
    def upsert(self, memory_item: dict) -> str:
        """Insert or update memory item."""
        memory_id = memory_item.get("id") or f"mem-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM memory_items WHERE id = ?", (memory_id,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update
            cursor.execute("""
                UPDATE memory_items
                SET scope = ?,
                    type = ?,
                    content = ?,
                    tags = ?,
                    project_id = ?,
                    confidence = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                memory_item.get("scope", "project"),
                memory_item.get("type", "convention"),
                json.dumps(memory_item.get("content", {})),
                json.dumps(memory_item.get("tags", [])),
                memory_item.get("project_id"),
                memory_item.get("confidence", 1.0),
                now,
                memory_id
            ))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO memory_items (
                    id, scope, type, content, tags, project_id, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                memory_item.get("scope", "project"),
                memory_item.get("type", "convention"),
                json.dumps(memory_item.get("content", {})),
                json.dumps(memory_item.get("tags", [])),
                memory_item.get("project_id"),
                memory_item.get("confidence", 1.0),
                now,
                now
            ))
        
        conn.commit()
        conn.close()
        return memory_id
    
    def get(self, memory_id: str) -> Optional[dict]:
        """Get memory by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "scope": row[1],
            "type": row[2],
            "content": json.loads(row[3]),
            "tags": json.loads(row[4]) if row[4] else [],
            "project_id": row[5],
            "confidence": row[6],
            "created_at": row[7],
            "updated_at": row[8]
        }
    
    def query(self, query: dict) -> list[dict]:
        """Query memories with filters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        filters = query.get("filters", {})
        params = []
        
        # Build query with full-text search if needed
        if query.get("query"):
            # Full-text search with filters
            sql = """
                SELECT m.* FROM memory_items m
                JOIN memory_items_fts fts ON m.rowid = fts.rowid
                WHERE fts.summary MATCH ?
            """
            params.append(query["query"])
            
            # Add filters
            if filters.get("scope"):
                sql += " AND m.scope = ?"
                params.append(filters["scope"])
            
            if filters.get("type"):
                sql += " AND m.type = ?"
                params.append(filters["type"])
            
            if filters.get("project_id"):
                sql += " AND m.project_id = ?"
                params.append(filters["project_id"])
            
            if filters.get("confidence_min"):
                sql += " AND m.confidence >= ?"
                params.append(filters["confidence_min"])
        else:
            # Regular filter query
            sql = "SELECT * FROM memory_items WHERE 1=1"
            
            if filters.get("scope"):
                sql += " AND scope = ?"
                params.append(filters["scope"])
            
            if filters.get("type"):
                sql += " AND type = ?"
                params.append(filters["type"])
            
            if filters.get("project_id"):
                sql += " AND project_id = ?"
                params.append(filters["project_id"])
            
            if filters.get("confidence_min"):
                sql += " AND confidence >= ?"
                params.append(filters["confidence_min"])
        
        # Limit
        top_k = query.get("top_k", 100)
        sql += f" LIMIT {top_k}"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "scope": row[1],
                "type": row[2],
                "content": json.loads(row[3]),
                "tags": json.loads(row[4]) if row[4] else [],
                "project_id": row[5],
                "confidence": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            })
        
        return results
    
    def delete(self, memory_id: str) -> bool:
        """Delete memory by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return deleted
    
    def build_context(self, project_id: str, agent_type: str, **kwargs) -> dict:
        """Build memory context."""
        # Query memories for this project
        query = {
            "filters": {"project_id": project_id},
            "top_k": 100
        }
        memories = self.query(query)
        
        # Group by scope
        context_blocks = []
        scopes = ["global", "project", "repo", "task", "agent"]
        
        for scope in scopes:
            scope_memories = [m for m in memories if m["scope"] == scope]
            if scope_memories:
                context_blocks.append({
                    "type": scope,
                    "memories": scope_memories,
                    "weight": 1.0
                })
        
        return {
            "schema_version": "1.0.0",
            "context_blocks": context_blocks,
            "metadata": {
                "total_memories": len(memories),
                "memoryos_version": "0.3.0",
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        }
