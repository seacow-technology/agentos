"""
BrainOS Statistics

Query statistics and metadata from BrainOS database.
"""

from typing import Dict, Any
from ..store import get_stats as store_get_stats


def get_stats(db_path: str) -> Dict[str, Any]:
    """
    Get statistics from BrainOS database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Dictionary containing:
        - entities: Entity count
        - edges: Edge count
        - evidence: Evidence count
        - last_build: Last build metadata (or None)
          - graph_version: Version string
          - source_commit: Commit hash
          - built_at: Unix timestamp
          - duration_ms: Build duration in milliseconds

    Example:
        >>> stats = get_stats('./brainos.db')
        >>> print(f"Entities: {stats['entities']}")
        >>> print(f"Last build: {stats['last_build']['graph_version']}")
    """
    return store_get_stats(db_path)
