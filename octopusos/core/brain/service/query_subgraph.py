"""
BrainOS Subgraph Query

Extracts k-hop neighborhood around a seed entity.

Returns a subgraph that can be used for:
- Visualization (graph rendering)
- Local context understanding
- Relationship exploration

Output format is compatible with graph visualization libraries.
"""

import os
import sqlite3
from typing import Any, Dict, List, Union

from ..store.query_helpers import (
    get_entity_by_key,
    get_k_hop_subgraph,
    get_evidence_for_edge,
    parse_seed
)
from ..store import SQLiteStore
from .query_why import QueryResult


def query_subgraph(
    db_path: str,
    seed: Union[str, dict],
    k_hop: int = 1
) -> QueryResult:
    """
    Extract k-hop neighborhood subgraph around seed entity.

    Uses BFS to explore up to k hops in both directions (incoming + outgoing edges).
    Returns a complete subgraph with all nodes, edges, and evidence.

    Args:
        db_path: Path to BrainOS SQLite database
        seed: Seed entity, can be:
            - String: 'file:path' or 'commit:hash' (with type prefix)
            - Dict: {'type': 'File', 'key': 'file:path'}
        k_hop: Number of hops to traverse (default: 1)

    Returns:
        QueryResult with:
        - result.nodes: List of nodes with distance from seed
        - result.edges: List of edges between nodes
        - result.top_evidence: Sample evidence from edges
        - stats: node_count, edge_count, k_hop

    Examples:
        >>> result = query_subgraph('./brainos.db', 'file:agentos/core/task/manager.py', k_hop=1)
        >>> print(f"Nodes: {len(result.result['nodes'])}")
        >>> print(f"Edges: {len(result.result['edges'])}")

    Raises:
        FileNotFoundError: If database doesn't exist
        ValueError: If k_hop < 0 or seed format is invalid
    """
    # Validate inputs
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Please run BrainIndexJob.run() first to build the index."
        )

    if k_hop < 0:
        raise ValueError(f"k_hop must be >= 0, got {k_hop}")

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
                result={'nodes': [], 'edges': [], 'top_evidence': []},
                evidence=[],
                stats={'node_count': 0, 'edge_count': 0, 'k_hop': k_hop}
            )

        # Extract k-hop subgraph
        nodes, edges = get_k_hop_subgraph(conn, seed_entity['id'], k=k_hop)

        # Collect evidence for top edges (limit to avoid huge payloads)
        all_evidence = []
        top_evidence = []
        max_evidence_edges = 10  # Limit evidence collection

        for i, edge in enumerate(edges):
            if i < max_evidence_edges:
                edge_evidence = get_evidence_for_edge(conn, edge['id'])
                all_evidence.extend(edge_evidence)

                if edge_evidence:
                    # Add first evidence as "top evidence"
                    top_evidence.append({
                        'edge_id': edge['id'],
                        'source_type': edge_evidence[0]['source_type'],
                        'source_ref': edge_evidence[0]['source_ref']
                    })

        # Format nodes for output (ensure seed is always first)
        formatted_nodes = []
        for node in nodes:
            formatted_nodes.append({
                'id': node['id'],
                'type': node['type'],
                'key': node['key'],
                'name': node['name'],
                'distance': node['distance']
            })

        # Sort nodes by distance (seed first)
        formatted_nodes.sort(key=lambda n: n['distance'])

        # Format edges for output
        formatted_edges = []
        for edge in edges:
            formatted_edges.append({
                'id': edge['id'],
                'src_id': edge['src_id'],
                'dst_id': edge['dst_id'],
                'type': edge['type'],
                'confidence': edge['confidence']
            })

        return QueryResult(
            graph_version=graph_version,
            seed={
                'type': seed_entity['type'],
                'key': seed_entity['key'],
                'name': seed_entity['name']
            },
            result={
                'nodes': formatted_nodes,
                'edges': formatted_edges,
                'top_evidence': top_evidence
            },
            evidence=all_evidence,
            stats={
                'node_count': len(nodes),
                'edge_count': len(edges),
                'k_hop': k_hop
            }
        )

    finally:
        conn.close()
