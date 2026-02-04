#!/usr/bin/env python3
"""
CASE-002 Task 8: Frontend State Synchronization Demo

This script demonstrates the frontend state synchronization functionality
for knowledge sources, which ensures the frontend activeKnowledgeSources
state is always in sync with the backend knowledge_sources table.

Features Demonstrated:
1. Real-time status badge updates (6 states: pending/active/indexed/inactive/error/failed)
2. Sync button integration with loading states
3. Status polling until terminal state
4. Error handling and user feedback

Frontend Changes:
- Added syncSource() method to trigger synchronization
- Added refreshSources() method to fetch latest state from backend
- Added pollSourceStatus() method for real-time status updates
- Added updateSourceStatus() method to update UI immediately
- Enhanced renderStatusBadge() to support all 6 backend states
- Added Sync button to each source row

Backend Contract:
- GET /api/knowledge/sources - List all sources with current status
- POST /api/knowledge/sources/{id}/sync - Trigger source synchronization
- Response includes: chunk_count, duration_ms, and updated status

Status Transitions:
pending -> active -> indexed (success path)
pending -> active -> error/failed (failure path)
inactive -> active -> indexed (re-sync path)

Usage:
    python3 examples/task8_frontend_state_sync_demo.py

Requirements:
    - Backend API running on http://localhost:8000
    - Frontend loaded with updated KnowledgeSourcesView.js
    - Browser console open for debugging
"""

import requests
import json
import time
import uuid
from typing import Dict, Any


