"""KB evaluation utilities for measuring search quality."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agentos.core.project_kb.service import ProjectKBService


@dataclass
class EvalQuery:
    """Evaluation query with expected results."""
    query: str
    expected_chunk_ids: list[str]
    expected_paths: Optional[list[str]] = None


@dataclass
class EvalMetrics:
    """Evaluation metrics for KB search quality."""
    recall_at_k: dict[int, float]
    mrr: float  # Mean Reciprocal Rank
    hit_rate: float
    total_queries: int
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "hit_rate": self.hit_rate,
            "total_queries": self.total_queries,
        }
    
    def summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Total Queries: {self.total_queries}",
            f"Hit Rate: {self.hit_rate:.2%}",
            f"MRR: {self.mrr:.3f}",
            "Recall@K:",
        ]
        for k, recall in sorted(self.recall_at_k.items()):
            lines.append(f"  @{k}: {recall:.2%}")
        return "\n".join(lines)


class KBEvaluator:
    """Evaluator for KB search quality."""
    
    def __init__(self, kb_service: ProjectKBService):
        """Initialize evaluator.
        
        Args:
            kb_service: ProjectKBService instance
        """
        self.kb_service = kb_service
    
    def evaluate(
        self, 
        queries: list[EvalQuery],
        k_values: Optional[list[int]] = None,
        use_rerank: Optional[bool] = None,
    ) -> EvalMetrics:
        """Evaluate KB search quality.
        
        Args:
            queries: List of evaluation queries
            k_values: List of k values for recall@k (default: [1, 3, 5, 10])
            use_rerank: Whether to use vector rerank
            
        Returns:
            EvalMetrics with computed metrics
        """
        if k_values is None:
            k_values = [1, 3, 5, 10]
        
        recall_at_k = {k: [] for k in k_values}
        reciprocal_ranks = []
        hits = 0
        
        for eval_query in queries:
            # Search
            results = self.kb_service.search(
                query=eval_query.query,
                top_k=max(k_values),
                explain=False,
                use_rerank=use_rerank,
            )
            
            # Get result chunk IDs
            result_ids = [r.chunk_id for r in results]
            
            # Compute metrics for this query
            expected = set(eval_query.expected_chunk_ids)
            
            # Hit rate (did we find at least one relevant result?)
            if any(rid in expected for rid in result_ids):
                hits += 1
            
            # Recall@K
            for k in k_values:
                top_k_ids = set(result_ids[:k])
                relevant_in_top_k = len(expected & top_k_ids)
                recall = relevant_in_top_k / len(expected) if expected else 0.0
                recall_at_k[k].append(recall)
            
            # MRR (position of first relevant result)
            first_relevant_rank = None
            for idx, rid in enumerate(result_ids, start=1):
                if rid in expected:
                    first_relevant_rank = idx
                    break
            
            if first_relevant_rank:
                reciprocal_ranks.append(1.0 / first_relevant_rank)
            else:
                reciprocal_ranks.append(0.0)
        
        # Aggregate metrics
        total_queries = len(queries)
        avg_recall_at_k = {
            k: sum(recalls) / total_queries 
            for k, recalls in recall_at_k.items()
        }
        mrr = sum(reciprocal_ranks) / total_queries if reciprocal_ranks else 0.0
        hit_rate = hits / total_queries if total_queries > 0 else 0.0
        
        return EvalMetrics(
            recall_at_k=avg_recall_at_k,
            mrr=mrr,
            hit_rate=hit_rate,
            total_queries=total_queries,
        )
    
    @staticmethod
    def load_queries_from_file(path: Path | str) -> list[EvalQuery]:
        """Load evaluation queries from JSONL file.
        
        File format (one JSON object per line):
        {
            "query": "JWT authentication",
            "expected_chunk_ids": ["chunk_abc123", "chunk_def456"],
            "expected_paths": ["docs/auth.md", "docs/jwt.md"]  // optional
        }
        
        Args:
            path: Path to JSONL file
            
        Returns:
            List of EvalQuery objects
        """
        path = Path(path)
        queries = []
        
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    obj = json.loads(line)
                    query = EvalQuery(
                        query=obj["query"],
                        expected_chunk_ids=obj["expected_chunk_ids"],
                        expected_paths=obj.get("expected_paths"),
                    )
                    queries.append(query)
                except (json.JSONDecodeError, KeyError) as e:
                    raise ValueError(f"Invalid query at line {line_num}: {e}")
        
        return queries
