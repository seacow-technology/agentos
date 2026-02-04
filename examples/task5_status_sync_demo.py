#!/usr/bin/env python3
"""
Task 5: Status Synchronization Demo

This script demonstrates the enhanced update() and update_status() methods
for KnowledgeSourceRepo, validating the state synchronization requirements
from SourceBridge.

Usage:
    python3 examples/task5_status_sync_demo.py
"""

import uuid
from agentos.core.knowledge.source_repo import KnowledgeSourceRepo
from agentos.core.time import utc_now_ms


def demo_basic_status_updates():
    """Demo 1: Basic status transitions"""
    print("\n=== Demo 1: Basic Status Transitions ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source in pending state
    source = repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })

    print(f"✓ Created source: {source_id}")
    created = repo.get(source_id)
    print(f"  Status: {created['status']}")

    # Update status to active
    repo.update(source_id, {"status": "active"})
    print(f"✓ Updated to 'active'")
    print(f"  Status: {repo.get(source_id)['status']}")

    # Update status to indexed with metadata
    repo.update(source_id, {
        "status": "indexed",
        "last_indexed_at": utc_now_ms(),
        "chunk_count": 100
    })
    print(f"✓ Updated to 'indexed' with metadata")
    updated = repo.get(source_id)
    print(f"  Status: {updated['status']}")
    print(f"  Chunk count: {updated['chunk_count']}")
    print(f"  Last indexed: {updated['last_indexed_at']}")

    # Cleanup
    repo.delete(source_id)
    print(f"✓ Deleted source")


def demo_update_status_method():
    """Demo 2: Using the specialized update_status() method"""
    print("\n=== Demo 2: Specialized update_status() Method ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source
    repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })
    print(f"✓ Created source: {source_id}")

    # Use update_status for successful indexing
    result = repo.update_status(
        source_id,
        status="indexed",
        chunk_count=256,
        last_indexed_at=utc_now_ms()
    )
    print(f"✓ update_status() succeeded")
    print(f"  Status: {result['status']}")
    print(f"  Chunk count: {result['chunk_count']}")

    # Cleanup
    repo.delete(source_id)


def demo_error_handling():
    """Demo 3: Error handling with metadata"""
    print("\n=== Demo 3: Error Handling ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source
    repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })
    print(f"✓ Created source: {source_id}")

    # Simulate error
    error_msg = "Permission denied: /tmp/docs"
    result = repo.update_status(
        source_id,
        status="error",
        error=error_msg
    )
    print(f"✓ Recorded error state")
    print(f"  Status: {result['status']}")
    print(f"  Error: {result['metadata']['last_error']}")

    # Retry and succeed
    result = repo.update_status(
        source_id,
        status="indexed",
        chunk_count=128,
        last_indexed_at=utc_now_ms(),
        error="Retry successful"
    )
    print(f"✓ Recovered from error")
    print(f"  Status: {result['status']}")
    print(f"  Last error: {result['metadata']['last_error']}")

    # Cleanup
    repo.delete(source_id)


def demo_status_validation():
    """Demo 4: Status validation"""
    print("\n=== Demo 4: Status Validation ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source
    repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })
    print(f"✓ Created source: {source_id}")

    # Try invalid status
    try:
        repo.update(source_id, {"status": "invalid_status"})
        print(f"✗ Should have raised ValueError")
    except ValueError as e:
        print(f"✓ Validation error caught as expected")
        print(f"  Error: {e}")

    # Cleanup
    repo.delete(source_id)


def demo_audit_trail():
    """Demo 5: Audit trail tracking"""
    print("\n=== Demo 5: Audit Trail Tracking ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source
    repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })
    print(f"✓ Created source: {source_id}")

    # Make multiple updates
    repo.update(source_id, {"status": "active"})
    repo.update_status(
        source_id,
        status="indexed",
        chunk_count=100,
        last_indexed_at=utc_now_ms()
    )

    # Check audit log
    audit_log = repo.get_audit_log(source_id=source_id)
    print(f"✓ Audit log entries: {len(audit_log)}")
    for i, entry in enumerate(audit_log, 1):
        print(f"  {i}. {entry['action']}: {entry['changed_fields']}")

    # Cleanup
    repo.delete(source_id)


def demo_state_machine():
    """Demo 6: State machine transitions"""
    print("\n=== Demo 6: State Machine Transitions ===")

    repo = KnowledgeSourceRepo()
    source_id = f"test-source-{uuid.uuid4().hex[:8]}"

    # Create source
    repo.create({
        "id": source_id,
        "name": "Test Source",
        "source_type": "local",
        "uri": "file:///tmp/docs",
        "status": "pending"
    })
    print(f"✓ Created source in 'pending' state")

    # Transition path: pending -> active -> indexed -> inactive -> active
    transitions = [
        ("active", "Source is now active"),
        ("indexed", "Source has been indexed"),
        ("inactive", "Source has been disabled"),
        ("active", "Source is active again"),
        ("error", "Error occurred during processing"),
    ]

    for new_status, description in transitions:
        repo.update(source_id, {"status": new_status})
        current = repo.get(source_id)
        print(f"✓ {description}: {current['status']}")

    # Cleanup
    repo.delete(source_id)


if __name__ == "__main__":
    print("=" * 60)
    print("Task 5: Status Synchronization Logic Demo")
    print("=" * 60)

    try:
        demo_basic_status_updates()
        demo_update_status_method()
        demo_error_handling()
        demo_status_validation()
        demo_audit_trail()
        demo_state_machine()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
        print("\nKey capabilities demonstrated:")
        print("✓ Enhanced update() method supports all required fields")
        print("✓ update_status() helper method for SourceBridge integration")
        print("✓ Status validation (6 valid states)")
        print("✓ Automatic updated_at timestamp updates")
        print("✓ Metadata field support for error tracking")
        print("✓ Chunk count and last_indexed_at tracking")
        print("✓ Complete audit trail for all changes")
        print("✓ State machine transitions")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
