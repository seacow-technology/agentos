"""
BrainOS API - WebUI Integration

Provides REST API endpoints for BrainOS query and dashboard features.

Endpoints:
- GET /api/brain/stats - Get BrainOS statistics and dashboard metrics
- POST /api/brain/query/why - Why query (trace origins)
- POST /api/brain/query/impact - Impact query (dependency analysis)
- POST /api/brain/query/trace - Trace query (evolution timeline)
- POST /api/brain/query/subgraph - Subgraph query (k-hop neighbors)
- GET /api/brain/coverage - Get cognitive coverage metrics
- GET /api/brain/blind-spots - Get cognitive blind spots
- GET /api/brain/autocomplete - Get cognitive-safe autocomplete suggestions
- GET /api/brain/suggest - Autocomplete suggestions (deprecated, use /autocomplete)
- GET /api/brain/resolve - Resolve entity reference to URL
- POST /api/brain/build - Rebuild BrainOS index (admin only)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.core.brain.service import (
    get_stats,
    query_why,
    query_impact,
    query_trace,
    query_subgraph,
    BrainIndexJob,
    QueryResult,
    compute_coverage,
    detect_blind_spots,
    autocomplete_suggest,
)
from agentos.core.brain.store import SQLiteStore

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for query endpoints"""
    seed: str = Field(..., description="Entity seed (e.g., 'file:path', 'doc:name', 'term:keyword')")
    depth: Optional[int] = Field(1, description="Query depth (for impact/subgraph queries)")
    k_hop: Optional[int] = Field(1, description="K-hop for subgraph queries")


class BuildRequest(BaseModel):
    """Request model for build endpoint"""
    force: bool = Field(False, description="Force rebuild even if index is up-to-date")


# ============================================================================
# Helper Functions
# ============================================================================

def get_brain_db_path() -> str:
    """
    Get the BrainOS database path.

    Returns:
        Path to BrainOS database
    """
    # Default: .brainos/v0.1_mvp.db in current directory
    brain_dir = Path(".brainos")
    db_path = brain_dir / "v0.1_mvp.db"

    # Fallback to environment variable if set
    env_path = os.getenv("BRAINOS_DB_PATH")
    if env_path:
        db_path = Path(env_path)

    return str(db_path)


def check_entity_exists(store: SQLiteStore, seed: str) -> bool:
    """
    Check if entity exists in the knowledge graph.

    Args:
        store: SQLiteStore instance
        seed: Entity seed (e.g., 'file:path', 'term:keyword')

    Returns:
        True if entity exists, False otherwise
    """
    try:
        # Parse seed format
        if ':' in seed:
            entity_type, entity_key = seed.split(':', 1)
        else:
            # No type prefix, try as term query
            entity_type = 'term'
            entity_key = seed

        # Query database
        conn = store.conn
        cursor = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE type = ? AND key = ?",
            (entity_type, entity_key)
        )
        count = cursor.fetchone()[0]
        return count > 0
    except Exception:
        return False


def compute_result_coverage_info(result: QueryResult) -> Dict[str, Any]:
    """
    Compute coverage information for a query result.

    Args:
        result: QueryResult object

    Returns:
        Coverage info dict with evidence sources and coverage score
    """
    # Collect evidence source types
    evidence_sources = set()
    for ev in result.evidence:
        source_type = ev.get('source_type', 'unknown')
        if 'commit' in source_type or 'git' in source_type:
            evidence_sources.add('git')
        elif 'doc' in source_type:
            evidence_sources.add('doc')
        elif 'import' in source_type or 'dependency' in source_type:
            evidence_sources.add('code')

    # Calculate coverage (based on 3 sources)
    source_coverage = len(evidence_sources) / 3.0  # 0.0-1.0

    return {
        "evidence_sources": sorted(list(evidence_sources)),
        "source_coverage": source_coverage,
        "source_count": len(evidence_sources),
        "evidence_count": len(result.evidence),
        "explanation": generate_coverage_explanation(evidence_sources)
    }


