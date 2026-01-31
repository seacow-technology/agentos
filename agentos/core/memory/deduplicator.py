"""Memory deduplicator for finding and merging duplicate memories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from agentos.core.time import utc_now_iso



class MemoryDeduplicator:
    """
    Deduplicator for finding and merging similar memories.
    
    Uses Levenshtein distance and content similarity for matching.
    """
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize deduplicator.
        
        Args:
            similarity_threshold: Threshold for considering memories duplicate (0.0-1.0)
        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        
        self.similarity_threshold = similarity_threshold
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts.
        
        Uses simplified Jaccard similarity (word overlap).
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity: intersection / union
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_duplicates(
        self,
        memory_item: dict,
        existing_memories: list[dict],
        check_same_type: bool = True,
        check_same_scope: bool = False
    ) -> list[dict]:
        """
        Find duplicate memories.
        
        Args:
            memory_item: Memory to check
            existing_memories: List of existing memories
            check_same_type: Only consider duplicates of same type
            check_same_scope: Only consider duplicates of same scope
        
        Returns:
            List of duplicate MemoryItem dicts
        """
        duplicates = []
        
        mem_summary = memory_item.get("content", {}).get("summary", "")
        mem_type = memory_item.get("type")
        mem_scope = memory_item.get("scope")
        mem_id = memory_item.get("id")
        
        for existing in existing_memories:
            # Skip self
            if existing.get("id") == mem_id:
                continue
            
            # Check type constraint
            if check_same_type and existing.get("type") != mem_type:
                continue
            
            # Check scope constraint
            if check_same_scope and existing.get("scope") != mem_scope:
                continue
            
            # Calculate similarity
            existing_summary = existing.get("content", {}).get("summary", "")
            similarity = self.calculate_similarity(mem_summary, existing_summary)
            
            if similarity >= self.similarity_threshold:
                duplicates.append(existing)
        
        return duplicates
    
    def merge(
        self,
        memories: list[dict],
        merge_strategy: str = "highest_confidence"
    ) -> dict:
        """
        Merge duplicate memories into one.
        
        Strategies:
        - highest_confidence: Keep memory with highest confidence
        - most_used: Keep memory with highest use_count
        - newest: Keep newest memory
        
        Args:
            memories: List of duplicate MemoryItem dicts to merge
            merge_strategy: Strategy for choosing primary memory
        
        Returns:
            Merged MemoryItem dict
        """
        if not memories:
            raise ValueError("Cannot merge empty list")
        
        if len(memories) == 1:
            return memories[0]
        
        # Select primary memory based on strategy
        if merge_strategy == "highest_confidence":
            primary = max(memories, key=lambda m: m.get("confidence", 0.0))
        elif merge_strategy == "most_used":
            primary = max(memories, key=lambda m: m.get("use_count", 0))
        elif merge_strategy == "newest":
            primary = max(
                memories,
                key=lambda m: m.get("created_at", "1970-01-01T00:00:00Z")
            )
        else:
            # Default: highest confidence
            primary = max(memories, key=lambda m: m.get("confidence", 0.0))
        
        # Create merged copy
        merged = primary.copy()
        
        # Merge sources from all memories
        all_sources = set()
        for mem in memories:
            sources = mem.get("sources", [])
            if sources:
                all_sources.update(sources)
        
        if all_sources:
            merged["sources"] = list(all_sources)
        
        # Merge tags
        all_tags = set()
        for mem in memories:
            tags = mem.get("tags", [])
            if tags:
                all_tags.update(tags)
        
        if all_tags:
            merged["tags"] = list(all_tags)
        
        # Sum use_counts
        total_use_count = sum(m.get("use_count", 0) for m in memories)
        merged["use_count"] = total_use_count
        
        # Take highest confidence
        max_confidence = max(m.get("confidence", 0.0) for m in memories)
        merged["confidence"] = max_confidence
        
        # Use oldest created_at
        oldest_created = min(
            (m.get("created_at", "9999-12-31T23:59:59Z") for m in memories)
        )
        merged["created_at"] = oldest_created
        
        # Use newest last_used_at
        if any(m.get("last_used_at") for m in memories):
            newest_used = max(
                (m.get("last_used_at", "1970-01-01T00:00:00Z") for m in memories)
            )
            merged["last_used_at"] = newest_used
        
        # Update timestamp
        merged["updated_at"] = utc_now_iso()
        
        # Add metadata about merge
        if "metadata" not in merged:
            merged["metadata"] = {}
        
        merged["metadata"]["merged_from"] = [m.get("id") for m in memories if m.get("id") != merged.get("id")]
        merged["metadata"]["merge_timestamp"] = merged["updated_at"]
        
        return merged
    
    def get_duplicate_groups(
        self,
        memories: list[dict],
        check_same_type: bool = True
    ) -> list[list[dict]]:
        """
        Find all groups of duplicate memories.
        
        Args:
            memories: List of MemoryItem dicts
            check_same_type: Only consider duplicates of same type
        
        Returns:
            List of duplicate groups (each group is a list of memories)
        """
        processed = set()
        groups = []
        
        for i, mem in enumerate(memories):
            mem_id = mem.get("id")
            
            # Skip if already processed
            if mem_id in processed:
                continue
            
            # Find duplicates for this memory
            duplicates = self.find_duplicates(
                mem,
                memories[i+1:],  # Only check remaining memories
                check_same_type=check_same_type
            )
            
            if duplicates:
                # Create group
                group = [mem] + duplicates
                groups.append(group)
                
                # Mark all as processed
                for dup in group:
                    processed.add(dup.get("id"))
        
        return groups
    
    def get_dedupe_stats(self, memories: list[dict]) -> dict:
        """
        Get deduplication statistics.
        
        Args:
            memories: List of MemoryItem dicts
        
        Returns:
            Stats dict
        """
        groups = self.get_duplicate_groups(memories)
        
        total_duplicates = sum(len(group) - 1 for group in groups)  # -1 because one is kept
        
        stats = {
            "total_memories": len(memories),
            "duplicate_groups": len(groups),
            "total_duplicates": total_duplicates,
            "reduction_percentage": (total_duplicates / len(memories) * 100) if memories else 0.0,
            "unique_after_dedupe": len(memories) - total_duplicates
        }
        
        return stats
