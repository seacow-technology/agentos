"""Memory promotion engine for scope升级 lifecycle management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from agentos.core.time import utc_now, utc_now_iso



class PromotionEngine:
    """
    Engine for memory scope promotion (temporary → project → global).
    
    Promotion rules:
    - temporary → project: use_count >= 3
    - project → global: use_count >= 10 AND age > 30 days AND no conflicts
    """
    
    # Promotion thresholds
    TEMP_TO_PROJECT_USES = 3
    PROJECT_TO_GLOBAL_USES = 10
    PROJECT_TO_GLOBAL_DAYS = 30
    
    def __init__(self):
        """Initialize promotion engine."""
        pass
    
    def check_promotion(
        self,
        memory_item: dict,
        now: Optional[datetime] = None
    ) -> tuple[bool, Optional[str], str]:
        """
        Check if a memory is eligible for promotion.
        
        Args:
            memory_item: MemoryItem dict
            now: Current time (defaults to now)
        
        Returns:
            (eligible, target_scope, reason)
        """
        if now is None:
            now = utc_now()
        
        current_scope = memory_item.get("scope")
        use_count = memory_item.get("use_count", 0)
        created_at = memory_item.get("created_at")
        
        # Check temporary → project
        if current_scope == "temporary":
            if use_count >= self.TEMP_TO_PROJECT_USES:
                return True, "project", f"Used {use_count} times (>={self.TEMP_TO_PROJECT_USES})"
        
        # Check project → global
        elif current_scope == "project":
            if use_count >= self.PROJECT_TO_GLOBAL_USES:
                # Also check age requirement
                if created_at:
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    
                    age_days = (now - created_dt).total_seconds() / 86400
                    
                    if age_days >= self.PROJECT_TO_GLOBAL_DAYS:
                        return True, "global", f"Used {use_count} times and {int(age_days)} days old"
                    else:
                        return False, None, f"Not old enough ({int(age_days)} < {self.PROJECT_TO_GLOBAL_DAYS} days)"
        
        # No promotion eligible
        return False, None, ""
    
    def promote(
        self,
        memory_item: dict,
        target_scope: str,
        check_conflicts: bool = True,
        existing_memories: Optional[list[dict]] = None
    ) -> tuple[dict, Optional[str]]:
        """
        Promote a memory to target scope.
        
        Args:
            memory_item: MemoryItem dict to promote
            target_scope: Target scope (project or global)
            check_conflicts: Whether to check for conflicts
            existing_memories: List of existing memories (for conflict check)
        
        Returns:
            (promoted_memory, error_message)
        """
        current_scope = memory_item.get("scope")
        
        # Validate promotion path
        valid_promotions = {
            "temporary": ["project"],
            "project": ["global"],
            "task": ["project"],  # Task memories can also promote
            "agent": ["project"]
        }
        
        if current_scope not in valid_promotions:
            return memory_item, f"Cannot promote from scope '{current_scope}'"
        
        if target_scope not in valid_promotions[current_scope]:
            return memory_item, f"Invalid promotion: {current_scope} → {target_scope}"
        
        # Check for conflicts if requested
        if check_conflicts and existing_memories:
            conflict = self._check_conflict(memory_item, target_scope, existing_memories)
            if conflict:
                return memory_item, f"Conflict with existing memory: {conflict}"
        
        # Create promoted copy
        promoted = memory_item.copy()
        promoted["scope"] = target_scope
        
        # Update retention policy if promoting to global
        if target_scope == "global":
            promoted["retention_policy"] = {
                "type": "permanent",
                "auto_cleanup": False
            }
        elif target_scope == "project":
            promoted["retention_policy"] = {
                "type": "project",
                "auto_cleanup": True
            }
        
        # Clear project-specific fields if promoting to global
        if target_scope == "global":
            promoted.pop("project_id", None)
        
        # Update timestamp
        promoted["updated_at"] = utc_now_iso()
        
        return promoted, None
    
    def _check_conflict(
        self,
        memory_item: dict,
        target_scope: str,
        existing_memories: list[dict]
    ) -> Optional[str]:
        """
        Check if promoting would create a conflict.
        
        Conflict = same type + similar content in target scope
        
        Args:
            memory_item: MemoryItem to promote
            target_scope: Target scope
            existing_memories: Existing memories
        
        Returns:
            Conflicting memory ID or None
        """
        mem_type = memory_item.get("type")
        summary = memory_item.get("content", {}).get("summary", "").lower()
        
        for existing in existing_memories:
            # Skip self
            if existing.get("id") == memory_item.get("id"):
                continue
            
            # Check if in target scope and same type
            if existing.get("scope") != target_scope:
                continue
            
            if existing.get("type") != mem_type:
                continue
            
            # Check content similarity (simple word overlap)
            existing_summary = existing.get("content", {}).get("summary", "").lower()
            
            # Simple similarity: check if >50% words overlap
            words1 = set(summary.split())
            words2 = set(existing_summary.split())
            
            if not words1 or not words2:
                continue
            
            overlap = len(words1 & words2)
            min_len = min(len(words1), len(words2))
            
            if min_len > 0 and overlap / min_len > 0.5:
                return existing.get("id")
        
        return None
    
    def get_promotion_stats(self, memories: list[dict]) -> dict:
        """
        Get promotion statistics for a set of memories.
        
        Args:
            memories: List of MemoryItem dicts
        
        Returns:
            Stats dict with eligible counts
        """
        stats = {
            "total": len(memories),
            "eligible_for_promotion": 0,
            "by_target_scope": {
                "project": 0,
                "global": 0
            },
            "blocked_by_age": 0,
            "blocked_by_uses": 0
        }
        
        for mem in memories:
            eligible, target_scope, reason = self.check_promotion(mem)
            
            if eligible:
                stats["eligible_for_promotion"] += 1
                if target_scope:
                    stats["by_target_scope"][target_scope] += 1
            else:
                if "Not old enough" in reason:
                    stats["blocked_by_age"] += 1
                elif reason == "":
                    stats["blocked_by_uses"] += 1
        
        return stats
