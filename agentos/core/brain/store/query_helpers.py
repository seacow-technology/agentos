"""
BrainOS Query Helpers

Read-only helper functions for graph traversal and querying.
All functions operate on SQLite connections and do not modify data.

These helpers support the four core reasoning queries:
- why: trace origins and decisions
- impact: analyze downstream dependencies
- trace: track evolution over time
- subgraph: extract local neighborhoods
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple


def get_neighbors(
    conn: sqlite3.Connection,
    entity_id: int,
    edge_type: Optional[str] = None,
    direction: str = "outgoing"
) -> List[Dict[str, Any]]:
    """
    Get neighboring entities connected by edges.

    Args:
        conn: SQLite connection
        entity_id: Entity ID to query neighbors for
        edge_type: Optional edge type filter (e.g., 'MODIFIES', 'DEPENDS_ON')
        direction: 'outgoing' (entity_id as source), 'incoming' (entity_id as target),
                  or 'both'

    Returns:
        List of neighbor entities with edge information
        Each dict contains: {
            'entity': {entity fields},
            'edge': {edge fields},
            'distance': 1
        }
    """
    cursor = conn.cursor()
    neighbors = []

    # Query outgoing edges (entity_id as source)
    if direction in ("outgoing", "both"):
        query = """
            SELECT
                e.id, e.type, e.key, e.name, e.attrs_json, e.created_at,
                edge.id, edge.type, edge.confidence, edge.attrs_json
            FROM edges AS edge
            JOIN entities AS e ON edge.dst_entity_id = e.id
            WHERE edge.src_entity_id = ?
        """
        params = [entity_id]

        if edge_type:
            query += " AND edge.type = ?"
            params.append(edge_type)

        cursor.execute(query, params)

        for row in cursor.fetchall():
            neighbors.append({
                'entity': {
                    'id': row[0],
                    'type': row[1],
                    'key': row[2],
                    'name': row[3],
                    'attrs': json.loads(row[4]),
                    'created_at': row[5]
                },
                'edge': {
                    'id': row[6],
                    'type': row[7],
                    'confidence': row[8],
                    'attrs': json.loads(row[9])
                },
                'distance': 1
            })

    # Query incoming edges (entity_id as target)
    if direction in ("incoming", "both"):
        query = """
            SELECT
                e.id, e.type, e.key, e.name, e.attrs_json, e.created_at,
                edge.id, edge.type, edge.confidence, edge.attrs_json
            FROM edges AS edge
            JOIN entities AS e ON edge.src_entity_id = e.id
            WHERE edge.dst_entity_id = ?
        """
        params = [entity_id]

        if edge_type:
            query += " AND edge.type = ?"
            params.append(edge_type)

        cursor.execute(query, params)

        for row in cursor.fetchall():
            neighbors.append({
                'entity': {
                    'id': row[0],
                    'type': row[1],
                    'key': row[2],
                    'name': row[3],
                    'attrs': json.loads(row[4]),
                    'created_at': row[5]
                },
                'edge': {
                    'id': row[6],
                    'type': row[7],
                    'confidence': row[8],
                    'attrs': json.loads(row[9])
                },
                'distance': 1
            })

    return neighbors


def get_evidence_for_edge(
    conn: sqlite3.Connection,
    edge_id: int
) -> List[Dict[str, Any]]:
    """
    Get all evidence for a specific edge.

    Args:
        conn: SQLite connection
        edge_id: Edge ID

    Returns:
        List of evidence dicts, each containing:
        - edge_id: Edge ID
        - source_type: Evidence source type (git/doc/code)
        - source_ref: Source reference (commit hash, file path, etc.)
        - span: Location span (line numbers, etc.)
        - attrs: Additional attributes
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, edge_id, source_type, source_ref,
            span_json, attrs_json, created_at
        FROM evidence
        WHERE edge_id = ?
        ORDER BY created_at DESC
    """, (edge_id,))

    evidence_list = []
    for row in cursor.fetchall():
        evidence_list.append({
            'id': row[0],
            'edge_id': row[1],
            'source_type': row[2],
            'source_ref': row[3],
            'span': json.loads(row[4]),
            'attrs': json.loads(row[5]),
            'created_at': row[6]
        })

    return evidence_list


def get_entities_by_type(
    conn: sqlite3.Connection,
    entity_type: str
) -> List[Dict[str, Any]]:
    """
    Get all entities of a specific type.

    Args:
        conn: SQLite connection
        entity_type: Entity type (e.g., 'file', 'commit', 'doc')

    Returns:
        List of entity dicts
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, type, key, name, attrs_json, created_at
        FROM entities
        WHERE type = ?
        ORDER BY created_at DESC
    """, (entity_type,))

    entities = []
    for row in cursor.fetchall():
        entities.append({
            'id': row[0],
            'type': row[1],
            'key': row[2],
            'name': row[3],
            'attrs': json.loads(row[4]),
            'created_at': row[5]
        })

    return entities


def get_edges_by_type(
    conn: sqlite3.Connection,
    edge_type: str
) -> List[Dict[str, Any]]:
    """
    Get all edges of a specific type.

    Args:
        conn: SQLite connection
        edge_type: Edge type (e.g., 'MODIFIES', 'DEPENDS_ON')

    Returns:
        List of edge dicts with source and target entities
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            e.id, e.type, e.key, e.confidence, e.attrs_json, e.created_at,
            src.id, src.type, src.key, src.name,
            dst.id, dst.type, dst.key, dst.name
        FROM edges AS e
        JOIN entities AS src ON e.src_entity_id = src.id
        JOIN entities AS dst ON e.dst_entity_id = dst.id
        WHERE e.type = ?
        ORDER BY e.created_at DESC
    """, (edge_type,))

    edges = []
    for row in cursor.fetchall():
        edges.append({
            'id': row[0],
            'type': row[1],
            'key': row[2],
            'confidence': row[3],
            'attrs': json.loads(row[4]),
            'created_at': row[5],
            'source': {
                'id': row[6],
                'type': row[7],
                'key': row[8],
                'name': row[9]
            },
            'target': {
                'id': row[10],
                'type': row[11],
                'key': row[12],
                'name': row[13]
            }
        })

    return edges


def reverse_traverse(
    conn: sqlite3.Connection,
    entity_id: int,
    edge_type: str,
    depth: int = 1
) -> List[Dict[str, Any]]:
    """
    Reverse traverse from entity following incoming edges of specific type.

    Used for impact analysis: "who depends on me?"

    Args:
        conn: SQLite connection
        entity_id: Starting entity ID
        edge_type: Edge type to follow (e.g., 'DEPENDS_ON')
        depth: Maximum traversal depth

    Returns:
        List of reached entities with distances
        Each dict contains: {
            'entity': {entity fields},
            'distance': int (1 to depth),
            'path': [edge_ids]
        }
    """
    cursor = conn.cursor()
    visited: Set[int] = set()
    result = []
    current_level = [(entity_id, 0, [])]  # (entity_id, distance, path)

    while current_level and current_level[0][1] < depth:
        next_level = []

        for eid, dist, path in current_level:
            if eid in visited:
                continue
            visited.add(eid)

            # Get incoming edges (reverse direction: who points to me?)
            cursor.execute("""
                SELECT
                    e.id, e.type, e.key, e.name, e.attrs_json, e.created_at,
                    edge.id
                FROM edges AS edge
                JOIN entities AS e ON edge.src_entity_id = e.id
                WHERE edge.dst_entity_id = ? AND edge.type = ?
            """, (eid, edge_type))

            for row in cursor.fetchall():
                neighbor_id = row[0]
                edge_id = row[6]

                if neighbor_id not in visited:
                    new_path = path + [edge_id]
                    next_level.append((neighbor_id, dist + 1, new_path))

                    result.append({
                        'entity': {
                            'id': row[0],
                            'type': row[1],
                            'key': row[2],
                            'name': row[3],
                            'attrs': json.loads(row[4]),
                            'created_at': row[5]
                        },
                        'distance': dist + 1,
                        'path': new_path
                    })

        current_level = next_level

    return result


def get_k_hop_subgraph(
    conn: sqlite3.Connection,
    entity_id: int,
    k: int = 1
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract k-hop neighborhood subgraph around entity.

    Uses BFS to explore up to k hops in both directions (incoming + outgoing).

    Args:
        conn: SQLite connection
        entity_id: Seed entity ID
        k: Number of hops (default 1)

    Returns:
        Tuple of (nodes, edges):
        - nodes: List of entity dicts with 'distance' field
        - edges: List of edge dicts between nodes in subgraph
    """
    cursor = conn.cursor()

    # Get seed entity
    cursor.execute("""
        SELECT id, type, key, name, attrs_json, created_at
        FROM entities
        WHERE id = ?
    """, (entity_id,))

    seed_row = cursor.fetchone()
    if not seed_row:
        return [], []

    # Initialize with seed
    nodes_dict: Dict[int, Dict[str, Any]] = {
        entity_id: {
            'id': seed_row[0],
            'type': seed_row[1],
            'key': seed_row[2],
            'name': seed_row[3],
            'attrs': json.loads(seed_row[4]),
            'created_at': seed_row[5],
            'distance': 0
        }
    }

    edges_dict: Dict[int, Dict[str, Any]] = {}
    visited: Set[int] = {entity_id}
    current_level = [entity_id]

    # BFS for k hops
    for hop in range(k):
        next_level = []

        for eid in current_level:
            # Get both outgoing and incoming edges
            neighbors = get_neighbors(conn, eid, edge_type=None, direction="both")

            for neighbor in neighbors:
                neighbor_entity = neighbor['entity']
                neighbor_id = neighbor_entity['id']
                edge_info = neighbor['edge']

                # Add edge to subgraph
                edge_id = edge_info['id']
                if edge_id not in edges_dict:
                    # Get source and target for this edge
                    cursor.execute("""
                        SELECT src_entity_id, dst_entity_id, type, key, confidence, attrs_json
                        FROM edges
                        WHERE id = ?
                    """, (edge_id,))
                    edge_row = cursor.fetchone()

                    if edge_row:
                        edges_dict[edge_id] = {
                            'id': edge_id,
                            'src_id': edge_row[0],
                            'dst_id': edge_row[1],
                            'type': edge_row[2],
                            'key': edge_row[3],
                            'confidence': edge_row[4],
                            'attrs': json.loads(edge_row[5])
                        }

                # Add node if not visited
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    neighbor_entity['distance'] = hop + 1
                    nodes_dict[neighbor_id] = neighbor_entity
                    next_level.append(neighbor_id)

        current_level = next_level

    # Convert dicts to lists
    nodes = list(nodes_dict.values())
    edges = list(edges_dict.values())

    return nodes, edges