class FrontendStateSync:
    """Demonstrates frontend state synchronization with backend"""

    def __init__(self, api_url: str = "http://localhost:8000/api"):
        self.api_url = api_url
        self.sources = {}

    def demo_1_create_test_source(self) -> Dict[str, Any]:
        """Demo 1: Create a test data source"""
        print("\n=== Demo 1: Create Test Data Source ===")

        source_data = {
            "type": "directory",
            "path": "/tmp/test-docs",
            "config": {
                "file_types": ["md", "txt"],
                "recursive": True
            }
        }

        response = requests.post(
            f"{self.api_url}/knowledge/sources",
            json=source_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                source_id = result["data"]["source_id"]
                self.sources["test_source"] = source_id
                print(f"✓ Created source: {source_id}")
                print(f"  Type: {source_data['type']}")
                print(f"  Path: {source_data['path']}")
                return result.get("data")
            else:
                print(f"✗ Creation failed: {result.get('error')}")
                return None
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            return None

    def demo_2_list_sources_before_sync(self) -> None:
        """Demo 2: List sources before sync"""
        print("\n=== Demo 2: List Sources Before Sync ===")

        response = requests.get(f"{self.api_url}/knowledge/sources")

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                sources = result["data"]["sources"]
                print(f"✓ Found {len(sources)} sources:")
                for source in sources:
                    print(f"\n  Source: {source['source_id']}")
                    print(f"    Type: {source['type']}")
                    print(f"    Path: {source['path']}")
                    print(f"    Status: {source['status']} (should be 'pending')")
                    print(f"    Chunks: {source['chunk_count']}")
                    print(f"    Last Indexed: {source['last_indexed_at']}")
            else:
                print(f"✗ List failed: {result.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")

    def demo_3_trigger_sync(self) -> Dict[str, Any]:
        """Demo 3: Trigger source synchronization"""
        print("\n=== Demo 3: Trigger Source Synchronization ===")

        source_id = self.sources.get("test_source")
        if not source_id:
            print("✗ No test source available")
            return None

        print(f"Syncing source: {source_id}")
        response = requests.post(
            f"{self.api_url}/knowledge/sources/{source_id}/sync"
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                data = result["data"]
                print(f"✓ Sync triggered successfully!")
                print(f"  Chunk Count: {data.get('chunk_count')}")
                print(f"  Duration: {data.get('duration_ms')}ms")
                print(f"  Message: {data.get('message')}")
                return data
            else:
                print(f"✗ Sync failed: {result.get('error')}")
                return None
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            return None

    def demo_4_poll_status_changes(self) -> None:
        """Demo 4: Poll for status changes"""
        print("\n=== Demo 4: Poll For Status Changes ===")

        source_id = self.sources.get("test_source")
        if not source_id:
            print("✗ No test source available")
            return

        print(f"Polling status for source: {source_id}")
        print("Waiting for status to reach terminal state (indexed/error/failed)...\n")

        max_attempts = 30
        poll_interval = 2  # seconds

        for attempt in range(max_attempts):
            response = requests.get(f"{self.api_url}/knowledge/sources")

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    sources = result["data"]["sources"]
                    source = next((s for s in sources if s["source_id"] == source_id), None)

                    if source:
                        status = source["status"]
                        chunk_count = source["chunk_count"]
                        last_indexed = source["last_indexed_at"]

                        print(f"Attempt {attempt + 1}: Status = {status}, Chunks = {chunk_count}")

                        # Terminal states
                        if status in ["indexed", "error", "failed"]:
                            print(f"\n✓ Reached terminal state: {status}")
                            print(f"  Final chunk count: {chunk_count}")
                            print(f"  Last indexed: {last_indexed}")
                            return

            time.sleep(poll_interval)

        print("\n✗ Polling timed out (status did not reach terminal state)")

    def demo_5_verify_frontend_sync(self) -> None:
        """Demo 5: Verify frontend synchronization"""
        print("\n=== Demo 5: Verify Frontend Synchronization ===")

        print("Frontend synchronization verification steps:")
        print("1. Open browser developer console (F12)")
        print("2. Navigate to Knowledge Sources page")
        print("3. Verify the Sync button appears on each row")
        print("4. Click the Sync button for your source")
        print("5. Observe status badge changes in real-time:")
        print("   - Pending (gray) -> Active (blue) -> Indexed (green)")
        print("6. Check browser console for debug logs")
        print("7. Verify Toast notifications appear for sync events")
        print("\nExpected behavior:")
        print("- Sync button becomes disabled (spinning icon) during sync")
        print("- Status badge updates reflect backend changes")
        print("- Success toast shows chunk count and duration")
        print("- Final status matches backend after polling completes")

    def demo_6_test_error_handling(self) -> None:
        """Demo 6: Test error handling"""
        print("\n=== Demo 6: Test Error Handling ===")

        print("Error handling scenarios:")
        print("\n1. Invalid Source ID:")
        response = requests.post(f"{self.api_url}/knowledge/sources/invalid-id/sync")
        print(f"   Response status: {response.status_code}")
        result = response.json()
        print(f"   Error: {result.get('error')}")

        print("\n2. Network Error Simulation:")
        print("   (Try clicking Sync with network throttling enabled in DevTools)")

        print("\n3. API Timeout:")
        print("   (Frontend polling will timeout after 60 attempts)")

    def demo_7_show_ui_elements(self) -> None:
        """Demo 7: Show UI elements added for state sync"""
        print("\n=== Demo 7: UI Elements Added ===")

        print("\n1. Status Badge Styling (6 states):")
        badges = {
            "pending": "badge-secondary (gray)",
            "active": "badge-info (blue)",
            "indexed": "badge-success (green)",
            "inactive": "badge-light (light gray)",
            "error": "badge-warning (yellow/orange)",
            "failed": "badge-danger (red)"
        }
        for status, styling in badges.items():
            print(f"   {status}: {styling}")

        print("\n2. Sync Button:")
        print("   - Location: First button in Actions column")
        print("   - Icon: Material Icon 'sync'")
        print("   - Color: Primary (blue)")
        print("   - Disabled during sync (shows spinning icon)")

        print("\n3. Polling Behavior:")
        print("   - Max attempts: 60")
        print("   - Poll interval: 1000ms")
        print("   - Total timeout: ~60 seconds")

    def demo_8_show_api_responses(self) -> None:
        """Demo 8: Show expected API responses"""
        print("\n=== Demo 8: Expected API Responses ===")

        print("\n1. GET /api/knowledge/sources - List all sources:")
        print(json.dumps({
            "ok": True,
            "data": {
                "sources": [
                    {
                        "source_id": "src-001",
                        "type": "directory",
                        "path": "/tmp/docs",
                        "config": {"file_types": ["md"]},
                        "chunk_count": 250,
                        "last_indexed_at": "2026-02-01T10:30:00.000Z",
                        "status": "indexed",
                        "created_at": "2026-02-01T09:00:00.000Z",
                        "updated_at": "2026-02-01T10:30:00.000Z"
                    }
                ],
                "total": 1
            }
        }, indent=2))

        print("\n2. POST /api/knowledge/sources/{id}/sync - Sync response:")
        print(json.dumps({
            "ok": True,
            "data": {
                "source_id": "src-001",
                "chunk_count": 250,
                "duration_ms": 1523,
                "message": "Source synced successfully"
            }
        }, indent=2))

        print("\n3. Error response:")
        print(json.dumps({
            "ok": False,
            "error": "Validation failed: Path does not exist"
        }, indent=2))


def main():
    """Run all demonstrations"""
    demo = FrontendStateSync()

    try:
        print("=" * 60)
        print("CASE-002 Task 8: Frontend State Synchronization Demo")
        print("=" * 60)

        demo.demo_1_create_test_source()
        demo.demo_2_list_sources_before_sync()
        demo.demo_3_trigger_sync()
        demo.demo_4_poll_status_changes()
        demo.demo_5_verify_frontend_sync()
        demo.demo_6_test_error_handling()
        demo.demo_7_show_ui_elements()
        demo.demo_8_show_api_responses()

        print("\n" + "=" * 60)
        print("Demo completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
