"""
BrainOS Subgraph Query Engine (P2-2)

This module implements the cognitive structure extraction engine that:
1. Extracts k-hop subgraphs centered around a seed entity
2. Computes cognitive attributes (evidence_count, coverage_sources, blind_spot_info)
3. Detects missing connections (空白区域)
4. Encodes visual semantics for frontend rendering

This is NOT simple graph traversal - this is "cognitive structure extraction +
evidence density calculation + blind spot identification".

Core Principles (Three Red Lines):
- Red Line 1: Every edge MUST have >= 1 evidence (no evidence-free edges)
- Red Line 2: Blind spots MUST be visibly marked (no hiding cognitive gaps)
- Red Line 3: Missing connections MUST be reported (no completeness illusion)

Reference:
- P2_COGNITIVE_MODEL_DEFINITION.md
- P2_VISUAL_SEMANTICS_QUICK_REFERENCE.md
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..store import SQLiteStore
from .blind_spot import BlindSpot, BlindSpotType, detect_blind_spots
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


# ============================================================================
# Data Models (Phase 1)
# ============================================================================

@dataclass
class NodeVisual:
    """
    Node visual encoding (computed based on P2-1 rules)

    Attributes:
        color: Fill color (hex) - based on coverage_sources count
        size: Radius in pixels - based on evidence_count and in_degree
        border_color: Border color (hex) - red/orange for blind spots
        border_width: Border width in pixels
        border_style: "solid" / "dashed" / "dotted"
        shape: Node shape - based on entity_type
        label: Display text
        tooltip: Hover tooltip text
    """
    color: str
    size: int
    border_color: str
    border_width: int
    border_style: str
    shape: str
    label: str
    tooltip: str


@dataclass
class GapAnchorNode:
    """
    Gap Anchor Node (virtual node representing missing connections)

    This is NOT a real entity - it's a visual anchor that makes coverage gaps
    visible in the subgraph. Represents "N missing connections detected here".

    Design principles:
    - Visual: Empty circle with dashed border (obviously not a real node)
    - Position: Connected to parent node via dashed edge
    - Interactive: Click to see gap details and suggestions
    - Filterable: Can be hidden/shown via controls
    """
    id: str  # "gap:{parent_entity_id}#1"
    parent_node_id: str  # The real node ID (e.g., "n123")
    missing_count: int  # Number of missing connections
    gap_types: List[str]  # ["missing_doc_coverage", "missing_intra_capability"]
    suggestions: List[str]  # ["Add documentation", "Rebuild index"]

    # Visual encoding (special for gap anchors)
    visual: NodeVisual


@dataclass
class SubgraphNode:
    """
    Subgraph node (with cognitive attributes)

    Represents a single node in the subgraph with all cognitive properties:
    - Basic attributes (id, type, name)
    - Evidence attributes (evidence_count, coverage_sources)
    - Blind spot attributes (is_blind_spot, severity, type)
    - Topology attributes (in_degree, out_degree, distance)
    - Visual encoding (NodeVisual)
    """
    # Basic attributes
    id: str
    entity_type: str
    entity_key: str
    entity_name: str
    entity_id: int  # Internal DB ID

    # Evidence attributes (CORE)
    evidence_count: int  # Total evidence count for this node
    coverage_sources: List[str]  # ["git", "doc", "code"]
    evidence_density: float  # Evidence density (0-1)

    # Blind spot attributes (CORE)
    is_blind_spot: bool
    blind_spot_severity: Optional[float]  # 0-1
    blind_spot_type: Optional[str]
    blind_spot_reason: Optional[str]

    # Topology attributes
    in_degree: int  # Incoming edges
    out_degree: int  # Outgoing edges
    distance_from_seed: int  # Hops from seed node

    # Visual encoding (computed at runtime)
    visual: NodeVisual

    # Gap anchor metadata (for nodes with missing connections)
    missing_connections_count: int = 0  # Number of missing connections
    gap_types: List[str] = field(default_factory=list)  # Types of gaps

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        result = {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_key": self.entity_key,
            "entity_name": self.entity_name,
            "entity_id": self.entity_id,
            "evidence_count": self.evidence_count,
            "coverage_sources": self.coverage_sources,
            "evidence_density": self.evidence_density,
            "is_blind_spot": self.is_blind_spot,
            "blind_spot_severity": self.blind_spot_severity,
            "blind_spot_type": self.blind_spot_type,
            "blind_spot_reason": self.blind_spot_reason,
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "distance_from_seed": self.distance_from_seed,
            "missing_connections_count": self.missing_connections_count,
            "gap_types": self.gap_types,
            "visual": {
                "color": self.visual.color,
                "size": self.visual.size,
                "border_color": self.visual.border_color,
                "border_width": self.visual.border_width,
                "border_style": self.visual.border_style,
                "shape": self.visual.shape,
                "label": self.visual.label,
                "tooltip": self.visual.tooltip
            }
        }

        # Add suggestions for Gap Anchor Nodes
        if self.entity_type == "gap_anchor":
            result["suggestions"] = generate_gap_suggestions(self.gap_types)

        return result


@dataclass
class EdgeVisual:
    """
    Edge visual encoding (computed based on P2-1 rules)

    Attributes:
        width: Line width in pixels (1-4) - based on evidence_count
        color: Line color (hex) - based on evidence_types diversity
        style: "solid" / "dashed" / "dotted"
        opacity: Opacity (0-1) - based on confidence
        label: Display text
        tooltip: Hover tooltip text
    """
    width: int
    color: str
    style: str
    opacity: float
    label: str
    tooltip: str


@dataclass
class SubgraphEdge:
    """
    Subgraph edge (with cognitive attributes)

    Represents a single edge in the subgraph with all cognitive properties:
    - Basic attributes (id, source, target, type)
    - Evidence attributes (evidence_count, evidence_types, evidence_list)
    - Status attributes (status, is_weak, is_suspected)
    - Visual encoding (EdgeVisual)
    """
    # Basic attributes
    id: str
    source_id: str  # Node ID
    target_id: str  # Node ID
    edge_type: str
    edge_db_id: int  # Internal DB ID

    # Evidence attributes (CORE)
    evidence_count: int
    evidence_types: List[str]  # ["git", "doc", "code"]
    evidence_list: List[Dict]  # Full evidence chain
    confidence: float  # 0-1

    # Status attributes
    status: str  # "confirmed" / "suspected"
    is_weak: bool  # evidence_count < 3
    is_suspected: bool  # evidence_count = 0

    # Visual encoding (computed at runtime)
    visual: EdgeVisual

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "edge_db_id": self.edge_db_id,
            "evidence_count": self.evidence_count,
            "evidence_types": self.evidence_types,
            "evidence_list": self.evidence_list,
            "confidence": self.confidence,
            "status": self.status,
            "is_weak": self.is_weak,
            "is_suspected": self.is_suspected,
            "visual": {
                "width": self.visual.width,
                "color": self.visual.color,
                "style": self.visual.style,
                "opacity": self.visual.opacity,
                "label": self.visual.label,
                "tooltip": self.visual.tooltip
            }
        }


@dataclass
class SubgraphMetadata:
    """
    Subgraph metadata (summary statistics)

    Provides cognitive completeness metrics:
    - Node/edge counts
    - Coverage percentage
    - Evidence density
    - Blind spot counts
    - Missing connections
    """
    seed_entity: str
    k_hop: int
    total_nodes: int
    total_edges: int
    confirmed_edges: int
    suspected_edges: int

    # Cognitive completeness metrics
    coverage_percentage: float  # Node coverage (0-1)
    evidence_density: float  # Average evidence per edge
    blind_spot_count: int
    high_risk_blind_spot_count: int

    # Missing connections (空白区域)
    missing_connections_count: int
    coverage_gaps: List[Dict]  # [{"type": "...", "description": "..."}]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "seed_entity": self.seed_entity,
            "k_hop": self.k_hop,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "confirmed_edges": self.confirmed_edges,
            "suspected_edges": self.suspected_edges,
            "coverage_percentage": self.coverage_percentage,
            "evidence_density": self.evidence_density,
            "blind_spot_count": self.blind_spot_count,
            "high_risk_blind_spot_count": self.high_risk_blind_spot_count,
            "missing_connections_count": self.missing_connections_count,
            "coverage_gaps": self.coverage_gaps
        }


@dataclass
class SubgraphResult:
    """
    Subgraph query result (top-level response)

    Wraps the complete subgraph data with metadata and error info.
    """
    ok: bool
    data: Optional[Dict]  # {"nodes": [...], "edges": [...], "metadata": {...}}
    error: Optional[str]
    graph_version: str
    computed_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "graph_version": self.graph_version,
            "computed_at": self.computed_at
        }


# ============================================================================
# Visual Encoding Functions
# ============================================================================

def compute_node_visual(node: SubgraphNode) -> NodeVisual:
    """
    Compute node visual encoding based on P2-1 rules

    Encoding rules:
    - Color: Based on coverage_sources count (3=green, 2=blue, 1=orange, 0=red)
    - Size: Based on evidence_count and in_degree
    - Border: Red/orange for blind spots
    - Shape: Based on entity_type
    - Label: Formatted with coverage and evidence info

    Args:
        node: SubgraphNode with cognitive attributes

    Returns:
        NodeVisual with encoded visual properties
    """
    # Color: Based on coverage_sources diversity
    sources_count = len(node.coverage_sources)
    color_map = {
        0: "#FF0000",  # Red: No evidence (violation!)
        1: "#FFA000",  # Orange: Single source (weak)
        2: "#4A90E2",  # Blue: Two sources (medium)
        3: "#00C853",  # Green: Three sources (strong)
    }
    fill_color = color_map.get(min(sources_count, 3), "#FFA000")

    # Size: Based on evidence_count and in_degree
    base_size = 20
    evidence_bonus = min(20, node.evidence_count * 2)
    fan_in_bonus = min(15, node.in_degree * 3)
    seed_bonus = 10 if node.distance_from_seed == 0 else 0
    size = base_size + evidence_bonus + fan_in_bonus + seed_bonus

    # Border: Highlight blind spots
    if node.is_blind_spot and node.blind_spot_severity is not None:
        if node.blind_spot_severity >= 0.7:
            border_color = "#FF0000"  # Red: High risk
            border_width = 3
            border_style = "dashed"
        elif node.blind_spot_severity >= 0.4:
            border_color = "#FF6600"  # Orange: Medium risk
            border_width = 2
            border_style = "dashed"
        else:
            border_color = "#FFB300"  # Yellow: Low risk
            border_width = 2
            border_style = "dotted"
    else:
        border_color = fill_color
        border_width = 1
        border_style = "solid"

    # Shape: Based on entity_type
    shape_map = {
        "file": "circle",
        "capability": "square",
        "term": "diamond",
        "doc": "rectangle",
        "commit": "hexagon",
        "symbol": "ellipse"
    }
    shape = shape_map.get(node.entity_type, "circle")

    # Label: Formatted with coverage info
    coverage_pct = node.evidence_density * 100
    if coverage_pct >= 80:
        badge = "✅"
    elif coverage_pct >= 50:
        badge = "⚠️"
    else:
        badge = "❌"

    if node.is_blind_spot:
        badge = "⚠️ BLIND SPOT"

    label = f"{node.entity_name}\n{badge} {coverage_pct:.0f}% | {node.evidence_count} evidence"

    # Tooltip: Detailed info
    sources_str = ", ".join(node.coverage_sources) if node.coverage_sources else "None"
    tooltip = (
        f"Entity: {node.entity_key}\n"
        f"Type: {node.entity_type}\n"
        f"Coverage: {coverage_pct:.1f}%\n"
        f"Evidence: {node.evidence_count}\n"
        f"Sources: {sources_str}\n"
        f"In-Degree: {node.in_degree}\n"
        f"Out-Degree: {node.out_degree}\n"
    )

    if node.is_blind_spot:
        tooltip += (
            f"\n⚠️ BLIND SPOT:\n"
            f"Type: {node.blind_spot_type}\n"
            f"Severity: {node.blind_spot_severity:.2f}\n"
            f"Reason: {node.blind_spot_reason}\n"
        )

    return NodeVisual(
        color=fill_color,
        size=size,
        border_color=border_color,
        border_width=border_width,
        border_style=border_style,
        shape=shape,
        label=label,
        tooltip=tooltip
    )


def compute_edge_visual(edge: SubgraphEdge) -> EdgeVisual:
    """
    Compute edge visual encoding based on P2-1 rules

    Encoding rules:
    - Width: Based on evidence_count (1-4px)
    - Color: Based on evidence_types diversity
    - Style: Based on status (confirmed=solid, suspected=dashed)
    - Opacity: Based on confidence
    - Label: Formatted with evidence info

    Args:
        edge: SubgraphEdge with cognitive attributes

    Returns:
        EdgeVisual with encoded visual properties
    """
    # Width: Based on evidence_count
    count = edge.evidence_count
    if count == 0:
        width = 1
    elif count == 1:
        width = 1
    elif count <= 4:
        width = 2
    elif count <= 9:
        width = 3
    else:
        width = 4

    # Color: Based on evidence_types diversity
    if edge.is_suspected:
        color = "#CCCCCC"  # Gray: Suspected edge
    else:
        types_count = len(edge.evidence_types)
        color_map = {
            0: "#FF0000",  # Red: No evidence (should not happen)
            1: "#B0B0B0",  # Light gray: Single type
            2: "#4A90E2",  # Blue: Two types
            3: "#00C853",  # Green: Three types
        }
        color = color_map.get(min(types_count, 3), "#B0B0B0")

    # Style: Based on status
    if edge.is_suspected:
        style = "dashed"
    elif edge.edge_type == "mentions":
        style = "dotted"
    else:
        style = "solid"

    # Opacity: Based on confidence
    if edge.is_suspected:
        opacity = 0.3
    elif count == 1:
        opacity = 0.4
    elif count <= 4:
        opacity = 0.7
    else:
        opacity = 1.0

    # Label: Formatted with evidence info
    if edge.is_suspected:
        label = f"Suspected: {edge.edge_type}"
    else:
        types_str = "+".join(sorted(edge.evidence_types))
        label = f"{edge.edge_type} | {count} ({types_str})"

    # Tooltip: Detailed evidence list
    tooltip = (
        f"Edge: {edge.edge_type}\n"
        f"Evidence: {count}\n"
        f"Confidence: {edge.confidence:.2f}\n"
        f"Status: {edge.status}\n"
    )

    if edge.evidence_list:
        tooltip += "\nEvidence Sources:\n"
        for i, ev in enumerate(edge.evidence_list[:5], 1):  # Show first 5
            tooltip += f"{i}. {ev.get('source_type', 'unknown')}: {ev.get('source_ref', 'N/A')}\n"
        if len(edge.evidence_list) > 5:
            tooltip += f"... and {len(edge.evidence_list) - 5} more\n"

    return EdgeVisual(
        width=width,
        color=color,
        style=style,
        opacity=opacity,
        label=label,
        tooltip=tooltip
    )


# ============================================================================
# Core Query Engine (Phase 2)
# ============================================================================

def query_subgraph(
    store: SQLiteStore,
    seed: str,
    k_hop: int = 2,
    include_suspected: bool = False,
    min_evidence: int = 1
) -> SubgraphResult:
    """
    Query k-hop subgraph centered around seed entity

    Core workflow:
    1. Parse seed and find seed node
    2. BFS traverse k-hop neighborhood (only edges with evidence)
    3. Compute cognitive attributes for each node
    4. Compute cognitive attributes for each edge
    5. Detect missing connections (空白区域)
    6. Compute visual encoding
    7. Generate metadata

    Three Red Lines:
    - Red Line 1: All edges must have >= min_evidence (default: 1)
    - Red Line 2: Blind spot nodes must be marked (is_blind_spot = True)
    - Red Line 3: Missing connections must be detected and reported

    Args:
        store: SQLiteStore instance (must be connected)
        seed: Seed entity key (e.g., "file:manager.py", "capability:api")
        k_hop: Number of hops from seed (default: 2)
        include_suspected: Include suspected edges with no evidence (default: False)
        min_evidence: Minimum evidence count per edge (default: 1, enforces Red Line 1)

    Returns:
        SubgraphResult with nodes, edges, and metadata

    Examples:
        >>> from agentos.core.db import registry_db
        >>> conn = registry_db.get_db()
        >>> store = SQLiteStore.from_connection(conn)
        >>> result = query_subgraph(store, "file:manager.py", k_hop=2)
        >>> print(f"Nodes: {result.data['metadata']['total_nodes']}")
        >>> print(f"Edges: {result.data['metadata']['total_edges']}")
    """
    start_time = time.time()
    logger.info(f"Querying subgraph: seed={seed}, k_hop={k_hop}, min_evidence={min_evidence}")

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Step 1: Find seed node
        logger.debug("Step 1: Finding seed node")
        seed_node_id = find_seed_node(cursor, seed)
        if seed_node_id is None:
            logger.warning(f"Seed node not found: {seed}")
            return SubgraphResult(
                ok=False,
                data=None,
                error=f"Seed node not found: {seed}",
                graph_version="unknown",
                computed_at=utc_now_iso()
            )

        # Step 2: BFS k-hop traversal
        logger.debug(f"Step 2: BFS {k_hop}-hop traversal")
        subgraph_data = bfs_k_hop(cursor, seed_node_id, k_hop, min_evidence)
        node_ids = subgraph_data["node_ids"]
        edge_data = subgraph_data["edges"]

        logger.info(f"BFS found {len(node_ids)} nodes and {len(edge_data)} edges")

        # Step 3: Compute node cognitive attributes
        logger.debug("Step 3: Computing node cognitive attributes")
        nodes_dict = {}
        for node_id in node_ids:
            node_attrs = compute_node_attributes(cursor, node_id, seed_node_id, subgraph_data)
            nodes_dict[node_id] = node_attrs

        # Step 4: Compute edge cognitive attributes
        logger.debug("Step 4: Computing edge cognitive attributes")
        edges_list = []
        for edge_db_id, src_id, dst_id, edge_type in edge_data:
            edge_attrs = compute_edge_attributes(cursor, edge_db_id, src_id, dst_id, edge_type)
            if edge_attrs["evidence_count"] >= min_evidence or include_suspected:
                edges_list.append(edge_attrs)

        # Step 5: Detect blind spots (enriches nodes_dict)
        logger.debug("Step 5: Detecting blind spots")
        blind_spot_dict = detect_blind_spots_for_subgraph(store, list(node_ids))
        for node_id, blind_spot in blind_spot_dict.items():
            if node_id in nodes_dict:
                nodes_dict[node_id]["is_blind_spot"] = True
                nodes_dict[node_id]["blind_spot_severity"] = blind_spot.severity
                nodes_dict[node_id]["blind_spot_type"] = blind_spot.blind_spot_type.value
                nodes_dict[node_id]["blind_spot_reason"] = blind_spot.reason

        # Step 6: Build SubgraphNode and SubgraphEdge objects
        logger.debug("Step 6: Building node and edge objects")
        subgraph_nodes = []
        for node_id, attrs in nodes_dict.items():
            node = SubgraphNode(
                id=f"n{node_id}",
                entity_type=attrs["entity_type"],
                entity_key=attrs["entity_key"],
                entity_name=attrs["entity_name"],
                entity_id=node_id,
                evidence_count=attrs["evidence_count"],
                coverage_sources=attrs["coverage_sources"],
                evidence_density=attrs["evidence_density"],
                is_blind_spot=attrs["is_blind_spot"],
                blind_spot_severity=attrs.get("blind_spot_severity"),
                blind_spot_type=attrs.get("blind_spot_type"),
                blind_spot_reason=attrs.get("blind_spot_reason"),
                in_degree=attrs["in_degree"],
                out_degree=attrs["out_degree"],
                distance_from_seed=attrs["distance_from_seed"],
                visual=NodeVisual("", 0, "", 0, "", "", "", "")  # Placeholder
            )
            # Compute visual encoding
            node.visual = compute_node_visual(node)
            subgraph_nodes.append(node)

        subgraph_edges = []
        for edge_attrs in edges_list:
            edge = SubgraphEdge(
                id=f"e{edge_attrs['edge_db_id']}",
                source_id=f"n{edge_attrs['source_id']}",
                target_id=f"n{edge_attrs['target_id']}",
                edge_type=edge_attrs["edge_type"],
                edge_db_id=edge_attrs["edge_db_id"],
                evidence_count=edge_attrs["evidence_count"],
                evidence_types=edge_attrs["evidence_types"],
                evidence_list=edge_attrs["evidence_list"],
                confidence=edge_attrs["confidence"],
                status=edge_attrs["status"],
                is_weak=edge_attrs["is_weak"],
                is_suspected=edge_attrs["is_suspected"],
                visual=EdgeVisual(0, "", "", 0.0, "", "")  # Placeholder
            )
            # Compute visual encoding
            edge.visual = compute_edge_visual(edge)
            subgraph_edges.append(edge)

        # Step 7: Detect missing connections
        logger.debug("Step 7: Detecting missing connections")
        missing_connections = detect_missing_connections(cursor, subgraph_nodes, subgraph_edges)

        # Step 7.5: Inject Gap Anchor Nodes (RED LINE 3 visualization)
        logger.debug("Step 7.5: Injecting Gap Anchor Nodes")
        gap_anchors, gap_edges = inject_gap_anchors(subgraph_nodes, missing_connections)

        # Merge gap anchors and edges into result
        subgraph_nodes.extend(gap_anchors)
        subgraph_edges.extend(gap_edges)

        logger.info(f"Injected {len(gap_anchors)} Gap Anchor Nodes")

        # Step 8: Compute metadata
        logger.debug("Step 8: Computing metadata")
        metadata = compute_subgraph_metadata(seed, k_hop, subgraph_nodes, subgraph_edges, missing_connections)

        # Get graph version
        build_meta = store.get_last_build_metadata()
        graph_version = build_meta["graph_version"] if build_meta else "unknown"

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Subgraph query completed in {duration_ms}ms: "
            f"nodes={len(subgraph_nodes)}, edges={len(subgraph_edges)}, "
            f"missing={len(missing_connections)}"
        )

        return SubgraphResult(
            ok=True,
            data={
                "nodes": [n.to_dict() for n in subgraph_nodes],
                "edges": [e.to_dict() for e in subgraph_edges],
                "metadata": metadata.to_dict()
            },
            error=None,
            graph_version=graph_version,
            computed_at=utc_now_iso()
        )

    except Exception as e:
        logger.error(f"Failed to query subgraph: {e}", exc_info=True)
        return SubgraphResult(
            ok=False,
            data=None,
            error=str(e),
            graph_version="unknown",
            computed_at=utc_now_iso()
        )


# ============================================================================
# Helper Functions
# ============================================================================

def find_seed_node(cursor, seed: str) -> Optional[int]:
    """
    Find seed node by parsing seed string

    Seed format examples:
    - "file:manager.py" -> type='file', key='manager.py'
    - "capability:api" -> type='capability', key='api'
    - "term:authentication" -> type='term', key='authentication'

    Args:
        cursor: SQLite cursor
        seed: Seed entity key

    Returns:
        Entity ID or None if not found
    """
    # Parse seed format: "type:key"
    if ":" not in seed:
        logger.warning(f"Invalid seed format (expected 'type:key'): {seed}")
        return None

    parts = seed.split(":", 1)
    entity_type = parts[0]
    entity_key = parts[1]

    cursor.execute("""
        SELECT id FROM entities
        WHERE type = ? AND (key = ? OR key LIKE ?)
    """, (entity_type, entity_key, f"%{entity_key}"))

    result = cursor.fetchone()
    if result:
        return result[0]

    return None


def bfs_k_hop(cursor, seed_id: int, k: int, min_evidence: int) -> Dict:
    """
    BFS k-hop traversal (only edges with evidence)

    RED LINE 1 ENFORCEMENT: Only traverse edges with >= min_evidence

    Algorithm:
    1. Initialize visited = {seed_id}, queue = [(seed_id, 0)]
    2. While queue not empty:
       - Dequeue (node_id, depth)
       - If depth >= k, skip
       - Query all adjacent edges with evidence >= min_evidence
       - For each unvisited neighbor, add to visited and queue
    3. Return {node_ids, edges}

    Args:
        cursor: SQLite cursor
        seed_id: Seed node entity ID
        k: Maximum number of hops
        min_evidence: Minimum evidence count per edge

    Returns:
        Dict with {
            "node_ids": Set[int],
            "edges": List[Tuple[edge_id, src_id, dst_id, type]]
        }
    """
    visited = {seed_id}
    queue = deque([(seed_id, 0)])
    edges = []
    distance_map = {seed_id: 0}  # Track distance from seed

    while queue:
        node_id, depth = queue.popleft()

        if depth >= k:
            continue

        # Query outgoing edges with evidence >= min_evidence
        cursor.execute("""
            SELECT DISTINCT e.id, e.src_entity_id, e.dst_entity_id, e.type,
                   COUNT(ev.id) AS evidence_count
            FROM edges e
            LEFT JOIN evidence ev ON ev.edge_id = e.id
            WHERE e.src_entity_id = ?
            GROUP BY e.id
            HAVING evidence_count >= ?
        """, (node_id, min_evidence))

        outgoing_edges = cursor.fetchall()

        for edge_id, src_id, dst_id, edge_type, _ in outgoing_edges:
            edges.append((edge_id, src_id, dst_id, edge_type))

            if dst_id not in visited:
                visited.add(dst_id)
                distance_map[dst_id] = depth + 1
                queue.append((dst_id, depth + 1))

        # Query incoming edges with evidence >= min_evidence
        cursor.execute("""
            SELECT DISTINCT e.id, e.src_entity_id, e.dst_entity_id, e.type,
                   COUNT(ev.id) AS evidence_count
            FROM edges e
            LEFT JOIN evidence ev ON ev.edge_id = e.id
            WHERE e.dst_entity_id = ?
            GROUP BY e.id
            HAVING evidence_count >= ?
        """, (node_id, min_evidence))

        incoming_edges = cursor.fetchall()

        for edge_id, src_id, dst_id, edge_type, _ in incoming_edges:
            # Avoid duplicate edges
            if (edge_id, src_id, dst_id, edge_type) not in edges:
                edges.append((edge_id, src_id, dst_id, edge_type))

            if src_id not in visited:
                visited.add(src_id)
                distance_map[src_id] = depth + 1
                queue.append((src_id, depth + 1))

    return {
        "node_ids": visited,
        "edges": edges,
        "distance_map": distance_map
    }


def compute_node_attributes(cursor, node_id: int, seed_id: int, subgraph_data: Dict) -> Dict:
    """
    Compute cognitive attributes for a node

    Computes:
    1. evidence_count: Total evidence for edges touching this node
    2. coverage_sources: Distinct evidence sources (git/doc/code)
    3. evidence_density: Normalized evidence density
    4. in_degree / out_degree: Topology within subgraph
    5. distance_from_seed: Hops from seed node

    Args:
        cursor: SQLite cursor
        node_id: Entity ID
        seed_id: Seed entity ID
        subgraph_data: BFS result with distance_map

    Returns:
        Dict with node attributes
    """
    # Get entity basic info
    cursor.execute("""
        SELECT type, key, name, attrs_json
        FROM entities
        WHERE id = ?
    """, (node_id,))

    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Node not found: {node_id}")

    entity_type, entity_key, entity_name, attrs_json = row

    # Evidence count and sources
    cursor.execute("""
        SELECT DISTINCT ev.source_type
        FROM evidence ev
        JOIN edges e ON e.id = ev.edge_id
        WHERE e.src_entity_id = ? OR e.dst_entity_id = ?
    """, (node_id, node_id))

    evidence_sources = cursor.fetchall()
    coverage_sources = [row[0] for row in evidence_sources]

    cursor.execute("""
        SELECT COUNT(DISTINCT ev.id)
        FROM evidence ev
        JOIN edges e ON e.id = ev.edge_id
        WHERE e.src_entity_id = ? OR e.dst_entity_id = ?
    """, (node_id, node_id))

    evidence_count = cursor.fetchone()[0]

    # Evidence density (normalized)
    # Simple heuristic: density = min(1.0, evidence_count / 10)
    evidence_density = min(1.0, evidence_count / 10.0)

    # In/out degree (within subgraph)
    node_ids_in_subgraph = subgraph_data["node_ids"]

    cursor.execute("""
        SELECT COUNT(*)
        FROM edges
        WHERE src_entity_id = ? AND dst_entity_id IN ({})
    """.format(",".join("?" * len(node_ids_in_subgraph))),
    (node_id, *node_ids_in_subgraph))

    out_degree = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM edges
        WHERE dst_entity_id = ? AND src_entity_id IN ({})
    """.format(",".join("?" * len(node_ids_in_subgraph))),
    (node_id, *node_ids_in_subgraph))

    in_degree = cursor.fetchone()[0]

    # Distance from seed
    distance_from_seed = subgraph_data["distance_map"].get(node_id, 999)

    return {
        "entity_type": entity_type,
        "entity_key": entity_key,
        "entity_name": entity_name,
        "evidence_count": evidence_count,
        "coverage_sources": coverage_sources,
        "evidence_density": evidence_density,
        "is_blind_spot": False,  # Will be enriched later
        "blind_spot_severity": None,
        "blind_spot_type": None,
        "blind_spot_reason": None,
        "in_degree": in_degree,
        "out_degree": out_degree,
        "distance_from_seed": distance_from_seed
    }


