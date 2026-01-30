"""
BrainOS Autocomplete Suggestion Engine (Cognitive Guardrail)

This is NOT a search engine optimization tool, but a COGNITIVE CONSTITUTION ENFORCER.

Autocomplete = Cognitive Boundary Guardrail

Core Mission:
- NOT "improve hit rate"
- NOT "faster typing"
- NOT "fuzzy matching"
- ONLY ONE THING: Only allow users to move along "structures that BrainOS has understood
  and has evidence chains for"

Without Autocomplete subgraph, we have "beautiful but dishonest cognitive interface".

Hard Acceptance Criteria (Cognitive Constitution):
Autocomplete ONLY suggests entities that satisfy ALL 4 conditions:

1. Indexed: Entity exists in entities table
2. Has Evidence Chain: >= 1 Evidence record
3. Coverage != 0: At least one evidence type (Git/Doc/Code)
4. Not High-Risk Blind Spot: Blind Spot severity < 0.7 (or explicitly marked with warning)

Otherwise:
- Do NOT suggest
- Do NOT autocomplete
- Do NOT "guess what you want to ask"

This is a marker of cognitive maturity - the system recognizing its own boundaries
and only offering paths it can actually explain.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..store import SQLiteStore
from .blind_spot import detect_blind_spots, BlindSpot, BlindSpotType

logger = logging.getLogger(__name__)


class EntitySafety(Enum):
    """Entity safety level for autocomplete suggestions."""
    SAFE = "safe"  # Meets all 4 criteria
    WARNING = "warning"  # Moderate blind spot risk (0.4-0.7)
    DANGEROUS = "dangerous"  # High blind spot risk (>=0.7)
    UNVERIFIED = "unverified"  # No evidence or not indexed


@dataclass
class AutocompleteSuggestion:
    """
    Autocomplete suggestion with cognitive safety information.

    This is not just a search result - it's a cognitive safety assessment
    for whether the user should be allowed to ask about this entity.

    Attributes:
        entity_type: Type of entity ('file', 'capability', 'term', 'doc')
        entity_key: Unique key for the entity
        entity_name: Display name of the entity
        safety_level: Safety level (SAFE/WARNING/DANGEROUS/UNVERIFIED)
        evidence_count: Number of evidence records supporting this entity
        coverage_sources: List of evidence sources (e.g., ['git', 'doc'])
        is_blind_spot: Whether this entity is a known blind spot
        blind_spot_severity: Blind spot severity score (0.0-1.0) if applicable
        blind_spot_reason: Explanation of blind spot if applicable
        display_text: Text to display to user
        hint_text: Additional hint/warning text
    """

    # Entity identification
    entity_type: str
    entity_key: str
    entity_name: str

    # Cognitive safety information
    safety_level: EntitySafety
    evidence_count: int
    coverage_sources: List[str]

    # Blind spot information
    is_blind_spot: bool
    blind_spot_severity: Optional[float]
    blind_spot_reason: Optional[str]

    # Display information
    display_text: str
    hint_text: str

    def to_dict(self) -> Dict:
        """Convert suggestion to dictionary for serialization."""
        return {
            "entity_type": self.entity_type,
            "entity_key": self.entity_key,
            "entity_name": self.entity_name,
            "safety_level": self.safety_level.value,
            "evidence_count": self.evidence_count,
            "coverage_sources": self.coverage_sources,
            "is_blind_spot": self.is_blind_spot,
            "blind_spot_severity": self.blind_spot_severity,
            "blind_spot_reason": self.blind_spot_reason,
            "display_text": self.display_text,
            "hint_text": self.hint_text
        }


@dataclass
class AutocompleteResult:
    """
    Autocomplete result with filtering metadata.

    Attributes:
        suggestions: List of suggestions that passed cognitive safety filters
        total_matches: Original number of matches (before filtering)
        filtered_out: Number of entities filtered out for safety reasons
        filter_reason: Explanation of filtering decisions
        graph_version: Graph version identifier
        computed_at: ISO timestamp when result was computed
    """

    suggestions: List[AutocompleteSuggestion]
    total_matches: int
    filtered_out: int
    filter_reason: str

    # Metadata
    graph_version: str
    computed_at: str

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization."""
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "total_matches": self.total_matches,
            "filtered_out": self.filtered_out,
            "filter_reason": self.filter_reason,
            "graph_version": self.graph_version,
            "computed_at": self.computed_at
        }


