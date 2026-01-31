#!/usr/bin/env python3
"""
v0.10 Gate F: Explain Snapshot Stability

Validates:
- Selected example results produce stable explain output
- Output structure is consistent across runs
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def load_json(path):
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_explain_structure(result_data):
    """Generate stable structure from result for snapshot."""
    return {
        "schema_version": result_data.get("schema_version"),
        "has_intent_ref": "intent_ref" in result_data,
        "has_graph": "graph" in result_data,
        "has_patch_plan": "patch_plan" in result_data,
        "has_commit_plan": "commit_plan" in result_data,
        "has_review_pack_stub": "review_pack_stub" in result_data,
        "graph_structure": {
            "has_nodes": "nodes" in result_data.get("graph", {}),
            "has_edges": "edges" in result_data.get("graph", {}),
            "has_swimlanes": "swimlanes" in result_data.get("graph", {}),
        } if "graph" in result_data else None,
        "metadata_fields": list(result_data.get("metadata", {}).keys()),
        "has_checksum": "checksum" in result_data,
        "has_lineage": "lineage" in result_data,
    }


def main():
    print("=" * 70)
    print("v0.10 Gate F: Explain Snapshot Stability")
    print("=" * 70)

    all_valid = True

    # Select 2 examples for snapshot
    example_results = [
        "examples/executor_dry/low_risk/output_result.json",
        "examples/executor_dry/high_risk/output_result.json",
    ]

    snapshot_file = Path("tests/snapshots/v10_dry_executor_explain.json")

    print("\n🔍 Generating explain structures from examples...")
    
    current_structures = {}
    for result_path in example_results:
        if not Path(result_path).exists():
            print(f"  ❌ {result_path} - NOT FOUND")
            all_valid = False
            continue

        try:
            result_data = load_json(result_path)
            structure = generate_explain_structure(result_data)
            current_structures[result_path] = structure
            print(f"  ✅ {result_path}")
        except Exception as e:
            print(f"  ❌ {result_path} - ERROR: {e}")
            all_valid = False

    if not all_valid:
        print("\n❌ Failed to generate structures")
        return False

    # Check if snapshot exists
    if not snapshot_file.exists():
        print(f"\n⚠️  Snapshot not found: {snapshot_file}")
        print("Creating new snapshot...")
        
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        
        snapshot_data = {
            "schema_version": "0.10.0",
            "snapshot_type": "dry_executor_explain_structure",
            "created_at": "2026-01-25T12:00:00Z",
            "structures": current_structures
        }
        
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2, sort_keys=True)
        
        print(f"✅ Snapshot created: {snapshot_file}")
        print("\n" + "=" * 70)
        print("✅ Gate F: PASSED (snapshot created)")
        print("=" * 70)
        return True

    # Load existing snapshot
    print(f"\n📖 Loading existing snapshot: {snapshot_file}")
    try:
        snapshot_data = load_json(snapshot_file)
        saved_structures = snapshot_data.get("structures", {})
    except Exception as e:
        print(f"  ❌ Failed to load snapshot: {e}")
        return False

    # Compare structures
    print("\n🔍 Comparing current structures with snapshot...")
    
    structures_match = True
    for path, current_struct in current_structures.items():
        if path not in saved_structures:
            print(f"  ⚠️  {path} not in snapshot")
            structures_match = False
            continue
        
        saved_struct = saved_structures[path]
        
        if current_struct == saved_struct:
            print(f"  ✅ {path} - structure matches")
        else:
            print(f"  ❌ {path} - structure mismatch")
            print(f"      Current: {current_struct}")
            print(f"      Saved:   {saved_struct}")
            structures_match = False

    # Summary
    print("\n" + "=" * 70)
    if structures_match:
        print("✅ Gate F: PASSED - Output structure stable")
        print("=" * 70)
        return True
    else:
        print("❌ Gate F: FAILED - Output structure changed")
        print("\nTo update snapshot, delete the file and re-run:")
        print(f"  rm {snapshot_file}")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
