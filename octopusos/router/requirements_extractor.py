"""
Requirements Extractor

Extracts task capability requirements from task spec/metadata.
MVP uses rule-based heuristics (no LLM needed).
"""

import logging
from typing import Dict, Any
from agentos.router.models import TaskRequirements

logger = logging.getLogger(__name__)


class RequirementsExtractor:
    """
    Extract task requirements from task spec

    MVP implementation uses simple keyword matching.
    Future: Could use LLM for more sophisticated analysis.
    """

    # Keyword patterns for capability detection
    CODING_KEYWORDS = [
        "code", "coding", "implement", "refactor", "debug", "fix", "bug",
        "function", "class", "method", "api", "endpoint", "test", "pytest",
        "jest", "pr", "commit", "git", "repository", "repo"
    ]

    FRONTEND_KEYWORDS = [
        "react", "vue", "angular", "svelte", "html", "css", "javascript",
        "typescript", "jsx", "tsx", "ui", "frontend", "web", "component",
        "mui", "tailwind", "bootstrap", "dom"
    ]

    BACKEND_KEYWORDS = [
        "backend", "server", "api", "rest", "graphql", "database", "db",
        "sql", "postgres", "mysql", "mongo", "redis", "cache", "queue"
    ]

    DATA_KEYWORDS = [
        "data", "analysis", "pandas", "numpy", "jupyter", "notebook",
        "csv", "json", "xml", "etl", "pipeline", "transform"
    ]

    TESTING_KEYWORDS = [
        "test", "testing", "pytest", "jest", "unit test", "integration test",
        "e2e", "qa", "quality", "coverage", "mock"
    ]

    LONG_CTX_KEYWORDS = [
        "long", "large", "multiple files", "entire", "whole", "全部",
        "所有", "完整", "总结", "summary", "summarize", "analyze"
    ]

    def extract(self, task_spec: Dict[str, Any]) -> TaskRequirements:
        """
        Extract requirements from task spec

        Args:
            task_spec: Task specification with title, description, metadata, etc.

        Returns:
            TaskRequirements
        """
        # Combine relevant fields for analysis
        text_parts = []

        if "title" in task_spec:
            text_parts.append(task_spec["title"])
        if "description" in task_spec:
            text_parts.append(task_spec["description"])
        if "nl_request" in task_spec:
            text_parts.append(task_spec["nl_request"])
        if "metadata" in task_spec and isinstance(task_spec["metadata"], dict):
            if "nl_request" in task_spec["metadata"]:
                text_parts.append(task_spec["metadata"]["nl_request"])

        combined_text = " ".join(text_parts).lower()

        # Extract needs (capabilities)
        needs = []

        if self._matches_keywords(combined_text, self.CODING_KEYWORDS):
            needs.append("coding")

        if self._matches_keywords(combined_text, self.FRONTEND_KEYWORDS):
            needs.append("frontend")

        if self._matches_keywords(combined_text, self.BACKEND_KEYWORDS):
            needs.append("backend")

        if self._matches_keywords(combined_text, self.DATA_KEYWORDS):
            needs.append("data")

        if self._matches_keywords(combined_text, self.TESTING_KEYWORDS):
            needs.append("testing")

        # Default to "general" if no specific needs detected
        if not needs:
            needs.append("general")

        # Extract preferences
        prefer = ["local"]  # Default: prefer local instances

        # Determine context requirements
        min_ctx = 4096  # Default
        if self._matches_keywords(combined_text, self.LONG_CTX_KEYWORDS):
            min_ctx = 8192
            needs.append("long_ctx")

        # Determine latency class
        latency_class = "normal"
        if any(kw in combined_text for kw in ["快", "urgent", "fast", "quick"]):
            latency_class = "fast"
        elif any(kw in combined_text for kw in ["batch", "offline", "background"]):
            latency_class = "batch"

        requirements = TaskRequirements(
            needs=needs,
            prefer=prefer,
            min_ctx=min_ctx,
            latency_class=latency_class,
        )

        logger.debug(f"Extracted requirements: {requirements.to_dict()}")
        return requirements

    def _matches_keywords(self, text: str, keywords: list) -> bool:
        """
        Check if text matches any keywords

        Args:
            text: Text to check (should be lowercase)
            keywords: List of keywords to match

        Returns:
            True if any keyword matches
        """
        return any(keyword in text for keyword in keywords)
