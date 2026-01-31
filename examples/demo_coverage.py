#!/usr/bin/env python3
"""
Demo script for BrainOS Coverage Calculation Engine

Shows how to compute and display cognitive coverage metrics.

Usage:
    python examples/demo_coverage.py [db_path]

Example:
    python examples/demo_coverage.py ./store/brainos.db
"""

import sys
from pathlib import Path

from agentos.core.brain.store import SQLiteStore
from agentos.core.brain.service import compute_coverage


def main():
    """Run coverage demo."""
    # Get database path from args or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "./store/brainos.db"

    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("\nPlease run BrainIndexJob first to build the knowledge graph:")
        print("  python -c 'from agentos.core.brain.service import BrainIndexJob; BrainIndexJob.run()'")
        return 1

    print(f"📊 Computing BrainOS Coverage Metrics")
    print(f"   Database: {db_path}\n")

    # Connect to database and compute coverage
    store = SQLiteStore(db_path, auto_init=False)
    try:
        store.connect()
        metrics = compute_coverage(store)

        # Display overall metrics
        print("=" * 60)
        print("OVERALL COVERAGE")
        print("=" * 60)
        print(f"Total Files:          {metrics.total_files:,}")
        print(f"Covered Files:        {metrics.covered_files:,}")
        print(f"Code Coverage:        {metrics.code_coverage:.1%}")
        print()

        # Display evidence-specific metrics
        print("=" * 60)
        print("COVERAGE BY EVIDENCE TYPE")
        print("=" * 60)
        print(f"Git Coverage:         {metrics.git_covered_files:,} files ({metrics.git_covered_files/metrics.total_files:.1%})" if metrics.total_files > 0 else "Git Coverage:         0 files (0.0%)")
        print(f"Doc Coverage:         {metrics.doc_covered_files:,} files ({metrics.doc_coverage:.1%})")
        print(f"Dependency Coverage:  {metrics.dep_covered_files:,} files ({metrics.dependency_coverage:.1%})")
        print()

        # Display evidence distribution
        print("=" * 60)
        print("EVIDENCE DISTRIBUTION")
        print("=" * 60)
        for key in ["0_evidence", "1_evidence", "2_evidence", "3_evidence"]:
            count = metrics.evidence_distribution.get(key, 0)
            if metrics.total_files > 0:
                pct = count / metrics.total_files * 100
                print(f"{key:15} {count:6,} files ({pct:5.1f}%)")
            else:
                print(f"{key:15} {count:6,} files (  0.0%)")
        print()

        # Display uncovered files (limited to first 10)
        if metrics.uncovered_files:
            print("=" * 60)
            print("UNCOVERED FILES (0 evidence)")
            print("=" * 60)
            display_count = min(10, len(metrics.uncovered_files))
            for i, file_key in enumerate(metrics.uncovered_files[:display_count], 1):
                print(f"{i:3}. {file_key}")

            if len(metrics.uncovered_files) > display_count:
                remaining = len(metrics.uncovered_files) - display_count
                print(f"     ... and {remaining} more")
            print()

        # Display metadata
        print("=" * 60)
        print("METADATA")
        print("=" * 60)
        print(f"Graph Version:        {metrics.graph_version}")
        print(f"Computed At:          {metrics.computed_at}")
        print()

        # Summary interpretation
        print("=" * 60)
        print("INTERPRETATION")
        print("=" * 60)
        if metrics.code_coverage >= 0.8:
            status = "✅ EXCELLENT"
            msg = "BrainOS has strong understanding of this codebase"
        elif metrics.code_coverage >= 0.5:
            status = "⚠️  GOOD"
            msg = "BrainOS understands most of the codebase"
        elif metrics.code_coverage >= 0.3:
            status = "⚠️  MODERATE"
            msg = "BrainOS has partial understanding - consider indexing more"
        else:
            status = "❌ LOW"
            msg = "BrainOS has limited understanding - run indexing jobs"

        print(f"Status:               {status}")
        print(f"Assessment:           {msg}")
        print("=" * 60)

    finally:
        store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
