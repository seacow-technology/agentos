#!/usr/bin/env python3
"""
v0.9.2 Gate F: Explain Snapshot Stability

Validates:
- Fixed intent → consistent output structure
- Output structure stable across runs (not content, but structure)
- Snapshot comparison
"""

import json
import sys
from pathlib import Path

SNAPSHOT_FILE = Path("tests/snapshots/v092_coordinator_snapshot.json")
EXAMPLE_GRAPH = Path("examples/coordinator/outputs/execution_graph_low_risk.json")


def extract_structure(obj, path=""):
    """Extract structure (keys and types) from JSON object"""
    if isinstance(obj, dict):
        structure = {"type": "object", "keys": {}}
        for key, value in obj.items():
            structure["keys"][key] = extract_structure(value, f"{path}.{key}")
        return structure
    elif isinstance(obj, list):
        if len(obj) > 0:
            return {"type": "array", "item_structure": extract_structure(obj[0], f"{path}[0]")}
        else:
            return {"type": "array", "item_structure": None}
    else:
        return {"type": type(obj).__name__}


def main():
    print("=" * 70)
    print("v0.9.2 Gate F: Explain Snapshot Stability")
    print("=" * 70)

    if not EXAMPLE_GRAPH.exists():
        print(f"\n❌ Example graph not found: {EXAMPLE_GRAPH}")
        return False

    # Load example
    with open(EXAMPLE_GRAPH, "r", encoding="utf-8") as f:
        example = json.load(f)

    # Extract structure
    current_structure = extract_structure(example)

    # Check if snapshot exists
    if not SNAPSHOT_FILE.exists():
        print(f"\n⚠️  Snapshot file not found: {SNAPSHOT_FILE}")
        print("Creating new snapshot...")
        
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        snapshot_data = {
            "schema_version": "0.9.2",
            "snapshot_type": "coordinator_output_structure",
            "created_at": "2026-01-25T10:00:00Z",
            "structure": current_structure
        }
        
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2)
        
        print(f"✅ Snapshot created: {SNAPSHOT_FILE}")
        print("\n" + "=" * 70)
        print("✅ Gate F: PASSED (snapshot created)")
        print("=" * 70)
        return True

    # Load existing snapshot
    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    # Compare structures
    print("\nComparing current output structure with snapshot...")
    
    if current_structure == snapshot["structure"]:
        print("✅ Structure matches snapshot - output is stable")
        print("\n" + "=" * 70)
        print("✅ Gate F: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Structure mismatch detected")
        print("\nTo update snapshot, delete the file and re-run this gate:")
        print(f"  rm {SNAPSHOT_FILE}")
        print("\n" + "=" * 70)
        print("❌ Gate F: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
