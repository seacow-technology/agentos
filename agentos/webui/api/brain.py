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
- GET /api/brain/time/health - Get cognitive health report (P3-C Time)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.core.brain.service import (
    get_stats,
    query_why,
    query_impact,
    query_trace,
    query_subgraph as query_subgraph_service,
    BrainIndexJob,
    QueryResult,
    compute_coverage,
    detect_blind_spots,
    autocomplete_suggest,
    SubgraphResult,
)
from agentos.core.brain.store import SQLiteStore

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Caching (Phase 3)
# ============================================================================

# Simple in-memory cache (production: use Redis)
_subgraph_cache: Dict[str, Tuple[Dict, datetime]] = {}
_cache_ttl = timedelta(minutes=15)


def get_cached_subgraph(cache_key: str) -> Optional[Dict]:
    """
    Get cached subgraph result

    Args:
        cache_key: Cache key (seed + k_hop + min_evidence)

    Returns:
        Cached result or None if expired/not found
    """
    if cache_key in _subgraph_cache:
        cached_data, cached_time = _subgraph_cache[cache_key]

        # Check if expired
        if datetime.now() - cached_time < _cache_ttl:
            logger.debug(f"Cache hit: {cache_key}")
            return cached_data
        else:
            # Expired, delete
            del _subgraph_cache[cache_key]
            logger.debug(f"Cache expired: {cache_key}")

    return None


def cache_subgraph(cache_key: str, data: Dict):
    """
    Cache subgraph result

    Args:
        cache_key: Cache key
        data: Subgraph data to cache
    """
    _subgraph_cache[cache_key] = (data, datetime.now())
    logger.debug(f"Cached: {cache_key}")


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

def validate_seed_format(seed: str) -> Tuple[str, str]:
    """
    Validate seed format and parse type and key

    Args:
        seed: Seed entity string (e.g., "file:manager.py")

    Returns:
        (entity_type, entity_key)

    Raises:
        ValueError: If format is invalid
    """
    if ":" not in seed:
        raise ValueError(f"Invalid seed format: '{seed}'. Expected 'type:key'.")

    parts = seed.split(":", 1)
    entity_type, entity_key = parts[0], parts[1]

    # Validate type
    valid_types = ["file", "capability", "term", "doc", "commit", "symbol"]
    if entity_type not in valid_types:
        raise ValueError(
            f"Invalid entity type: '{entity_type}'. Must be one of {valid_types}."
        )

    # Validate key non-empty
    if not entity_key.strip():
        raise ValueError("Entity key cannot be empty.")

    return entity_type, entity_key


def get_brain_db_path() -> str:
    """
    Get the BrainOS database path from environment variable or default location.

    Returns:
        Path to BrainOS database
    """
    # Use environment variable with fallback to default location
    env_path = os.getenv("BRAINOS_DB_PATH")
    if env_path:
        return str(Path(env_path))

    # Default: use component_db_path
    from agentos.core.storage.paths import component_db_path
    return str(component_db_path("brainos"))


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


