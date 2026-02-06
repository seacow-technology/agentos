"""
Dry Executor Core Module (v0.10)

This module provides a "dry execution" capability that generates planning artifacts
without performing any actual execution. It transforms ExecutionIntent (v0.9.1)
into auditable, reviewable execution plans.

Red Lines (DE1-DE6):
- DE1: No execution (no subprocess, os.system, exec, eval)
- DE2: No file system writes (except output artifacts)
- DE3: No path fabrication (only use paths from intent/evidence)
- DE4: All nodes must have evidence_refs
- DE5: High/critical risk must have requires_review
- DE6: Output must be freezable (checksum + lineage + stable explain)
"""

from .dry_executor import DryExecutor, run_dry_execution
from .graph_builder import GraphBuilder
from .patch_planner import PatchPlanner
from .commit_planner import CommitPlanner
from .review_pack_stub import ReviewPackStubGenerator
from .validator import DryExecutorValidator, validate_dry_execution_result

__all__ = [
    "DryExecutor",
    "run_dry_execution",
    "GraphBuilder",
    "PatchPlanner",
    "CommitPlanner",
    "ReviewPackStubGenerator",
    "DryExecutorValidator",
    "validate_dry_execution_result",
]

__version__ = "0.10.0"
