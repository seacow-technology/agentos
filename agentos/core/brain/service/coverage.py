"""
BrainOS Coverage Calculation Engine

Computes cognitive completeness metrics for BrainOS knowledge graph.

Coverage is not test coverage, but "cognitive coverage" - measuring how much
of the codebase is understood by BrainOS based on evidence from:
- Git: Files modified by commits (MODIFIES edges)
- Docs: Files referenced by documentation (REFERENCES edges)
- Code: Files participating in dependency relationships (DEPENDS_ON edges)

Key Metrics:
- Code Coverage: % of files with at least 1 evidence
- Doc Coverage: % of files referenced by documentation
- Dependency Coverage: % of files in dependency graph
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..store import SQLiteStore
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class CoverageMetrics:
    """
    Coverage metrics for BrainOS knowledge graph.

    Attributes:
        total_files: Total number of file entities in the graph
        covered_files: Number of files with at least 1 evidence
        code_coverage: Ratio of covered files to total files (0.0 - 1.0)

        git_covered_files: Number of files covered by git commits
        doc_covered_files: Number of files covered by documentation
        dep_covered_files: Number of files in dependency graph

        doc_coverage: Ratio of doc-covered files to total (0.0 - 1.0)
        dependency_coverage: Ratio of dep-covered files to total (0.0 - 1.0)

        uncovered_files: List of file keys with zero evidence
        evidence_distribution: Distribution of evidence counts per file

        graph_version: Graph version identifier
        computed_at: ISO timestamp when metrics were computed
    """

    # Overall metrics
    total_files: int
    covered_files: int
    code_coverage: float

    # Evidence-specific metrics
    git_covered_files: int
    doc_covered_files: int
    dep_covered_files: int

    doc_coverage: float
    dependency_coverage: float

    # Detailed information
    uncovered_files: List[str] = field(default_factory=list)
    evidence_distribution: Dict[str, int] = field(default_factory=dict)

    # Metadata
    graph_version: str = "unknown"
    computed_at: str = ""

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_files": self.total_files,
            "covered_files": self.covered_files,
            "code_coverage": self.code_coverage,
            "git_covered_files": self.git_covered_files,
            "doc_covered_files": self.doc_covered_files,
            "dep_covered_files": self.dep_covered_files,
            "doc_coverage": self.doc_coverage,
            "dependency_coverage": self.dependency_coverage,
            "uncovered_files": self.uncovered_files,
            "evidence_distribution": self.evidence_distribution,
            "graph_version": self.graph_version,
            "computed_at": self.computed_at
        }


def compute_coverage(store: SQLiteStore) -> CoverageMetrics:
    """
    Compute cognitive coverage metrics for BrainOS knowledge graph.

    This calculates what percentage of the codebase BrainOS "understands"
    based on available evidence from git, documentation, and code analysis.

    Args:
        store: SQLiteStore instance with initialized connection

    Returns:
        CoverageMetrics object with computed metrics

    Examples:
        >>> from agentos.core.db import registry_db
        >>> conn = registry_db.get_db()
        >>> store = SQLiteStore.from_connection(conn)
        >>> metrics = compute_coverage(store)
        >>> print(f"Code Coverage: {metrics.code_coverage:.1%}")
        >>> print(f"Uncovered files: {len(metrics.uncovered_files)}")

    Notes:
        - Returns empty metrics on error rather than crashing
        - Uses DISTINCT to avoid double-counting files
        - Performance scales with number of entities and edges
    """
    logger.info("Computing BrainOS coverage metrics")
    start_time = utc_now()

    try:
        conn = store.connect()
        cursor = conn.cursor()

        # Get graph version from metadata
        metadata = store.get_last_build_metadata()
        graph_version = metadata['graph_version'] if metadata else 'unknown'

        # Step 1: Count total file entities
        logger.debug("Step 1: Counting total file entities")
        cursor.execute("""
            SELECT COUNT(*) FROM entities WHERE type = 'file'
        """)
        total_files = cursor.fetchone()[0]
        logger.info(f"Total files in graph: {total_files}")

        if total_files == 0:
            logger.warning("No file entities found in graph - returning empty metrics")
            return _empty_metrics(graph_version, start_time)

        # Step 2: Count Git coverage (files with MODIFIES edges)
        logger.debug("Step 2: Computing Git coverage (MODIFIES edges)")
        cursor.execute("""
            SELECT COUNT(DISTINCT dst_entity_id)
            FROM edges
            WHERE type = 'modifies'
              AND dst_entity_id IN (SELECT id FROM entities WHERE type = 'file')
        """)
        git_covered = cursor.fetchone()[0]
        logger.info(f"Git-covered files (MODIFIES): {git_covered}")

        # Step 3: Count Doc coverage (files with REFERENCES edges)
        logger.debug("Step 3: Computing Doc coverage (REFERENCES edges)")
        cursor.execute("""
            SELECT COUNT(DISTINCT dst_entity_id)
            FROM edges
            WHERE type = 'references'
              AND dst_entity_id IN (SELECT id FROM entities WHERE type = 'file')
        """)
        doc_covered = cursor.fetchone()[0]
        logger.info(f"Doc-covered files (REFERENCES): {doc_covered}")

        # Step 4: Count Dependency coverage (files in DEPENDS_ON edges)
        logger.debug("Step 4: Computing Dependency coverage (DEPENDS_ON edges)")
        cursor.execute("""
            SELECT COUNT(DISTINCT entity_id)
            FROM (
                SELECT src_entity_id AS entity_id FROM edges WHERE type = 'depends_on'
                UNION
                SELECT dst_entity_id AS entity_id FROM edges WHERE type = 'depends_on'
            )
            WHERE entity_id IN (SELECT id FROM entities WHERE type = 'file')
        """)
        dep_covered = cursor.fetchone()[0]
        logger.info(f"Dependency-covered files (DEPENDS_ON): {dep_covered}")

        # Step 5: Count files with at least 1 evidence (union of all coverage types)
        logger.debug("Step 5: Computing overall coverage (union of all evidence)")
        cursor.execute("""
            SELECT COUNT(DISTINCT file_id)
            FROM (
                SELECT dst_entity_id AS file_id FROM edges WHERE type = 'modifies'
                UNION
                SELECT dst_entity_id AS file_id FROM edges WHERE type = 'references'
                UNION
                SELECT src_entity_id AS file_id FROM edges WHERE type = 'depends_on'
                UNION
                SELECT dst_entity_id AS file_id FROM edges WHERE type = 'depends_on'
            )
            WHERE file_id IN (SELECT id FROM entities WHERE type = 'file')
        """)
        covered_files = cursor.fetchone()[0]
        logger.info(f"Total covered files (≥1 evidence): {covered_files}")

        # Step 6: Find uncovered files (0 evidence)
        logger.debug("Step 6: Finding uncovered files (0 evidence)")
        cursor.execute("""
            SELECT key
            FROM entities
            WHERE type = 'file'
              AND id NOT IN (
                SELECT file_id FROM (
                    SELECT dst_entity_id AS file_id FROM edges WHERE type = 'modifies'
                    UNION
                    SELECT dst_entity_id AS file_id FROM edges WHERE type = 'references'
                    UNION
                    SELECT src_entity_id AS file_id FROM edges WHERE type = 'depends_on'
                    UNION
                    SELECT dst_entity_id AS file_id FROM edges WHERE type = 'depends_on'
                )
              )
            ORDER BY key
        """)
        uncovered_files = [row[0] for row in cursor.fetchall()]
        logger.info(f"Uncovered files (0 evidence): {len(uncovered_files)}")

        # Step 7: Compute evidence distribution
        logger.debug("Step 7: Computing evidence distribution per file")
        evidence_distribution = _compute_evidence_distribution(cursor, total_files)
        logger.debug(f"Evidence distribution: {evidence_distribution}")

        # Calculate coverage ratios
        code_coverage = covered_files / total_files if total_files > 0 else 0.0
        doc_coverage = doc_covered / total_files if total_files > 0 else 0.0
        dependency_coverage = dep_covered / total_files if total_files > 0 else 0.0

        computed_at = utc_now_iso()
        duration_ms = int((utc_now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Coverage computation completed in {duration_ms}ms: "
            f"code={code_coverage:.1%}, doc={doc_coverage:.1%}, dep={dependency_coverage:.1%}"
        )

        return CoverageMetrics(
            total_files=total_files,
            covered_files=covered_files,
            code_coverage=code_coverage,
            git_covered_files=git_covered,
            doc_covered_files=doc_covered,
            dep_covered_files=dep_covered,
            doc_coverage=doc_coverage,
            dependency_coverage=dependency_coverage,
            uncovered_files=uncovered_files,
            evidence_distribution=evidence_distribution,
            graph_version=graph_version,
            computed_at=computed_at
        )

    except Exception as e:
        logger.error(f"Failed to compute coverage metrics: {e}", exc_info=True)
        # Return empty metrics rather than crashing
        return _empty_metrics("unknown", start_time)


def _compute_evidence_distribution(cursor, total_files: int) -> Dict[str, int]:
    """
    Compute distribution of evidence counts per file.

    Args:
        cursor: SQLite cursor
        total_files: Total number of files for validation

    Returns:
        Dictionary with distribution: {"0_evidence": 10, "1_evidence": 20, ...}
    """
    # Count evidence types per file
    cursor.execute("""
        WITH file_evidence AS (
            SELECT
                e.id AS file_id,
                COUNT(DISTINCT CASE WHEN edges.type = 'modifies' THEN edges.id END) AS git_count,
                COUNT(DISTINCT CASE WHEN edges.type = 'references' THEN edges.id END) AS doc_count,
                COUNT(DISTINCT CASE WHEN edges.type = 'depends_on' THEN edges.id END) AS dep_count
            FROM entities e
            LEFT JOIN edges ON (
                (edges.dst_entity_id = e.id AND edges.type IN ('modifies', 'references'))
                OR (edges.src_entity_id = e.id AND edges.type = 'depends_on')
                OR (edges.dst_entity_id = e.id AND edges.type = 'depends_on')
            )
            WHERE e.type = 'file'
            GROUP BY e.id
        ),
        file_evidence_total AS (
            SELECT
                file_id,
                CASE
                    WHEN git_count > 0 THEN 1 ELSE 0
                END +
                CASE
                    WHEN doc_count > 0 THEN 1 ELSE 0
                END +
                CASE
                    WHEN dep_count > 0 THEN 1 ELSE 0
                END AS evidence_count
            FROM file_evidence
        )
        SELECT
            evidence_count,
            COUNT(*) AS file_count
        FROM file_evidence_total
        GROUP BY evidence_count
        ORDER BY evidence_count
    """)

    results = cursor.fetchall()
    distribution = {
        "0_evidence": 0,
        "1_evidence": 0,
        "2_evidence": 0,
        "3_evidence": 0
    }

    for row in results:
        evidence_count, file_count = row
        if evidence_count == 0:
            distribution["0_evidence"] = file_count
        elif evidence_count == 1:
            distribution["1_evidence"] = file_count
        elif evidence_count == 2:
            distribution["2_evidence"] = file_count
        elif evidence_count >= 3:
            distribution["3_evidence"] += file_count

    return distribution


def _empty_metrics(graph_version: str, start_time: datetime) -> CoverageMetrics:
    """
    Create empty metrics object for error cases.

    Args:
        graph_version: Graph version identifier
        start_time: Computation start time

    Returns:
        CoverageMetrics with all zeros
    """
    return CoverageMetrics(
        total_files=0,
        covered_files=0,
        code_coverage=0.0,
        git_covered_files=0,
        doc_covered_files=0,
        dep_covered_files=0,
        doc_coverage=0.0,
        dependency_coverage=0.0,
        uncovered_files=[],
        evidence_distribution={
            "0_evidence": 0,
            "1_evidence": 0,
            "2_evidence": 0,
            "3_evidence": 0
        },
        graph_version=graph_version,
        computed_at=utc_now_iso()
    )