def get_entity_by_key(
    conn: sqlite3.Connection,
    entity_key: str
) -> Optional[Dict[str, Any]]:
    """
    Get entity by key (without type filter).

    Args:
        conn: SQLite connection
        entity_key: Entity key (e.g., 'file:path/to/file.py', 'commit:abc123')

    Returns:
        Entity dict or None if not found
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, type, key, name, attrs_json, created_at
        FROM entities
        WHERE key = ?
        LIMIT 1
    """, (entity_key,))

    row = cursor.fetchone()
    if not row:
        return None

    return {
        'id': row[0],
        'type': row[1],
        'key': row[2],
        'name': row[3],
        'attrs': json.loads(row[4]),
        'created_at': row[5]
    }


def parse_seed(seed_input: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse seed input into (entity_type, key).

    Args:
        seed_input: Can be:
            - str: 'file:path' or 'commit:hash' (extracts type from prefix)
            - dict: {'type': 'File', 'key': '...'}

    Returns:
        Tuple of (entity_type, key) or (None, None) if invalid
    """
    if isinstance(seed_input, str):
        if ':' in seed_input:
            # Format: 'type:key'
            parts = seed_input.split(':', 1)
            return parts[0].lower(), seed_input
        else:
            # Assume it's a key, type unknown
            return None, seed_input

    elif isinstance(seed_input, dict):
        entity_type = seed_input.get('type', '').lower()
        key = seed_input.get('key', '')
        return entity_type, key

    return None, None
