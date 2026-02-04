"""
Demo Script for Task 7 - SourceBridge API Integration

This script demonstrates how to use the new sync API endpoints:
1. POST /api/knowledge/sources/{source_id}/sync
2. POST /api/knowledge/sources/sync-all
3. POST /api/knowledge/jobs (enhanced with source_id)

Prerequisites:
    - AgentOS WebUI server running on http://localhost:8000
    - At least one knowledge source configured in the system

Usage:
    python examples/demo_task7_sync_api.py
"""

import json
import time
import requests
from typing import Dict, Any


# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/knowledge"


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_response(response: requests.Response):
    """Pretty print API response"""
    print(f"Status: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def demo_list_sources() -> list:
    """
    Demo: List all knowledge sources

    Returns:
        List of source IDs
    """
    print_section("1. List Knowledge Sources")

    response = requests.get(f"{API_BASE}/sources")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            sources = data["data"]["sources"]
            source_ids = [s["source_id"] for s in sources]
            print(f"\nFound {len(source_ids)} sources: {source_ids}")
            return source_ids

    return []


def demo_sync_single_source(source_id: str):
    """
    Demo: Sync a single knowledge source

    Args:
        source_id: Source ID to sync
    """
    print_section(f"2. Sync Single Source: {source_id}")

    print(f"Triggering sync for source: {source_id}...")
    start_time = time.time()

    response = requests.post(f"{API_BASE}/sources/{source_id}/sync")
    print_response(response)

    elapsed = time.time() - start_time

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            result = data["data"]
            print(f"\n✓ Sync completed successfully!")
            print(f"  - Chunks indexed: {result['chunk_count']}")
            print(f"  - Duration: {result['duration_ms']}ms")
            print(f"  - Client elapsed: {elapsed:.2f}s")
        else:
            print(f"\n✗ Sync failed: {data.get('error')}")
    else:
        print(f"\n✗ Request failed: {response.status_code}")


def demo_sync_all_sources():
    """
    Demo: Batch sync all active sources
    """
    print_section("3. Batch Sync All Active Sources")

    print("Triggering batch sync for all active sources...")
    start_time = time.time()

    response = requests.post(f"{API_BASE}/sources/sync-all")
    print_response(response)

    elapsed = time.time() - start_time

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            summary = data["data"]
            print(f"\n✓ Batch sync completed!")
            print(f"  - Total sources: {summary['total_sources']}")
            print(f"  - Succeeded: {summary['success_count']}")
            print(f"  - Failed: {summary['failed_count']}")
            print(f"  - Client elapsed: {elapsed:.2f}s")

            # Show individual results
            print("\n  Individual Results:")
            for idx, result in enumerate(summary["results"], 1):
                status = "✓" if result["success"] else "✗"
                print(f"    {idx}. {status} {result['source_id']}: "
                      f"{result['chunk_count']} chunks, "
                      f"{result['duration_ms']}ms")
                if not result["success"]:
                    print(f"       Error: {result['error']}")
        else:
            print(f"\n✗ Batch sync failed: {data.get('error')}")
    else:
        print(f"\n✗ Request failed: {response.status_code}")


def demo_enhanced_jobs_endpoint(source_id: str):
    """
    Demo: Enhanced /jobs endpoint with source_id

    Args:
        source_id: Source ID to sync via jobs endpoint
    """
    print_section(f"4. Enhanced /jobs Endpoint with source_id: {source_id}")

    print(f"Triggering job with source_id: {source_id}...")

    payload = {
        "type": "incremental",
        "source_id": source_id
    }

    response = requests.post(f"{API_BASE}/jobs", json=payload)
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            result = data["data"]
            print(f"\n✓ Job completed successfully!")
            print(f"  - Job ID: {result['job_id']}")
            print(f"  - Source ID: {result['source_id']}")
            print(f"  - Chunks indexed: {result['chunk_count']}")
            print(f"  - Duration: {result['duration_ms']}ms")
            print(f"  - Status: {result['status']}")
        else:
            print(f"\n✗ Job failed: {data.get('error')}")
    else:
        print(f"\n✗ Request failed: {response.status_code}")


def demo_traditional_jobs_endpoint():
    """
    Demo: Traditional /jobs endpoint (without source_id)
    """
    print_section("5. Traditional /jobs Endpoint (Backward Compatibility)")

    print("Triggering traditional incremental job...")

    payload = {
        "type": "incremental"
    }

    response = requests.post(f"{API_BASE}/jobs", json=payload)
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            result = data["data"]
            print(f"\n✓ Job created successfully!")
            print(f"  - Job ID: {result['job_id']}")
            print(f"  - Type: {result['type']}")
            print(f"  - Status: {result['status']} (asynchronous)")
            print(f"\n  Note: This is a background job. Check status with:")
            print(f"  GET /api/knowledge/jobs/{result['job_id']}")
        else:
            print(f"\n✗ Job failed: {data.get('error')}")
    else:
        print(f"\n✗ Request failed: {response.status_code}")


def demo_create_test_source() -> str:
    """
    Demo: Create a test source for demonstration

    Returns:
        Source ID if created successfully, None otherwise
    """
    print_section("0. Create Test Source (if needed)")

    import tempfile
    import os

    # Create temporary directory with test content
    test_dir = tempfile.mkdtemp(prefix="agentos_demo_")
    test_file = os.path.join(test_dir, "README.md")

    with open(test_file, "w") as f:
        f.write("""
# Test Knowledge Source

This is a test document created by the Task 7 demo script.

## Features

- Demonstrates API integration
- Tests SourceBridge synchronization
- Validates chunk indexing

## Usage

This source will be synced to demonstrate the new API endpoints.
""")

    print(f"Created test directory: {test_dir}")

    # Create source via API
    payload = {
        "type": "local",
        "path": test_dir,
        "config": {
            "file_types": ["md"],
            "recursive": True
        }
    }

    response = requests.post(f"{API_BASE}/sources", json=payload)
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            source_id = data["data"]["source"]["source_id"]
            print(f"\n✓ Test source created: {source_id}")
            print(f"  Path: {test_dir}")
            print(f"\n  Note: Remember to clean up this source after demo!")
            print(f"  DELETE /api/knowledge/sources/{source_id}")
            return source_id

    print(f"\n✗ Failed to create test source")
    return None


def main():
    """Main demo function"""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║  AgentOS - Task 7 SourceBridge API Integration Demo           ║")
    print("╚" + "=" * 68 + "╝")

    try:
        # Check if server is running
        print("\nChecking if server is running...")
        response = requests.get(f"{API_BASE}/sources", timeout=2)
        if response.status_code != 200:
            print(f"✗ Server returned unexpected status: {response.status_code}")
            print("\nPlease start the AgentOS WebUI server:")
            print("  python -m agentos.webui.app")
            return
        print("✓ Server is running")

        # List existing sources
        source_ids = demo_list_sources()

        # If no sources, create a test source
        if not source_ids:
            print("\n⚠ No sources found. Creating a test source...")
            test_source_id = demo_create_test_source()
            if test_source_id:
                source_ids = [test_source_id]
            else:
                print("\n✗ Failed to create test source. Exiting.")
                return

        # Use first source for demos
        if source_ids:
            demo_source_id = source_ids[0]

            # Demo 1: Sync single source
            demo_sync_single_source(demo_source_id)

            # Demo 2: Batch sync all sources
            demo_sync_all_sources()

            # Demo 3: Enhanced /jobs with source_id
            demo_enhanced_jobs_endpoint(demo_source_id)

            # Demo 4: Traditional /jobs without source_id
            demo_traditional_jobs_endpoint()

        print_section("Demo Complete")
        print("All API endpoints demonstrated successfully!")
        print("\nFor more information, see:")
        print("  - docs/TASK7_API_ROUTING_INTEGRATION.md")
        print("  - tests/api/test_knowledge_sync_endpoints.py")

    except requests.exceptions.ConnectionError:
        print("\n✗ Could not connect to server at", BASE_URL)
        print("\nPlease start the AgentOS WebUI server:")
        print("  python -m agentos.webui.app")
    except KeyboardInterrupt:
        print("\n\n✗ Demo interrupted by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
