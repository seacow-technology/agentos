"""
InfoNeed Classification Quality Metrics Calculator

This module calculates quality metrics for InfoNeed classification based solely
on audit logs. No semantic analysis or model inference involved - pure statistics.

Core Metrics:
1. comm_trigger_rate: How often REQUIRE_COMM is triggered
2. false_positive_rate: Unnecessary comm requests
3. false_negative_rate: User corrections for missed comm opportunities
4. ambient_hit_rate: AMBIENT_STATE classification accuracy
5. decision_latency: Classification performance (p50, p95, p99, avg)
6. decision_stability: Consistency for similar questions

Constraints:
- Only uses audit log data
- No LLM or semantic processing
- Can run offline as batch job
- Pure statistical calculation
"""

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agentos.store import get_db


class InfoNeedMetrics:
    """
    InfoNeed classification quality metrics calculator

    This class provides methods to calculate various quality metrics
    for InfoNeed classification based on audit log events.
    """

    def __init__(self):
        """Initialize metrics calculator"""
        pass

    def calculate_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate all quality metrics for a time period

        Args:
            start_time: Start of time period (default: 24 hours ago)
            end_time: End of time period (default: now)

        Returns:
            Dictionary containing all calculated metrics
        """
        # Set default time range
        if not end_time:
            end_time = datetime.now(timezone.utc)
        if not start_time:
            start_time = end_time - timedelta(hours=24)

        # Load audit events
        classifications = self._load_classifications(start_time, end_time)
        outcomes = self._load_outcomes(start_time, end_time)

        # Enrich classifications with outcomes
        enriched_data = self._enrich_with_outcomes(classifications, outcomes)

        # Calculate all metrics
        metrics = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "total_classifications": len(classifications),
            "total_outcomes": len(outcomes),
            "comm_trigger_rate": self._calc_comm_trigger_rate(enriched_data),
            "false_positive_rate": self._calc_false_positive_rate(enriched_data),
            "false_negative_rate": self._calc_false_negative_rate(enriched_data),
            "ambient_hit_rate": self._calc_ambient_hit_rate(enriched_data),
            "decision_latency": self._calc_decision_latency(classifications),
            "decision_stability": self._calc_decision_stability(classifications),
            "breakdown_by_type": self._calc_breakdown_by_type(enriched_data),
            "outcome_distribution": self._calc_outcome_distribution(outcomes),
            "metadata": {
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        }

        return metrics

    def _load_classifications(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Load info_need_classification events from audit log

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            List of classification events
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            # Convert datetime to Unix timestamp
            start_ts = int(start_time.timestamp())
            end_ts = int(end_time.timestamp())

            cursor.execute("""
                SELECT audit_id, task_id, event_type, payload, created_at
                FROM task_audits
                WHERE event_type = 'info_need_classification'
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at ASC
            """, (start_ts, end_ts))

            rows = cursor.fetchall()

            events = []
            for row in rows:
                payload = json.loads(row["payload"]) if row["payload"] else {}
                events.append({
                    "audit_id": row["audit_id"],
                    "task_id": row["task_id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    "message_id": payload.get("message_id"),
                    "decision": payload.get("decision"),
                    "classified_type": payload.get("classified_type"),
                    "confidence_level": payload.get("confidence_level"),
                    "latency_ms": payload.get("latency_ms"),
                    "question": payload.get("question", ""),
                    "payload": payload,
                })

            return events

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def _load_outcomes(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Load info_need_outcome events from audit log

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            List of outcome events
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            # Convert datetime to Unix timestamp
            start_ts = int(start_time.timestamp())
            end_ts = int(end_time.timestamp())

            cursor.execute("""
                SELECT audit_id, task_id, event_type, payload, created_at
                FROM task_audits
                WHERE event_type = 'info_need_outcome'
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at ASC
            """, (start_ts, end_ts))

            rows = cursor.fetchall()

            events = []
            for row in rows:
                payload = json.loads(row["payload"]) if row["payload"] else {}
                events.append({
                    "audit_id": row["audit_id"],
                    "task_id": row["task_id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    "message_id": payload.get("message_id"),
                    "outcome": payload.get("outcome"),
                    "payload": payload,
                })

            return events

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def _enrich_with_outcomes(
        self,
        classifications: List[Dict],
        outcomes: List[Dict]
    ) -> List[Dict]:
        """
        Enrich classifications with corresponding outcome data

        Args:
            classifications: List of classification events
            outcomes: List of outcome events

        Returns:
            List of enriched classification events
        """
        # Build outcome lookup map by message_id
        outcome_map = {}
        for outcome in outcomes:
            msg_id = outcome.get("message_id")
            if msg_id:
                outcome_map[msg_id] = outcome

        # Enrich classifications
        enriched = []
        for classification in classifications:
            enriched_item = classification.copy()
            msg_id = classification.get("message_id")

            if msg_id and msg_id in outcome_map:
                enriched_item["outcome"] = outcome_map[msg_id]
            else:
                enriched_item["outcome"] = None

            enriched.append(enriched_item)

        return enriched

    def _calc_comm_trigger_rate(self, data: List[Dict]) -> float:
        """
        Calculate communication trigger rate

        comm_trigger_rate = count(decision == "REQUIRE_COMM") / count(all)

        Args:
            data: Enriched classification events

        Returns:
            Trigger rate as float (0.0 to 1.0)
        """
        if not data:
            return 0.0

        comm_count = sum(
            1 for item in data
            if item.get("decision") == "REQUIRE_COMM"
        )

        return comm_count / len(data)

    def _calc_false_positive_rate(self, data: List[Dict]) -> float:
        """
        Calculate false positive rate

        false_positive_rate = count(REQUIRE_COMM AND unnecessary) / count(REQUIRE_COMM)

        Args:
            data: Enriched classification events

        Returns:
            False positive rate as float (0.0 to 1.0)
        """
        require_comm = [
            item for item in data
            if item.get("decision") == "REQUIRE_COMM"
        ]

        if not require_comm:
            return 0.0

        unnecessary = sum(
            1 for item in require_comm
            if item.get("outcome") and
               item["outcome"].get("outcome") == "unnecessary_comm"
        )

        return unnecessary / len(require_comm)

    def _calc_false_negative_rate(self, data: List[Dict]) -> float:
        """
        Calculate false negative rate

        false_negative_rate = count(NOT REQUIRE_COMM AND user_corrected) / count(NOT REQUIRE_COMM)

        Args:
            data: Enriched classification events

        Returns:
            False negative rate as float (0.0 to 1.0)
        """
        no_comm = [
            item for item in data
            if item.get("decision") != "REQUIRE_COMM"
        ]

        if not no_comm:
            return 0.0

        corrected = sum(
            1 for item in no_comm
            if item.get("outcome") and
               item["outcome"].get("outcome") == "user_corrected"
        )

        return corrected / len(no_comm)

    def _calc_ambient_hit_rate(self, data: List[Dict]) -> float:
        """
        Calculate ambient state hit rate

        ambient_hit_rate = count(AMBIENT_STATE AND validated) / count(AMBIENT_STATE)

        Args:
            data: Enriched classification events

        Returns:
            Hit rate as float (0.0 to 1.0)
        """
        ambient = [
            item for item in data
            if item.get("classified_type") == "AMBIENT_STATE"
        ]

        if not ambient:
            return 0.0

        validated = sum(
            1 for item in ambient
            if item.get("outcome") and
               item["outcome"].get("outcome") == "validated"
        )

        return validated / len(ambient)

    def _calc_decision_latency(self, classifications: List[Dict]) -> Dict[str, float]:
        """
        Calculate decision latency percentiles

        Returns p50, p95, p99, and average latency in milliseconds

        Args:
            classifications: Classification events with latency_ms

        Returns:
            Dictionary with latency percentiles
        """
        latencies = [
            item["latency_ms"] for item in classifications
            if item.get("latency_ms") is not None
        ]

        if not latencies:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "avg": 0.0,
                "count": 0,
            }

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(values: List[float], p: float) -> float:
            """Calculate percentile value"""
            if not values:
                return 0.0
            k = (len(values) - 1) * p
            f = int(k)
            c = f + 1
            if c >= len(values):
                return values[-1]
            d0 = values[f] * (c - k)
            d1 = values[c] * (k - f)
            return d0 + d1

        return {
            "p50": percentile(sorted_latencies, 0.50),
            "p95": percentile(sorted_latencies, 0.95),
            "p99": percentile(sorted_latencies, 0.99),
            "avg": statistics.mean(latencies),
            "count": n,
        }

    def _calc_decision_stability(self, classifications: List[Dict]) -> float:
        """
        Calculate decision stability (consistency for similar questions)

        This is a simplified implementation that groups by exact question match.
        A full implementation would use similarity scoring (e.g., Jaccard similarity).

        Args:
            classifications: Classification events

        Returns:
            Stability score as float (0.0 to 1.0)
        """
        # Group by question text
        question_groups = defaultdict(list)
        for item in classifications:
            question = item.get("question", "").strip().lower()
            if question:
                decision = item.get("decision")
                question_groups[question].append(decision)

        # Calculate stability: questions with consistent decisions
        if not question_groups:
            return 0.0

        total_questions = 0
        consistent_questions = 0

        for question, decisions in question_groups.items():
            if len(decisions) > 1:  # Only consider questions asked multiple times
                total_questions += 1
                # Check if all decisions are the same
                if len(set(decisions)) == 1:
                    consistent_questions += 1

        if total_questions == 0:
            return 0.0  # Not enough data

        return consistent_questions / total_questions

    def _calc_breakdown_by_type(self, data: List[Dict]) -> Dict[str, Any]:
        """
        Calculate statistics breakdown by classification type

        Args:
            data: Enriched classification events

        Returns:
            Dictionary with per-type statistics
        """
        breakdown = {}

        # Get all unique types
        types = set(item.get("classified_type") for item in data if item.get("classified_type"))

        for info_type in types:
            type_data = [item for item in data if item.get("classified_type") == info_type]

            # Calculate latencies for this type
            latencies = [
                item["latency_ms"] for item in type_data
                if item.get("latency_ms") is not None
            ]

            breakdown[info_type] = {
                "count": len(type_data),
                "percentage": (len(type_data) / len(data) * 100) if data else 0.0,
                "avg_latency": statistics.mean(latencies) if latencies else 0.0,
            }

        return breakdown

    def _calc_outcome_distribution(self, outcomes: List[Dict]) -> Dict[str, int]:
        """
        Calculate outcome distribution

        Args:
            outcomes: Outcome events

        Returns:
            Dictionary mapping outcome types to counts
        """
        distribution = {
            "validated": 0,
            "unnecessary_comm": 0,
            "user_corrected": 0,
            "user_cancelled": 0,
        }

        for outcome in outcomes:
            outcome_type = outcome.get("outcome", "unknown")
            if outcome_type in distribution:
                distribution[outcome_type] += 1
            else:
                # Track unknown outcomes
                if "unknown" not in distribution:
                    distribution["unknown"] = 0
                distribution["unknown"] += 1

        return distribution


def generate_metrics_report(
    output_path: str = "metrics_report.json",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Generate metrics report and save to file

    Args:
        output_path: Path to save JSON report
        start_time: Start of time period (default: 24 hours ago)
        end_time: End of time period (default: now)

    Returns:
        Metrics dictionary
    """
    calculator = InfoNeedMetrics()
    metrics = calculator.calculate_metrics(start_time, end_time)

    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return metrics