def compute_edge_attributes(cursor, edge_db_id: int, src_id: int, dst_id: int, edge_type: str) -> Dict:
    """
    Compute cognitive attributes for an edge

    Computes:
    1. evidence_count: Number of evidence records
    2. evidence_types: Distinct evidence types (git/doc/code)
    3. evidence_list: Full evidence records
    4. confidence: Computed confidence score
    5. status: "confirmed" or "suspected"

    Args:
        cursor: SQLite cursor
        edge_db_id: Edge ID
        src_id: Source entity ID
        dst_id: Destination entity ID
        edge_type: Edge type

    Returns:
        Dict with edge attributes
    """
    # Query evidence
    cursor.execute("""
        SELECT id, source_type, source_ref, span_json, attrs_json
        FROM evidence
        WHERE edge_id = ?
    """, (edge_db_id,))

    evidence_rows = cursor.fetchall()
    evidence_count = len(evidence_rows)

    evidence_types = list(set(row[1] for row in evidence_rows))
    evidence_list = [
        {
            "id": row[0],
            "source_type": row[1],
            "source_ref": row[2],
            "span": json.loads(row[3]) if row[3] else {},
            "attrs": json.loads(row[4]) if row[4] else {}
        }
        for row in evidence_rows
    ]

    # Compute confidence
    # Simple heuristic:
    # - 1 evidence, 1 type -> 0.4
    # - 3 evidence, 2 types -> 0.7
    # - 5+ evidence, 3 types -> 1.0
    if evidence_count == 0:
        confidence = 0.0
    elif evidence_count == 1:
        confidence = 0.4
    elif evidence_count <= 2:
        confidence = 0.5 + (0.1 * len(evidence_types))
    elif evidence_count <= 4:
        confidence = 0.6 + (0.1 * len(evidence_types))
    else:
        confidence = min(1.0, 0.7 + (0.1 * len(evidence_types)))

    # Status
    if evidence_count == 0:
        status = "suspected"
    else:
        status = "confirmed"

    is_weak = evidence_count < 3
    is_suspected = evidence_count == 0

    return {
        "edge_db_id": edge_db_id,
        "source_id": src_id,
        "target_id": dst_id,
        "edge_type": edge_type,
        "evidence_count": evidence_count,
        "evidence_types": evidence_types,
        "evidence_list": evidence_list,
        "confidence": confidence,
        "status": status,
        "is_weak": is_weak,
        "is_suspected": is_suspected
    }


