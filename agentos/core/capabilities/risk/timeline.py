"""
Risk Timeline Management

Provides append-only, immutable risk history tracking for extensions.
This module enables:
- Recording risk assessments over time
- Querying historical risk evolution
- Analyzing risk trends (increasing/decreasing)
- Answering "why is it riskier/safer than before"

Design Principles:
1. APPEND-ONLY: Historical records cannot be modified
2. IMMUTABILITY: No updates or deletes allowed
3. TRACEABILITY: Every record has source attribution
4. COMPLETENESS: Full dimension breakdown preserved

Example:
    from agentos.core.capabilities.risk.timeline import RiskTimeline
    from agentos.core.capabilities.risk.scorer import RiskScorer

    # Initialize
    timeline = RiskTimeline(db_path="path/to/agentos.db")
    scorer = RiskScorer(db_path="path/to/agentos.db")

    # Calculate and record risk
    risk_score = scorer.calculate_risk("my_extension")
    timeline.record(risk_score, "my_extension", source="scorer_auto")

    # Query timeline
    history = timeline.get_timeline("my_extension", days=30)
    trend = timeline.get_trend("my_extension", days=30)
    comparison = timeline.compare_timepoints("my_extension", days_ago_1=0, days_ago_2=21)
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .models import RiskScore


@dataclass
class TimelineEntry:
    """
    Single entry in risk timeline.

    Attributes:
        timeline_id: Unique timeline entry ID
        extension_id: Extension identifier
        action_id: Action identifier
        risk_score: Risk score (0-100)
        risk_level: Risk level (LOW/MEDIUM/HIGH)
        dimensions: Dimension values dict
        dimension_details: Dimension explanations dict
        window_days: Historical window used
        sample_size: Number of executions analyzed
        explanation: Human-readable explanation
        source: Source of this record
        calculated_at: When risk was calculated
        recorded_at: When record was inserted
    """
    timeline_id: str
    extension_id: str
    action_id: str
    risk_score: float
    risk_level: str
    dimensions: Dict[str, float]
    dimension_details: Dict[str, str]
    window_days: int
    sample_size: int
    explanation: str
    source: str
    calculated_at: datetime
    recorded_at: datetime

    def to_dict(self) -> Dict:
        """Convert to API-friendly dictionary."""
        return {
            "timeline_id": self.timeline_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level,
            "dimensions": self.dimensions,
            "dimension_details": self.dimension_details,
            "window_days": self.window_days,
            "sample_size": self.sample_size,
            "explanation": self.explanation,
            "source": self.source,
            "calculated_at": int(self.calculated_at.timestamp() * 1000),
            "recorded_at": int(self.recorded_at.timestamp() * 1000),
        }


@dataclass
class RiskTrend:
    """
    Risk trend analysis result.

    Attributes:
        extension_id: Extension identifier
        action_id: Action identifier
        assessment_count: Total number of assessments
        first_risk: First recorded risk score
        last_risk: Most recent risk score
        min_risk: Minimum risk score in period
        max_risk: Maximum risk score in period
        avg_risk: Average risk score in period
        trend_direction: INCREASING, DECREASING, or STABLE
        risk_change: Absolute change (last - first)
        first_date: Date of first assessment
        last_date: Date of last assessment
    """
    extension_id: str
    action_id: str
    assessment_count: int
    first_risk: float
    last_risk: float
    min_risk: float
    max_risk: float
    avg_risk: float
    trend_direction: str
    risk_change: float
    first_date: datetime
    last_date: datetime

    def to_dict(self) -> Dict:
        """Convert to API-friendly dictionary."""
        return {
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "assessment_count": self.assessment_count,
            "first_risk": round(self.first_risk, 2),
            "last_risk": round(self.last_risk, 2),
            "min_risk": round(self.min_risk, 2),
            "max_risk": round(self.max_risk, 2),
            "avg_risk": round(self.avg_risk, 2),
            "trend_direction": self.trend_direction,
            "risk_change": round(self.risk_change, 2),
            "first_date": self.first_date.isoformat(),
            "last_date": self.last_date.isoformat(),
        }


class RiskTimeline:
    """
    Risk timeline manager for append-only risk history.

    This class provides:
    - Recording risk assessments to immutable timeline
    - Querying historical risk data
    - Trend analysis and comparison
    - Risk evolution visualization data

    All operations are read-only except record().
    Historical records cannot be modified or deleted.
    """

    def __init__(self, db_path: str):
        """
        Initialize risk timeline manager.

        Args:
            db_path: Path to SQLite database with risk_timeline table
        """
        self.db_path = db_path
        self._counter = 0  # Counter for same-millisecond records

    def record(
        self,
        risk_score: RiskScore,
        extension_id: str,
        action_id: str = "*",
        source: str = "scorer_auto",
        source_details: Optional[Dict] = None
    ) -> str:
        """
        Record a risk assessment to the timeline.

        This is the ONLY way to add entries to the timeline.
        Records are immutable after insertion.

        Args:
            risk_score: RiskScore object from scorer
            extension_id: Extension identifier
            action_id: Action identifier (default "*")
            source: Source of this record (scorer_auto, manual_override, etc.)
            source_details: Additional source context (optional)

        Returns:
            timeline_id of the inserted record

        Raises:
            ValueError: If risk_score is invalid
            sqlite3.IntegrityError: If database constraints violated
        """
        if not risk_score or risk_score.score < 0 or risk_score.score > 100:
            raise ValueError(f"Invalid risk_score: {risk_score}")

        # Generate timeline_id
        calculated_at_ms = int(risk_score.calculated_at.timestamp() * 1000)
        self._counter = (self._counter + 1) % 1000
        timeline_id = f"rtl-{extension_id}-{calculated_at_ms}-{self._counter:03d}"

        # Extract dimensions (normalized 0-1 values)
        dimensions = risk_score.dimensions
        dimension_write_ratio = dimensions.get("write_ratio", 0.0)
        dimension_external_call = dimensions.get("external_call", 0.0)
        dimension_failure_rate = dimensions.get("failure_rate", 0.0)
        dimension_revoke_count = dimensions.get("revoke_count", 0.0)
        dimension_duration_anomaly = dimensions.get("duration_anomaly", 0.0)

        # Build dimension_details JSON (from explanation or defaults)
        dimension_details = self._extract_dimension_details(risk_score)

        # Prepare source_details JSON
        source_details_json = json.dumps(source_details or {})
        dimension_details_json = json.dumps(dimension_details)

        # Current time for recorded_at
        recorded_at_ms = int(time.time() * 1000)

        # Insert into database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO risk_timeline (
                    timeline_id,
                    extension_id,
                    action_id,
                    risk_score,
                    risk_level,
                    dimension_write_ratio,
                    dimension_external_call,
                    dimension_failure_rate,
                    dimension_revoke_count,
                    dimension_duration_anomaly,
                    dimension_details,
                    window_days,
                    sample_size,
                    explanation,
                    source,
                    source_details,
                    calculated_at,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timeline_id,
                extension_id,
                action_id,
                risk_score.score,
                risk_score.get_level(),
                dimension_write_ratio,
                dimension_external_call,
                dimension_failure_rate,
                dimension_revoke_count,
                dimension_duration_anomaly,
                dimension_details_json,
                risk_score.window_days,
                risk_score.sample_size,
                risk_score.explanation,
                source,
                source_details_json,
                calculated_at_ms,
                recorded_at_ms
            ))

            conn.commit()
            conn.close()

            return timeline_id

        except sqlite3.IntegrityError as e:
            if "append-only" in str(e).lower() or "forbidden" in str(e).lower():
                raise ValueError(f"Cannot modify risk timeline: {e}")
            raise

    def _extract_dimension_details(self, risk_score: RiskScore) -> Dict[str, str]:
        """
        Extract dimension details from risk score explanation.

        This is a heuristic parser for backwards compatibility.
        Future scorers should provide dimension_details directly.

        Args:
            risk_score: RiskScore object

        Returns:
            Dict mapping dimension name to detail string
        """
        # Check if scorer provided dimension_details (via temporary attribute)
        if hasattr(risk_score, '_dimension_details'):
            return risk_score._dimension_details

        # Fallback: return placeholder details
        return {
            "write_ratio": "N/A",
            "external_call": "N/A",
            "failure_rate": "N/A",
            "revoke_count": "N/A",
            "duration_anomaly": "N/A"
        }

    def get_timeline(
        self,
        extension_id: str,
        action_id: str = "*",
        days: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[TimelineEntry]:
        """
        Get risk timeline for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*")
            days: Number of days to look back (optional)
            limit: Maximum number of entries to return (optional)

        Returns:
            List of TimelineEntry objects, ordered chronologically (oldest first)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT
                    timeline_id,
                    extension_id,
                    action_id,
                    risk_score,
                    risk_level,
                    dimension_write_ratio,
                    dimension_external_call,
                    dimension_failure_rate,
                    dimension_revoke_count,
                    dimension_duration_anomaly,
                    dimension_details,
                    window_days,
                    sample_size,
                    explanation,
                    source,
                    calculated_at,
                    recorded_at
                FROM risk_timeline
                WHERE extension_id = ? AND action_id = ?
            """
            params = [extension_id, action_id]

            # Add time filter if specified
            if days is not None:
                cutoff = datetime.utcnow() - timedelta(days=days)
                cutoff_ms = int(cutoff.timestamp() * 1000)
                query += " AND calculated_at >= ?"
                params.append(cutoff_ms)

            query += " ORDER BY calculated_at ASC"

            # Add limit if specified
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to TimelineEntry objects
            entries = []
            for row in rows:
                dimensions = {
                    "write_ratio": row["dimension_write_ratio"],
                    "external_call": row["dimension_external_call"],
                    "failure_rate": row["dimension_failure_rate"],
                    "revoke_count": row["dimension_revoke_count"],
                    "duration_anomaly": row["dimension_duration_anomaly"],
                }

                dimension_details = json.loads(row["dimension_details"])

                entry = TimelineEntry(
                    timeline_id=row["timeline_id"],
                    extension_id=row["extension_id"],
                    action_id=row["action_id"],
                    risk_score=row["risk_score"],
                    risk_level=row["risk_level"],
                    dimensions=dimensions,
                    dimension_details=dimension_details,
                    window_days=row["window_days"],
                    sample_size=row["sample_size"],
                    explanation=row["explanation"],
                    source=row["source"],
                    calculated_at=datetime.fromtimestamp(row["calculated_at"] / 1000),
                    recorded_at=datetime.fromtimestamp(row["recorded_at"] / 1000)
                )
                entries.append(entry)

            return entries

        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                return []
            raise

    def get_latest(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> Optional[TimelineEntry]:
        """
        Get the most recent risk assessment for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*")

        Returns:
            TimelineEntry or None if no history exists
        """
        entries = self.get_timeline(extension_id, action_id, limit=1000)
        return entries[-1] if entries else None

    def get_trend(
        self,
        extension_id: str,
        action_id: str = "*",
        days: Optional[int] = None
    ) -> Optional[RiskTrend]:
        """
        Calculate risk trend for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*")
            days: Number of days to analyze (optional)

        Returns:
            RiskTrend object or None if insufficient data
        """
        entries = self.get_timeline(extension_id, action_id, days=days)

        if len(entries) < 2:
            return None

        # Calculate statistics
        scores = [e.risk_score for e in entries]
        first_risk = scores[0]
        last_risk = scores[-1]
        risk_change = last_risk - first_risk

        # Determine trend direction
        if abs(risk_change) < 5.0:  # Within 5 points = stable
            trend_direction = "STABLE"
        elif risk_change > 0:
            trend_direction = "INCREASING"
        else:
            trend_direction = "DECREASING"

        return RiskTrend(
            extension_id=extension_id,
            action_id=action_id,
            assessment_count=len(entries),
            first_risk=first_risk,
            last_risk=last_risk,
            min_risk=min(scores),
            max_risk=max(scores),
            avg_risk=sum(scores) / len(scores),
            trend_direction=trend_direction,
            risk_change=risk_change,
            first_date=entries[0].calculated_at,
            last_date=entries[-1].calculated_at
        )

    def compare_timepoints(
        self,
        extension_id: str,
        action_id: str = "*",
        days_ago_1: int = 0,
        days_ago_2: int = 21
    ) -> Dict:
        """
        Compare risk at two points in time.

        This answers: "Why is it riskier/safer than N days ago?"

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*")
            days_ago_1: First time point (days ago, default 0 = now)
            days_ago_2: Second time point (days ago, default 21 = 3 weeks)

        Returns:
            Dict with comparison details:
            {
                "timepoint_1": {...},
                "timepoint_2": {...},
                "risk_change": float,
                "trend": "INCREASING" | "DECREASING" | "STABLE",
                "dimension_changes": {...}
            }
        """
        # Get entries near the two time points
        now = datetime.utcnow()
        time_1 = now - timedelta(days=days_ago_1)
        time_2 = now - timedelta(days=days_ago_2)

        all_entries = self.get_timeline(extension_id, action_id)

        # Find closest entry to each time point
        entry_1 = self._find_closest_entry(all_entries, time_1)
        entry_2 = self._find_closest_entry(all_entries, time_2)

        if not entry_1 or not entry_2:
            return {
                "error": "Insufficient timeline data for comparison",
                "available_entries": len(all_entries)
            }

        # Calculate changes
        risk_change = entry_1.risk_score - entry_2.risk_score

        # Determine trend
        if abs(risk_change) < 5.0:
            trend = "STABLE"
        elif risk_change > 0:
            trend = "INCREASING"
        else:
            trend = "DECREASING"

        # Calculate dimension changes
        dimension_changes = {}
        for dim in entry_1.dimensions.keys():
            val_1 = entry_1.dimensions[dim]
            val_2 = entry_2.dimensions[dim]
            change = val_1 - val_2
            dimension_changes[dim] = {
                "old_value": round(val_2, 4),
                "new_value": round(val_1, 4),
                "change": round(change, 4),
                "direction": "increased" if change > 0.05 else ("decreased" if change < -0.05 else "stable")
            }

        return {
            "extension_id": extension_id,
            "action_id": action_id,
            "timepoint_1": {
                "date": entry_1.calculated_at.isoformat(),
                "days_ago": days_ago_1,
                "risk_score": round(entry_1.risk_score, 2),
                "risk_level": entry_1.risk_level,
                "dimensions": entry_1.dimensions
            },
            "timepoint_2": {
                "date": entry_2.calculated_at.isoformat(),
                "days_ago": days_ago_2,
                "risk_score": round(entry_2.risk_score, 2),
                "risk_level": entry_2.risk_level,
                "dimensions": entry_2.dimensions
            },
            "risk_change": round(risk_change, 2),
            "trend": trend,
            "dimension_changes": dimension_changes,
            "explanation": self._generate_comparison_explanation(
                entry_1, entry_2, risk_change, dimension_changes
            )
        }

    def _find_closest_entry(
        self,
        entries: List[TimelineEntry],
        target_time: datetime
    ) -> Optional[TimelineEntry]:
        """
        Find the timeline entry closest to a target time.

        Args:
            entries: List of timeline entries (must be chronologically ordered)
            target_time: Target datetime

        Returns:
            Closest TimelineEntry or None
        """
        if not entries:
            return None

        # Find entry with minimum time difference
        closest = min(
            entries,
            key=lambda e: abs((e.calculated_at - target_time).total_seconds())
        )

        return closest

    def _generate_comparison_explanation(
        self,
        entry_1: TimelineEntry,
        entry_2: TimelineEntry,
        risk_change: float,
        dimension_changes: Dict
    ) -> str:
        """
        Generate human-readable explanation of risk change.

        Args:
            entry_1: Recent entry
            entry_2: Older entry
            risk_change: Risk score change
            dimension_changes: Dimension change details

        Returns:
            Human-readable explanation string
        """
        if abs(risk_change) < 5.0:
            base = "Risk has remained relatively stable"
        elif risk_change > 0:
            base = f"Risk has increased by {abs(risk_change):.1f} points"
        else:
            base = f"Risk has decreased by {abs(risk_change):.1f} points"

        # Find significant dimension changes
        significant = []
        for dim, change in dimension_changes.items():
            if change["direction"] != "stable":
                dim_name = dim.replace("_", " ").title()
                significant.append(f"{dim_name} {change['direction']}")

        if significant:
            base += " due to: " + ", ".join(significant)

        return base

    def get_count(
        self,
        extension_id: str,
        action_id: str = "*",
        days: Optional[int] = None
    ) -> int:
        """
        Get count of timeline entries for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*")
            days: Number of days to count (optional)

        Returns:
            Number of timeline entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
                SELECT COUNT(*) FROM risk_timeline
                WHERE extension_id = ? AND action_id = ?
            """
            params = [extension_id, action_id]

            if days is not None:
                cutoff = datetime.utcnow() - timedelta(days=days)
                cutoff_ms = int(cutoff.timestamp() * 1000)
                query += " AND calculated_at >= ?"
                params.append(cutoff_ms)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            conn.close()

            return count

        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                return 0
            raise