def print_metrics_summary(metrics: Dict[str, Any]) -> None:
    """
    Print human-readable metrics summary

    Args:
        metrics: Metrics dictionary from calculate_metrics()
    """
    print("=" * 70)
    print("InfoNeed Classification Quality Metrics")
    print("=" * 70)
    print()

    # Period
    period = metrics.get("period", {})
    print(f"Period: {period.get('start', 'N/A')} to {period.get('end', 'N/A')}")
    print(f"Total Classifications: {metrics.get('total_classifications', 0)}")
    print(f"Total Outcomes: {metrics.get('total_outcomes', 0)}")
    print()

    # Core metrics
    print("Core Metrics:")
    print(f"  Comm Trigger Rate:     {metrics.get('comm_trigger_rate', 0):.2%}")
    print(f"  False Positive Rate:   {metrics.get('false_positive_rate', 0):.2%}")
    print(f"  False Negative Rate:   {metrics.get('false_negative_rate', 0):.2%}")
    print(f"  Ambient Hit Rate:      {metrics.get('ambient_hit_rate', 0):.2%}")
    print(f"  Decision Stability:    {metrics.get('decision_stability', 0):.2%}")
    print()

    # Latency
    latency = metrics.get("decision_latency", {})
    print("Decision Latency:")
    print(f"  P50: {latency.get('p50', 0):.1f}ms")
    print(f"  P95: {latency.get('p95', 0):.1f}ms")
    print(f"  P99: {latency.get('p99', 0):.1f}ms")
    print(f"  Avg: {latency.get('avg', 0):.1f}ms")
    print()

    # Breakdown by type
    breakdown = metrics.get("breakdown_by_type", {})
    if breakdown:
        print("Breakdown by Type:")
        for type_name, stats in breakdown.items():
            print(f"  {type_name:30s}: {stats['count']:3d} ({stats['percentage']:5.1f}%) - avg {stats['avg_latency']:.1f}ms")
        print()

    # Outcome distribution
    outcomes = metrics.get("outcome_distribution", {})
    if outcomes:
        print("Outcome Distribution:")
        for outcome_type, count in outcomes.items():
            print(f"  {outcome_type:30s}: {count:3d}")
        print()

    print("=" * 70)