def autocomplete_suggest(
    store: SQLiteStore,
    prefix: str,
    limit: int = 10,
    entity_types: Optional[List[str]] = None,
    include_warnings: bool = False
) -> AutocompleteResult:
    """
    Provide cognitively safe autocomplete suggestions.

    This is a COGNITIVE FILTER, not a search engine. Only suggests entities
    that BrainOS has actually understood and can explain with evidence.

    Args:
        store: SQLiteStore instance with active connection
        prefix: User input prefix to match against
        limit: Maximum number of suggestions to return (default: 10)
        entity_types: Optional list of entity types to filter (e.g., ['file', 'capability'])
        include_warnings: Whether to include moderate-risk blind spots (default: False)

    Returns:
        AutocompleteResult with filtered suggestions

    Examples:
        >>> store = SQLiteStore("./brainos.db")
        >>> store.connect()
        >>> result = autocomplete_suggest(store, "task", limit=5)
        >>> print(f"Safe suggestions: {len(result.suggestions)}")
        >>> print(f"Filtered out: {result.filtered_out}")
        >>> for suggestion in result.suggestions:
        ...     print(f"  {suggestion.display_text} - {suggestion.hint_text}")
        >>> store.close()

    Notes:
        - Returns empty result on error rather than crashing
        - Applies all 4 hard criteria (indexed, evidence, coverage, non-dangerous)
        - Results sorted by safety level first, then evidence count
        - High-risk blind spots (severity >= 0.7) excluded by default
    """
    logger.info(f"Autocomplete suggest: prefix='{prefix}', limit={limit}, types={entity_types}")
    start_time = datetime.now(timezone.utc)

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Get graph version
        metadata = store.get_last_build_metadata()
        graph_version = metadata['graph_version'] if metadata else 'unknown'

        # Step 1: Find matching entities (raw matches)
        logger.debug("Step 1: Finding matching entities")
        raw_matches = _find_matching_entities(cursor, prefix, entity_types)
        total_matches = len(raw_matches)
        logger.info(f"Found {total_matches} raw matches")

        if total_matches == 0:
            logger.info("No matches found")
            return _empty_result(graph_version, start_time, "No matching entities found")

        # Step 2: Get blind spots for risk assessment
        logger.debug("Step 2: Detecting blind spots for risk assessment")
        blind_spots_report = detect_blind_spots(store, high_fan_in_threshold=5, max_results=100)
        blind_spot_map = _build_blind_spot_map(blind_spots_report.blind_spots)
        logger.debug(f"Found {len(blind_spot_map)} blind spots")

        # Step 3: Filter and enrich each entity with cognitive safety info
        logger.debug("Step 3: Applying cognitive filters")
        suggestions = []
        unverified_count = 0
        dangerous_count = 0

        for entity_id, entity_type, entity_key, entity_name in raw_matches:
            # Check evidence (hard criterion 2)
            evidence_count = _count_evidence(cursor, entity_id)
            if evidence_count == 0:
                logger.debug(f"Filtered out {entity_key}: no evidence")
                unverified_count += 1
                continue

            # Check coverage (hard criterion 3)
            coverage_sources = _get_coverage_sources(cursor, entity_id)
            if len(coverage_sources) == 0:
                logger.debug(f"Filtered out {entity_key}: zero coverage")
                unverified_count += 1
                continue

            # Check blind spot status (hard criterion 4)
            blind_spot = blind_spot_map.get((entity_type, entity_key))

            if blind_spot:
                if blind_spot.severity >= 0.7:
                    # High-risk blind spot - exclude by default
                    logger.debug(f"Filtered out {entity_key}: high-risk blind spot (severity={blind_spot.severity:.2f})")
                    dangerous_count += 1
                    if not include_warnings:
                        continue

            # Create suggestion
            suggestion = _create_suggestion(
                entity_type, entity_key, entity_name,
                evidence_count, coverage_sources, blind_spot
            )
            suggestions.append(suggestion)

        logger.info(
            f"After filtering: {len(suggestions)} safe, "
            f"{unverified_count} unverified, {dangerous_count} dangerous"
        )

        # Step 4: Sort by safety level and evidence quality
        suggestions.sort(key=lambda s: (
            s.safety_level.value,  # SAFE < WARNING < DANGEROUS
            -s.evidence_count,  # More evidence = better
            -len(s.coverage_sources),  # More coverage = better
            s.entity_name  # Alphabetical
        ))

        # Step 5: Apply limit
        limited_suggestions = suggestions[:limit]

        # Step 6: Generate filter report
        filtered_out = total_matches - len(limited_suggestions)
        filter_reason = (
            f"Filtered out {filtered_out} entities: "
            f"{unverified_count} unverified (no evidence/coverage), "
            f"{dangerous_count} high-risk blind spots"
        )

        computed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        logger.info(
            f"Autocomplete completed in {duration_ms}ms: "
            f"{len(limited_suggestions)}/{total_matches} suggestions returned"
        )

        return AutocompleteResult(
            suggestions=limited_suggestions,
            total_matches=total_matches,
            filtered_out=filtered_out,
            filter_reason=filter_reason,
            graph_version=graph_version,
            computed_at=computed_at
        )

    except Exception as e:
        logger.error(f"Autocomplete suggest failed: {e}", exc_info=True)
        # Return empty result rather than crashing
        return _empty_result(
            graph_version="unknown",
            start_time=start_time,
            reason=f"Error: {str(e)}"
        )