def detect_blind_spots_for_subgraph(store: SQLiteStore, node_ids: List[int]) -> Dict[int, BlindSpot]:
    """
    Detect blind spots for nodes in subgraph

    Runs blind spot detection and filters results to only nodes in subgraph.

    Args:
        store: SQLiteStore instance
        node_ids: List of entity IDs in subgraph

    Returns:
        Dict mapping node_id -> BlindSpot
    """
    try:
        # Run full blind spot detection
        blind_spot_report = detect_blind_spots(store)

        # Build map of node_id -> BlindSpot
        blind_spot_dict = {}

        conn = store.connect()
        cursor = conn.cursor()

        for blind_spot in blind_spot_report.blind_spots:
            # Find entity ID by key
            cursor.execute("""
                SELECT id FROM entities
                WHERE key = ?
            """, (blind_spot.entity_key,))

            result = cursor.fetchone()
            if result:
                entity_id = result[0]
                if entity_id in node_ids:
                    blind_spot_dict[entity_id] = blind_spot

        return blind_spot_dict

    except Exception as e:
        logger.warning(f"Blind spot detection failed: {e}")
        return {}


def detect_missing_connections(cursor, nodes: List[SubgraphNode], edges: List[SubgraphEdge]) -> List[Dict]:
    """
    Detect missing connections (空白区域)

    RED LINE 3 ENFORCEMENT: Must detect and report missing connections

    Implements 3 detection scenarios:
    1. Code dependency without documentation
    2. Same capability but no connection
    3. Blind spot suggested connections

    Args:
        cursor: SQLite cursor
        nodes: List of SubgraphNode
        edges: List of SubgraphEdge

    Returns:
        List of missing connection dicts (with source_id for anchoring)
    """
    missing = []

    # Scenario 1: Code depends_on but no doc references
    depends_on_edges = [e for e in edges if e.edge_type == "depends_on"]
    for edge in depends_on_edges:
        # Check if target has any doc references
        has_doc_ref = any(
            e.edge_type == "references" and
            e.target_id == edge.target_id and
            "doc" in e.evidence_types
            for e in edges
        )

        if not has_doc_ref:
            target_node = next((n for n in nodes if n.id == edge.target_id), None)
            if target_node:
                missing.append({
                    "type": "missing_doc_coverage",
                    "description": f"Code depends on {target_node.entity_name} but no doc explains this relationship",
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "severity": 0.6,
                    "anchor_to": edge.target_id  # Anchor gap to target node
                })

    # Scenario 2: Same capability but no connection
    capability_map: Dict[str, List[SubgraphNode]] = {}
    for node in nodes:
        if node.entity_type == "file":
            # Extract capability from entity_key or attrs (simplified)
            # In a real implementation, would query attrs_json for "capability" field
            pass  # Skip for now, requires capability extraction logic

    # Scenario 3: Blind spot suggested connections
    blind_spot_nodes = [n for n in nodes if n.is_blind_spot]
    for node in blind_spot_nodes:
        if node.blind_spot_type == "high_fan_in_undocumented":
            missing.append({
                "type": "missing_documentation_edge",
                "description": f"{node.entity_name} has {node.in_degree} dependents but no documentation",
                "source_id": None,
                "target_id": node.id,
                "severity": 0.8,
                "anchor_to": node.id  # Anchor gap to blind spot node
            })

    return missing


