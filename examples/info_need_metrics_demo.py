#!/usr/bin/env python3
"""
InfoNeed Metrics Demo

This script demonstrates how to use the InfoNeed metrics calculator
to analyze classification quality from audit logs.

Usage:
    python examples/info_need_metrics_demo.py
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentos.metrics.info_need_metrics import (
    InfoNeedMetrics,
    print_metrics_summary,
)
from agentos.core.audit import log_audit_event


def create_demo_database():
    """Create a temporary database with sample audit data"""
    # Create temp database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = temp_db.name
    temp_db.close()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            created_by TEXT,
            metadata TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_audits (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            level TEXT DEFAULT 'info',
            event_type TEXT NOT NULL,
            payload TEXT,
            created_at INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        )
    """)

    # Create ORPHAN task
    now_ts = int(datetime.now(timezone.utc).timestamp())
    cursor.execute("""
        INSERT INTO tasks (task_id, title, status, created_at, updated_at, created_by, metadata)
        VALUES ('ORPHAN', 'Orphan Events Container', 'orphan', ?, ?, 'system', '{}')
    """, (now_ts, now_ts))

    conn.commit()
    return db_path, conn


def insert_sample_data(conn):
    """Insert sample audit events for demonstration"""
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)

    # Sample classification events
    sample_events = [
        # External fact queries (should trigger REQUIRE_COMM)
        {
            "message_id": "msg_001",
            "question": "What is the latest Python version?",
            "decision": "REQUIRE_COMM",
            "classified_type": "external_fact_uncertain",
            "confidence_level": "low",
            "latency_ms": 150.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_002",
            "question": "What are today's news about AI?",
            "decision": "REQUIRE_COMM",
            "classified_type": "external_fact_uncertain",
            "confidence_level": "low",
            "latency_ms": 180.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_003",
            "question": "What is the current weather in Beijing?",
            "decision": "REQUIRE_COMM",
            "classified_type": "external_fact_uncertain",
            "confidence_level": "low",
            "latency_ms": 200.0,
            "outcome": "unnecessary_comm",  # False positive
        },

        # Local knowledge queries (direct answer)
        {
            "message_id": "msg_004",
            "question": "What is a Python decorator?",
            "decision": "DIRECT_ANSWER",
            "classified_type": "local_knowledge",
            "confidence_level": "high",
            "latency_ms": 80.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_005",
            "question": "How do I use pytest fixtures?",
            "decision": "DIRECT_ANSWER",
            "classified_type": "local_knowledge",
            "confidence_level": "high",
            "latency_ms": 90.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_006",
            "question": "What are Python best practices?",
            "decision": "DIRECT_ANSWER",
            "classified_type": "local_knowledge",
            "confidence_level": "medium",
            "latency_ms": 120.0,
            "outcome": "user_corrected",  # False negative - user wanted external opinion
        },

        # Ambient state queries (local capability)
        {
            "message_id": "msg_007",
            "question": "What is the current session mode?",
            "decision": "LOCAL_CAPABILITY",
            "classified_type": "AMBIENT_STATE",
            "confidence_level": "high",
            "latency_ms": 50.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_008",
            "question": "What time is it now?",
            "decision": "LOCAL_CAPABILITY",
            "classified_type": "AMBIENT_STATE",
            "confidence_level": "high",
            "latency_ms": 40.0,
            "outcome": "validated",
        },
        {
            "message_id": "msg_009",
            "question": "What is the current project status?",
            "decision": "LOCAL_CAPABILITY",
            "classified_type": "AMBIENT_STATE",
            "confidence_level": "high",
            "latency_ms": 60.0,
            "outcome": "validated",
        },

        # Opinion queries (suggest comm)
        {
            "message_id": "msg_010",
            "question": "Should I use React or Vue?",
            "decision": "SUGGEST_COMM",
            "classified_type": "opinion",
            "confidence_level": "medium",
            "latency_ms": 100.0,
            "outcome": "user_cancelled",
        },
    ]

    # Insert events
    for event in sample_events:
        # Insert classification
        classification_payload = {
            "message_id": event["message_id"],
            "question": event["question"],
            "decision": event["decision"],
            "classified_type": event["classified_type"],
            "confidence_level": event["confidence_level"],
            "latency_ms": event["latency_ms"],
        }

        timestamp = int((now - timedelta(hours=len(sample_events) - sample_events.index(event))).timestamp())

        cursor.execute("""
            INSERT INTO task_audits (task_id, event_type, level, payload, created_at)
            VALUES ('ORPHAN', 'info_need_classification', 'info', ?, ?)
        """, (json.dumps(classification_payload), timestamp))

        # Insert outcome if present
        if "outcome" in event:
            outcome_payload = {
                "message_id": event["message_id"],
                "outcome": event["outcome"],
            }

            cursor.execute("""
                INSERT INTO task_audits (task_id, event_type, level, payload, created_at)
                VALUES ('ORPHAN', 'info_need_outcome', 'info', ?, ?)
            """, (json.dumps(outcome_payload), timestamp + 60))

    conn.commit()


