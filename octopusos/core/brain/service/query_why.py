"""
BrainOS Why Query

Traces the origin and rationale of code/files/capabilities:
- File → Commits that modified it → Docs that referenced it
- Term → Docs/Commits that mention it
- Capability → Docs that define it → Files that implement it

Returns paths with evidence, sorted by confidence and recency.
"""

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..store.query_helpers import (
    get_entity_by_key,
    get_neighbors,
    get_evidence_for_edge,
    parse_seed
)
from ..store import SQLiteStore


@dataclass
class QueryResult:
    """
    Unified query result structure for all BrainOS queries.

    Attributes:
        graph_version: Graph version identifier (timestamp + commit)
        seed: Seed entity that was queried
        result: Query-specific results (paths, timeline, nodes, etc.)
        evidence: List of evidence supporting the results
        stats: Statistics about the query results
    """
    graph_version: str
    seed: Dict[str, Any]
    result: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    stats: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "graph_version": self.graph_version,
            "seed": self.seed,
            "result": self.result,
            "evidence": self.evidence,
            "stats": self.stats
        }


def query_why(db_path: str, seed: Union[str, dict]) -> QueryResult:
    """
    Query why a file/capability/term exists by tracing its origins.

    Traces upward to find:
    - For File: Commits that modified it, Docs that reference it
    - For Commit: Docs that reference it
    - For Term: Docs/Commits that mention it
    - For Capability: Docs that define it

    Args:
        db_path: Path to BrainOS SQLite database
        seed: Seed entity, can be:
            - String: 'file:path' or 'commit:hash' (with type prefix)
            - Dict: {'type': 'File', 'key': 'file:path'}

    Returns:
        QueryResult with:
        - result.paths: List of paths from seed to origin nodes
        - evidence: All evidence supporting the paths
        - stats: path_count, evidence_count

    Examples:
        >>> result = query_why('./brainos.db', 'file:agentos/core/task/manager.py')
        >>> print(result.result['paths'][0]['nodes'])
        [{'type': 'file', 'name': 'manager.py'}, {'type': 'commit', 'name': 'feat: add retry'}]

    Raises:
        FileNotFoundError: If database doesn't exist
        ValueError: If seed format is invalid
    """
    # Validate database exists
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Please run BrainIndexJob.run() first to build the index."
        )

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
                result={'paths': []},
                evidence=[],
                stats={'path_count': 0, 'evidence_count': 0}
            )

        # Trace upward based on entity type
        paths = []
        all_evidence = []

        entity_type = seed_entity['type'].lower()

        if entity_type == 'file':
            # File → Commits (via MODIFIES) → Docs (via REFERENCES)
            paths, all_evidence = _trace_file_origins(conn, seed_entity)

        elif entity_type == 'commit':
            # Commit → Docs (via REFERENCES)
            paths, all_evidence = _trace_commit_origins(conn, seed_entity)

        elif entity_type == 'term':
            # Term ← Docs/Commits (via MENTIONS)
            paths, all_evidence = _trace_term_origins(conn, seed_entity)

        elif entity_type == 'capability':
            # Capability ← Docs (via REFERENCES), Files (via IMPLEMENTS)
            paths, all_evidence = _trace_capability_origins(conn, seed_entity)

        else:
            # Unknown type - try generic neighbor search
            paths, all_evidence = _trace_generic_origins(conn, seed_entity)

        # Sort paths by confidence (descending) and recency (descending)
        paths.sort(
            key=lambda p: (
                -min(e.get('confidence', 1.0) for e in p.get('edges', [{'confidence': 1.0}])),
                -max(n.get('created_at', 0) for n in p.get('nodes', [{'created_at': 0}]))
            )
        )

        return QueryResult(
            graph_version=graph_version,
            seed={
                'type': seed_entity['type'],
                'key': seed_entity['key'],
                'name': seed_entity['name']
            },
            result={'paths': paths},
            evidence=all_evidence,
            stats={
                'path_count': len(paths),
                'evidence_count': len(all_evidence)
            }
        )

    finally:
        conn.close()