def compute_gap_anchor_visual(missing_count: int) -> NodeVisual:
    """
    Compute visual encoding for Gap Anchor Node

    Visual characteristics:
    - Empty circle (white fill) with dashed border
    - Gray color (#9ca3af)
    - Size scales with missing_count (15-40px)
    - "?" icon + count in label
    - Clear tooltip explaining the gap

    Args:
        missing_count: Number of missing connections

    Returns:
        NodeVisual with gap anchor styling
    """
    # Size: 15-40px based on missing_count (capped at 40)
    base_size = 15
    scale_factor = min(2, missing_count / 5)  # Cap scaling at 2x
    size = int(base_size + (25 * scale_factor))
    size = min(size, 40)  # Hard cap at 40px

    # Label: "?" + count
    label = f"❓ {missing_count}"

    # Tooltip
    tooltip = (
        f"{missing_count} missing connection{'s' if missing_count > 1 else ''} detected.\n"
        f"Click for details and suggestions."
    )

    return NodeVisual(
        color="#ffffff",  # White fill (empty circle)
        size=size,
        border_color="#9ca3af",  # Gray border
        border_width=2,
        border_style="dashed",  # Dashed border (clearly virtual)
        shape="ellipse",  # Circle shape
        label=label,
        tooltip=tooltip
    )