def _find_matching_entities(
    cursor,
    prefix: str,
    entity_types: Optional[List[str]] = None
) -> List[Tuple[int, str, str, str]]:
    """
    Find entities matching the prefix.

    Returns:
        List of (entity_id, entity_type, entity_key, entity_name) tuples
    """
    prefix_pattern = f"{prefix}%"

    if entity_types:
        # Build placeholders for IN clause
        type_placeholders = ','.join('?' * len(entity_types))
        query = f"""
            SELECT id, type, key, name
            FROM entities
            WHERE (key LIKE ? OR name LIKE ?)
              AND type IN ({type_placeholders})
            ORDER BY
                CASE
                    WHEN key = ? THEN 0  -- Exact match first
                    WHEN key LIKE ? THEN 1  -- Prefix match second
                    ELSE 2
                END,
                name
        """
        params = [prefix_pattern, prefix_pattern] + entity_types + [prefix, prefix_pattern]
    else:
        query = """
            SELECT id, type, key, name
            FROM entities
            WHERE (key LIKE ? OR name LIKE ?)
              AND type IN ('file', 'capability', 'term', 'doc')
            ORDER BY
                CASE
                    WHEN key = ? THEN 0  -- Exact match first
                    WHEN key LIKE ? THEN 1  -- Prefix match second
                    ELSE 2
                END,
                name
        """
        params = [prefix_pattern, prefix_pattern, prefix, prefix_pattern]

    cursor.execute(query, params)
    return cursor.fetchall()


def _count_evidence(cursor, entity_id: int) -> int:
    """
    Count evidence records for an entity.

    Note: We count evidence for edges where this entity is the destination,
    as that's where evidence typically points (e.g., commits modifying files).
    """
    cursor.execute("""
        SELECT COUNT(DISTINCT ev.id)
        FROM evidence ev
        JOIN edges e ON e.id = ev.edge_id
        WHERE e.dst_entity_id = ? OR e.src_entity_id = ?
    """, (entity_id, entity_id))

    result = cursor.fetchone()
    return result[0] if result else 0