def _trace_file_origins(
    conn: sqlite3.Connection,
    file_entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trace file origins: File → Commits (MODIFIES) → Docs (REFERENCES).

    Returns:
        Tuple of (paths, evidence)
    """
    paths = []
    all_evidence = []

    # Find commits that modified this file
    commits = get_neighbors(conn, file_entity['id'], edge_type='modifies', direction='incoming')

    for commit_info in commits:
        commit_entity = commit_info['entity']
        edge_info = commit_info['edge']

        # Get evidence for this edge
        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        # Create path: File → Commit
        path = {
            'nodes': [
                {
                    'type': file_entity['type'],
                    'key': file_entity['key'],
                    'name': file_entity['name'],
                    'created_at': file_entity['created_at']
                },
                {
                    'type': commit_entity['type'],
                    'key': commit_entity['key'],
                    'name': commit_entity['name'],
                    'created_at': commit_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

        # Continue to docs that reference this commit
        docs = get_neighbors(conn, commit_entity['id'], edge_type='references', direction='incoming')

        for doc_info in docs:
            doc_entity = doc_info['entity']
            doc_edge_info = doc_info['edge']

            doc_evidence = get_evidence_for_edge(conn, doc_edge_info['id'])
            all_evidence.extend(doc_evidence)

            # Create extended path: File → Commit → Doc
            extended_path = {
                'nodes': path['nodes'] + [
                    {
                        'type': doc_entity['type'],
                        'key': doc_entity['key'],
                        'name': doc_entity['name'],
                        'created_at': doc_entity['created_at']
                    }
                ],
                'edges': path['edges'] + [
                    {
                        'type': doc_edge_info['type'],
                        'confidence': doc_edge_info['confidence']
                    }
                ]
            }
            paths.append(extended_path)

    # Also look for docs that directly reference this file
    docs = get_neighbors(conn, file_entity['id'], edge_type='references', direction='incoming')

    for doc_info in docs:
        doc_entity = doc_info['entity']
        edge_info = doc_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': file_entity['type'],
                    'key': file_entity['key'],
                    'name': file_entity['name'],
                    'created_at': file_entity['created_at']
                },
                {
                    'type': doc_entity['type'],
                    'key': doc_entity['key'],
                    'name': doc_entity['name'],
                    'created_at': doc_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    return paths, all_evidence


def _trace_commit_origins(
    conn: sqlite3.Connection,
    commit_entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trace commit origins: Commit → Docs (REFERENCES).

    Returns:
        Tuple of (paths, evidence)
    """
    paths = []
    all_evidence = []

    # Find docs that reference this commit
    docs = get_neighbors(conn, commit_entity['id'], edge_type='references', direction='incoming')

    for doc_info in docs:
        doc_entity = doc_info['entity']
        edge_info = doc_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': commit_entity['type'],
                    'key': commit_entity['key'],
                    'name': commit_entity['name'],
                    'created_at': commit_entity['created_at']
                },
                {
                    'type': doc_entity['type'],
                    'key': doc_entity['key'],
                    'name': doc_entity['name'],
                    'created_at': doc_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    return paths, all_evidence


def _trace_term_origins(
    conn: sqlite3.Connection,
    term_entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trace term origins: Term ← Docs/Commits/Files (MENTIONS).

    Returns:
        Tuple of (paths, evidence)
    """
    paths = []
    all_evidence = []

    # Find entities that mention this term
    mentions = get_neighbors(conn, term_entity['id'], edge_type='mentions', direction='incoming')

    for mention_info in mentions:
        entity = mention_info['entity']
        edge_info = mention_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': term_entity['type'],
                    'key': term_entity['key'],
                    'name': term_entity['name'],
                    'created_at': term_entity['created_at']
                },
                {
                    'type': entity['type'],
                    'key': entity['key'],
                    'name': entity['name'],
                    'created_at': entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    return paths, all_evidence


def _trace_capability_origins(
    conn: sqlite3.Connection,
    capability_entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trace capability origins: Capability ← Docs (REFERENCES), Files (IMPLEMENTS).

    Returns:
        Tuple of (paths, evidence)
    """
    paths = []
    all_evidence = []

    # Find docs that reference this capability
    docs = get_neighbors(conn, capability_entity['id'], edge_type='references', direction='incoming')

    for doc_info in docs:
        doc_entity = doc_info['entity']
        edge_info = doc_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': capability_entity['type'],
                    'key': capability_entity['key'],
                    'name': capability_entity['name'],
                    'created_at': capability_entity['created_at']
                },
                {
                    'type': doc_entity['type'],
                    'key': doc_entity['key'],
                    'name': doc_entity['name'],
                    'created_at': doc_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    # Find files that implement this capability
    files = get_neighbors(conn, capability_entity['id'], edge_type='implements', direction='incoming')

    for file_info in files:
        file_entity = file_info['entity']
        edge_info = file_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': capability_entity['type'],
                    'key': capability_entity['key'],
                    'name': capability_entity['name'],
                    'created_at': capability_entity['created_at']
                },
                {
                    'type': file_entity['type'],
                    'key': file_entity['key'],
                    'name': file_entity['name'],
                    'created_at': file_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    return paths, all_evidence


def _trace_generic_origins(
    conn: sqlite3.Connection,
    entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generic origin tracing for unknown entity types.

    Returns all incoming neighbors.

    Returns:
        Tuple of (paths, evidence)
    """
    paths = []
    all_evidence = []

    # Get all incoming neighbors
    neighbors = get_neighbors(conn, entity['id'], edge_type=None, direction='incoming')

    for neighbor_info in neighbors:
        neighbor_entity = neighbor_info['entity']
        edge_info = neighbor_info['edge']

        evidence = get_evidence_for_edge(conn, edge_info['id'])
        all_evidence.extend(evidence)

        path = {
            'nodes': [
                {
                    'type': entity['type'],
                    'key': entity['key'],
                    'name': entity['name'],
                    'created_at': entity['created_at']
                },
                {
                    'type': neighbor_entity['type'],
                    'key': neighbor_entity['key'],
                    'name': neighbor_entity['name'],
                    'created_at': neighbor_entity['created_at']
                }
            ],
            'edges': [
                {
                    'type': edge_info['type'],
                    'confidence': edge_info['confidence']
                }
            ]
        }
        paths.append(path)

    return paths, all_evidence