def generate_gap_suggestions(gap_types: List[str]) -> List[str]:
    """
    Generate actionable suggestions based on gap types

    Maps gap types to user-friendly suggestions.

    Args:
        gap_types: List of gap type identifiers

    Returns:
        List of suggestion strings
    """
    suggestions = []

    if "missing_doc_coverage" in gap_types:
        suggestions.append("Add documentation mentioning this relationship")

    if "missing_intra_capability" in gap_types:
        suggestions.append("Increase k-hop to explore more connections")

    if "missing_suspected_dependency" in gap_types:
        suggestions.append("Rebuild index to update detected dependencies")

    if "missing_documentation_edge" in gap_types:
        suggestions.append("Add documentation for this high-impact component")

    if not suggestions:
        suggestions.append("Lower min_evidence filter to see weak connections")

    return suggestions


def inject_gap_anchors(
    nodes: List[SubgraphNode],
    coverage_gaps: List[Dict]
) -> Tuple[List[SubgraphNode], List[SubgraphEdge]]:
    """
    Inject Gap Anchor Nodes for visualization (RED LINE 3)

    This is the core implementation of "making gaps visible on the graph".

    Algorithm:
    1. Group coverage_gaps by anchor_to node
    2. For each node with gaps, create ONE Gap Anchor Node
    3. Create dashed edge: parent_node -> gap_anchor
    4. Apply special visual encoding (empty circle, dashed border)

    Gap Anchor Nodes:
    - entity_type: "gap_anchor" (special type)
    - id: "gap:{parent_id}#1"
    - distance_from_seed: -1 (marks as virtual)
    - Not included in topology calculations

    Args:
        nodes: Current subgraph nodes
        coverage_gaps: List of detected gaps (from detect_missing_connections)

    Returns:
        Tuple of (gap_anchor_nodes, gap_edges)
    """
    gap_anchors = []
    gap_edges = []

    # 1. Group gaps by anchor_to node
    gaps_by_node: Dict[str, List[Dict]] = {}
    for gap in coverage_gaps:
        anchor_to = gap.get("anchor_to")
        if anchor_to:
            if anchor_to not in gaps_by_node:
                gaps_by_node[anchor_to] = []
            gaps_by_node[anchor_to].append(gap)

    # 2. Create Gap Anchor Node for each node with gaps
    for parent_id, gaps in gaps_by_node.items():
        missing_count = len(gaps)

        # Extract gap types
        gap_types = [gap["type"] for gap in gaps]

        # Generate suggestions
        suggestions = generate_gap_suggestions(gap_types)

        # Create Gap Anchor Node ID
        gap_id = f"gap:{parent_id}#1"

        # Compute visual encoding
        visual = compute_gap_anchor_visual(missing_count)

        # Create Gap Anchor Node (as SubgraphNode with special entity_type)
        gap_anchor = SubgraphNode(
            id=gap_id,
            entity_type="gap_anchor",  # SPECIAL TYPE
            entity_key=gap_id,
            entity_name=f"Gap: {missing_count}",
            entity_id=-1,  # Virtual node (no DB entity)
            evidence_count=0,
            coverage_sources=[],
            evidence_density=0.0,
            is_blind_spot=False,
            blind_spot_severity=None,
            blind_spot_type=None,
            blind_spot_reason=None,
            in_degree=1,  # 1 incoming edge (from parent)
            out_degree=0,
            distance_from_seed=-1,  # Marks as virtual (not part of k-hop)
            visual=visual,
            missing_connections_count=missing_count,
            gap_types=gap_types
        )

        gap_anchors.append(gap_anchor)

        # 3. Create dashed edge: parent -> gap_anchor
        gap_edge = SubgraphEdge(
            id=f"edge:gap:{parent_id}",
            source_id=parent_id,
            target_id=gap_id,
            edge_type="coverage_gap",  # SPECIAL TYPE
            edge_db_id=-1,  # Virtual edge (no DB edge)
            evidence_count=0,
            evidence_types=[],
            evidence_list=[],
            confidence=0.0,
            status="virtual",  # Mark as virtual
            is_weak=False,
            is_suspected=False,
            visual=EdgeVisual(
                width=1,
                color="#9ca3af",  # Gray
                style="dashed",  # Dashed line (clearly virtual)
                opacity=0.6,
                label="",  # No label (too cluttered)
                tooltip=f"{missing_count} missing connection{'s' if missing_count > 1 else ''}: {', '.join(suggestions)}"
            )
        )

        gap_edges.append(gap_edge)

        # 4. Update parent node with gap metadata
        parent_node = next((n for n in nodes if n.id == parent_id), None)
        if parent_node:
            parent_node.missing_connections_count = missing_count
            parent_node.gap_types = gap_types

    return gap_anchors, gap_edges


