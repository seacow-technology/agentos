"""Memory compactor for merging similar memories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from agentos.core.memory import MemoryService


class SummaryStrategy(ABC):
    """
    Abstract strategy for merging memory summaries.

    Implementations can use different approaches:
    - SimpleSummaryStrategy: Concatenation-based (no LLM)
    - LLMSummaryStrategy: LLM-based generation (optional)
    """

    @abstractmethod
    def merge(self, summaries: list[str]) -> str:
        """
        Merge multiple summaries into one.

        Args:
            summaries: List of summary strings to merge

        Returns:
            Merged summary string
        """
        pass


class SimpleSummaryStrategy(SummaryStrategy):
    """
    Simple concatenation-based summary strategy (no LLM).

    This is the default strategy that works without any external dependencies.
    """

    def merge(self, summaries: list[str]) -> str:
        """
        Merge summaries using simple concatenation.

        Args:
            summaries: List of summary strings

        Returns:
            Merged summary (deduplicated and joined)
        """
        if len(summaries) == 1:
            return summaries[0]

        # Dedupe and join
        unique_summaries = []
        seen = set()

        for summary in summaries:
            if summary.lower() not in seen:
                unique_summaries.append(summary)
                seen.add(summary.lower())

        return " | ".join(unique_summaries)


class LLMSummaryStrategy(SummaryStrategy):
    """
    LLM-based summary strategy (optional, for future use).

    This strategy can use an LLM to generate higher-quality merged summaries.
    It's a placeholder for future implementation.
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize LLM summary strategy.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3")
            api_key: API key for the LLM provider

        Note:
            If model or api_key is not provided, falls back to simple strategy.
        """
        self.model = model
        self.api_key = api_key
        self._fallback = SimpleSummaryStrategy()

    def merge(self, summaries: list[str]) -> str:
        """
        Merge summaries using LLM (or fallback to simple merge).

        Args:
            summaries: List of summary strings

        Returns:
            LLM-generated merged summary (or fallback)
        """
        # TODO: Implement actual LLM call when enabled
        # For now, use fallback
        if not self.model or not self.api_key:
            return self._fallback.merge(summaries)

        # Placeholder for future LLM integration
        # Example:
        # prompt = f"Merge these summaries into one: {summaries}"
        # response = llm_client.generate(prompt)
        # return response

        # Fall back for now
        return self._fallback.merge(summaries)


@dataclass
class CompactionCluster:
    """A cluster of similar memories."""
    memories: list[dict]
    similarity_score: float
    summary: Optional[str] = None


class MemoryCompactor:
    """Compactor for merging similar memories into summaries."""

    def __init__(
        self,
        memory_service: MemoryService,
        similarity_threshold: float = 0.7,
        summary_strategy: Optional[SummaryStrategy] = None,
    ):
        """Initialize compactor.

        Args:
            memory_service: MemoryService instance
            similarity_threshold: Minimum similarity for clustering (0.0-1.0)
            summary_strategy: Strategy for merging summaries (defaults to SimpleSummaryStrategy)
        """
        self.memory_service = memory_service
        self.similarity_threshold = similarity_threshold
        self.summary_strategy = summary_strategy or SimpleSummaryStrategy()
    
    def compact(
        self,
        scope: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Compact memories in the specified scope.
        
        Args:
            scope: Memory scope to compact
            project_id: Project ID (if scope requires it)
            task_id: Task ID (if scope requires it)
            dry_run: If True, don't actually merge (just show what would happen)
            
        Returns:
            Compaction statistics
        """
        # Get memories for the scope
        memories = self.memory_service.list(
            scope=scope,
            project_id=project_id,
            limit=1000  # Process up to 1000 memories
        )
        
        if not memories:
            return {
                "total_memories": 0,
                "clusters_found": 0,
                "memories_merged": 0,
                "summaries_created": 0,
            }
        
        # Cluster similar memories
        clusters = self._cluster_memories(memories)
        
        # Filter clusters (only keep those with > 1 memory)
        significant_clusters = [c for c in clusters if len(c.memories) > 1]
        
        if dry_run:
            return {
                "total_memories": len(memories),
                "clusters_found": len(significant_clusters),
                "memories_per_cluster": [len(c.memories) for c in significant_clusters],
                "dry_run": True,
            }
        
        # Merge clusters
        summaries_created = 0
        memories_merged = 0
        
        for cluster in significant_clusters:
            summary_memory = self._create_summary(cluster, scope, project_id)

            # Add summary as new memory
            summary_id = self.memory_service.upsert("system", summary_memory)
            summaries_created += 1

            # Delete original memories
            for mem in cluster.memories:
                self.memory_service.delete("system", mem["id"])
                memories_merged += 1
        
        return {
            "total_memories": len(memories),
            "clusters_found": len(significant_clusters),
            "memories_merged": memories_merged,
            "summaries_created": summaries_created,
        }
    
    def _cluster_memories(self, memories: list[dict]) -> list[CompactionCluster]:
        """Cluster similar memories using Jaccard similarity.
        
        Args:
            memories: List of memory items
            
        Returns:
            List of clusters
        """
        from agentos.core.memory.deduplicator import MemoryDeduplicator
        
        deduplicator = MemoryDeduplicator(None)  # We only need similarity calculation
        clusters = []
        processed = set()
        
        for i, mem1 in enumerate(memories):
            if mem1["id"] in processed:
                continue
            
            # Start a new cluster
            cluster_memories = [mem1]
            processed.add(mem1["id"])
            
            # Find similar memories
            for j, mem2 in enumerate(memories):
                if i == j or mem2["id"] in processed:
                    continue
                
                # Calculate similarity
                similarity = deduplicator._jaccard_similarity(
                    mem1["content"]["summary"],
                    mem2["content"]["summary"]
                )
                
                if similarity >= self.similarity_threshold:
                    cluster_memories.append(mem2)
                    processed.add(mem2["id"])
            
            # Create cluster
            if cluster_memories:
                avg_similarity = self.similarity_threshold  # Simplified
                clusters.append(
                    CompactionCluster(
                        memories=cluster_memories,
                        similarity_score=avg_similarity
                    )
                )
        
        return clusters
    
    def _create_summary(
        self,
        cluster: CompactionCluster,
        scope: str,
        project_id: str | None
    ) -> dict:
        """Create a summary memory from a cluster.
        
        Args:
            cluster: CompactionCluster to summarize
            scope: Memory scope
            project_id: Project ID
            
        Returns:
            Memory item dict
        """
        # Collect all summaries
        summaries = [mem["content"]["summary"] for mem in cluster.memories]

        # Use configured summary strategy
        combined_summary = self.summary_strategy.merge(summaries)
        
        # Collect all tags
        all_tags = set()
        for mem in cluster.memories:
            if mem.get("tags"):
                all_tags.update(mem["tags"])
        
        # Collect all sources
        all_sources = []
        for mem in cluster.memories:
            if mem.get("sources"):
                all_sources.extend(mem["sources"])
        
        # Create summary memory
        # Use type from first memory
        mem_type = cluster.memories[0].get("type", "convention")
        
        summary_memory = {
            "schema_version": "1.0.0",
            "scope": scope,
            "type": mem_type,
            "content": {
                "summary": combined_summary,
                "details": f"Merged from {len(cluster.memories)} memories",
            },
            "tags": list(all_tags),
            "sources": list(set(all_sources)),  # Dedupe sources
            "confidence": 0.8,  # Slightly lower confidence for merged memories
        }
        
        if project_id:
            summary_memory["project_id"] = project_id
        
        return summary_memory
    
    def _simple_merge(self, summaries: list[str]) -> str:
        """
        ⚠️  DEPRECATED: Use summary_strategy.merge() instead.

        Kept for backward compatibility.
        """
        return SimpleSummaryStrategy().merge(summaries)

    def _llm_merge(self, summaries: list[str]) -> str:
        """
        ⚠️  DEPRECATED: Use LLMSummaryStrategy instead.

        Kept for backward compatibility.
        """
        return LLMSummaryStrategy().merge(summaries)
