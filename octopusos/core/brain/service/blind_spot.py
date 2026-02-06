"""
BrainOS Blind Spot Detection Engine

Detects cognitive blind spots in the knowledge graph - areas where BrainOS
"knows that it doesn't know". This is not about data absence, but about
recognizing where understanding is incomplete or risky.

Blind Spot Definition:
- NOT "no data exists"
- BUT "important yet unexplained"
- BUT "heavily depended upon yet undocumented"
- BUT "appears in execution paths yet never mentioned"

Three Types of Blind Spots:
1. High Fan-In Undocumented: Critical files with many dependents but no documentation
2. Capability Without Implementation: Declared capabilities with no code implementation
3. Trace Discontinuity: Active files with git history but no documented evolution

This is a marker of cognitive maturity - the system recognizing its own gaps.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from ..store import SQLiteStore
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


class BlindSpotType(Enum):
    """Types of blind spots in the knowledge graph"""
    HIGH_FAN_IN_UNDOCUMENTED = "high_fan_in_undocumented"
    CAPABILITY_NO_IMPLEMENTATION = "capability_no_implementation"
    TRACE_DISCONTINUITY = "trace_discontinuity"


@dataclass
class BlindSpot:
    """
    Represents a cognitive blind spot in BrainOS.

    A blind spot is an area where the system recognizes it lacks complete
    understanding - "I know that I don't know".

    Attributes:
        entity_type: Type of entity (e.g., 'file', 'capability')
        entity_key: Unique key for the entity
        entity_name: Display name of the entity
        blind_spot_type: Type of blind spot detected
        severity: Severity score (0.0-1.0), higher = more critical
        reason: Human-readable explanation of why this is a blind spot
        metrics: Relevant metrics (e.g., fan_in_count, doc_count)
        suggested_action: Actionable recommendation to address the blind spot
        detected_at: ISO timestamp when blind spot was detected
    """

    # Identification
    entity_type: str
    entity_key: str
    entity_name: str

    # Blind spot classification
    blind_spot_type: BlindSpotType

    # Severity (0.0-1.0)
    severity: float

    # Details
    reason: str
    metrics: Dict[str, int]

    # Recommendation
    suggested_action: str

    # Metadata
    detected_at: str


@dataclass
class BlindSpotReport:
    """
    Summary of all blind spots detected in the knowledge graph.

    Attributes:
        total_blind_spots: Total number of blind spots detected
        by_type: Count of blind spots by type
        by_severity: Count of blind spots by severity category
        blind_spots: List of all blind spots, sorted by severity (descending)
        graph_version: Graph version identifier
        computed_at: ISO timestamp when report was generated
    """

    total_blind_spots: int
    by_type: Dict[BlindSpotType, int]
    by_severity: Dict[str, int]  # {"high": 5, "medium": 10, "low": 15}

    blind_spots: List[BlindSpot]  # Sorted by severity (descending)

    # Metadata
    graph_version: str
    computed_at: str

    def to_dict(self) -> Dict:
        """Convert report to dictionary for serialization."""
        return {
            "total_blind_spots": self.total_blind_spots,
            "by_type": {k.value: v for k, v in self.by_type.items()},
            "by_severity": self.by_severity,
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
                for bs in self.blind_spots
            ],
            "graph_version": self.graph_version,
            "computed_at": self.computed_at
        }


def detect_blind_spots(
    store: SQLiteStore,
    high_fan_in_threshold: int = 5,
    max_results: int = 50
) -> BlindSpotReport:
    """
    Detect cognitive blind spots in the knowledge graph.

    This function identifies areas where BrainOS "knows that it doesn't know" -
    important entities or relationships that lack sufficient documentation or
    explanation despite being critical to the system.

    Args:
        store: SQLiteStore instance with active connection
        high_fan_in_threshold: Minimum fan-in count to trigger Type 1 detection (default: 5)
        max_results: Maximum number of blind spots to return (default: 50)

    Returns:
        BlindSpotReport with all detected blind spots, sorted by severity

    Examples:
        >>> from agentos.core.db import registry_db
        >>> conn = registry_db.get_db()
        >>> store = SQLiteStore.from_connection(conn)
        >>> report = detect_blind_spots(store)
        >>> print(f"Total blind spots: {report.total_blind_spots}")
        >>> print(f"High severity: {report.by_severity['high']}")

    Notes:
        - Returns empty report on error rather than crashing
        - Three independent detection algorithms run in sequence
        - Results are sorted by severity (highest first)
        - Limited to max_results to avoid overwhelming output
    """
    logger.info(f"Detecting blind spots (threshold={high_fan_in_threshold}, max={max_results})")
    start_time = utc_now()

    try:
        # Get graph version
        metadata = store.get_last_build_metadata()
        graph_version = metadata['graph_version'] if metadata else 'unknown'

        # Run three independent detection algorithms
        logger.debug("Running Type 1: High Fan-In Undocumented detection")
        type1_blind_spots = detect_high_fan_in_undocumented(store, high_fan_in_threshold)
        logger.info(f"Type 1 detected: {len(type1_blind_spots)} blind spots")

        logger.debug("Running Type 2: Capability Without Implementation detection")
        type2_blind_spots = detect_capability_no_implementation(store)
        logger.info(f"Type 2 detected: {len(type2_blind_spots)} blind spots")

        logger.debug("Running Type 3: Trace Discontinuity detection")
        type3_blind_spots = detect_trace_discontinuity(store)
        logger.info(f"Type 3 detected: {len(type3_blind_spots)} blind spots")

        # Combine all blind spots
        all_blind_spots = type1_blind_spots + type2_blind_spots + type3_blind_spots

        # Sort by severity (descending)
        all_blind_spots.sort(key=lambda bs: bs.severity, reverse=True)

        # Limit to max_results
        limited_blind_spots = all_blind_spots[:max_results]

        # Compute statistics
        by_type = _count_by_type(limited_blind_spots)
        by_severity = _count_by_severity(limited_blind_spots)

        computed_at = utc_now_iso()
        duration_ms = int((utc_now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Blind spot detection completed in {duration_ms}ms: "
            f"total={len(limited_blind_spots)}, "
            f"type1={by_type.get(BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED, 0)}, "
            f"type2={by_type.get(BlindSpotType.CAPABILITY_NO_IMPLEMENTATION, 0)}, "
            f"type3={by_type.get(BlindSpotType.TRACE_DISCONTINUITY, 0)}"
        )

        return BlindSpotReport(
            total_blind_spots=len(limited_blind_spots),
            by_type=by_type,
            by_severity=by_severity,
            blind_spots=limited_blind_spots,
            graph_version=graph_version,
            computed_at=computed_at
        )

    except Exception as e:
        logger.error(f"Failed to detect blind spots: {e}", exc_info=True)
        # Return empty report rather than crashing
        return _empty_report("unknown", start_time)


def detect_high_fan_in_undocumented(
    store: SQLiteStore,
    threshold: int = 5
) -> List[BlindSpot]:
    """
    Detect Type 1: High Fan-In Undocumented blind spots.

    These are critical files that many other files depend on, but have no
    documentation explaining their purpose or rationale. This represents a
    significant risk - if something is heavily used but not documented, changes
    could have unexpected cascading effects.

    Detection Algorithm:
    1. Find all file entities with fan-in >= threshold (incoming DEPENDS_ON edges)
    2. Check if these files have any REFERENCES edges from documentation
    3. Generate blind spot for files with high fan-in but zero doc references

    Args:
        store: SQLiteStore instance
        threshold: Minimum fan-in count to trigger detection (default: 5)

    Returns:
        List of BlindSpot objects for high-fan-in undocumented files

    Examples:
        File with 15 dependents but no docs:
        → BlindSpot(severity=0.75, reason="Critical file with 15 dependents but no documentation")
    """
    logger.debug(f"Detecting high fan-in undocumented files (threshold={threshold})")
    blind_spots = []

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Step 1: Find files with high fan-in (many incoming DEPENDS_ON edges)
        logger.debug("Step 1: Finding files with high fan-in")
        cursor.execute("""
            SELECT
                e.id,
                e.key AS entity_key,
                e.name AS entity_name,
                COUNT(dep.id) AS fan_in_count
            FROM entities e
            LEFT JOIN edges dep ON dep.dst_entity_id = e.id AND dep.type = 'depends_on'
            WHERE e.type = 'file'
            GROUP BY e.id
            HAVING fan_in_count >= ?
            ORDER BY fan_in_count DESC
        """, (threshold,))

        high_fan_in_files = cursor.fetchall()
        logger.debug(f"Found {len(high_fan_in_files)} files with fan-in >= {threshold}")

        # Step 2: For each high fan-in file, check if it has documentation
        for row in high_fan_in_files:
            file_id = row[0]
            entity_key = row[1]
            entity_name = row[2]
            fan_in_count = row[3]

            # Check for REFERENCES edges (documentation references)
            cursor.execute("""
                SELECT COUNT(*)
                FROM edges
                WHERE dst_entity_id = ? AND type = 'references'
            """, (file_id,))

            doc_count = cursor.fetchone()[0]

            # If no documentation, this is a blind spot
            if doc_count == 0:
                severity = calculate_severity(
                    BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED,
                    {'fan_in_count': fan_in_count}
                )

                blind_spot = BlindSpot(
                    entity_type='file',
                    entity_key=entity_key,
                    entity_name=entity_name,
                    blind_spot_type=BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED,
                    severity=severity,
                    reason=f"Critical file with {fan_in_count} dependents but no documentation",
                    metrics={'fan_in_count': fan_in_count, 'doc_count': 0},
                    suggested_action="Add ADR or design doc explaining this file's purpose and architecture",
                    detected_at=utc_now_iso()
                )

                blind_spots.append(blind_spot)
                logger.debug(
                    f"Blind spot detected: {entity_name} "
                    f"(fan_in={fan_in_count}, docs=0, severity={severity:.2f})"
                )

        logger.info(f"Detected {len(blind_spots)} high fan-in undocumented blind spots")
        return blind_spots

    except Exception as e:
        logger.error(f"Failed to detect high fan-in undocumented: {e}", exc_info=True)
        return []


def detect_capability_no_implementation(
    store: SQLiteStore
) -> List[BlindSpot]:
    """
    Detect Type 2: Capability Without Implementation blind spots.

    These are declared capabilities in the system that have no corresponding
    implementation files. This represents a gap between what the system claims
    to do and what it actually can do.

    Detection Algorithm:
    1. Find all capability entities
    2. Check if each capability has any IMPLEMENTS edges (files implementing it)
    3. Generate blind spot for capabilities with no implementation

    Args:
        store: SQLiteStore instance

    Returns:
        List of BlindSpot objects for capabilities without implementation

    Examples:
        Capability "governance" with no implementation:
        → BlindSpot(severity=0.8, reason="Declared capability with no implementation files")
    """
    logger.debug("Detecting capabilities without implementation")
    blind_spots = []

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Step 1: Find all capability entities
        logger.debug("Step 1: Finding all capability entities")
        cursor.execute("""
            SELECT id, key, name
            FROM entities
            WHERE type = 'capability'
        """)

        capabilities = cursor.fetchall()
        logger.debug(f"Found {len(capabilities)} capability entities")

        # Step 2: Check each capability for IMPLEMENTS edges
        for row in capabilities:
            capability_id = row[0]
            entity_key = row[1]
            entity_name = row[2]

            # Check for IMPLEMENTS edges (files implementing this capability)
            cursor.execute("""
                SELECT COUNT(*)
                FROM edges
                WHERE dst_entity_id = ? AND type = 'implements'
            """, (capability_id,))

            implementation_count = cursor.fetchone()[0]

            # If no implementation, this is a blind spot
            if implementation_count == 0:
                severity = calculate_severity(
                    BlindSpotType.CAPABILITY_NO_IMPLEMENTATION,
                    {'implementation_count': 0}
                )

                blind_spot = BlindSpot(
                    entity_type='capability',
                    entity_key=entity_key,
                    entity_name=entity_name,
                    blind_spot_type=BlindSpotType.CAPABILITY_NO_IMPLEMENTATION,
                    severity=severity,
                    reason="Declared capability with no implementation files",
                    metrics={'implementation_count': 0},
                    suggested_action="Add implementation file or remove orphaned capability declaration",
                    detected_at=utc_now_iso()
                )

                blind_spots.append(blind_spot)
                logger.debug(
                    f"Blind spot detected: {entity_name} "
                    f"(capability with no implementation, severity={severity:.2f})"
                )

        logger.info(f"Detected {len(blind_spots)} capability without implementation blind spots")
        return blind_spots

    except Exception as e:
        logger.error(f"Failed to detect capability without implementation: {e}", exc_info=True)
        return []


def detect_trace_discontinuity(
    store: SQLiteStore
) -> List[BlindSpot]:
    """
    Detect Type 3: Trace Discontinuity blind spots.

    These are files with active git history (commits modifying them) but no
    documented evolution or rationale. This represents a gap in understanding
    WHY changes were made - the file has a history, but no narrative.

    Detection Algorithm:
    1. Find all files with MODIFIES edges (git commits)
    2. Check if these files have REFERENCES or MENTIONS edges (documentation)
    3. Generate blind spot for files with commits but no documentation trace

    Args:
        store: SQLiteStore instance

    Returns:
        List of BlindSpot objects for files with trace discontinuity

    Examples:
        File with 5 commits but no docs:
        → BlindSpot(severity=0.5, reason="Active file (5 commits) with no documented evolution")
    """
    logger.debug("Detecting trace discontinuity")
    blind_spots = []

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Step 1: Find files with git history (MODIFIES edges)
        logger.debug("Step 1: Finding files with git history")
        cursor.execute("""
            SELECT
                e.id,
                e.key AS entity_key,
                e.name AS entity_name,
                COUNT(mod.id) AS commit_count
            FROM entities e
            JOIN edges mod ON mod.dst_entity_id = e.id AND mod.type = 'modifies'
            WHERE e.type = 'file'
            GROUP BY e.id
            HAVING commit_count > 0
            ORDER BY commit_count DESC
        """)

        files_with_commits = cursor.fetchall()
        logger.debug(f"Found {len(files_with_commits)} files with commit history")

        # Step 2: Check each file for documentation trace
        for row in files_with_commits:
            file_id = row[0]
            entity_key = row[1]
            entity_name = row[2]
            commit_count = row[3]

            # Check for REFERENCES edges (documentation)
            cursor.execute("""
                SELECT COUNT(*)
                FROM edges
                WHERE dst_entity_id = ? AND type = 'references'
            """, (file_id,))

            doc_count = cursor.fetchone()[0]

            # Check for MENTIONS edges (terms mentioned in context of this file)
            cursor.execute("""
                SELECT COUNT(*)
                FROM edges
                WHERE dst_entity_id = ? AND type = 'mentions'
            """, (file_id,))

            mention_count = cursor.fetchone()[0]

            # If no documentation trace, this is a blind spot
            if doc_count == 0 and mention_count == 0:
                severity = calculate_severity(
                    BlindSpotType.TRACE_DISCONTINUITY,
                    {'commit_count': commit_count}
                )

                blind_spot = BlindSpot(
                    entity_type='file',
                    entity_key=entity_key,
                    entity_name=entity_name,
                    blind_spot_type=BlindSpotType.TRACE_DISCONTINUITY,
                    severity=severity,
                    reason=f"Active file ({commit_count} commits) with no documented evolution",
                    metrics={
                        'commit_count': commit_count,
                        'doc_count': 0,
                        'mention_count': 0
                    },
                    suggested_action="Add commit messages or ADR explaining changes and evolution",
                    detected_at=utc_now_iso()
                )

                blind_spots.append(blind_spot)
                logger.debug(
                    f"Blind spot detected: {entity_name} "
                    f"(commits={commit_count}, docs=0, mentions=0, severity={severity:.2f})"
                )

        logger.info(f"Detected {len(blind_spots)} trace discontinuity blind spots")
        return blind_spots

    except Exception as e:
        logger.error(f"Failed to detect trace discontinuity: {e}", exc_info=True)
        return []


def calculate_severity(
    blind_spot_type: BlindSpotType,
    metrics: Dict[str, int]
) -> float:
    """
    Calculate severity score for a blind spot (0.0-1.0).

    Severity indicates how critical the blind spot is - higher severity means
    more urgent need for attention.

    Calculation Logic:
    - HIGH_FAN_IN_UNDOCUMENTED: Based on fan_in_count, normalized to 0-1
      - Formula: min(1.0, fan_in_count / 20)
      - Example: 10 dependents → 0.5, 20 dependents → 1.0

    - CAPABILITY_NO_IMPLEMENTATION: Fixed at 0.8 (high severity)
      - Rationale: Missing capability is always a significant gap

    - TRACE_DISCONTINUITY: Based on commit_count, normalized to 0-1
      - Formula: min(1.0, commit_count / 10)
      - Example: 5 commits → 0.5, 10 commits → 1.0

    Args:
        blind_spot_type: Type of blind spot
        metrics: Relevant metrics for severity calculation

    Returns:
        Severity score between 0.0 and 1.0

    Examples:
        >>> calculate_severity(BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED, {'fan_in_count': 15})
        0.75
        >>> calculate_severity(BlindSpotType.CAPABILITY_NO_IMPLEMENTATION, {})
        0.8
        >>> calculate_severity(BlindSpotType.TRACE_DISCONTINUITY, {'commit_count': 5})
        0.5
    """
    if blind_spot_type == BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED:
        fan_in = metrics.get('fan_in_count', 0)
        # Normalize: 20+ dependents = severity 1.0
        return min(1.0, fan_in / 20.0)

    elif blind_spot_type == BlindSpotType.CAPABILITY_NO_IMPLEMENTATION:
        # Fixed high severity - missing capabilities are always critical
        return 0.8

    elif blind_spot_type == BlindSpotType.TRACE_DISCONTINUITY:
        commits = metrics.get('commit_count', 0)
        # Normalize: 10+ commits = severity 1.0
        return min(1.0, commits / 10.0)

    # Default medium severity for unknown types
    return 0.5


def _count_by_type(blind_spots: List[BlindSpot]) -> Dict[BlindSpotType, int]:
    """Count blind spots by type."""
    counts = {
        BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED: 0,
        BlindSpotType.CAPABILITY_NO_IMPLEMENTATION: 0,
        BlindSpotType.TRACE_DISCONTINUITY: 0
    }

    for bs in blind_spots:
        counts[bs.blind_spot_type] = counts.get(bs.blind_spot_type, 0) + 1

    return counts


def _count_by_severity(blind_spots: List[BlindSpot]) -> Dict[str, int]:
    """
    Count blind spots by severity category.

    Categories:
    - high: severity >= 0.7
    - medium: 0.4 <= severity < 0.7
    - low: severity < 0.4
    """
    counts = {"high": 0, "medium": 0, "low": 0}

    for bs in blind_spots:
        if bs.severity >= 0.7:
            counts["high"] += 1
        elif bs.severity >= 0.4:
            counts["medium"] += 1
        else:
            counts["low"] += 1

    return counts


def _empty_report(graph_version: str, start_time: datetime) -> BlindSpotReport:
    """
    Create empty report for error cases.

    Args:
        graph_version: Graph version identifier
        start_time: Detection start time

    Returns:
        Empty BlindSpotReport
    """
    return BlindSpotReport(
        total_blind_spots=0,
        by_type={
            BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED: 0,
            BlindSpotType.CAPABILITY_NO_IMPLEMENTATION: 0,
            BlindSpotType.TRACE_DISCONTINUITY: 0
        },
        by_severity={"high": 0, "medium": 0, "low": 0},
        blind_spots=[],
        graph_version=graph_version,
        computed_at=utc_now_iso()
    )


def detect_blind_spots_for_entities(
    store: SQLiteStore,
    entity_ids: List[str]
) -> List[BlindSpot]:
    """
    Detect blind spots for specific entities (used by Navigation P3-A).

    This is a lightweight version that checks if given entities are blind spots
    without running full detection algorithms.

    Args:
        store: SQLiteStore instance
        entity_ids: List of entity IDs to check

    Returns:
        List of BlindSpot objects for the given entities
    """
    logger.debug(f"Checking blind spots for {len(entity_ids)} entities")
    blind_spots = []

    try:
        conn = store.connect()
        cursor = conn.cursor()

        for entity_id in entity_ids:
            # Get entity info
            cursor.execute("""
                SELECT type, key, name
                FROM entities
                WHERE id = ?
            """, (entity_id,))

            entity = cursor.fetchone()
            if not entity:
                continue

            entity_type, entity_key, entity_name = entity

            # Check Type 1: High fan-in undocumented (only for files)
            if entity_type == 'file':
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM edges
                    WHERE dst_entity_id = ? AND type = 'depends_on'
                """, (entity_id,))
                fan_in_count = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM edges
                    WHERE dst_entity_id = ? AND type = 'references'
                """, (entity_id,))
                doc_count = cursor.fetchone()[0]

                if fan_in_count >= 5 and doc_count == 0:
                    severity = calculate_severity(
                        BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED,
                        {'fan_in_count': fan_in_count}
                    )

                    blind_spot = BlindSpot(
                        entity_type=entity_type,
                        entity_key=entity_key,
                        entity_name=entity_name,
                        blind_spot_type=BlindSpotType.HIGH_FAN_IN_UNDOCUMENTED,
                        severity=severity,
                        reason=f"Critical file with {fan_in_count} dependents but no documentation",
                        metrics={'fan_in_count': fan_in_count, 'doc_count': 0},
                        suggested_action="Add ADR or design doc explaining this file's purpose",
                        detected_at=utc_now_iso()
                    )
                    blind_spots.append(blind_spot)

            # Check Type 2: Capability without implementation
            if entity_type == 'capability':
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM edges
                    WHERE dst_entity_id = ? AND type = 'implements'
                """, (entity_id,))
                implementation_count = cursor.fetchone()[0]

                if implementation_count == 0:
                    severity = calculate_severity(
                        BlindSpotType.CAPABILITY_NO_IMPLEMENTATION,
                        {'implementation_count': 0}
                    )

                    blind_spot = BlindSpot(
                        entity_type=entity_type,
                        entity_key=entity_key,
                        entity_name=entity_name,
                        blind_spot_type=BlindSpotType.CAPABILITY_NO_IMPLEMENTATION,
                        severity=severity,
                        reason="Declared capability with no implementation files",
                        metrics={'implementation_count': 0},
                        suggested_action="Add implementation or remove orphaned capability",
                        detected_at=utc_now_iso()
                    )
                    blind_spots.append(blind_spot)

            # Check Type 3: Trace discontinuity (only for files)
            if entity_type == 'file':
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM edges
                    WHERE dst_entity_id = ? AND type = 'modifies'
                """, (entity_id,))
                commit_count = cursor.fetchone()[0]

                if commit_count > 0:
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM edges
                        WHERE dst_entity_id = ? AND type IN ('references', 'mentions')
                    """, (entity_id,))
                    doc_mention_count = cursor.fetchone()[0]

                    if doc_mention_count == 0:
                        severity = calculate_severity(
                            BlindSpotType.TRACE_DISCONTINUITY,
                            {'commit_count': commit_count}
                        )

                        blind_spot = BlindSpot(
                            entity_type=entity_type,
                            entity_key=entity_key,
                            entity_name=entity_name,
                            blind_spot_type=BlindSpotType.TRACE_DISCONTINUITY,
                            severity=severity,
                            reason=f"Active file ({commit_count} commits) with no documented evolution",
                            metrics={'commit_count': commit_count, 'doc_count': 0},
                            suggested_action="Add commit messages or ADR explaining changes",
                            detected_at=utc_now_iso()
                        )
                        blind_spots.append(blind_spot)

        logger.debug(f"Found {len(blind_spots)} blind spots for given entities")
        return blind_spots

    except Exception as e:
        logger.error(f"Failed to check blind spots for entities: {e}", exc_info=True)
        return []
