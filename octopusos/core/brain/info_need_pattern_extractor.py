"""
InfoNeed Pattern Extractor - Extract patterns from MemoryOS judgments

This module extracts long-term decision patterns from short-term MemoryOS
judgment history and stores them in BrainOS knowledge graph.

Key Operations:
1. Query recent judgments from MemoryOS
2. Extract question features (non-semantic)
3. Cluster judgments by feature similarity
4. Calculate pattern statistics
5. Generate pattern nodes for BrainOS
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from agentos.core.time import utc_now
from agentos.core.brain.info_need_pattern_models import (
    InfoNeedPatternNode,
    PatternType,
)
from agentos.core.memory.schema import InfoNeedJudgment
from agentos.core.memory.info_need_writer import InfoNeedMemoryWriter

logger = logging.getLogger(__name__)


class QuestionFeatureExtractor:
    """
    Extract non-semantic features from question text.

    Uses rule-based and statistical methods only - NO LLM or embeddings.
    """

    # Feature keyword sets
    TIME_KEYWORDS = [
        "today", "latest", "current", "now", "recently", "recent",
        "2025", "2026", "2027", "this year", "last year",
        "新", "最新", "现在", "当前", "今天", "最近"
    ]

    POLICY_KEYWORDS = [
        "policy", "regulation", "law", "official", "standard",
        "government", "announcement", "compliance", "guideline",
        "政策", "法规", "官方", "公告", "规定", "标准"
    ]

    TECH_KEYWORDS = [
        "api", "function", "class", "method", "library", "framework",
        "code", "program", "software", "file", "directory",
        "函数", "类", "方法", "代码", "文件"
    ]

    STATE_KEYWORDS = [
        "status", "running", "active", "config", "setting",
        "time", "phase", "session", "mode",
        "状态", "运行", "配置", "设置", "当前"
    ]

    OPINION_KEYWORDS = [
        "recommend", "suggest", "should", "better", "prefer",
        "think", "believe", "opinion",
        "推荐", "建议", "应该", "最好", "认为"
    ]

    # Question type patterns
    INTERROGATIVE_WORDS = [
        "what", "when", "where", "who", "why", "how", "which",
        "什么", "何时", "哪里", "谁", "为什么", "如何", "哪个"
    ]

    def extract_features(self, question: str) -> Dict[str, Any]:
        """
        Extract features from question text.

        Args:
            question: Question text

        Returns:
            Dictionary of extracted features
        """
        features = {}

        # Basic statistics
        features["length"] = len(question)
        features["word_count"] = len(question.split())

        # Normalize for matching
        question_lower = question.lower()

        # Keyword matching
        features["has_time_keywords"] = self._has_keywords(question_lower, self.TIME_KEYWORDS)
        features["has_policy_keywords"] = self._has_keywords(question_lower, self.POLICY_KEYWORDS)
        features["has_tech_keywords"] = self._has_keywords(question_lower, self.TECH_KEYWORDS)
        features["has_state_keywords"] = self._has_keywords(question_lower, self.STATE_KEYWORDS)
        features["has_opinion_keywords"] = self._has_keywords(question_lower, self.OPINION_KEYWORDS)

        # Matched keywords (for pattern specificity)
        features["time_keywords"] = self._find_keywords(question_lower, self.TIME_KEYWORDS)
        features["policy_keywords"] = self._find_keywords(question_lower, self.POLICY_KEYWORDS)
        features["tech_keywords"] = self._find_keywords(question_lower, self.TECH_KEYWORDS)
        features["state_keywords"] = self._find_keywords(question_lower, self.STATE_KEYWORDS)
        features["opinion_keywords"] = self._find_keywords(question_lower, self.OPINION_KEYWORDS)

        # Question type
        features["interrogative_word"] = self._find_interrogative(question_lower)
        features["is_question"] = "?" in question or features["interrogative_word"] is not None

        # Structural features
        features["has_code_patterns"] = self._has_code_patterns(question)

        # Generate feature signature (for clustering)
        features["signature"] = self._generate_signature(features)

        return features

    def _has_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any keywords."""
        return any(keyword.lower() in text for keyword in keywords)

    def _find_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Find all matching keywords in text."""
        return [kw for kw in keywords if kw.lower() in text]

    def _find_interrogative(self, text: str) -> Optional[str]:
        """Find interrogative word in text."""
        for word in self.INTERROGATIVE_WORDS:
            if word.lower() in text.split()[:5]:  # Check first 5 words
                return word
        return None

    def _has_code_patterns(self, text: str) -> bool:
        """Check for code-related patterns."""
        patterns = [
            r'\bclass\s+\w+',
            r'\bfunction\s+\w+',
            r'\bmethod\s+\w+',
            r'\.(py|js|java|go|rs)\b',
            r'\bAPI\b',
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _generate_signature(self, features: Dict[str, Any]) -> str:
        """
        Generate feature signature for clustering.

        Signature is a string encoding the feature vector.
        """
        parts = []

        # Binary features
        if features["has_time_keywords"]:
            parts.append("TIME")
        if features["has_policy_keywords"]:
            parts.append("POLICY")
        if features["has_tech_keywords"]:
            parts.append("TECH")
        if features["has_state_keywords"]:
            parts.append("STATE")
        if features["has_opinion_keywords"]:
            parts.append("OPINION")
        if features["has_code_patterns"]:
            parts.append("CODE")

        # Question type
        if features["interrogative_word"]:
            parts.append(f"Q:{features['interrogative_word'].upper()}")

        # Length category
        length = features["length"]
        if length < 20:
            parts.append("SHORT")
        elif length < 100:
            parts.append("MEDIUM")
        else:
            parts.append("LONG")

        return "|".join(parts) if parts else "GENERIC"


class PatternClusterer:
    """
    Cluster judgments by feature similarity.

    Uses simple rule-based clustering for efficiency.
    """

    def cluster_judgments(
        self,
        judgments: List[InfoNeedJudgment],
        features_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Tuple[InfoNeedJudgment, Dict[str, Any]]]]:
        """
        Cluster judgments by feature signature.

        Args:
            judgments: List of InfoNeedJudgment instances
            features_list: List of extracted features (parallel to judgments)

        Returns:
            Dictionary mapping signature to list of (judgment, features) tuples
        """
        clusters = defaultdict(list)

        for judgment, features in zip(judgments, features_list):
            signature = features["signature"]
            clusters[signature].append((judgment, features))

        logger.info(f"Clustered {len(judgments)} judgments into {len(clusters)} clusters")

        return clusters


class InfoNeedPatternExtractor:
    """
    Extract long-term patterns from MemoryOS judgment history.

    Main operations:
    1. Query recent judgments from MemoryOS
    2. Extract features and cluster
    3. Calculate pattern statistics
    4. Generate pattern nodes
    """

    def __init__(self):
        """Initialize pattern extractor."""
        self.memory_writer = InfoNeedMemoryWriter()
        self.feature_extractor = QuestionFeatureExtractor()
        self.clusterer = PatternClusterer()

    async def extract_patterns(
        self,
        time_window: timedelta = timedelta(days=7),
        min_occurrences: int = 5,
        session_id: Optional[str] = None,
    ) -> List[InfoNeedPatternNode]:
        """
        Extract patterns from MemoryOS judgment history.

        Args:
            time_window: Time window to query (default 7 days)
            min_occurrences: Minimum occurrences for a pattern (default 5)
            session_id: Optional session filter

        Returns:
            List of extracted InfoNeedPatternNode instances
        """
        logger.info(f"Extracting patterns from last {time_window.days} days...")

        # Step 1: Query recent judgments from MemoryOS
        time_range = f"{int(time_window.total_seconds() / 3600)}h"
        judgments = await self.memory_writer.query_recent_judgments(
            session_id=session_id,
            time_range=time_range,
            limit=10000,  # Large limit to get all recent judgments
        )

        if not judgments:
            logger.warning("No judgments found in MemoryOS")
            return []

        logger.info(f"Retrieved {len(judgments)} judgments from MemoryOS")

        # Step 2: Extract features
        features_list = []
        for judgment in judgments:
            features = self.feature_extractor.extract_features(judgment.question_text)
            features_list.append(features)

        # Step 3: Cluster by feature similarity
        clusters = self.clusterer.cluster_judgments(judgments, features_list)

        # Step 4: Generate patterns from clusters
        patterns = []
        for signature, cluster_items in clusters.items():
            # Filter by minimum occurrences
            if len(cluster_items) < min_occurrences:
                logger.debug(
                    f"Skipping cluster '{signature}' with only {len(cluster_items)} occurrences "
                    f"(min: {min_occurrences})"
                )
                continue

            # Calculate pattern statistics
            pattern = self._generate_pattern_from_cluster(signature, cluster_items)
            patterns.append(pattern)
            logger.debug(
                f"Generated pattern '{signature}': {pattern.occurrence_count} occurrences, "
                f"{pattern.success_rate:.2f} success rate"
            )

        logger.info(f"Extracted {len(patterns)} patterns (min_occurrences: {min_occurrences})")

        return patterns

    def _generate_pattern_from_cluster(
        self,
        signature: str,
        cluster_items: List[Tuple[InfoNeedJudgment, Dict[str, Any]]]
    ) -> InfoNeedPatternNode:
        """
        Generate pattern node from cluster.

        Args:
            signature: Feature signature
            cluster_items: List of (judgment, features) tuples

        Returns:
            InfoNeedPatternNode instance
        """
        judgments, features_list = zip(*cluster_items)

        # Aggregate question features (use first item as representative)
        representative_features = features_list[0]

        # Determine dominant classification type
        type_counts = defaultdict(int)
        for judgment in judgments:
            type_counts[judgment.classified_type.value] += 1

        dominant_type = max(type_counts, key=type_counts.get)

        # Determine dominant confidence level
        confidence_counts = defaultdict(int)
        for judgment in judgments:
            confidence_counts[judgment.confidence_level.value] += 1

        dominant_confidence = max(confidence_counts, key=confidence_counts.get)

        # Calculate statistics
        occurrence_count = len(judgments)
        success_count = sum(
            1 for j in judgments
            if j.outcome.value in ["user_proceeded", "pending"]
        )
        failure_count = sum(
            1 for j in judgments
            if j.outcome.value in ["user_declined", "system_fallback"]
        )

        avg_confidence_score = sum(j.llm_confidence_score for j in judgments) / occurrence_count
        avg_latency_ms = sum(j.decision_latency_ms for j in judgments) / occurrence_count

        # Time metadata
        timestamps = [j.timestamp for j in judgments]
        first_seen = min(timestamps)
        last_seen = max(timestamps)

        # Create pattern node
        pattern = InfoNeedPatternNode(
            pattern_type=PatternType.QUESTION_KEYWORD_PATTERN,
            question_features=representative_features,
            classification_type=dominant_type,
            confidence_level=dominant_confidence,
            occurrence_count=occurrence_count,
            success_count=success_count,
            failure_count=failure_count,
            avg_confidence_score=avg_confidence_score,
            avg_latency_ms=avg_latency_ms,
            first_seen=first_seen,
            last_seen=last_seen,
            last_updated=utc_now(),
            pattern_version=1,
        )

        # Calculate success rate
        pattern.success_rate = pattern.calculate_success_rate()

        return pattern

    def merge_patterns(
        self,
        existing_pattern: InfoNeedPatternNode,
        new_judgments: List[InfoNeedJudgment]
    ) -> InfoNeedPatternNode:
        """
        Merge new judgments into existing pattern.

        This is used to update patterns incrementally rather than
        recalculating from scratch.

        Args:
            existing_pattern: Existing pattern node
            new_judgments: New judgments to merge

        Returns:
            Updated pattern node
        """
        # Update counts
        for judgment in new_judgments:
            success = judgment.outcome.value in ["user_proceeded", "pending"]
            existing_pattern.update_statistics(
                success=success,
                confidence_score=judgment.llm_confidence_score,
                latency_ms=judgment.decision_latency_ms,
            )

        # Increment version
        existing_pattern.pattern_version += 1

        return existing_pattern