def compute_subgraph_metadata(
    seed: str,
    k_hop: int,
    nodes: List[SubgraphNode],
    edges: List[SubgraphEdge],
    missing: List[Dict]
) -> SubgraphMetadata:
    """
    Compute subgraph metadata

    Computes:
    - Node/edge counts
    - Coverage percentage
    - Evidence density
    - Blind spot counts
    - Missing connections

    Args:
        seed: Seed entity key
        k_hop: K-hop value
        nodes: List of SubgraphNode
        edges: List of SubgraphEdge
        missing: List of missing connections

    Returns:
        SubgraphMetadata with summary statistics
    """
    total_nodes = len(nodes)
    total_edges = len(edges)
    confirmed_edges = len([e for e in edges if e.status == "confirmed"])
    suspected_edges = len([e for e in edges if e.status == "suspected"])

    # Coverage percentage (nodes with evidence > 0)
    nodes_with_evidence = len([n for n in nodes if n.evidence_count > 0])
    coverage_percentage = nodes_with_evidence / total_nodes if total_nodes > 0 else 0.0

    # Evidence density (average evidence per edge)
    if total_edges > 0:
        total_evidence = sum(e.evidence_count for e in edges)
        evidence_density = total_evidence / total_edges
    else:
        evidence_density = 0.0

    # Blind spot counts
    blind_spot_nodes = [n for n in nodes if n.is_blind_spot]
    blind_spot_count = len(blind_spot_nodes)
    high_risk_blind_spot_count = len([n for n in blind_spot_nodes if n.blind_spot_severity and n.blind_spot_severity >= 0.7])

    # Missing connections
    missing_connections_count = len(missing)
    coverage_gaps = [
        {
            "type": m["type"],
            "description": m["description"]
        }
        for m in missing
    ]

    return SubgraphMetadata(
        seed_entity=seed,
        k_hop=k_hop,
        total_nodes=total_nodes,
        total_edges=total_edges,
        confirmed_edges=confirmed_edges,
        suspected_edges=suspected_edges,
        coverage_percentage=coverage_percentage,
        evidence_density=evidence_density,
        blind_spot_count=blind_spot_count,
        high_risk_blind_spot_count=high_risk_blind_spot_count,
        missing_connections_count=missing_connections_count,
        coverage_gaps=coverage_gaps
    )
