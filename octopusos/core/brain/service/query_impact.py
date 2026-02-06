"""
BrainOS Impact Query

Analyzes the impact of modifying a file or module:
- Who depends on this file? (reverse DEPENDS_ON traversal)
- Which commits recently modified downstream files?
- What terms are associated with affected files?

Returns affected nodes with risk assessment hints.
"""

import os
import sqlite3
from typing import Any, Dict, List, Union

from ..store.query_helpers import (
    get_entity_by_key,
    reverse_traverse,
    get_neighbors,
    get_evidence_for_edge,
    parse_seed
)
from ..store import SQLiteStore
from .query_why import QueryResult


def query_impact(
    db_path: str,
    seed: Union[str, dict],
    depth: int = 1
) -> QueryResult:
    """
    Query the impact of modifying a file or module.

    Performs reverse traversal along DEPENDS_ON edges to find downstream dependencies.
    Also associates:
    - Recent commits that modified downstream files
    - Terms mentioned in affected files

    Args:
        db_path: Path to BrainOS SQLite database
        seed: Seed entity (typically a File or Module), can be:
            - String: 'file:path' (with type prefix)
            - Dict: {'type': 'File', 'key': 'file:path'}
        depth: Maximum traversal depth for dependencies (default: 1)

    Returns:
        QueryResult with:
        - result.affected_nodes: List of downstream files/modules with distances
        - result.risk_hints: List of risk indicators (high fan-out, recent changes)
        - evidence: All evidence supporting dependencies
        - stats: affected_count, max_depth

    Examples:
        >>> result = query_impact('./brainos.db', 'file:agentos/core/task/models.py')
        >>> print(f"Affected files: {len(result.result['affected_nodes'])}")
        >>> print(f"Risk hints: {result.result['risk_hints']}")

    Raises:
        FileNotFoundError: If database doesn't exist
        ValueError: If depth < 0 or seed format is invalid
    """
    # Validate inputs
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Please run BrainIndexJob.run() first to build the index."
        )

    if depth < 0:
        raise ValueError(f"depth must be >= 0, got {depth}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Get graph version
        store = SQLiteStore(db_path, auto_init=False)
        store.connect()
        metadata = store.get_last_build_metadata()
        graph_version = metadata['graph_version'] if metadata else 'unknown'
        store.close()

        # Parse seed
        seed_type, seed_key = parse_seed(seed)

        # Get seed entity
        seed_entity = get_entity_by_key(conn, seed_key) if seed_key else None

        if not seed_entity:
            # Seed not found - return empty result
            return QueryResult(
                graph_version=graph_version,
                seed={'type': seed_type or 'unknown', 'key': seed_key or str(seed)},
                result={'affected_nodes': [], 'risk_hints': []},
                evidence=[],
                stats={'affected_count': 0, 'max_depth': depth}
            )

        # Perform reverse traversal to find downstream dependents
        downstream = reverse_traverse(
            conn,
            seed_entity['id'],
            edge_type='depends_on',
            depth=depth
        )

        # Collect evidence and format affected nodes
        all_evidence = []
        affected_nodes = []

        for item in downstream:
            entity = item['entity']
            distance = item['distance']
            path = item['path']

            # Collect evidence for this dependency path
            for edge_id in path:
                evidence = get_evidence_for_edge(conn, edge_id)
                all_evidence.extend(evidence)

            affected_nodes.append({
                'type': entity['type'],
                'key': entity['key'],
                'name': entity['name'],
                'distance': distance
            })

        # Associate recent commits for affected files
        recent_commits = []
        for item in downstream:
            if item['entity']['type'].lower() == 'file':
                # Find commits that modified this file
                commits = get_neighbors(
                    conn,
                    item['entity']['id'],
                    edge_type='modifies',
                    direction='incoming'
                )

                for commit_info in commits:
                    commit_entity = commit_info['entity']
                    recent_commits.append({
                        'type': commit_entity['type'],
                        'key': commit_entity['key'],
                        'name': commit_entity['name'],
                        'distance': item['distance']
                    })

                    # Add to affected nodes if not already there
                    if not any(n['key'] == commit_entity['key'] for n in affected_nodes):
                        affected_nodes.append({
                            'type': commit_entity['type'],
                            'key': commit_entity['key'],
                            'name': commit_entity['name'],
                            'distance': item['distance']
                        })

        # Generate risk hints
        risk_hints = _generate_risk_hints(downstream, recent_commits)

        return QueryResult(
            graph_version=graph_version,
            seed={
                'type': seed_entity['type'],
                'key': seed_entity['key'],
                'name': seed_entity['name']
            },
            result={
                'affected_nodes': affected_nodes,
                'risk_hints': risk_hints
            },
            evidence=all_evidence,
            stats={
                'affected_count': len(affected_nodes),
                'max_depth': depth
            }
        )

    finally:
        conn.close()


def _generate_risk_hints(
    downstream: List[Dict[str, Any]],
    recent_commits: List[Dict[str, Any]]
) -> List[str]:
    """
    Generate risk assessment hints based on impact analysis.

    Args:
        downstream: List of downstream dependencies
        recent_commits: List of recent commits affecting downstream files

    Returns:
        List of risk hint strings
    """
    hints = []

    # High fan-out warning
    file_count = sum(1 for item in downstream if item['entity']['type'].lower() == 'file')
    if file_count >= 10:
        hints.append(f"High fan-out: {file_count} downstream files")
    elif file_count >= 5:
        hints.append(f"Medium fan-out: {file_count} downstream files")

    # Recent changes warning
    if len(recent_commits) >= 3:
        hints.append(f"Recently modified: {len(recent_commits)} commits in downstream files")

    # Multi-hop warning
    max_distance = max((item['distance'] for item in downstream), default=0)
    if max_distance > 1:
        hints.append(f"Multi-hop impact: affects files up to {max_distance} levels deep")

    # No downstream warning
    if file_count == 0:
        hints.append("No downstream dependencies found")

    return hints