@router.get(
    "/subgraph",
    summary="Query Subgraph",
    description="Query a k-hop subgraph centered at a seed entity. Returns nodes, edges, and metadata with cognitive attributes.",
    responses={
        200: {
            "description": "Successful query",
            "content": {
                "application/json": {
                    "example": {
                        "ok": True,
                        "data": {
                            "nodes": [],
                            "edges": [],
                            "metadata": {}
                        },
                        "error": None,
                        "cached": False
                    }
                }
            }
        },
        400: {
            "description": "Invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "ok": False,
                        "data": None,
                        "error": "Invalid seed format. Expected 'type:key', got '...'"
                    }
                }
            }
        },
        404: {
            "description": "Index or entity not found",
            "content": {
                "application/json": {
                    "example": {
                        "ok": False,
                        "data": None,
                        "error": "BrainOS index not found. Run '/brain build' first."
                    }
                }
            }
        }
    },
    tags=["BrainOS"]
)
async def get_subgraph(
    seed: str = Query(
        ...,
        description="Seed entity (e.g., 'file:manager.py', 'capability:api', 'term:auth')",
        pattern=r"^(file|capability|term|doc|commit|symbol):.+"
    ),
    k_hop: int = Query(
        2,
        description="Number of hops from seed",
        ge=1,
        le=3
    ),
    min_evidence: int = Query(
        1,
        description="Minimum evidence count per edge",
        ge=1,
        le=10
    ),
    include_suspected: bool = Query(
        False,
        description="Include suspected edges (dashed lines)"
    ),
    project_id: Optional[str] = Query(
        None,
        description="Project ID filter"
    )
) -> Dict[str, Any]:
    """
    Query subgraph centered at a seed entity.

    Returns a subgraph with nodes, edges, and metadata. All nodes and edges
    include cognitive attributes (evidence count, coverage sources, blind spots).

    Example:
        GET /api/brain/subgraph?seed=file:manager.py&k_hop=2&min_evidence=1

    Response:
        {
            "ok": true,
            "data": {
                "nodes": [
                    {
                        "id": "entity_123",
                        "entity_type": "file",
                        "entity_key": "manager.py",
                        "entity_name": "Task Manager",
                        "evidence_count": 15,
                        "coverage_sources": ["git", "doc", "code"],
                        "is_blind_spot": false,
                        "visual": {
                            "color": "#10b981",
                            "size": 35,
                            "border_color": "#374151",
                            "label": "manager.py\\n✅ 100% | 15 evidence"
                        },
                        ...
                    },
                    ...
                ],
                "edges": [
                    {
                        "id": "edge_456",
                        "source_id": "entity_123",
                        "target_id": "entity_789",
                        "edge_type": "imports",
                        "evidence_count": 3,
                        "evidence_types": ["git", "code"],
                        "confidence": 0.7,
                        "visual": {
                            "width": 2,
                            "color": "#3b82f6",
                            "style": "solid",
                            "label": "imports | 3"
                        },
                        ...
                    },
                    ...
                ],
                "metadata": {
                    "seed_entity": "file:manager.py",
                    "k_hop": 2,
                    "total_nodes": 12,
                    "total_edges": 18,
                    "coverage_percentage": 0.83,
                    "evidence_density": 8.5,
                    "blind_spot_count": 2,
                    "missing_connections_count": 3,
                    "coverage_gaps": [],
                    "graph_version": "main_abc123_2026-01-30",
                    "computed_at": "2026-01-30T12:34:56Z"
                }
            },
            "error": null,
            "cached": false
        }

    Error Response (400):
        {
            "ok": false,
            "data": null,
            "error": "Invalid seed format. Expected 'type:key', got '...'"
        }

    Error Response (404):
        {
            "ok": false,
            "data": null,
            "error": "Seed entity not found: file:nonexistent.py"
        }

    Error Response (500):
        {
            "ok": false,
            "data": null,
            "error": "Internal server error: {details}"
        }
    """
    try:
        # 1. Validate seed format
        try:
            validate_seed_format(seed)
        except ValueError as e:
            return {
                "ok": False,
                "data": None,
                "error": str(e)
            }

        # 2. Generate cache key
        cache_key = f"subgraph:{seed}:{k_hop}:{min_evidence}:{include_suspected}"

        # 3. Try to get from cache
        cached_result = get_cached_subgraph(cache_key)
        if cached_result:
            return {
                "ok": True,
                "data": cached_result,
                "error": None,
                "cached": True
            }

        # 4. Get BrainOS database path
        db_path = get_brain_db_path()

        if not Path(db_path).exists():
            return {
                "ok": False,
                "data": None,
                "error": "BrainOS index not found. Run '/brain build' to create the index first."
            }

        # 5. Query subgraph
        store = SQLiteStore(db_path)
        store.connect()

        try:
            result: SubgraphResult = query_subgraph_service(
                store,
                seed=seed,
                k_hop=k_hop,
                min_evidence=min_evidence,
                include_suspected=include_suspected
            )
        finally:
            store.close()

        # 6. Handle errors
        if not result.ok:
            if "not found" in result.error.lower():
                return {
                    "ok": False,
                    "data": None,
                    "error": f"Seed entity not found: '{seed}'. This entity may not be indexed yet."
                }
            else:
                return {
                    "ok": False,
                    "data": None,
                    "error": result.error
                }

        # 7. Cache successful result
        if result.data:
            cache_subgraph(cache_key, result.data)

        # 8. Return response
        return {
            "ok": True,
            "data": result.data,
            "error": None,
            "cached": False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_subgraph")
        return {
            "ok": False,
            "data": None,
            "error": f"Internal server error. Please contact support. Details: {str(e)}"
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


# ============================================================================
# P3-C: Time API (Cognitive Health Monitoring)
# ============================================================================

@router.get("/time/health")
async def get_health_report(
    window_days: int = Query(30, description="Time window in days", ge=1, le=365),
    granularity: str = Query("day", description="Granularity (day/week)")
) -> Dict[str, Any]:
    """
    获取认知健康报告（P3-C Time）

    核心：回答"我的理解是在变好，还是在变坏？"

    Args:
        window_days: 时间窗口（天）
        granularity: 粒度（day/week）

    Returns:
        {
            "ok": true,
            "data": {
                "window_start": "...",
                "window_end": "...",
                "current_health_level": "GOOD",
                "current_health_score": 72.5,
                "coverage_trend": {...},
                "blind_spot_trend": {...},
                "warnings": [...],
                "recommendations": [...]
            }
        }
    """
    try:
        db_path = get_brain_db_path()

        # Check if database exists
        if not Path(db_path).exists():
            return {
                "ok": False,
                "data": None,
                "error": "BrainOS database not found. Please run 'brain build' first."
            }

        # Connect to database
        store = SQLiteStore(str(db_path))
        store.connect()

        try:
            # Import here to avoid circular dependency
            from agentos.core.brain.cognitive_time.trend_analyzer import analyze_trends

            # Analyze trends
            report = analyze_trends(store, window_days, granularity)

            # Convert to dict
            import dataclasses
            report_dict = dataclasses.asdict(report)

            # Convert enums to strings
            report_dict["current_health_level"] = report.current_health_level.value
            report_dict["coverage_trend"]["direction"] = report.coverage_trend.direction.value
            report_dict["blind_spot_trend"]["direction"] = report.blind_spot_trend.direction.value
            report_dict["evidence_density_trend"]["direction"] = report.evidence_density_trend.direction.value

            # Convert source_migration enums
            for key in report_dict["source_migration"]:
                report_dict["source_migration"][key] = report.source_migration[key].value

            return {
                "ok": True,
                "data": report_dict,
                "error": None
            }

        finally:
            store.close()

    except Exception as e:
        logger.exception("Error in get_health_report")
        return {
            "ok": False,
            "data": None,
            "error": f"Failed to generate health report: {str(e)}"
        }
