"""
BrainOS Service Module

Provides BrainOS query service interfaces and index build capabilities.

M1 Services:
1. Index Build: Extract and store knowledge graph (Git extractor)
2. Statistics: Query counts and build metadata

M2 Services:
- WhyQuery: Trace back to evidence (ADR/Doc/Commit)
- ImpactQuery: Impact analysis (dependency graph)
- TraceQuery: Evolution tracking (time series)
- SubgraphQuery: Subgraph extraction (around seed nodes)

P1 Services:
- Coverage: Cognitive completeness metrics (code/doc/dependency coverage)
- BlindSpot: Cognitive blind spot detection (high fan-in, missing impl, trace gaps)
- Autocomplete: Cognitive guardrail for user input (only suggest safe entities)
"""

from .brain_service import BrainService
from .index_job import BrainIndexJob, BuildResult
from .stats import get_stats
from .query_why import query_why, QueryResult
from .query_impact import query_impact
from .query_trace import query_trace
from .subgraph import (
    query_subgraph,
    SubgraphNode,
    SubgraphEdge,
    SubgraphResult,
    SubgraphMetadata,
    NodeVisual,
    EdgeVisual,
    compute_node_visual,
    compute_edge_visual
)
from .coverage import compute_coverage, CoverageMetrics
from .blind_spot import (
    detect_blind_spots,
    BlindSpot,
    BlindSpotReport,
    BlindSpotType,
    calculate_severity
)
from .autocomplete import (
    autocomplete_suggest,
    AutocompleteResult,
    AutocompleteSuggestion,
    EntitySafety
)

__all__ = [
    # M1: Build and Stats
    "BrainService",
    "BrainIndexJob",
    "BuildResult",
    "get_stats",

    # M2: Query Services
    "query_why",
    "query_impact",
    "query_trace",
    "QueryResult",

    # P2: Subgraph Query (P2-2)
    "query_subgraph",
    "SubgraphNode",
    "SubgraphEdge",
    "SubgraphResult",
    "SubgraphMetadata",
    "NodeVisual",
    "EdgeVisual",
    "compute_node_visual",
    "compute_edge_visual",

    # P1: Coverage, Blind Spot, and Autocomplete
    "compute_coverage",
    "CoverageMetrics",
    "detect_blind_spots",
    "BlindSpot",
    "BlindSpotReport",
    "BlindSpotType",
    "calculate_severity",
    "autocomplete_suggest",
    "AutocompleteResult",
    "AutocompleteSuggestion",
    "EntitySafety",
]
