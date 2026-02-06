"""Context Differ - Compare context snapshots to show changes"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
import logging
import json
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class ContextDiffItem:
    """Single diff item (added/removed/changed)"""
    item_type: str  # window_msg|rag_chunk|memory|summary
    item_id: str
    tokens_est: int
    change_type: str  # added|removed|changed
    rank: Optional[int] = None


@dataclass
class ContextDiff:
    """Context diff result between two snapshots"""
    session_id: str
    prev_snapshot_id: str
    curr_snapshot_id: str
    
    # Token changes
    tokens_prev: int
    tokens_curr: int
    tokens_delta: int
    
    # Item changes
    added_items: List[ContextDiffItem]
    removed_items: List[ContextDiffItem]
    changed_items: List[ContextDiffItem]
    
    # Breakdown by type
    breakdown: Dict[str, Dict[str, int]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "prev_snapshot_id": self.prev_snapshot_id,
            "curr_snapshot_id": self.curr_snapshot_id,
            "tokens_prev": self.tokens_prev,
            "tokens_curr": self.tokens_curr,
            "tokens_delta": self.tokens_delta,
            "added_items": [
                {
                    "item_type": item.item_type,
                    "item_id": item.item_id,
                    "tokens_est": item.tokens_est,
                    "rank": item.rank
                }
                for item in self.added_items
            ],
            "removed_items": [
                {
                    "item_type": item.item_type,
                    "item_id": item.item_id,
                    "tokens_est": item.tokens_est,
                    "rank": item.rank
                }
                for item in self.removed_items
            ],
            "changed_items": [
                {
                    "item_type": item.item_type,
                    "item_id": item.item_id,
                    "tokens_est": item.tokens_est,
                    "rank": item.rank
                }
                for item in self.changed_items
            ],
            "breakdown": self.breakdown
        }
    
    def format_summary(self) -> str:
        """Format diff as human-readable summary"""
        lines = []
        lines.append(f"Context Diff ({self.prev_snapshot_id[:8]}...{self.curr_snapshot_id[:8]})")
        lines.append("")
        
        # Added items
        if self.added_items:
            for item in self.added_items:
                item_label = self._format_item_label(item)
                lines.append(f"+ Added: {item_label} (+{item.tokens_est} tokens)")
        
        # Removed items
        if self.removed_items:
            for item in self.removed_items:
                item_label = self._format_item_label(item)
                lines.append(f"- Removed: {item_label} (-{item.tokens_est} tokens)")
        
        # Changed items
        if self.changed_items:
            for item in self.changed_items:
                item_label = self._format_item_label(item)
                lines.append(f"~ Changed: {item_label}")
        
        # Net change
        lines.append("")
        sign = "+" if self.tokens_delta >= 0 else ""
        lines.append(f"Net change: {sign}{self.tokens_delta} tokens ({self.tokens_prev} → {self.tokens_curr})")
        
        return "\n".join(lines)
    
    def _format_item_label(self, item: ContextDiffItem) -> str:
        """Format item as readable label"""
        type_labels = {
            "window_msg": "message",
            "rag_chunk": "RAG chunk",
            "memory": "memory fact",
            "summary": "summary"
        }
        type_label = type_labels.get(item.item_type, item.item_type)
        return f"{type_label} {item.item_id[:8]}"


class ContextDiffer:
    """Compares context snapshots to explain token changes"""
    
    def __init__(self, db_path: str):
        """Initialize ContextDiffer
        
        Args:
            db_path: Database path
        """
        self.db_path = db_path
    
    def diff(
        self,
        prev_snapshot_id: str,
        curr_snapshot_id: str
    ) -> ContextDiff:
        """Calculate diff between two snapshots
        
        Args:
            prev_snapshot_id: Previous snapshot ID
            curr_snapshot_id: Current snapshot ID
        
        Returns:
            ContextDiff object
        
        Raises:
            ValueError: If snapshots not found or from different sessions
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Load snapshot metadata
            prev_snapshot = self._load_snapshot(cursor, prev_snapshot_id)
            curr_snapshot = self._load_snapshot(cursor, curr_snapshot_id)
            
            if prev_snapshot["session_id"] != curr_snapshot["session_id"]:
                raise ValueError(
                    f"Snapshots from different sessions: "
                    f"{prev_snapshot['session_id']} vs {curr_snapshot['session_id']}"
                )
            
            session_id = prev_snapshot["session_id"]
            
            # Load snapshot items
            prev_items = self._load_snapshot_items(cursor, prev_snapshot_id)
            curr_items = self._load_snapshot_items(cursor, curr_snapshot_id)
            
            # Calculate differences
            added_items, removed_items, changed_items = self._calculate_item_diff(
                prev_items, curr_items
            )
            
            # Calculate token changes
            tokens_prev = prev_snapshot["total_tokens_est"]
            tokens_curr = curr_snapshot["total_tokens_est"]
            tokens_delta = tokens_curr - tokens_prev
            
            # Calculate breakdown by type
            breakdown = self._calculate_breakdown(
                prev_snapshot, curr_snapshot,
                added_items, removed_items
            )
            
            return ContextDiff(
                session_id=session_id,
                prev_snapshot_id=prev_snapshot_id,
                curr_snapshot_id=curr_snapshot_id,
                tokens_prev=tokens_prev,
                tokens_curr=tokens_curr,
                tokens_delta=tokens_delta,
                added_items=added_items,
                removed_items=removed_items,
                changed_items=changed_items,
                breakdown=breakdown
            )
        
        finally:
            conn.close()
    
    def diff_last_two(self, session_id: str) -> Optional[ContextDiff]:
        """Diff the last two snapshots for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            ContextDiff or None if < 2 snapshots
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT snapshot_id
                FROM context_snapshots
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 2
            """, (session_id,))
            
            rows = cursor.fetchall()
            
            if len(rows) < 2:
                return None
            
            curr_snapshot_id = rows[0]["snapshot_id"]
            prev_snapshot_id = rows[1]["snapshot_id"]
            
            return self.diff(prev_snapshot_id, curr_snapshot_id)
        
        finally:
            conn.close()
    
    def list_snapshots(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List snapshots for a session
        
        Args:
            session_id: Session ID
            limit: Maximum number of snapshots to return
        
        Returns:
            List of snapshot metadata dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    snapshot_id,
                    created_at,
                    reason,
                    total_tokens_est,
                    budget_tokens,
                    metadata
                FROM context_snapshots
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (session_id, limit))
            
            rows = cursor.fetchall()
            
            snapshots = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                snapshots.append({
                    "snapshot_id": row["snapshot_id"],
                    "created_at": row["created_at"],
                    "reason": row["reason"],
                    "total_tokens_est": row["total_tokens_est"],
                    "budget_tokens": row["budget_tokens"],
                    "usage_ratio": row["total_tokens_est"] / row["budget_tokens"] if row["budget_tokens"] > 0 else 0,
                    "watermark": metadata.get("watermark"),
                    "metadata": metadata
                })
            
            return snapshots
        
        finally:
            conn.close()
    
    def _load_snapshot(self, cursor, snapshot_id: str) -> Dict[str, Any]:
        """Load snapshot metadata from DB"""
        cursor.execute("""
            SELECT 
                snapshot_id, session_id, created_at, reason,
                budget_tokens, total_tokens_est,
                tokens_system, tokens_window, tokens_rag,
                tokens_memory, tokens_summary, tokens_policy,
                composition_json, metadata
            FROM context_snapshots
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        return dict(row)
    
    def _load_snapshot_items(
        self,
        cursor,
        snapshot_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """Load snapshot items indexed by (item_type, item_id)"""
        cursor.execute("""
            SELECT item_type, item_id, tokens_est, rank, metadata
            FROM context_snapshot_items
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        
        rows = cursor.fetchall()
        
        items = {}
        for row in rows:
            key = (row["item_type"], row["item_id"])
            items[key] = {
                "item_type": row["item_type"],
                "item_id": row["item_id"],
                "tokens_est": row["tokens_est"],
                "rank": row["rank"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }
        
        return items
    
    def _calculate_item_diff(
        self,
        prev_items: Dict[str, Dict[str, Any]],
        curr_items: Dict[str, Dict[str, Any]]
    ) -> tuple[List[ContextDiffItem], List[ContextDiffItem], List[ContextDiffItem]]:
        """Calculate added/removed/changed items"""
        prev_keys = set(prev_items.keys())
        curr_keys = set(curr_items.keys())
        
        # Added: in curr but not in prev
        added_keys = curr_keys - prev_keys
        added_items = [
            ContextDiffItem(
                item_type=item["item_type"],
                item_id=item["item_id"],
                tokens_est=item["tokens_est"],
                change_type="added",
                rank=item["rank"]
            )
            for key in added_keys
            for item in [curr_items[key]]
        ]
        
        # Removed: in prev but not in curr
        removed_keys = prev_keys - curr_keys
        removed_items = [
            ContextDiffItem(
                item_type=item["item_type"],
                item_id=item["item_id"],
                tokens_est=item["tokens_est"],
                change_type="removed",
                rank=item["rank"]
            )
            for key in removed_keys
            for item in [prev_items[key]]
        ]
        
        # Changed: in both but different rank (reordered)
        common_keys = prev_keys & curr_keys
        changed_items = [
            ContextDiffItem(
                item_type=curr_items[key]["item_type"],
                item_id=curr_items[key]["item_id"],
                tokens_est=curr_items[key]["tokens_est"],
                change_type="changed",
                rank=curr_items[key]["rank"]
            )
            for key in common_keys
            if prev_items[key]["rank"] != curr_items[key]["rank"]
        ]
        
        return added_items, removed_items, changed_items
    
    def _calculate_breakdown(
        self,
        prev_snapshot: Dict[str, Any],
        curr_snapshot: Dict[str, Any],
        added_items: List[ContextDiffItem],
        removed_items: List[ContextDiffItem]
    ) -> Dict[str, Dict[str, int]]:
        """Calculate token breakdown by source type"""
        breakdown = {
            "system": {
                "prev": prev_snapshot["tokens_system"],
                "curr": curr_snapshot["tokens_system"],
                "delta": curr_snapshot["tokens_system"] - prev_snapshot["tokens_system"]
            },
            "window": {
                "prev": prev_snapshot["tokens_window"],
                "curr": curr_snapshot["tokens_window"],
                "delta": curr_snapshot["tokens_window"] - prev_snapshot["tokens_window"]
            },
            "rag": {
                "prev": prev_snapshot["tokens_rag"],
                "curr": curr_snapshot["tokens_rag"],
                "delta": curr_snapshot["tokens_rag"] - prev_snapshot["tokens_rag"]
            },
            "memory": {
                "prev": prev_snapshot["tokens_memory"],
                "curr": curr_snapshot["tokens_memory"],
                "delta": curr_snapshot["tokens_memory"] - prev_snapshot["tokens_memory"]
            },
            "summary": {
                "prev": prev_snapshot["tokens_summary"],
                "curr": curr_snapshot["tokens_summary"],
                "delta": curr_snapshot["tokens_summary"] - prev_snapshot["tokens_summary"]
            }
        }
        
        return breakdown