def generate_coverage_explanation(sources: set) -> str:
    """Generate user-friendly coverage explanation"""
    if len(sources) == 3:
        return "This explanation is based on all sources (Git + Doc + Code)."
    elif len(sources) == 2:
        missing = {'git', 'doc', 'code'} - sources
        return f"This explanation is based on {'/'.join(sorted(sources))}. Missing: {'/'.join(sorted(missing))}."
    elif len(sources) == 1:
        source = list(sources)[0]
        return f"This explanation is based only on {source}. Limited coverage."
    else:
        return "No evidence sources found. Result may be incomplete."


def transform_to_viewmodel(result: QueryResult, query_type: str) -> Dict[str, Any]:
    """
    Transform QueryResult to WebUI ViewModel.

    Args:
        result: QueryResult from BrainOS query
        query_type: Type of query ('why', 'impact', 'trace', 'subgraph')

    Returns:
        Dictionary in WebUI-friendly format
    """
    # Compute coverage info for this query result
    coverage_info = compute_result_coverage_info(result)

    base = {
        "graph_version": result.graph_version,
        "seed": result.seed,
        "query_type": query_type,
        "stats": result.stats,
        "coverage_info": coverage_info,
    }

    if query_type == 'why':
        return {
            **base,
            "summary": generate_summary(result, query_type),
            "paths": [
                {
                    "nodes": [node_to_vm(n) for n in path.get('nodes', [])],
                    "edges": [edge_to_vm(e) for e in path.get('edges', [])]
                }
                for path in result.result.get('paths', [])
            ],
            "evidence": [evidence_to_vm(e) for e in result.evidence]
        }

    elif query_type == 'impact':
        return {
            **base,
            "summary": generate_summary(result, query_type),
            "affected_nodes": result.result.get('affected_nodes', []),
            "risk_hints": result.result.get('risk_hints', []),
            "evidence": [evidence_to_vm(e) for e in result.evidence]
        }

    elif query_type == 'trace':
        return {
            **base,
            "summary": generate_summary(result, query_type),
            "timeline": result.result.get('timeline', []),
            "nodes": [node_to_vm(n) for n in result.result.get('nodes', [])],
            "evidence": [evidence_to_vm(e) for e in result.evidence]
        }

    elif query_type == 'subgraph':
        return {
            **base,
            "summary": generate_summary(result, query_type),
            "nodes": [node_to_vm(n) for n in result.result.get('nodes', [])],
            "edges": [edge_to_vm(e) for e in result.result.get('edges', [])],
            "evidence": [evidence_to_vm(e) for e in result.evidence]
        }

    # Default: return raw result
    return {**base, "result": result.result, "evidence": result.evidence}


def node_to_vm(node: Dict[str, Any]) -> Dict[str, Any]:
    """Convert node to ViewModel"""
    node_type = node.get('type', 'unknown').lower()
    node_key = node.get('key', '')

    return {
        "type": node_type,
        "name": node.get('name', ''),
        "key": node_key,
        "url": resolve_entity_to_url(node_key),
        "icon": get_icon_for_type(node_type),
        "created_at": node.get('created_at', 0)
    }


def edge_to_vm(edge: Dict[str, Any]) -> Dict[str, Any]:
    """Convert edge to ViewModel"""
    return {
        "type": edge.get('type', 'unknown'),
        "confidence": edge.get('confidence', 1.0),
        "label": edge.get('type', 'unknown').replace('_', ' ').title()
    }


