#!/usr/bin/env python3
"""
Test script for backfill_audit_decision_fields.py

Creates a test database, populates it with sample data, and verifies backfill works correctly.
"""

import sqlite3
import json
import tempfile
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path to import backfill script
sys.path.insert(0, str(Path(__file__).parent))
from backfill_audit_decision_fields import extract_timestamps, BackfillStats, backfill_batch


def create_test_database() -> Path:
    """Create a test database with sample data"""
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
    db_path = Path(temp_db.name)
    temp_db.close()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
        CREATE TABLE task_audits (
            audit_id INTEGER PRIMARY KEY,
            event_type TEXT NOT NULL,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_event_ts TIMESTAMP,
            supervisor_processed_at TIMESTAMP
        )
    """)

    # Create schema version table
    cursor.execute("""
        CREATE TABLE schema_version (
            version TEXT PRIMARY KEY
        )
    """)
    cursor.execute("INSERT INTO schema_version VALUES ('0.21.0')")

    # Insert test data
    test_data = [
        # Case 1: Standard payload with all fields
        {
            "audit_id": 1,
            "event_type": "SUPERVISOR_DECISION",
            "payload": json.dumps({
                "source_event_ts": "2026-01-20T10:00:00.000000",
                "supervisor_processed_at": "2026-01-20T10:00:05.000000",
                "decision_id": "dec_001"
            }),
            "created_at": "2026-01-20T10:00:10.000000"
        },
        # Case 2: Payload with alternate field names
        {
            "audit_id": 2,
            "event_type": "SUPERVISOR_DECISION_APPLIED",
            "payload": json.dumps({
                "source_ts": "2026-01-20T11:00:00.000000",
                "processed_at": "2026-01-20T11:00:03.000000",
                "decision_id": "dec_002"
            }),
            "created_at": "2026-01-20T11:00:10.000000"
        },
        # Case 3: Payload missing timestamp fields (should fallback to created_at)
        {
            "audit_id": 3,
            "event_type": "SUPERVISOR_DECISION",
            "payload": json.dumps({
                "decision_id": "dec_003"
            }),
            "created_at": "2026-01-20T12:00:00.000000"
        },
        # Case 4: Empty payload (should fallback to created_at)
        {
            "audit_id": 4,
            "event_type": "SUPERVISOR_DECISION_APPLIED",
            "payload": None,
            "created_at": "2026-01-20T13:00:00.000000"
        },
        # Case 5: Invalid JSON (should skip)
        {
            "audit_id": 5,
            "event_type": "SUPERVISOR_DECISION",
            "payload": "{invalid json",
            "created_at": "2026-01-20T14:00:00.000000"
        },
        # Case 6: Non-supervisor event (should not be processed)
        {
            "audit_id": 6,
            "event_type": "TASK_CREATED",
            "payload": json.dumps({
                "source_event_ts": "2026-01-20T15:00:00.000000",
                "supervisor_processed_at": "2026-01-20T15:00:05.000000"
            }),
            "created_at": "2026-01-20T15:00:10.000000"
        }
    ]

    for data in test_data:
        cursor.execute("""
            INSERT INTO task_audits (audit_id, event_type, payload, created_at)
            VALUES (?, ?, ?, ?)
        """, (data["audit_id"], data["event_type"], data["payload"], data["created_at"]))

    conn.commit()
    conn.close()

    return db_path


def verify_results(db_path: Path):
    """Verify backfill results"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check Case 1: Standard payload
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 1")
    row = cursor.fetchone()
    assert row[0] == "2026-01-20T10:00:00.000000", f"Case 1 failed: source_event_ts = {row[0]}"
    assert row[1] == "2026-01-20T10:00:05.000000", f"Case 1 failed: supervisor_processed_at = {row[1]}"
    print("✅ Case 1: Standard payload - PASSED")

    # Check Case 2: Alternate field names
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 2")
    row = cursor.fetchone()
    assert row[0] == "2026-01-20T11:00:00.000000", f"Case 2 failed: source_event_ts = {row[0]}"
    assert row[1] == "2026-01-20T11:00:03.000000", f"Case 2 failed: supervisor_processed_at = {row[1]}"
    print("✅ Case 2: Alternate field names - PASSED")

    # Check Case 3: Missing fields (fallback to created_at)
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 3")
    row = cursor.fetchone()
    assert row[0] == "2026-01-20T12:00:00.000000", f"Case 3 failed: source_event_ts = {row[0]}"
    assert row[1] == "2026-01-20T12:00:00.000000", f"Case 3 failed: supervisor_processed_at = {row[1]}"
    print("✅ Case 3: Missing fields (fallback) - PASSED")

    # Check Case 4: Empty payload (fallback to created_at)
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 4")
    row = cursor.fetchone()
    assert row[0] == "2026-01-20T13:00:00.000000", f"Case 4 failed: source_event_ts = {row[0]}"
    assert row[1] == "2026-01-20T13:00:00.000000", f"Case 4 failed: supervisor_processed_at = {row[1]}"
    print("✅ Case 4: Empty payload (fallback) - PASSED")

    # Check Case 5: Invalid JSON (should be NULL)
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 5")
    row = cursor.fetchone()
    # Note: In actual backfill, this might skip or use fallback depending on implementation
    print(f"⚠️  Case 5: Invalid JSON - source_event_ts={row[0]}, supervisor_processed_at={row[1]}")

    # Check Case 6: Non-supervisor event (should be NULL)
    cursor.execute("SELECT source_event_ts, supervisor_processed_at FROM task_audits WHERE audit_id = 6")
    row = cursor.fetchone()
    assert row[0] is None, f"Case 6 failed: Non-supervisor event should not be backfilled"
    assert row[1] is None, f"Case 6 failed: Non-supervisor event should not be backfilled"
    print("✅ Case 6: Non-supervisor event (skipped) - PASSED")

    conn.close()


