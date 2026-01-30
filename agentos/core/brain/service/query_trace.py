"""
BrainOS Trace Query

Traces the evolution of a term or capability over time:
- Find all commits/docs/files that mention the term
- Sort by timestamp to create a timeline
- Show when the concept was introduced, evolved, and how it's used

Returns a timeline of mentions with evidence.
"""

import os
import sqlite3
from typing import Any, Dict, List, Union

from ..store.query_helpers import (
    get_entity_by_key,
    get_neighbors,
    get_evidence_for_edge,
    parse_seed
)
from ..store import SQLiteStore
from .query_why import QueryResult


def query_trace(
    db_path: str,
    seed: Union[str, dict]
) -> QueryResult:
    """
    Trace the evolution of a term or capability over time.

    Finds all entities that mention the term (via MENTIONS edges) and creates
    a timeline sorted by timestamp.

    Args:
        db_path: Path to BrainOS SQLite database
        seed: Seed entity (typically a Term or Capability), can be:
            - String: 'term:websocket' or 'capability:extensions' (with type prefix)
            - String: 'websocket' (assumes Term if no prefix)
            - Dict: {'type': 'Term', 'key': 'term:websocket'}

    Returns:
        QueryResult with:
        - result.timeline: Chronologically sorted list of mentions
        - result.nodes: All entities involved in the timeline
        - evidence: All evidence supporting mentions
        - stats: mention_count, time_span_days

    Examples:
        >>> result = query_trace('./brainos.db', 'term:planning_guard')
        >>> for event in result.result['timeline']:
        ...     print(f"{event['timestamp']}: {event['node']['name']}")

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

        # Parse seed - if no type prefix, assume term
        seed_type, seed_key = parse_seed(seed)

        # If no type detected, try to find as term
        if not seed_type or seed_type == 'unknown':
            # Try with 'term:' prefix
            seed_key = f"term:{seed}" if isinstance(seed, str) else seed_key

        # Get seed entity
        seed_entity = get_entity_by_key(conn, seed_key) if seed_key else None

        if not seed_entity:
            # Seed not found - return empty result
            return QueryResult(
                graph_version=graph_version,
                seed={'type': seed_type or 'term', 'key': seed_key or str(seed)},
                result={'timeline': [], 'nodes': []},
                evidence=[],
                stats={'mention_count': 0, 'time_span_days': 0}
            )

        # Find all entities that mention this term/capability
        mentions = get_neighbors(
            conn,
            seed_entity['id'],
            edge_type='mentions',
            direction='incoming'
        )

        # Collect timeline events
        timeline = []
        all_evidence = []
        all_nodes = [seed_entity]

        for mention_info in mentions:
            entity = mention_info['entity']
            edge_info = mention_info['edge']

            # Get evidence for this mention
            evidence = get_evidence_for_edge(conn, edge_info['id'])
            all_evidence.extend(evidence)

            # Extract timestamp
            timestamp = _extract_timestamp(entity)

            # Create timeline event
            event = {
                'timestamp': timestamp,
                'node': {
                    'type': entity['type'],
                    'key': entity['key'],
                    'name': entity['name']
                },
                'relation': edge_info['type'],
                'evidence': {
                    'source_type': evidence[0]['source_type'] if evidence else None,
                    'source_ref': evidence[0]['source_ref'] if evidence else None
                }
            }
            timeline.append(event)
            all_nodes.append(entity)

        # Sort timeline by timestamp (oldest first)
        timeline.sort(key=lambda e: e['timestamp'] or 0)

        # Calculate time span
        if timeline:
            timestamps = [e['timestamp'] for e in timeline if e['timestamp']]
            if timestamps:
                time_span_seconds = max(timestamps) - min(timestamps)
                time_span_days = int(time_span_seconds / 86400)  # Convert to days
            else:
                time_span_days = 0
        else:
            time_span_days = 0

        # Format nodes for output
        formatted_nodes = []
        for node in all_nodes:
            formatted_nodes.append({
                'type': node['type'],
                'key': node['key'],
                'name': node['name']
            })

        return QueryResult(
            graph_version=graph_version,
            seed={
                'type': seed_entity['type'],
                'key': seed_entity['key'],
                'name': seed_entity['name']
            },
            result={
                'timeline': timeline,
                'nodes': formatted_nodes
            },
            evidence=all_evidence,
            stats={
                'mention_count': len(mentions),
                'time_span_days': time_span_days
            }
        )

    finally:
        conn.close()


def _extract_timestamp(entity: Dict[str, Any]) -> float:
    """
    Extract timestamp from entity.

    Priority:
    1. attrs.timestamp (for commits)
    2. attrs.date (for commits)
    3. created_at (entity creation time)

    Args:
        entity: Entity dict

    Returns:
        Unix timestamp (float)
    """
    attrs = entity.get('attrs', {})

    # Try attrs.timestamp first (Git commits)
    if 'timestamp' in attrs:
        return float(attrs['timestamp'])

    # Try attrs.date (alternative format)
    if 'date' in attrs:
        date = attrs['date']
        # If it's already a number, use it
        if isinstance(date, (int, float)):
            return float(date)
        # If it's a string, try to parse it
        # TODO: Add proper ISO timestamp parsing if needed
        # For now, use created_at as fallback

    # Fallback to created_at
    return entity.get('created_at', 0)
