"""
Risk Scorer

Main risk calculation engine that:
1. Queries historical execution data
2. Calculates individual risk dimensions
3. Aggregates weighted risk score
4. Generates explanation

All calculations are deterministic and based on measurable facts.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .models import RiskScore
from .dimensions import (
    calc_write_ratio,
    calc_external_call,
    calc_failure_rate,
    calc_revoke_count,
    calc_duration_anomaly,
)
from .explainer import RiskExplainer


class RiskScorer:
    """
    Risk score calculator for extensions based on historical audit data.

    Provides deterministic, explainable risk scores based on:
    - Write operation frequency
    - External API calls
    - Historical failure rate
    - Authorization revocation history
    - Execution duration anomalies

    Risk scores are NOT used for execution decisions directly,
    they are provided as input to Policy Engine (D4).
    """

    # Dimension weights (v0 fixed weights)
    WEIGHTS = {
        "write_ratio": 0.30,
        "external_call": 0.25,
        "failure_rate": 0.25,
        "revoke_count": 0.15,
        "duration_anomaly": 0.05,
    }

    def __init__(self, db_path: str, record_timeline: bool = True):
        """
        Initialize risk scorer.

        Args:
            db_path: Path to SQLite database with execution history
            record_timeline: Whether to automatically record to risk timeline (default True)
        """
        self.db_path = db_path
        self.record_timeline = record_timeline
        self._timeline = None  # Lazy initialization

    def calculate_risk(
        self,
        extension_id: str,
        action_id: str = "*",
        window_days: int = 30
    ) -> RiskScore:
        """
        Calculate risk score for an extension/action.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*" for all actions)
            window_days: Historical window in days (default 30)

        Returns:
            RiskScore with score, dimensions, and explanation
        """
        # 1. Query historical execution data
        executions = self._query_history(extension_id, action_id, window_days)

        # 2. Calculate individual dimensions
        dimension_values = {}
        dimension_details = {}

        # Write ratio
        write_val, write_detail = calc_write_ratio(executions)
        dimension_values["write_ratio"] = write_val
        dimension_details["write_ratio"] = write_detail

        # External calls
        external_val, external_detail = calc_external_call(executions)
        dimension_values["external_call"] = external_val
        dimension_details["external_call"] = external_detail

        # Failure rate
        failure_val, failure_detail = calc_failure_rate(executions)
        dimension_values["failure_rate"] = failure_val
        dimension_details["failure_rate"] = failure_detail

        # Revoke count
        revoke_val, revoke_detail = calc_revoke_count(self.db_path, extension_id)
        dimension_values["revoke_count"] = revoke_val
        dimension_details["revoke_count"] = revoke_detail

        # Duration anomaly
        duration_val, duration_detail = calc_duration_anomaly(executions)
        dimension_values["duration_anomaly"] = duration_val
        dimension_details["duration_anomaly"] = duration_detail

        # 3. Calculate weighted risk score
        risk_score = self._aggregate_score(dimension_values)

        # 4. Create RiskScore object
        risk_score_obj = RiskScore(
            score=risk_score,
            dimensions=dimension_values,
            explanation="",  # Will be filled next
            calculated_at=datetime.utcnow(),
            window_days=window_days,
            sample_size=len(executions)
        )

        # 5. Generate explanation
        explanation = RiskExplainer.explain(risk_score_obj, dimension_details)
        risk_score_obj.explanation = explanation

        # 6. Record to timeline (if enabled)
        self._record_to_timeline(risk_score_obj, extension_id, action_id, dimension_details)

        return risk_score_obj

    def _aggregate_score(self, dimensions: Dict[str, float]) -> float:
        """
        Aggregate dimension values into final risk score.

        Args:
            dimensions: Dict of dimension name -> normalized value (0-1)

        Returns:
            Risk score (0-100)
        """
        weighted_sum = 0.0
        for dim_name, dim_value in dimensions.items():
            weight = self.WEIGHTS.get(dim_name, 0.0)
            weighted_sum += dim_value * weight

        # Scale to 0-100
        return weighted_sum * 100

    def _query_history(
        self,
        extension_id: str,
        action_id: str,
        window_days: int
    ) -> List[Dict]:
        """
        Query execution history from database.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier ("*" for all)
            window_days: Number of days to look back

        Returns:
            List of execution records as dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Calculate window start timestamp
            window_start = datetime.utcnow() - timedelta(days=window_days)
            window_start_ms = int(window_start.timestamp() * 1000)

            # Build query
            if action_id == "*":
                query = """
                    SELECT
                        execution_id,
                        extension_id,
                        action_id,
                        runner_type,
                        status,
                        exit_code,
                        duration_ms,
                        metadata,
                        started_at,
                        completed_at
                    FROM extension_executions
                    WHERE extension_id = ?
                      AND started_at >= ?
                    ORDER BY started_at DESC
                """
                params = (extension_id, window_start_ms)
            else:
                query = """
                    SELECT
                        execution_id,
                        extension_id,
                        action_id,
                        runner_type,
                        status,
                        exit_code,
                        duration_ms,
                        metadata,
                        started_at,
                        completed_at
                    FROM extension_executions
                    WHERE extension_id = ?
                      AND action_id = ?
                      AND started_at >= ?
                    ORDER BY started_at DESC
                """
                params = (extension_id, action_id, window_start_ms)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dicts
            executions = [dict(row) for row in rows]
            return executions

        except sqlite3.OperationalError as e:
            # Table might not exist yet
            if "no such table" in str(e).lower():
                return []
            raise

        except Exception as e:
            # Log error but don't fail
            print(f"Warning: Failed to query execution history: {e}")
            return []

    def get_risk_summary(
        self,
        extension_id: str,
        action_id: str = "*",
        window_days: int = 30
    ) -> str:
        """
        Get compact risk summary (one-liner).

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            window_days: Historical window in days

        Returns:
            One-line risk summary
        """
        risk_score = self.calculate_risk(extension_id, action_id, window_days)
        return RiskExplainer.explain_compact(risk_score)

    def _record_to_timeline(
        self,
        risk_score: RiskScore,
        extension_id: str,
        action_id: str,
        dimension_details: Dict[str, str]
    ) -> None:
        """
        Record risk score to timeline (if enabled).

        Args:
            risk_score: Calculated risk score
            extension_id: Extension identifier
            action_id: Action identifier
            dimension_details: Dimension detail strings
        """
        if not self.record_timeline:
            return

        try:
            # Lazy import to avoid circular dependency
            from .timeline import RiskTimeline

            # Lazy initialization
            if self._timeline is None:
                self._timeline = RiskTimeline(self.db_path)

            # Enhance risk_score with dimension_details
            # Store in a temporary attribute for timeline recording
            risk_score._dimension_details = dimension_details

            # Record to timeline
            self._timeline.record(
                risk_score=risk_score,
                extension_id=extension_id,
                action_id=action_id,
                source="scorer_auto",
                source_details={
                    "scorer_version": "0.1.0",
                    "weights": self.WEIGHTS
                }
            )

        except Exception as e:
            # Graceful degradation - don't fail scoring if timeline recording fails
            print(f"Warning: Failed to record to risk timeline: {e}")
