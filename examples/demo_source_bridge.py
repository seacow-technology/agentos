"""
Demo: SourceBridge - Connecting Knowledge Sources to KB System
================================================================

This example demonstrates the SourceBridge functionality for Task 4.

Workflow:
1. Create a knowledge source configuration
2. Sync the source using SourceBridge
3. Verify indexed data in kb_sources and kb_chunks
4. Check source health status
"""

import tempfile
from pathlib import Path

from agentos.core.knowledge.source_bridge import SourceBridge
from agentos.core.knowledge.source_repo import KnowledgeSourceRepo


def main():
    print("=" * 70)
    print("Demo: SourceBridge - Knowledge Source Synchronization")
    print("=" * 70)
    print()

    # Step 1: Create temporary test documents
    print("[Step 1] Creating test documents...")
    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "test_doc.md"
    test_content = """# AgentOS Knowledge Base

## Introduction

AgentOS is a modern agent orchestration system.

## Features

- Knowledge base management
- Source synchronization
- Full-text search with FTS5
- Chunk-based indexing

## Architecture

The system consists of:
- KnowledgeSourceRepo: Configuration storage
- SourceBridge: Synchronization layer
- ProjectKBIndexer: Index management
- LocalSource: File system integration

## Conclusion

This demonstrates the end-to-end workflow.
"""
    test_file.write_text(test_content)
    print(f"   Created test file: {test_file}")
    print()

    # Step 2: Create knowledge source
    print("[Step 2] Creating knowledge source...")
    repo = KnowledgeSourceRepo()

    # Generate unique ID for this demo
    import uuid
    source_id = f"demo-source-{uuid.uuid4().hex[:8]}"

    repo.create({
        "id": source_id,
        "name": "Demo Documentation",
        "source_type": "local",
        "uri": f"file://{temp_dir}",
        "options": {
            "file_types": ["md"],
            "recursive": False
        },
        "status": "pending"
    })

    source = repo.get(source_id)
    print(f"   Created source: {source_id}")
    print(f"   Name: {source['name']}")
    print(f"   Type: {source['source_type']}")
    print(f"   URI: {source['uri']}")
    print(f"   Status: {source['status']}")
    print()

    # Step 3: Initialize SourceBridge
    print("[Step 3] Initializing SourceBridge...")
    bridge = SourceBridge()
    print("   SourceBridge initialized successfully")
    print()

    # Step 4: Sync the source
    print("[Step 4] Synchronizing source...")
    result = bridge.sync_source(source_id)

    if result.success:
        print(f"   ✓ Sync successful!")
        print(f"   - Chunks indexed: {result.chunk_count}")
        print(f"   - Duration: {result.duration_ms}ms")
    else:
        print(f"   ✗ Sync failed!")
        print(f"   - Error: {result.error}")
        return

    print()

    # Step 5: Verify updated source status
    print("[Step 5] Verifying source status...")
    updated_source = repo.get(source_id)
    print(f"   Status: {updated_source['status']}")
    print(f"   Chunk count: {updated_source['chunk_count']}")
    print(f"   Last indexed: {updated_source['last_indexed_at']}")
    print()

    # Step 6: Check source health
    print("[Step 6] Checking source health...")
    health = bridge.check_source_health(source_id)

    if health["healthy"]:
        print(f"   ✓ Source is healthy")
        metrics = health["metrics"]
        print(f"   - Files available: {metrics.get('file_count', 0)}")
        print(f"   - Path exists: {metrics.get('path_exists', False)}")
        print(f"   - Readable: {metrics.get('readable', False)}")
    else:
        print(f"   ✗ Source is unhealthy")
        print(f"   - Error: {health.get('error')}")

    print()

    # Step 7: View sync result details
    print("[Step 7] Sync Result Summary")
    print("-" * 70)
    sync_dict = result.to_dict()
    for key, value in sync_dict.items():
        print(f"   {key:15s}: {value}")

    print()
    print("=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