def demo_basic_calculation():
    """Demo: Basic metrics calculation"""
    print("=" * 70)
    print("Demo 1: Basic Metrics Calculation")
    print("=" * 70)
    print()

    # Create demo database
    db_path, conn = create_demo_database()
    insert_sample_data(conn)

    # Mock get_db to use our demo database
    import agentos.metrics.info_need_metrics as metrics_module
    original_get_db = metrics_module.get_db
    metrics_module.get_db = lambda: conn

    try:
        # Calculate metrics
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics()

        # Print summary
        print_metrics_summary(metrics)

        # Highlight key insights
        print("\nKey Insights:")
        print(f"  - {metrics['total_classifications']} questions classified")
        print(f"  - {metrics['comm_trigger_rate']:.0%} triggered external communication")
        print(f"  - {metrics['false_positive_rate']:.0%} false positive rate (1 unnecessary comm out of 3)")
        print(f"  - {metrics['false_negative_rate']:.0%} false negative rate (1 user correction)")
        print(f"  - {metrics['ambient_hit_rate']:.0%} ambient state accuracy (3/3 validated)")
        print()

    finally:
        # Restore original get_db
        metrics_module.get_db = original_get_db
        conn.close()
        Path(db_path).unlink()


def demo_time_range():
    """Demo: Time range filtering"""
    print("=" * 70)
    print("Demo 2: Time Range Filtering")
    print("=" * 70)
    print()

    # Create demo database
    db_path, conn = create_demo_database()
    insert_sample_data(conn)

    # Mock get_db
    import agentos.metrics.info_need_metrics as metrics_module
    original_get_db = metrics_module.get_db
    metrics_module.get_db = lambda: conn

    try:
        # Calculate metrics for last 6 hours
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=6)

        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics(start_time, end_time)

        print(f"Metrics for last 6 hours:")
        print(f"  Period: {metrics['period']['start']} to {metrics['period']['end']}")
        print(f"  Total Classifications: {metrics['total_classifications']}")
        print(f"  Comm Trigger Rate: {metrics['comm_trigger_rate']:.2%}")
        print()

    finally:
        metrics_module.get_db = original_get_db
        conn.close()
        Path(db_path).unlink()


def demo_export_json():
    """Demo: Export metrics as JSON"""
    print("=" * 70)
    print("Demo 3: Export Metrics as JSON")
    print("=" * 70)
    print()

    # Create demo database
    db_path, conn = create_demo_database()
    insert_sample_data(conn)

    # Mock get_db
    import agentos.metrics.info_need_metrics as metrics_module
    original_get_db = metrics_module.get_db
    metrics_module.get_db = lambda: conn

    try:
        # Calculate metrics
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics()

        # Export to JSON
        output_path = "/tmp/info_need_metrics_demo.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        print(f"Metrics exported to: {output_path}")
        print()
        print("Sample JSON structure:")
        print(json.dumps({
            "total_classifications": metrics["total_classifications"],
            "comm_trigger_rate": metrics["comm_trigger_rate"],
            "decision_latency": metrics["decision_latency"],
        }, indent=2))
        print()

    finally:
        metrics_module.get_db = original_get_db
        conn.close()
        Path(db_path).unlink()


def demo_breakdown_analysis():
    """Demo: Breakdown by type analysis"""
    print("=" * 70)
    print("Demo 4: Breakdown Analysis")
    print("=" * 70)
    print()

    # Create demo database
    db_path, conn = create_demo_database()
    insert_sample_data(conn)

    # Mock get_db
    import agentos.metrics.info_need_metrics as metrics_module
    original_get_db = metrics_module.get_db
    metrics_module.get_db = lambda: conn

    try:
        # Calculate metrics
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics()

        # Analyze breakdown
        breakdown = metrics["breakdown_by_type"]

        print("Classification Type Analysis:")
        print()
        for info_type, stats in sorted(breakdown.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  {info_type}:")
            print(f"    Count: {stats['count']}")
            print(f"    Percentage: {stats['percentage']:.1f}%")
            print(f"    Avg Latency: {stats['avg_latency']:.1f}ms")
            print()

        # Identify fastest and slowest types
        fastest = min(breakdown.items(), key=lambda x: x[1]["avg_latency"])
        slowest = max(breakdown.items(), key=lambda x: x[1]["avg_latency"])

        print(f"Fastest Type: {fastest[0]} ({fastest[1]['avg_latency']:.1f}ms)")
        print(f"Slowest Type: {slowest[0]} ({slowest[1]['avg_latency']:.1f}ms)")
        print()

    finally:
        metrics_module.get_db = original_get_db
        conn.close()
        Path(db_path).unlink()


def main():
    """Run all demos"""
    print()
    print("InfoNeed Metrics Demo")
    print("=" * 70)
    print()

    demos = [
        demo_basic_calculation,
        demo_time_range,
        demo_export_json,
        demo_breakdown_analysis,
    ]

    for demo in demos:
        try:
            demo()
            print()
        except Exception as e:
            print(f"Error in demo: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 70)
    print("Demo Complete!")
    print()
    print("Next steps:")
    print("  1. Try CLI: python -m agentos.cli.metrics show")
    print("  2. Generate report: python -m agentos.cli.metrics generate --output report.json")
    print("  3. Run tests: pytest tests/unit/metrics/")
    print("=" * 70)


if __name__ == "__main__":
    main()