def evidence_to_vm(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Convert evidence to ViewModel"""
    source_ref = evidence.get('source_ref', '')

    return {
        "source_type": evidence.get('source_type', ''),
        "source_ref": source_ref,
        "url": resolve_evidence_to_url(evidence),
        "span": evidence.get('span', {}),
        "label": format_evidence_label(evidence),
        "confidence": evidence.get('confidence', 1.0)
    }


def generate_summary(result: QueryResult, query_type: str) -> str:
    """Generate human-readable summary for query result"""
    stats = result.stats

    if query_type == 'why':
        path_count = stats.get('path_count', 0)
        evidence_count = stats.get('evidence_count', 0)
        if path_count == 0:
            return "No origin paths found for this entity."
        return f"Found {path_count} path(s) explaining this entity, supported by {evidence_count} evidence item(s)."

    elif query_type == 'impact':
        affected_count = len(result.result.get('affected_nodes', []))
        if affected_count == 0:
            return "No downstream dependencies found."
        return f"This change affects {affected_count} downstream node(s)."

    elif query_type == 'trace':
        event_count = len(result.result.get('timeline', []))
        if event_count == 0:
            return "No evolution history found."
        return f"Found {event_count} event(s) in the evolution timeline."

    elif query_type == 'subgraph':
        node_count = len(result.result.get('nodes', []))
        edge_count = len(result.result.get('edges', []))
        return f"Subgraph contains {node_count} node(s) and {edge_count} edge(s)."

    return "Query completed successfully."


def get_icon_for_type(entity_type: str) -> str:
    """Get Material icon name for entity type"""
    icon_map = {
        'file': 'description',
        'commit': 'commit',
        'doc': 'article',
        'term': 'label',
        'capability': 'extension',
        'module': 'folder',
        'dependency': 'link',
    }
    return icon_map.get(entity_type.lower(), 'help_outline')


def resolve_entity_to_url(entity_key: str) -> Optional[str]:
    """
    Resolve entity reference to WebUI URL.

    Args:
        entity_key: Entity key (e.g., 'file:path', 'doc:name')

    Returns:
        WebUI URL or None
    """
    if not entity_key:
        return None

    if entity_key.startswith('file:'):
        # Map to context view with file filter
        file_path = entity_key[5:]
        return f"/#/context?file={file_path}"

    elif entity_key.startswith('doc:'):
        # Map to docs or knowledge view
        doc_name = entity_key[4:]
        return f"/#/knowledge?doc={doc_name}"

    elif entity_key.startswith('commit:'):
        # Map to history view with commit filter
        commit_hash = entity_key[7:]
        return f"/#/history?commit={commit_hash}"

    elif entity_key.startswith('capability:'):
        # Map to extensions view
        cap_name = entity_key[11:]
        return f"/#/extensions?name={cap_name}"

    return None


def resolve_evidence_to_url(evidence: Dict[str, Any]) -> Optional[str]:
    """
    Resolve evidence to viewable URL.

    Args:
        evidence: Evidence dictionary

    Returns:
        WebUI URL or None
    """
    source_type = evidence.get('source_type', '')
    source_ref = evidence.get('source_ref', '')
    span = evidence.get('span', {})

    if source_type == 'git_commit':
        return f"/#/history?commit={source_ref}"

    elif source_type == 'doc_reference':
        line = span.get('line', '')
        if line:
            return f"/#/knowledge?doc={source_ref}&line={line}"
        return f"/#/knowledge?doc={source_ref}"

    elif source_type == 'code_dependency':
        return f"/#/context?file={source_ref}"

    return None


def format_evidence_label(evidence: Dict[str, Any]) -> str:
    """Format evidence as human-readable label"""
    source_type = evidence.get('source_type', '')
    source_ref = evidence.get('source_ref', '')
    span = evidence.get('span', {})

    if source_type == 'git_commit':
        return f"Git commit: {source_ref[:8]}"

    elif source_type == 'doc_reference':
        line = span.get('line', '')
        if line:
            return f"Doc reference: {source_ref} (line {line})"
        return f"Doc reference: {source_ref}"

    elif source_type == 'code_dependency':
        return f"Code dependency: {source_ref}"

    return f"{source_type}: {source_ref}"


def calculate_coverage(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate cognitive coverage metrics.

    Args:
        stats: Raw statistics from BrainOS

    Returns:
        Coverage metrics dictionary
    """
    # TODO: Implement coverage calculation based on entity/edge analysis
    # For now, return placeholder metrics
    return {
        "doc_refs_pct": 0,  # Percentage of files with doc references
        "dep_graph_pct": 0,  # Percentage of files in dependency graph
        "git_coverage": True,
        "doc_coverage": True,
        "code_coverage": True,
    }


def find_blind_spots(db_path: str, limit: int = 3) -> List[Dict[str, str]]:
    """
    Find top blind spots in knowledge graph.

    Args:
        db_path: Path to BrainOS database
        limit: Max number of blind spots to return

    Returns:
        List of blind spot descriptions
    """
    # TODO: Implement blind spot detection
    # For now, return empty list
    return []


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/stats")
async def get_brain_stats() -> Dict[str, Any]:
    """
    Get BrainOS statistics and dashboard metrics.

    Returns:
        Dictionary containing:
        - entities: Entity count
        - edges: Edge count
        - evidence: Evidence count
        - last_build: Build metadata
        - coverage: Coverage metrics
        - blind_spots: List of blind spots
    """
    try:
        db_path = get_brain_db_path()

        # Check if database exists
        if not Path(db_path).exists():
            return {
                "ok": False,
                "error": "BrainOS index not found",
                "hint": "Run BrainIndexJob to build the index first",
                "stats": None
            }

        # Get raw statistics
        stats = get_stats(db_path)

        # Enhance with coverage and blind spots
        enhanced_stats = {
            **stats,
            "coverage": calculate_coverage(stats),
            "blind_spots": find_blind_spots(db_path, limit=3)
        }

        return {
            "ok": True,
            "data": enhanced_stats,
            "error": None
        }

    except Exception as e:
        logger.error(f"Failed to get BrainOS stats: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "hint": "Check if BrainOS index is properly initialized",
            "stats": None
        }


@router.post("/query/why")
async def api_query_why(request: QueryRequest) -> Dict[str, Any]:
    """
    Why query - Trace entity origins.

    Args:
        request: QueryRequest with seed entity

    Returns:
        Query result with paths and evidence
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            raise HTTPException(
                status_code=404,
                detail="BrainOS index not found. Build index first."
            )

        result = query_why(db_path, request.seed)
        viewmodel = transform_to_viewmodel(result, 'why')

        # Add reason field for empty results
        reason = None
        if viewmodel.get('paths') is not None and len(viewmodel.get('paths', [])) == 0:
            # Check if entity exists in graph
            store = SQLiteStore(db_path)
            entity_exists = check_entity_exists(store, request.seed)
            if entity_exists:
                reason = "no_coverage"  # Entity exists but no document references
            else:
                reason = "entity_not_indexed"  # Entity not indexed

        return {
            "ok": True,
            "data": viewmodel,
            "error": None,
            "reason": reason
        }

    except Exception as e:
        logger.error(f"Why query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/impact")
async def api_query_impact(request: QueryRequest) -> Dict[str, Any]:
    """
    Impact query - Analyze downstream dependencies.

    Args:
        request: QueryRequest with seed entity and optional depth

    Returns:
        Query result with affected nodes and risk hints
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            raise HTTPException(
                status_code=404,
                detail="BrainOS index not found. Build index first."
            )

        result = query_impact(db_path, request.seed, depth=request.depth or 1)
        viewmodel = transform_to_viewmodel(result, 'impact')

        # Add reason field for empty results
        reason = None
        if len(viewmodel.get('affected_nodes', [])) == 0:
            # Check if entity exists in graph
            store = SQLiteStore(db_path)
            entity_exists = check_entity_exists(store, request.seed)
            if entity_exists:
                reason = "no_coverage"  # Entity exists but no downstream dependencies
            else:
                reason = "entity_not_indexed"  # Entity not indexed

        return {
            "ok": True,
            "data": viewmodel,
            "error": None,
            "reason": reason
        }

    except Exception as e:
        logger.error(f"Impact query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/trace")
async def api_query_trace(request: QueryRequest) -> Dict[str, Any]:
    """
    Trace query - Track entity evolution over time.

    Args:
        request: QueryRequest with seed entity

    Returns:
        Query result with timeline and events
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            raise HTTPException(
                status_code=404,
                detail="BrainOS index not found. Build index first."
            )

        result = query_trace(db_path, request.seed)
        viewmodel = transform_to_viewmodel(result, 'trace')

        # Add reason field for empty results
        reason = None
        if len(viewmodel.get('timeline', [])) == 0:
            # Check if entity exists in graph
            store = SQLiteStore(db_path)
            entity_exists = check_entity_exists(store, request.seed)
            if entity_exists:
                reason = "no_coverage"  # Entity exists but no evolution history
            else:
                reason = "entity_not_indexed"  # Entity not indexed

        return {
            "ok": True,
            "data": viewmodel,
            "error": None,
            "reason": reason
        }

    except Exception as e:
        logger.error(f"Trace query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/subgraph")
async def api_query_subgraph(request: QueryRequest) -> Dict[str, Any]:
    """
    Subgraph query - Extract k-hop neighborhood.

    Args:
        request: QueryRequest with seed entity and optional k_hop

    Returns:
        Query result with nodes and edges
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            raise HTTPException(
                status_code=404,
                detail="BrainOS index not found. Build index first."
            )

        result = query_subgraph(db_path, request.seed, k_hop=request.k_hop or 1)
        viewmodel = transform_to_viewmodel(result, 'subgraph')

        # Add reason field for empty results
        reason = None
        if len(viewmodel.get('nodes', [])) == 0:
            # Check if entity exists in graph
            store = SQLiteStore(db_path)
            entity_exists = check_entity_exists(store, request.seed)
            if entity_exists:
                reason = "no_coverage"  # Entity exists but no neighbors
            else:
                reason = "entity_not_indexed"  # Entity not indexed

        return {
            "ok": True,
            "data": viewmodel,
            "error": None,
            "reason": reason
        }

    except Exception as e:
        logger.error(f"Subgraph query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autocomplete")
async def get_autocomplete(
    prefix: str = Query(..., description="Entity prefix to search for"),
    limit: int = Query(10, description="Max suggestions to return", ge=1, le=50),
    entity_types: str = Query(None, description="Comma-separated entity types (e.g., 'file,capability')"),
    include_warnings: bool = Query(False, description="Include moderate-risk blind spots")
) -> Dict[str, Any]:
    """
    Get cognitive-safe autocomplete suggestions.

    Only suggests entities that meet ALL of these criteria:
    - Indexed in BrainOS graph
    - Have >= 1 evidence
    - Coverage != 0 (at least one source: Git/Doc/Code)
    - Not high-risk blind spot (severity < 0.7)

    This is a cognitive guardrail, not a search optimizer.

    Args:
        prefix: Entity prefix to search for
        limit: Maximum number of suggestions to return (1-50)
        entity_types: Optional comma-separated entity types (e.g., 'file,capability')
        include_warnings: Whether to include moderate-risk blind spots (default: False)

    Returns:
        Dictionary containing:
        - suggestions: List of safe autocomplete suggestions
        - total_matches: Number of entities that matched the prefix
        - filtered_out: Number of entities filtered out for safety
        - filter_reason: Explanation of filtering decisions
        - graph_version: Graph version identifier
        - computed_at: ISO timestamp
    """
    try:
        logger.info(f"Autocomplete request: prefix='{prefix}', limit={limit}, entity_types='{entity_types}', include_warnings={include_warnings}")

        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            logger.warning("BrainOS index not found")
            return {
                "ok": False,
                "data": None,
                "error": "BrainOS index not found. Build index first."
            }

        # Parse entity_types parameter
        entity_types_list = None
        if entity_types:
            entity_types_list = [t.strip() for t in entity_types.split(',') if t.strip()]
            logger.debug(f"Parsed entity types: {entity_types_list}")

        # Call autocomplete engine
        store = SQLiteStore(db_path)
        store.connect()

        result = autocomplete_suggest(
            store,
            prefix=prefix,
            limit=limit,
            entity_types=entity_types_list,
            include_warnings=include_warnings
        )

        store.close()

        # Transform to API response format
        response_data = {
            "suggestions": [
                {
                    "entity_type": s.entity_type,
                    "entity_key": s.entity_key,
                    "entity_name": s.entity_name,
                    "safety_level": s.safety_level.value,
                    "evidence_count": s.evidence_count,
                    "coverage_sources": s.coverage_sources,
                    "is_blind_spot": s.is_blind_spot,
                    "blind_spot_severity": s.blind_spot_severity,
                    "blind_spot_reason": s.blind_spot_reason,
                    "display_text": s.display_text,
                    "hint_text": s.hint_text
                }
                for s in result.suggestions
            ],
            "total_matches": result.total_matches,
            "filtered_out": result.filtered_out,
            "filter_reason": result.filter_reason,
            "graph_version": result.graph_version,
            "computed_at": result.computed_at
        }

        logger.info(
            f"Autocomplete completed: {len(result.suggestions)} suggestions "
            f"({result.filtered_out} filtered out of {result.total_matches} total)"
        )

        return {
            "ok": True,
            "data": response_data,
            "error": None
        }

    except Exception as e:
        logger.error(f"Autocomplete failed: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }


@router.get("/suggest")
async def api_suggest(
    entity_type: Optional[str] = Query(None, description="Entity type filter (file, doc, term, capability)"),
    prefix: str = Query("", description="Search prefix")
) -> Dict[str, Any]:
    """
    Get autocomplete suggestions for entity search.

    DEPRECATED: Use /api/brain/autocomplete instead.
    This endpoint is maintained for backward compatibility.

    Args:
        entity_type: Optional entity type filter
        prefix: Search prefix

    Returns:
        List of matching entities
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            return {"ok": True, "data": [], "error": None}

        # TODO: Implement entity search with prefix matching
        # For now, return empty list
        suggestions = []

        return {
            "ok": True,
            "data": suggestions,
            "error": None
        }

    except Exception as e:
        logger.error(f"Suggest failed: {e}", exc_info=True)
        return {"ok": False, "data": [], "error": str(e)}


@router.get("/resolve")
async def api_resolve(ref: str = Query(..., description="Entity reference to resolve")) -> Dict[str, Any]:
    """
    Resolve entity reference to WebUI URL.

    Args:
        ref: Entity reference (e.g., 'file:path', 'doc:name')

    Returns:
        URL for entity or None
    """
    try:
        url = resolve_entity_to_url(ref)

        return {
            "ok": True,
            "data": {"url": url},
            "error": None
        }

    except Exception as e:
        logger.error(f"Resolve failed: {e}", exc_info=True)
        return {"ok": False, "data": None, "error": str(e)}


@router.get("/coverage")
async def get_coverage() -> Dict[str, Any]:
    """
    Get cognitive coverage metrics.

    Returns coverage statistics showing what BrainOS knows vs. what exists.
    Coverage is not test coverage, but "cognitive coverage" - measuring how much
    of the codebase is understood by BrainOS based on evidence from Git, Docs, and Code.

    Returns:
        Dictionary containing:
        - total_files: Total number of files in the graph
        - covered_files: Number of files with at least 1 evidence
        - code_coverage: Ratio of covered files to total (0.0-1.0)
        - git_covered_files: Files covered by git commits
        - doc_covered_files: Files covered by documentation
        - dep_covered_files: Files in dependency graph
        - doc_coverage: Ratio of doc-covered files to total
        - dependency_coverage: Ratio of dep-covered files to total
        - uncovered_files: List of file keys with zero evidence
        - evidence_distribution: Distribution of evidence counts
        - graph_version: Graph version identifier
        - computed_at: ISO timestamp when metrics were computed
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            return {
                "ok": False,
                "data": None,
                "error": "BrainOS index not found. Build index first."
            }

        store = SQLiteStore(db_path)
        store.connect()

        metrics = compute_coverage(store)

        store.close()

        return {
            "ok": True,
            "data": {
                "total_files": metrics.total_files,
                "covered_files": metrics.covered_files,
                "code_coverage": metrics.code_coverage,
                "git_covered_files": metrics.git_covered_files,
                "doc_covered_files": metrics.doc_covered_files,
                "dep_covered_files": metrics.dep_covered_files,
                "doc_coverage": metrics.doc_coverage,
                "dependency_coverage": metrics.dependency_coverage,
                "uncovered_files": metrics.uncovered_files,
                "evidence_distribution": metrics.evidence_distribution,
                "graph_version": metrics.graph_version,
                "computed_at": metrics.computed_at
            },
            "error": None
        }

    except Exception as e:
        logger.error(f"Failed to get coverage: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }


@router.get("/blind-spots")
async def get_blind_spots(
    threshold: int = Query(5, description="High fan-in threshold"),
    max_results: int = Query(50, description="Max blind spots to return")
) -> Dict[str, Any]:
    """
    Get cognitive blind spots.

    Returns list of areas where BrainOS knows it doesn't know enough - important
    entities that lack sufficient documentation or explanation despite being
    critical to the system.

    Three types of blind spots:
    1. High Fan-In Undocumented: Critical files with many dependents but no docs
    2. Capability Without Implementation: Declared capabilities with no code
    3. Trace Discontinuity: Active files with git history but no documented evolution

    Args:
        threshold: Minimum fan-in count to trigger Type 1 detection (default: 5)
        max_results: Maximum number of blind spots to return (default: 50)

    Returns:
        Dictionary containing:
        - total_blind_spots: Total number of blind spots detected
        - by_type: Count of blind spots by type
        - by_severity: Count by severity category (high/medium/low)
        - blind_spots: List of blind spot objects with details
        - graph_version: Graph version identifier
        - computed_at: ISO timestamp when report was generated
    """
    try:
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            return {
                "ok": False,
                "data": None,
                "error": "BrainOS index not found. Build index first."
            }

        store = SQLiteStore(db_path)
        store.connect()

        report = detect_blind_spots(store, high_fan_in_threshold=threshold, max_results=max_results)

        store.close()

        return {
            "ok": True,
            "data": {
                "total_blind_spots": report.total_blind_spots,
                "by_type": {k.value: v for k, v in report.by_type.items()},
                "by_severity": report.by_severity,
                "blind_spots": [
                    {
                        "entity_type": bs.entity_type,
                        "entity_key": bs.entity_key,
                        "entity_name": bs.entity_name,
                        "blind_spot_type": bs.blind_spot_type.value,
                        "severity": bs.severity,
                        "reason": bs.reason,
                        "metrics": bs.metrics,
                        "suggested_action": bs.suggested_action,
                        "detected_at": bs.detected_at
                    }
                    for bs in report.blind_spots
                ],
                "graph_version": report.graph_version,
                "computed_at": report.computed_at
            },
            "error": None
        }

    except Exception as e:
        logger.error(f"Failed to get blind spots: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }


@router.post("/build")
async def api_build(request: BuildRequest) -> Dict[str, Any]:
    """
    Rebuild BrainOS index (admin only).

    Args:
        request: BuildRequest with force flag

    Returns:
        Build result with manifest
    """
    try:
        # TODO: Add admin authentication check

        db_path = get_brain_db_path()
        repo_path = os.getcwd()

        logger.info(f"Starting BrainOS index build: repo={repo_path}, db={db_path}")

        # Run index job
        result = BrainIndexJob.run(
            repo_path=repo_path,
            db_path=db_path
        )

        return {
            "ok": True,
            "data": {
                "success": True,
                "manifest": result.manifest.to_dict(),
                "graph_version": result.manifest.graph_version
            },
            "error": None
        }

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
            "hint": "Check logs for detailed error information"
        }