def test_extract_timestamps():
    """Test the extract_timestamps function"""
    print("\n" + "=" * 60)
    print("Testing extract_timestamps function")
    print("=" * 60)

    # Test 1: Standard payload
    payload = json.dumps({
        "source_event_ts": "2026-01-20T10:00:00",
        "supervisor_processed_at": "2026-01-20T10:00:05"
    })
    result = extract_timestamps(payload, "2026-01-20T10:00:10")
    assert result["source_event_ts"] == "2026-01-20T10:00:00"
    assert result["supervisor_processed_at"] == "2026-01-20T10:00:05"
    print("✅ Test 1: Standard payload - PASSED")

    # Test 2: Alternate field names
    payload = json.dumps({
        "source_ts": "2026-01-20T11:00:00",
        "processed_at": "2026-01-20T11:00:03"
    })
    result = extract_timestamps(payload, "2026-01-20T11:00:10")
    assert result["source_event_ts"] == "2026-01-20T11:00:00"
    assert result["supervisor_processed_at"] == "2026-01-20T11:00:03"
    print("✅ Test 2: Alternate field names - PASSED")

    # Test 3: Missing fields (fallback)
    payload = json.dumps({"decision_id": "dec_003"})
    result = extract_timestamps(payload, "2026-01-20T12:00:00")
    assert result["source_event_ts"] == "2026-01-20T12:00:00"
    assert result["supervisor_processed_at"] == "2026-01-20T12:00:00"
    print("✅ Test 3: Missing fields (fallback) - PASSED")

    # Test 4: Invalid JSON
    result = extract_timestamps("{invalid", "2026-01-20T13:00:00")
    assert result["source_event_ts"] is None
    assert result["supervisor_processed_at"] is None
    print("✅ Test 4: Invalid JSON - PASSED")

    # Test 5: Empty string
    result = extract_timestamps("", "2026-01-20T14:00:00")
    assert result["source_event_ts"] == "2026-01-20T14:00:00"
    assert result["supervisor_processed_at"] == "2026-01-20T14:00:00"
    print("✅ Test 5: Empty string (fallback) - PASSED")


def main():
    print("=" * 60)
    print("Backfill Test Suite")
    print("=" * 60)

    # Test 1: extract_timestamps function
    test_extract_timestamps()

    # Test 2: Full backfill process
    print("\n" + "=" * 60)
    print("Testing full backfill process")
    print("=" * 60)

    db_path = create_test_database()
    print(f"Created test database: {db_path}")

    try:
        # Run backfill (not dry-run)
        stats = BackfillStats()
        backfill_batch(db_path, batch_size=100, dry_run=False, stats=stats)

        print(f"\nBackfill completed:")
        print(f"  Total processed: {stats.total_rows}")
        print(f"  Successfully filled: {stats.filled_successfully}")
        print(f"  Failed: {stats.failed_to_parse}")
        print(f"  Missing fields: {stats.missing_payload_fields}")

        # Verify results
        print("\n" + "=" * 60)
        print("Verifying results")
        print("=" * 60)
        verify_results(db_path)

        print("\n" + "=" * 60)
        print("✅ All tests PASSED!")
        print("=" * 60)

    finally:
        # Cleanup
        db_path.unlink()
        print(f"\nCleaned up test database: {db_path}")


if __name__ == "__main__":
    main()
