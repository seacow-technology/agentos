"""Budget Recommender - Smart Budget Recommendations Based on Usage Patterns

P2-9: Budget 推荐系统（只"建议"，不"决定"）

This module provides non-intrusive budget recommendations based on historical usage patterns.
Recommendations are SUGGESTIONS ONLY - they NEVER auto-apply.

Key Principles:
- Recommendations based on STATISTICS ONLY (P95 usage + buffer)
- No semantic analysis or content-based recommendations
- User must explicitly confirm before applying
- Marked as "user_applied_recommendation" (NOT "system_adjusted")

Data Sources (Read-Only):
- context_snapshots: Historical token usage by component
- Truncation frequency from watermark states
- Model context window information

Algorithm:
- Recommendation = P95(historical_usage) * 1.2  # 20% conservative buffer
- Ensures total does not exceed 85% of model window
"""

import logging
import sqlite3
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from statistics import mean, median

from agentos.store import get_db
from agentos.providers.base import ModelInfo

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Usage statistics for budget recommendation"""
    sample_size: int

    # Window usage
    avg_window: float
    p95_window: int
    max_window: int

    # RAG usage
    avg_rag: float
    p95_rag: int
    max_rag: int

    # Memory usage
    avg_memory: float
    p95_memory: int
    max_memory: int

    # System usage
    avg_system: float
    p95_system: int
    max_system: int

    # Truncation metrics
    truncation_rate: float  # % of snapshots with critical watermark
    warning_rate: float     # % of snapshots with warning watermark

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "sample_size": self.sample_size,
            "window": {
                "avg": round(self.avg_window, 1),
                "p95": self.p95_window,
                "max": self.max_window
            },
            "rag": {
                "avg": round(self.avg_rag, 1),
                "p95": self.p95_rag,
                "max": self.max_rag
            },
            "memory": {
                "avg": round(self.avg_memory, 1),
                "p95": self.p95_memory,
                "max": self.max_memory
            },
            "system": {
                "avg": round(self.avg_system, 1),
                "p95": self.p95_system,
                "max": self.max_system
            },
            "truncation_rate": round(self.truncation_rate, 3),
            "warning_rate": round(self.warning_rate, 3)
        }


@dataclass
class BudgetRecommendation:
    """Budget recommendation with reasoning"""
    window_tokens: int
    rag_tokens: int
    memory_tokens: int
    system_tokens: int
    max_tokens: int

    # Reasoning
    based_on_samples: int
    confidence: str  # "high" (>30 samples), "medium" (10-30), "low" (<10)
    estimated_savings: float  # Percentage change from current
    truncation_reduction: float  # Expected reduction in truncation events

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "window_tokens": self.window_tokens,
            "rag_tokens": self.rag_tokens,
            "memory_tokens": self.memory_tokens,
            "system_tokens": self.system_tokens,
            "max_tokens": self.max_tokens,
            "metadata": {
                "source": "ai_recommended",
                "based_on_samples": self.based_on_samples,
                "confidence": self.confidence,
                "estimated_savings": round(self.estimated_savings, 2),
                "truncation_reduction": round(self.truncation_reduction, 2)
            }
        }


class BudgetRecommender:
    """Generate budget recommendations based on usage patterns

    Recommendations are:
    - Non-intrusive (must be manually requested)
    - Based on statistics only (no semantic analysis)
    - Conservative (P95 + 20% buffer)
    - User-confirmed before applying
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize budget recommender

        Args:
            db_path: Optional database path (defaults to store default)
        """
        self.db_path = db_path
        self.min_samples = 10  # Minimum samples needed for recommendation

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_usage_pattern(
        self,
        session_id: str,
        last_n: int = 30
    ) -> Optional[UsageStats]:
        """Analyze usage pattern from context snapshots

        Args:
            session_id: Session ID to analyze
            last_n: Number of recent snapshots to analyze

        Returns:
            UsageStats if sufficient data available, None otherwise
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Query recent snapshots
            cursor.execute("""
                SELECT
                    tokens_window,
                    tokens_rag,
                    tokens_memory,
                    tokens_system,
                    metadata
                FROM context_snapshots
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (session_id, last_n))

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < self.min_samples:
                logger.info(f"Insufficient data for recommendation: {len(rows)} samples (need {self.min_samples})")
                return None

            # Extract usage data
            window_usage = [row['tokens_window'] for row in rows]
            rag_usage = [row['tokens_rag'] for row in rows]
            memory_usage = [row['tokens_memory'] for row in rows]
            system_usage = [row['tokens_system'] for row in rows]

            # Parse metadata for watermark states
            import json
            truncation_count = 0
            warning_count = 0

            for row in rows:
                if row['metadata']:
                    metadata = json.loads(row['metadata'])
                    watermark = metadata.get('watermark', 'safe')
                    if watermark == 'critical':
                        truncation_count += 1
                    elif watermark == 'warning':
                        warning_count += 1

            # Calculate statistics
            stats = UsageStats(
                sample_size=len(rows),
                avg_window=mean(window_usage),
                p95_window=self._percentile(window_usage, 95),
                max_window=max(window_usage),
                avg_rag=mean(rag_usage),
                p95_rag=self._percentile(rag_usage, 95),
                max_rag=max(rag_usage),
                avg_memory=mean(memory_usage),
                p95_memory=self._percentile(memory_usage, 95),
                max_memory=max(memory_usage),
                avg_system=mean(system_usage),
                p95_system=self._percentile(system_usage, 95),
                max_system=max(system_usage),
                truncation_rate=truncation_count / len(rows),
                warning_rate=warning_count / len(rows)
            )

            logger.info(f"Analyzed {stats.sample_size} snapshots for session {session_id}")
            logger.debug(f"Truncation rate: {stats.truncation_rate:.1%}, Warning rate: {stats.warning_rate:.1%}")

            return stats

        except Exception as e:
            logger.error(f"Failed to analyze usage pattern: {e}", exc_info=True)
            return None

    def _percentile(self, data: List[int], percentile: int) -> int:
        """Calculate percentile of data

        Args:
            data: List of integers
            percentile: Percentile (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0

        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def recommend_budget(
        self,
        stats: UsageStats,
        current_budget: Dict[str, int],
        model_info: ModelInfo
    ) -> Optional[BudgetRecommendation]:
        """Generate budget recommendation based on statistics

        Algorithm:
        - Recommended value = P95(usage) * 1.2  # 20% conservative buffer
        - Ensure total <= 85% of model window
        - Calculate savings vs current budget

        Args:
            stats: Usage statistics
            current_budget: Current budget configuration
            model_info: Model information (for context window)

        Returns:
            BudgetRecommendation if improvement possible, None otherwise
        """
        try:
            # Step 1: Calculate recommended values (P95 + 20% buffer)
            recommended_window = int(stats.p95_window * 1.2)
            recommended_rag = int(stats.p95_rag * 1.2)
            recommended_memory = int(stats.p95_memory * 1.2)
            recommended_system = int(stats.p95_system * 1.2)

            # Step 2: Ensure minimum viable values
            recommended_window = max(recommended_window, 2000)
            recommended_rag = max(recommended_rag, 1000)
            recommended_memory = max(recommended_memory, 500)
            recommended_system = max(recommended_system, 500)

            # Step 3: Check against model window (85% limit)
            total_recommended = recommended_window + recommended_rag + recommended_memory + recommended_system
            max_allowed = int(model_info.context_window * 0.85) if model_info.context_window else 100000

            if total_recommended > max_allowed:
                logger.info(f"Recommended total ({total_recommended}) exceeds model limit ({max_allowed}), scaling down")
                # Scale proportionally
                scale_factor = max_allowed / total_recommended
                recommended_window = int(recommended_window * scale_factor)
                recommended_rag = int(recommended_rag * scale_factor)
                recommended_memory = int(recommended_memory * scale_factor)
                recommended_system = int(recommended_system * scale_factor)
                total_recommended = recommended_window + recommended_rag + recommended_memory + recommended_system

            # Step 4: Calculate savings vs current
            current_total = (
                current_budget.get('window_tokens', 0) +
                current_budget.get('rag_tokens', 0) +
                current_budget.get('memory_tokens', 0) +
                current_budget.get('system_tokens', 0)
            )

            savings_pct = ((current_total - total_recommended) / current_total * 100) if current_total > 0 else 0

            # Step 5: Estimate truncation reduction
            # If currently truncating frequently, expect significant reduction
            truncation_reduction = stats.truncation_rate * 0.8 if stats.truncation_rate > 0.1 else 0

            # Step 6: Determine confidence level
            confidence = "high" if stats.sample_size >= 30 else "medium" if stats.sample_size >= 20 else "low"

            recommendation = BudgetRecommendation(
                window_tokens=recommended_window,
                rag_tokens=recommended_rag,
                memory_tokens=recommended_memory,
                system_tokens=recommended_system,
                max_tokens=total_recommended,
                based_on_samples=stats.sample_size,
                confidence=confidence,
                estimated_savings=savings_pct,
                truncation_reduction=truncation_reduction
            )

            logger.info(f"Generated recommendation: {total_recommended} tokens total, "
                       f"{savings_pct:+.1f}% change from current")

            return recommendation

        except Exception as e:
            logger.error(f"Failed to generate recommendation: {e}", exc_info=True)
            return None

    def calculate_savings(
        self,
        current: Dict[str, int],
        recommended: Dict[str, int]
    ) -> float:
        """Calculate estimated savings percentage

        Args:
            current: Current budget configuration
            recommended: Recommended budget configuration

        Returns:
            Savings percentage (negative = increase, positive = decrease)
        """
        current_total = sum(current.values())
        recommended_total = sum(recommended.values())

        if current_total == 0:
            return 0.0

        return ((current_total - recommended_total) / current_total) * 100

    def get_recommendation(
        self,
        session_id: str,
        current_budget: Dict[str, int],
        model_info: ModelInfo,
        last_n: int = 30
    ) -> Dict[str, Any]:
        """Get budget recommendation for session (main entry point)

        Args:
            session_id: Session ID
            current_budget: Current budget configuration
            model_info: Model information
            last_n: Number of recent snapshots to analyze

        Returns:
            Recommendation result dictionary
        """
        # Analyze usage pattern
        stats = self.analyze_usage_pattern(session_id, last_n)

        if not stats:
            return {
                "available": False,
                "reason": "insufficient_data",
                "hint": f"At least {self.min_samples} conversations needed for recommendation. "
                       f"Keep using the system and recommendations will become available.",
                "min_samples": self.min_samples
            }

        # Generate recommendation
        recommendation = self.recommend_budget(stats, current_budget, model_info)

        if not recommendation:
            return {
                "available": False,
                "reason": "recommendation_failed",
                "hint": "Unable to generate recommendation. Please check logs."
            }

        # Check if recommendation is significantly different from current
        savings = abs(recommendation.estimated_savings)
        if savings < 5:  # Less than 5% difference
            return {
                "available": False,
                "reason": "no_improvement",
                "hint": "Your current budget is already well-optimized based on usage patterns.",
                "stats": stats.to_dict()
            }

        return {
            "available": True,
            "current": current_budget,
            "recommended": recommendation.to_dict(),
            "stats": stats.to_dict(),
            "message": self._generate_recommendation_message(stats, recommendation)
        }

    def _generate_recommendation_message(
        self,
        stats: UsageStats,
        recommendation: BudgetRecommendation
    ) -> str:
        """Generate human-readable recommendation message

        Args:
            stats: Usage statistics
            recommendation: Budget recommendation

        Returns:
            Recommendation message
        """
        messages = []

        # Overall assessment
        if recommendation.estimated_savings > 10:
            messages.append(f"Based on your last {stats.sample_size} conversations, you can reduce budget by ~{recommendation.estimated_savings:.0f}% without impacting quality.")
        elif recommendation.estimated_savings < -10:
            messages.append(f"Based on your last {stats.sample_size} conversations, increasing budget by ~{abs(recommendation.estimated_savings):.0f}% may reduce truncation.")
        else:
            messages.append(f"Based on your last {stats.sample_size} conversations, minor budget adjustments are recommended.")

        # Truncation warning
        if stats.truncation_rate > 0.2:
            messages.append(f"⚠️ High truncation rate detected ({stats.truncation_rate:.0%}). Recommended budget may reduce this by {recommendation.truncation_reduction:.0%}.")

        # Confidence level
        if recommendation.confidence == "low":
            messages.append("ℹ️ Confidence is low due to limited data. More usage will improve recommendations.")

        return " ".join(messages)
