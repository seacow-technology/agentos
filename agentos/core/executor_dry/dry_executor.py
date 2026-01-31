"""
Dry Executor Main Entry Point

Orchestrates the generation of execution plans without performing any actual execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .commit_planner import CommitPlanner
from .graph_builder import GraphBuilder
from .patch_planner import PatchPlanner
from .review_pack_stub import ReviewPackStubGenerator
from .utils import compute_checksum, enforce_red_lines, extract_evidence_from_intent, generate_id
from agentos.core.time import utc_now, utc_now_iso



class DryExecutor:
    """
    Main dry executor orchestrator.
    
    Red Line Enforcement:
    - DE1: No execution (subprocess, os.system, exec, eval forbidden)
    - DE2: No file system writes (except output artifacts)
    - DE3: No path fabrication
    - DE4: All nodes must have evidence_refs
    - DE5: High/critical risk must have requires_review
    - DE6: Output must be freezable (checksum + lineage + stable explain)
    """
    
    VERSION = "0.10.0"
    
    def __init__(self):
        """Initialize dry executor."""
        self.audit_log: list[Dict[str, Any]] = []
    
    def run(self, intent: Dict[str, Any], 
            coordinator_outputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run dry execution planning.
        
        Args:
            intent: ExecutionIntent (v0.9.1)
            coordinator_outputs: Optional coordinator outputs (v0.9.2)
        
        Returns:
            DryExecutionResult matching dry_execution_result.schema.json
        """
        start_time = utc_now()
        
        # Log decision: starting dry execution
        self._log_decision(
            decision_type="graph_structure",
            decision="Starting dry execution planning",
            rationale=f"Processing intent {intent['id']} with risk level {intent.get('risk', {}).get('overall', 'unknown')}"
        )
        
        # Build execution graph
        coordinator_graph = coordinator_outputs.get("execution_graph") if coordinator_outputs else None
        graph_builder = GraphBuilder(intent, coordinator_graph)
        graph = graph_builder.build()
        
        self._log_decision(
            decision_type="graph_structure",
            decision=f"Built execution graph with {len(graph['nodes'])} nodes",
            rationale="Graph structure derived from intent workflows and commands"
        )
        
        # Build patch plan
        patch_planner = PatchPlanner(intent)
        patch_plan = patch_planner.plan()
        
        self._log_decision(
            decision_type="file_inclusion",
            decision=f"Planned changes for {len(patch_plan['files'])} files",
            rationale="Files from intent scope.targets.files",
            evidence_refs=extract_evidence_from_intent(intent)
        )
        
        # Build commit plan
        commit_planner = CommitPlanner(intent, patch_plan)
        commit_plan = commit_planner.plan()
        
        self._log_decision(
            decision_type="commit_grouping",
            decision=f"Grouped into {len(commit_plan['commits'])} commits",
            rationale=f"Respects max_commits budget: {commit_plan['metadata']['respects_max_commits_budget']}"
        )
        
        # Generate review pack stub
        review_generator = ReviewPackStubGenerator(intent, graph, patch_plan, commit_plan)
        review_pack_stub = review_generator.generate()
        
        self._log_decision(
            decision_type="risk_assessment",
            decision=f"Dominant risk: {review_pack_stub['risk_summary']['dominant_risk']}",
            rationale="Risk determined from intent and planned changes"
        )
        
        # Build result object
        result_id = generate_id("dryexec", intent["id"])
        
        result_data = {
            "result_id": result_id,
            "schema_version": self.VERSION,
            "intent_ref": {
                "intent_id": intent["id"],
                "checksum": intent["audit"]["checksum"],
                "version": intent.get("version", "0.9.1")
            },
            "created_at": utc_now_iso() + "Z",
            "graph": graph,
            "patch_plan": patch_plan,
            "commit_plan": commit_plan,
            "review_pack_stub": review_pack_stub,
            "audit_log": self.audit_log,
            "metadata": {
                "dry_executor_version": self.VERSION,
                "execution_mode": "dry_run",
                "constraints_enforced": [
                    "DE1_no_exec",
                    "DE2_no_fs_write",
                    "DE3_no_fabrication",
                    "DE4_evidence_required",
                    "DE5_high_risk_review",
                    "DE6_freezable"
                ],
                "warnings": [],
                "processing_time_ms": int((utc_now() - start_time).total_seconds() * 1000)
            },
            "lineage": {
                "derived_from": [
                    {
                        "type": "intent",
                        "id": intent["id"],
                        "checksum": intent["audit"]["checksum"]
                    }
                ],
                "generation_context": {
                    "environment": "dry_executor_v0.10"
                }
            }
        }
        
        # Add coordinator ref if provided
        if coordinator_outputs:
            result_data["coordinator_ref"] = {
                "run_id": coordinator_outputs.get("run_id", "unknown"),
                "outputs_used": ["execution_graph"] if coordinator_graph else []
            }
        
        # Compute final checksum
        result_data["checksum"] = compute_checksum(result_data)
        
        # Enforce red lines
        violations = enforce_red_lines(result_data)
        if violations:
            result_data["metadata"]["warnings"].extend(violations)
        
        return result_data
    
    def _log_decision(self, decision_type: str, decision: str, rationale: str, 
                      evidence_refs: list[str] = None, alternatives: list[str] = None):
        """Log a decision to the audit log."""
        entry = {
            "timestamp": utc_now_iso() + "Z",
            "decision_type": decision_type,
            "decision": decision,
            "rationale": rationale
        }
        
        if evidence_refs:
            entry["evidence_refs"] = evidence_refs
        if alternatives:
            entry["alternatives_considered"] = alternatives
        
        self.audit_log.append(entry)


def run_dry_execution(intent: Dict[str, Any], 
                      coordinator_outputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to run dry execution.
    
    Args:
        intent: ExecutionIntent (v0.9.1)
        coordinator_outputs: Optional coordinator outputs (v0.9.2)
    
    Returns:
        DryExecutionResult
    """
    executor = DryExecutor()
    return executor.run(intent, coordinator_outputs)