def _get_coverage_sources(cursor, entity_id: int) -> List[str]:
    """
    Get coverage sources for an entity.

    Returns list of source categories: ['git', 'doc', 'code']
    """
    cursor.execute("""
        SELECT DISTINCT
            CASE
                WHEN e.type = 'modifies' THEN 'git'
                WHEN e.type = 'references' THEN 'doc'
                WHEN e.type = 'depends_on' THEN 'code'
                WHEN e.type = 'implements' THEN 'code'
                WHEN e.type = 'mentions' THEN 'doc'
                ELSE 'other'
            END AS source_category
        FROM edges e
        WHERE (e.dst_entity_id = ? OR e.src_entity_id = ?)
          AND e.id IN (SELECT edge_id FROM evidence)
    """, (entity_id, entity_id))

    results = cursor.fetchall()
    sources = [row[0] for row in results if row[0] != 'other']
    return list(set(sources))  # Deduplicate


def _build_blind_spot_map(blind_spots: List[BlindSpot]) -> Dict[Tuple[str, str], BlindSpot]:
    """
    Build a lookup map for blind spots.

    Returns:
        Dictionary mapping (entity_type, entity_key) -> BlindSpot
    """
    return {
        (bs.entity_type, bs.entity_key): bs
        for bs in blind_spots
    }


def _create_suggestion(
    entity_type: str,
    entity_key: str,
    entity_name: str,
    evidence_count: int,
    coverage_sources: List[str],
    blind_spot: Optional[BlindSpot]
) -> AutocompleteSuggestion:
    """
    Create an AutocompleteSuggestion with cognitive safety information.
    """
    # Determine safety level
    if blind_spot:
        if blind_spot.severity >= 0.7:
            safety_level = EntitySafety.DANGEROUS
        elif blind_spot.severity >= 0.4:
            safety_level = EntitySafety.WARNING
        else:
            safety_level = EntitySafety.SAFE
    else:
        safety_level = EntitySafety.SAFE

    # Generate display text
    display_text = f"{entity_type}:{entity_key}"

    # Generate hint text based on safety level
    if safety_level == EntitySafety.DANGEROUS:
        hint_text = f"🚨 High-risk blind spot (severity={blind_spot.severity:.2f}) - Use with caution"
    elif safety_level == EntitySafety.WARNING:
        sources_str = "+".join(coverage_sources)
        hint_text = f"⚠️ Moderate blind spot ({len(coverage_sources)}/3 sources: {sources_str})"
    else:
        sources_str = "+".join(coverage_sources)
        hint_text = f"✅ {len(coverage_sources)}/3 sources covered ({sources_str})"

    return AutocompleteSuggestion(
        entity_type=entity_type,
        entity_key=entity_key,
        entity_name=entity_name,
        safety_level=safety_level,
        evidence_count=evidence_count,
        coverage_sources=coverage_sources,
        is_blind_spot=(blind_spot is not None),
        blind_spot_severity=blind_spot.severity if blind_spot else None,
        blind_spot_reason=blind_spot.reason if blind_spot else None,
        display_text=display_text,
        hint_text=hint_text
    )


def _empty_result(
    graph_version: str,
    start_time: datetime,
    reason: str
) -> AutocompleteResult:
    """
    Create empty result for no matches or error cases.
    """
    computed_at = datetime.now(timezone.utc).isoformat()
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    logger.info(f"Returning empty result: {reason} (took {duration_ms}ms)")

    return AutocompleteResult(
        suggestions=[],
        total_matches=0,
        filtered_out=0,
        filter_reason=reason,
        graph_version=graph_version,
        computed_at=computed_at
    )
