#!/usr/bin/env python3
"""
Knowledge Sources Persistent Storage Demo

This script demonstrates the new persistent storage for knowledge data sources.
Previously, data sources were stored in memory and lost on restart.
Now they are persisted to SQLite with full audit logging.

Usage:
    python examples/knowledge_sources_demo.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.knowledge import KnowledgeSourceRepo
import json


def demo_knowledge_sources():
    """Demonstrate knowledge source persistence"""

    print("\n" + "=" * 70)
    print("  Knowledge Sources Persistent Storage Demo")
    print("=" * 70)

    repo = KnowledgeSourceRepo()

    # Demo 1: Create sources
    print("\n📝 Creating knowledge sources...")

    sources_to_create = [
        {
            "id": "demo-docs-001",
            "name": "Project Documentation",
            "source_type": "local",
            "uri": "/path/to/project/docs",
            "options": {
                "recursive": True,
                "file_types": ["md", "txt", "rst"]
            },
            "status": "pending"
        },
        {
            "id": "demo-api-001",
            "name": "External API Docs",
            "source_type": "web",
            "uri": "https://api.example.com/docs",
            "options": {
                "refresh_interval": 3600
            },
            "status": "active"
        },
        {
            "id": "demo-db-001",
            "name": "Customer Database",
            "source_type": "database",
            "uri": "postgresql://localhost/customers",
            "auth_config": {
                "username": "demo_user",
                "password": "REDACTED"
            },
            "options": {
                "tables": ["users", "orders"],
                "sync_interval": 900
            },
            "status": "active"
        }
    ]

    for source in sources_to_create:
        source_id = repo.create(source)
        print(f"  ✓ Created: {source['name']} ({source['source_type']})")

    # Demo 2: List and filter
    print("\n📋 Listing sources...")

    all_sources = repo.list()
    print(f"  Total sources: {len(all_sources)}")

    local_sources = repo.list(source_type="local")
    print(f"  Local sources: {len(local_sources)}")

    active_sources = repo.list(status="active")
    print(f"  Active sources: {len(active_sources)}")

    # Demo 3: Update a source
    print("\n🔄 Updating source status...")

    repo.update("demo-docs-001", {
        "status": "indexed",
        "chunk_count": 250,
        "last_indexed_at": 1738416000000  # 2026-02-01 12:00:00 UTC
    })

    updated = repo.get("demo-docs-001")
    print(f"  ✓ Updated: {updated['name']}")
    print(f"    Status: {updated['status']}")
    print(f"    Chunks: {updated['chunk_count']}")

    # Demo 4: View audit log
    print("\n📊 Audit log for 'Project Documentation'...")

    audit_log = repo.get_audit_log(source_id="demo-docs-001")
    print(f"  Found {len(audit_log)} audit entries:")

    for i, entry in enumerate(audit_log, 1):
        print(f"\n  Entry {i}:")
        print(f"    Action: {entry['action']}")
        print(f"    Changed fields: {entry.get('changed_fields', [])}")

        if entry['action'] == 'create':
            print(f"    Initial values: name={entry['new_values'].get('name')}")
        elif entry['action'] == 'update':
            print(f"    Old status: {entry['old_values'].get('status')}")
            print(f"    New status: {entry['new_values'].get('status')}")

    # Demo 5: Persistence demonstration
    print("\n🔁 Demonstrating persistence...")
    print("  Creating new repo instance (simulates restart)...")

    new_repo = KnowledgeSourceRepo()
    persisted = new_repo.get("demo-docs-001")

    if persisted:
        print(f"  ✓ Data persists: {persisted['name']}")
        print(f"    Status: {persisted['status']}")
        print(f"    Chunks: {persisted['chunk_count']}")
    else:
        print("  ✗ Data not found!")

    # Demo 6: Cleanup
    print("\n🧹 Cleaning up demo data...")

    for source_id in ["demo-docs-001", "demo-api-001", "demo-db-001"]:
        if repo.get(source_id):
            repo.delete(source_id)
            print(f"  ✓ Deleted: {source_id}")

    # Verify audit log persists after deletion
    print("\n📊 Verifying audit log persists after deletion...")
    audit_after_delete = repo.get_audit_log(source_id="demo-docs-001")
    print(f"  Audit entries after deletion: {len(audit_after_delete)}")

    delete_entry = next((e for e in audit_after_delete if e["action"] == "delete"), None)
    if delete_entry:
        print(f"  ✓ Delete action recorded in audit log")
    else:
        print(f"  ✗ Delete action not found")

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\nKey Features Demonstrated:")
    print("  ✓ Persistent storage (survives restarts)")
    print("  ✓ CRUD operations (Create, Read, Update, Delete)")
    print("  ✓ Filtering by type and status")
    print("  ✓ Full audit logging")
    print("  ✓ Audit log preserved after deletion")
    print("\n")


if __name__ == "__main__":
    try:
        demo_knowledge_sources()
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
