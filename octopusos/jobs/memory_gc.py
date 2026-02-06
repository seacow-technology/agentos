"""Memory garbage collection job for automated cleanup and maintenance."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from agentos.core.memory.decay import DecayEngine
from agentos.core.memory.deduplicator import MemoryDeduplicator
from agentos.core.memory.promotion import PromotionEngine

console = Console()


class MemoryGCJob:
    """
    Garbage collection job for memory maintenance.
    
    Performs:
    1. Confidence decay
    2. Cleanup of expired/low-quality memories
    3. Deduplication
    4. Promotion of eligible memories
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        decay_rate: float = 0.95,
        min_confidence: float = 0.2,
        similarity_threshold: float = 0.85,
        dry_run: bool = False
    ):
        """
        Initialize GC job.
        
        Args:
            db_path: Database path (defaults to ~/.agentos/store.db)
            decay_rate: Decay rate for confidence
            min_confidence: Minimum confidence threshold
            similarity_threshold: Similarity threshold for deduplication
            dry_run: If True, no changes are made
        """
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("memoryos")
        
        self.db_path = db_path
        self.dry_run = dry_run
        
        # Initialize engines
        self.decay_engine = DecayEngine(
            decay_rate=decay_rate,
            min_confidence_threshold=min_confidence
        )
        self.deduplicator = MemoryDeduplicator(similarity_threshold=similarity_threshold)
        self.promotion_engine = PromotionEngine()
        
        # Track stats
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "memories_decayed": 0,
            "memories_deleted": 0,
            "memories_promoted": 0,
            "memories_deduplicated": 0,
            "error": None
        }
    
    def run(self) -> dict:
        """
        Run garbage collection.
        
        Returns:
            Stats dict
        """
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["status"] = "running"
        
        try:
            console.print("[cyan]Starting Memory GC job...[/cyan]")
            
            # Load all memories
            memories = self._load_memories()
            console.print(f"[dim]Loaded {len(memories)} memories[/dim]")
            
            # 1. Decay confidence
            decay_count = self._decay_confidence(memories)
            self.stats["memories_decayed"] = decay_count
            console.print(f"[green]✓ Decayed {decay_count} memories[/green]")
            
            # Reload after decay
            memories = self._load_memories()
            
            # 2. Cleanup expired/low-quality
            cleanup_count = self._cleanup_memories(memories)
            self.stats["memories_deleted"] = cleanup_count
            console.print(f"[green]✓ Cleaned up {cleanup_count} memories[/green]")
            
            # Reload after cleanup
            memories = self._load_memories()
            
            # 3. Deduplicate
            dedupe_count = self._deduplicate_memories(memories)
            self.stats["memories_deduplicated"] = dedupe_count
            console.print(f"[green]✓ Deduplicated {dedupe_count} memories[/green]")
            
            # Reload after dedupe
            memories = self._load_memories()
            
            # 4. Promote eligible
            promote_count = self._promote_memories(memories)
            self.stats["memories_promoted"] = promote_count
            console.print(f"[green]✓ Promoted {promote_count} memories[/green]")
            
            self.stats["status"] = "completed"
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            # Record GC run
            if not self.dry_run:
                self._record_gc_run()
            
            console.print(f"\n[bold green]GC Complete![/bold green]")
            console.print(f"  Decayed: {decay_count}")
            console.print(f"  Deleted: {cleanup_count}")
            console.print(f"  Deduplicated: {dedupe_count}")
            console.print(f"  Promoted: {promote_count}")
            
            if self.dry_run:
                console.print("\n[yellow]DRY RUN - No changes were made[/yellow]")
            
            return self.stats
            
        except Exception as e:
            self.stats["status"] = "failed"
            self.stats["error"] = str(e)
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
            console.print(f"[red]✗ GC failed: {e}[/red]")
            return self.stats
    
    def _load_memories(self) -> list[dict]:
        """Load all memories from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memory_items")
        rows = cursor.fetchall()
        
        memories = []
        for row in rows:
            memories.append(self._row_to_dict(row))
        
        conn.close()
        return memories
    
    def _decay_confidence(self, memories: list[dict]) -> int:
        """Apply confidence decay."""
        decay_results = self.decay_engine.calculate_decay_batch(memories)
        
        if not decay_results or self.dry_run:
            return len(decay_results)
        
        # Update database
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for memory_id, old_conf, new_conf in decay_results:
            cursor.execute(
                "UPDATE memory_items SET confidence = ?, updated_at = ? WHERE id = ?",
                (new_conf, datetime.now(timezone.utc).isoformat(), memory_id)
            )
            
            # Audit log
            self._log_audit(cursor, "decayed", memory_id, {
                "old_confidence": old_conf,
                "new_confidence": new_conf
            })
        
        conn.commit()
        conn.close()
        
        return len(decay_results)
    
    def _cleanup_memories(self, memories: list[dict]) -> int:
        """Cleanup expired/low-quality memories."""
        candidates = self.decay_engine.get_cleanup_candidates(memories)
        
        if not candidates or self.dry_run:
            return len(candidates)
        
        # Delete from database
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for memory_id, reason in candidates:
            cursor.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
            
            # Audit log
            self._log_audit(cursor, "deleted", memory_id, {"reason": reason})
        
        conn.commit()
        conn.close()
        
        return len(candidates)
    
    def _deduplicate_memories(self, memories: list[dict]) -> int:
        """Deduplicate memories."""
        groups = self.deduplicator.get_duplicate_groups(memories)
        
        if not groups or self.dry_run:
            return sum(len(g) - 1 for g in groups)
        
        # Merge each group
        conn = self._get_connection()
        cursor = conn.cursor()
        
        total_removed = 0
        
        for group in groups:
            # Merge group
            merged = self.deduplicator.merge(group)
            
            # Update primary memory
            self._update_memory(cursor, merged)
            
            # Delete duplicates
            for mem in group:
                if mem.get("id") != merged.get("id"):
                    cursor.execute("DELETE FROM memory_items WHERE id = ?", (mem.get("id"),))
                    total_removed += 1
                    
                    # Audit log
                    self._log_audit(cursor, "merged", mem.get("id"), {
                        "merged_into": merged.get("id")
                    })
        
        conn.commit()
        conn.close()
        
        return total_removed
    
    def _promote_memories(self, memories: list[dict]) -> int:
        """Promote eligible memories."""
        promoted_count = 0
        
        if self.dry_run:
            # Just count eligible
            for mem in memories:
                eligible, _, _ = self.promotion_engine.check_promotion(mem)
                if eligible:
                    promoted_count += 1
            return promoted_count
        
        # Actually promote
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for mem in memories:
            eligible, target_scope, reason = self.promotion_engine.check_promotion(mem)
            
            if eligible and target_scope:
                promoted, error = self.promotion_engine.promote(mem, target_scope, check_conflicts=True, existing_memories=memories)
                
                if not error:
                    self._update_memory(cursor, promoted)
                    promoted_count += 1
                    
                    # Audit log
                    self._log_audit(cursor, "promoted", mem.get("id"), {
                        "from_scope": mem.get("scope"),
                        "to_scope": target_scope,
                        "reason": reason
                    })
        
        conn.commit()
        conn.close()
        
        return promoted_count
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert row to dict."""
        return {
            "id": row["id"],
            "scope": row["scope"],
            "type": row["type"],
            "content": json.loads(row["content"]),
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "sources": json.loads(row["sources"]) if row["sources"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "confidence": row["confidence"],
            "project_id": row["project_id"],
            "use_count": row.get("use_count", 0),
            "last_used_at": row.get("last_used_at"),
            "retention_policy": self._parse_retention_policy(row)
        }
    
    def _parse_retention_policy(self, row: sqlite3.Row) -> dict:
        """Parse retention policy from row."""
        return {
            "type": row.get("retention_type", "project"),
            "expires_at": row.get("expires_at"),
            "auto_cleanup": bool(row.get("auto_cleanup", 1))
        }
    
    def _update_memory(self, cursor: sqlite3.Cursor, memory: dict):
        """Update memory in database."""
        cursor.execute("""
            UPDATE memory_items
            SET scope = ?,
                type = ?,
                content = ?,
                tags = ?,
                sources = ?,
                confidence = ?,
                updated_at = ?,
                use_count = ?,
                retention_type = ?
            WHERE id = ?
        """, (
            memory.get("scope"),
            memory.get("type"),
            json.dumps(memory.get("content", {})),
            json.dumps(memory.get("tags", [])),
            json.dumps(memory.get("sources", [])),
            memory.get("confidence", 0.5),
            memory.get("updated_at"),
            memory.get("use_count", 0),
            memory.get("retention_policy", {}).get("type", "project"),
            memory.get("id")
        ))
    
    def _log_audit(self, cursor: sqlite3.Cursor, event: str, memory_id: str, metadata: dict):
        """Log audit event."""
        cursor.execute("""
            INSERT INTO memory_audit_log (event, memory_id, metadata)
            VALUES (?, ?, ?)
        """, (event, memory_id, json.dumps(metadata)))
    
    def _record_gc_run(self):
        """Record GC run in database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memory_gc_runs (
                started_at, completed_at, status,
                memories_decayed, memories_deleted, memories_promoted,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.stats["started_at"],
            self.stats["completed_at"],
            self.stats["status"],
            self.stats["memories_decayed"],
            self.stats["memories_deleted"],
            self.stats["memories_promoted"],
            json.dumps({"memories_deduplicated": self.stats["memories_deduplicated"]})
        ))
        
        conn.commit()
        conn.close()
