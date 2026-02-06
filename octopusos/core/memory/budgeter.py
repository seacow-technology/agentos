"""Context budget manager for memory trimming and token control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextBudget:
    """Budget constraints for context building."""
    
    max_tokens: int = 4000
    max_memories: int = 100
    
    def __post_init__(self):
        """Validate budget parameters."""
        if self.max_tokens < 100:
            raise ValueError("max_tokens must be at least 100")
        if self.max_memories < 1:
            raise ValueError("max_memories must be at least 1")


class ContextBudgeter:
    """
    Manages context size budgets and smart trimming.
    
    Prioritization strategy:
    1. Scope priority: task > agent > project > repo > global
    2. Confidence score (higher is better)
    3. Recency (last_used_at or created_at)
    """
    
    # Scope priority weights (higher = more important)
    SCOPE_WEIGHTS = {
        "task": 5,
        "agent": 4,
        "project": 3,
        "repo": 2,
        "global": 1
    }
    
    def __init__(self, budget: Optional[ContextBudget] = None):
        """
        Initialize budgeter.
        
        Args:
            budget: Budget constraints (defaults to ContextBudget())
        """
        self.budget = budget or ContextBudget()
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Simple heuristic: length * 1.3 (assumes ~0.77 chars/token average)
        
        Args:
            text: Text to estimate
        
        Returns:
            Estimated token count
        """
        return int(len(text) * 1.3)
    
    def calculate_priority_score(self, memory_item: dict) -> float:
        """
        Calculate priority score for a memory item.
        
        Score = scope_weight * confidence * recency_factor
        
        Args:
            memory_item: MemoryItem dict
        
        Returns:
            Priority score (higher = more important)
        """
        # Scope weight
        scope = memory_item.get("scope", "project")
        scope_weight = self.SCOPE_WEIGHTS.get(scope, 1)
        
        # Confidence
        confidence = memory_item.get("confidence", 0.5)
        
        # Recency factor (simplified: use_count as proxy)
        use_count = memory_item.get("use_count", 0)
        recency_factor = 1.0 + (use_count * 0.1)  # +10% per use
        
        return scope_weight * confidence * recency_factor
    
    def trim_context(
        self,
        memories: list[dict],
        query_context: Optional[dict] = None
    ) -> tuple[list[dict], dict]:
        """
        Trim memories to fit within budget.
        
        Args:
            memories: List of MemoryItem dicts
            query_context: Optional context (unused for now, for future relevance scoring)
        
        Returns:
            (trimmed_memories, stats)
        """
        if not memories:
            return [], {"total_memories": 0, "total_tokens": 0, "trimmed": False}
        
        # Calculate priority scores
        scored_memories = []
        for mem in memories:
            score = self.calculate_priority_score(mem)
            tokens = self._estimate_memory_tokens(mem)
            scored_memories.append((score, tokens, mem))
        
        # Sort by priority (descending)
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # Trim to budget
        selected = []
        total_tokens = 0
        total_memories = 0
        
        for score, tokens, mem in scored_memories:
            # Check if adding this memory exceeds budget
            if total_memories >= self.budget.max_memories:
                break
            
            if total_tokens + tokens > self.budget.max_tokens:
                # Try to fit if there's significant room
                if total_tokens < self.budget.max_tokens * 0.9:
                    # Still some budget left, but this memory too large
                    continue
                else:
                    # Budget nearly full, stop
                    break
            
            selected.append(mem)
            total_tokens += tokens
            total_memories += 1
        
        # Stats
        trimmed = len(selected) < len(memories)
        stats = {
            "total_memories": total_memories,
            "total_tokens": total_tokens,
            "trimmed": trimmed,
            "original_count": len(memories),
            "removed_count": len(memories) - len(selected),
            "budget_utilization": {
                "memories": total_memories / self.budget.max_memories,
                "tokens": total_tokens / self.budget.max_tokens
            }
        }
        
        return selected, stats
    
    def _estimate_memory_tokens(self, memory_item: dict) -> int:
        """
        Estimate total tokens for a memory item.
        
        Includes: summary + details + examples
        
        Args:
            memory_item: MemoryItem dict
        
        Returns:
            Estimated token count
        """
        content = memory_item.get("content", {})
        
        # Summary (always present)
        summary = content.get("summary", "")
        tokens = self.estimate_tokens(summary)
        
        # Details (optional)
        details = content.get("details", "")
        if details:
            tokens += self.estimate_tokens(details)
        
        # Examples (optional)
        examples = content.get("examples", [])
        for example in examples:
            tokens += self.estimate_tokens(str(example))
        
        # Metadata overhead (~50 tokens)
        tokens += 50
        
        return tokens
    
    def group_by_scope(self, memories: list[dict]) -> dict[str, list[dict]]:
        """
        Group memories by scope.
        
        Args:
            memories: List of MemoryItem dicts
        
        Returns:
            Dict mapping scope -> list of memories
        """
        grouped = {}
        for mem in memories:
            scope = mem.get("scope", "project")
            if scope not in grouped:
                grouped[scope] = []
            grouped[scope].append(mem)
        
        return grouped
    
    def get_budget_breakdown(self, memories: list[dict]) -> dict:
        """
        Get detailed budget breakdown by scope.
        
        Args:
            memories: List of MemoryItem dicts
        
        Returns:
            Budget breakdown dict
        """
        grouped = self.group_by_scope(memories)
        
        breakdown = {}
        total_tokens = 0
        total_memories = 0
        
        for scope in ["task", "agent", "project", "repo", "global"]:
            scope_memories = grouped.get(scope, [])
            scope_tokens = sum(self._estimate_memory_tokens(m) for m in scope_memories)
            
            breakdown[scope] = {
                "count": len(scope_memories),
                "tokens": scope_tokens,
                "percentage": 0.0  # Will calculate after total
            }
            
            total_tokens += scope_tokens
            total_memories += len(scope_memories)
        
        # Calculate percentages
        for scope in breakdown:
            if total_tokens > 0:
                breakdown[scope]["percentage"] = breakdown[scope]["tokens"] / total_tokens * 100
        
        breakdown["total"] = {
            "memories": total_memories,
            "tokens": total_tokens
        }
        
        return breakdown
