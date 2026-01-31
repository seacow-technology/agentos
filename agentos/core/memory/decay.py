"""Memory decay engine for confidence degradation and cleanup decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from agentos.core.time import utc_now



class DecayEngine:
    """
    Engine for memory confidence decay and cleanup decisions.
    
    Implements exponential decay: confidence_new = confidence_old * (decay_rate ** days_since_last_used)
    """
    
    def __init__(
        self,
        decay_rate: float = 0.95,
        min_confidence_threshold: float = 0.2,
        temporary_days_threshold: int = 7,
        unused_days_threshold: int = 30,
    ):
        """
        Initialize decay engine.
        
        Args:
            decay_rate: Daily decay multiplier (0.95 = 5% decay per day)
            min_confidence_threshold: Confidence below which memories are eligible for cleanup
            temporary_days_threshold: Days after which temporary memories expire
            unused_days_threshold: Days unused after which low-confidence memories are cleaned
        """
        self.decay_rate = decay_rate
        self.min_confidence_threshold = min_confidence_threshold
        self.temporary_days_threshold = temporary_days_threshold
        self.unused_days_threshold = unused_days_threshold
    
    def decay_confidence(
        self,
        current_confidence: float,
        last_used_at: str | datetime,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Calculate decayed confidence based on time since last use.
        
        Formula: confidence_new = confidence_old * (decay_rate ** days_since_last_used)
        
        Args:
            current_confidence: Current confidence score (0.0-1.0)
            last_used_at: ISO8601 timestamp or datetime of last use
            now: Current time (defaults to now)
        
        Returns:
            Decayed confidence score (clamped to 0.0-1.0)
        """
        if now is None:
            now = utc_now()
        
        # Parse last_used_at if string
        if isinstance(last_used_at, str):
            last_used_at = datetime.fromisoformat(last_used_at.replace('Z', '+00:00'))
        
        # Ensure timezone aware
        if last_used_at.tzinfo is None:
            last_used_at = last_used_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        
        # Calculate days since last used
        delta = now - last_used_at
        days_since_last_used = delta.total_seconds() / 86400  # seconds per day
        
        # Apply exponential decay
        decayed = current_confidence * (self.decay_rate ** days_since_last_used)
        
        # Clamp to valid range
        return max(0.0, min(1.0, decayed))
    
    def should_cleanup(
        self,
        memory_item: dict,
        now: Optional[datetime] = None,
    ) -> tuple[bool, str]:
        """
        Determine if a memory should be cleaned up.
        
        Cleanup rules:
        1. expires_at is past (and auto_cleanup=true)
        2. confidence < threshold AND unused for > unused_days_threshold
        3. retention_type='temporary' AND unused for > temporary_days_threshold
        
        Args:
            memory_item: MemoryItem dict
            now: Current time (defaults to now)
        
        Returns:
            (should_cleanup, reason)
        """
        if now is None:
            now = utc_now()
        
        # Extract fields
        retention_policy = memory_item.get("retention_policy", {})
        retention_type = retention_policy.get("type", "project")
        expires_at = retention_policy.get("expires_at")
        auto_cleanup = retention_policy.get("auto_cleanup", True)
        confidence = memory_item.get("confidence", 0.5)
        last_used_at = memory_item.get("last_used_at")
        
        # Rule 1: Explicit expiration
        if expires_at and auto_cleanup:
            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            
            if now >= expires_dt:
                return True, f"Expired at {expires_at}"
        
        # Calculate days since last used (if available)
        days_unused = None
        if last_used_at:
            last_used_dt = datetime.fromisoformat(last_used_at.replace('Z', '+00:00'))
            if last_used_dt.tzinfo is None:
                last_used_dt = last_used_dt.replace(tzinfo=timezone.utc)
            days_unused = (now - last_used_dt).total_seconds() / 86400
        
        # Rule 2: Low confidence + long unused
        if days_unused is not None and confidence < self.min_confidence_threshold:
            if days_unused > self.unused_days_threshold:
                return True, f"Low confidence ({confidence:.2f}) and unused for {int(days_unused)} days"
        
        # Rule 3: Temporary memory expired
        if retention_type == "temporary" and days_unused is not None:
            if days_unused > self.temporary_days_threshold:
                return True, f"Temporary memory unused for {int(days_unused)} days (>{self.temporary_days_threshold})"
        
        return False, ""
    
    def calculate_decay_batch(
        self,
        memory_items: list[dict],
        now: Optional[datetime] = None,
    ) -> list[tuple[str, float, float]]:
        """
        Calculate decay for a batch of memories.
        
        Args:
            memory_items: List of MemoryItem dicts
            now: Current time (defaults to now)
        
        Returns:
            List of (memory_id, old_confidence, new_confidence) tuples
        """
        if now is None:
            now = utc_now()
        
        results = []
        for item in memory_items:
            memory_id = item.get("id")
            old_confidence = item.get("confidence", 0.5)
            last_used_at = item.get("last_used_at")
            
            if not last_used_at:
                # No decay if never used (use created_at as fallback)
                last_used_at = item.get("created_at")
            
            if last_used_at:
                new_confidence = self.decay_confidence(old_confidence, last_used_at, now)
                if new_confidence != old_confidence:
                    results.append((memory_id, old_confidence, new_confidence))
        
        return results
    
    def get_cleanup_candidates(
        self,
        memory_items: list[dict],
        now: Optional[datetime] = None,
    ) -> list[tuple[str, str]]:
        """
        Get list of memories eligible for cleanup.
        
        Args:
            memory_items: List of MemoryItem dicts
            now: Current time (defaults to now)
        
        Returns:
            List of (memory_id, reason) tuples
        """
        if now is None:
            now = utc_now()
        
        candidates = []
        for item in memory_items:
            should_cleanup, reason = self.should_cleanup(item, now)
            if should_cleanup:
                candidates.append((item.get("id"), reason))
        
        return candidates
