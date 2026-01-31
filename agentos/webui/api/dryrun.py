"""Dry-Run API - Read-only endpoints for dry-run plan/explain/validate operations

This module provides read-only API endpoints for accessing dry-run execution plans,
explanations, and validation results. No actual execution is performed through these endpoints.

Wave1-A3: Dry-run plan/explain/validate API

Endpoints:
    GET  /api/dryrun/{task_id}/plan        - Get execution plan
    GET  /api/dryrun/{task_id}/explain     - Get plan explanation
    GET  /api/dryrun/{task_id}/validate    - Get validation results
    POST /api/dryrun/proposal              - Generate new execution proposal (no execution)

Red Lines:
    - No actual execution (no subprocess, os.system, exec, eval)
    - All write operations generate proposals only (pending_review state)
    - All operations are audited
    - Unified contract response format (ok/data/error/hint/reason_code)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from agentos.core.task.service import TaskService
from agentos.core.task.audit_service import TaskAuditService
from agentos.core.executor_dry.dry_executor import DryExecutor
from agentos.core.task.models import Task


from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models (Unified Contract)
# ============================================================================

class UnifiedResponse(BaseModel):
    """Unified API response format following Agent-API-Contract"""
    ok: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    hint: Optional[str] = None
    reason_code: Optional[str] = None


class ExecutionStep(BaseModel):
    """Single execution step in a plan"""
    step_id: str
    step_type: str  # workflow, command, action
    name: str
    description: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    risk_level: str = "low"
    evidence_refs: List[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """Execution plan structure"""
    plan_id: str
    task_id: str
    steps: List[ExecutionStep]
    total_steps: int
    risk_markers: Dict[str, List[str]] = Field(default_factory=dict)
    estimated_duration: Optional[str] = None
    created_at: str


class PlanExplanation(BaseModel):
    """Natural language explanation of execution plan"""
    task_id: str
    summary: str
    rationale: str
    alternatives: List[str] = Field(default_factory=list)
    key_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    structured_fields: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Plan validation result"""
    task_id: str
    is_valid: bool
    checks_passed: List[str] = Field(default_factory=list)
    checks_failed: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)


class ProposalRequest(BaseModel):
    """Request to generate execution proposal"""
    task_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "webui"


class ProposalResponse(BaseModel):
    """Generated proposal response"""
    proposal_id: str
    task_id: str
    status: str = "pending_review"
    plan: Optional[ExecutionPlan] = None
    requires_approval: bool = True
    created_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def _get_dry_run_result_from_task(task: Task) -> Optional[Dict[str, Any]]:
    """Extract dry-run result from task metadata

    Args:
        task: Task object

    Returns:
        Dry-run result dict or None if not found
    """
    if not task.metadata:
        return None

    # Check for dry_run_result in metadata
    dry_run_result = task.metadata.get("dry_run_result")
    if dry_run_result:
        return dry_run_result

    # Check for execution_context with dry_run info
    exec_context = task.metadata.get("execution_context", {})
    if exec_context.get("dry_run_mode"):
        return exec_context.get("dry_run_output")

    return None


def _convert_graph_to_steps(graph: Dict[str, Any]) -> List[ExecutionStep]:
    """Convert execution graph to step list

    Args:
        graph: Execution graph from DryExecutor

    Returns:
        List of ExecutionStep objects
    """
    steps = []

    for node in graph.get("nodes", []):
        step = ExecutionStep(
            step_id=node.get("node_id", "unknown"),
            step_type=node.get("type", "action"),
            name=node.get("name", "Unnamed step"),
            description=node.get("description"),
            dependencies=node.get("depends_on", []),
            risk_level=node.get("risk_level", "low"),
            evidence_refs=node.get("evidence_refs", [])
        )
        steps.append(step)

    return steps


def _extract_risk_markers(dry_run_result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract risk markers from dry-run result

    Args:
        dry_run_result: Dry-run execution result

    Returns:
        Risk markers organized by level
    """
    risk_markers = {
        "high": [],
        "medium": [],
        "low": []
    }

    # Extract from review pack stub
    review_pack = dry_run_result.get("review_pack_stub", {})
    risk_summary = review_pack.get("risk_summary", {})

    if risk_summary.get("dominant_risk"):
        level = risk_summary["dominant_risk"]
        risk_markers[level].append("Dominant risk identified")

    # Extract from graph nodes
    graph = dry_run_result.get("graph", {})
    for node in graph.get("nodes", []):
        risk_level = node.get("risk_level", "low")
        if risk_level in risk_markers:
            risk_markers[risk_level].append(
                f"Step '{node.get('name')}' has {risk_level} risk"
            )

    return risk_markers


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/dryrun/{task_id}/plan")
async def get_execution_plan(task_id: str) -> UnifiedResponse:
    """Get execution plan for a task

    Returns:
        ExecutionPlan with steps structure, dependencies, and risk markers

    Example:
        GET /api/dryrun/task_123/plan

        Response:
        {
            "ok": true,
            "data": {
                "plan_id": "plan_abc123",
                "task_id": "task_123",
                "steps": [...],
                "total_steps": 5,
                "risk_markers": {...}
            }
        }
    """
    try:
        # Get task
        task_service = TaskService()
        task = task_service.get_task(task_id)

        if not task:
            return UnifiedResponse(
                ok=False,
                error=f"Task not found: {task_id}",
                reason_code="TASK_NOT_FOUND",
                hint="Verify the task ID exists"
            )

        # Get dry-run result from task metadata
        dry_run_result = _get_dry_run_result_from_task(task)

        if not dry_run_result:
            return UnifiedResponse(
                ok=False,
                error="No dry-run plan found for this task",
                reason_code="NO_DRY_RUN_RESULT",
                hint="Generate a dry-run plan first using POST /api/dryrun/proposal"
            )

        # Convert to ExecutionPlan
        graph = dry_run_result.get("graph", {})
        steps = _convert_graph_to_steps(graph)
        risk_markers = _extract_risk_markers(dry_run_result)

        plan = ExecutionPlan(
            plan_id=dry_run_result.get("result_id", f"plan_{task_id}"),
            task_id=task_id,
            steps=steps,
            total_steps=len(steps),
            risk_markers=risk_markers,
            created_at=dry_run_result.get("created_at", iso_z(utc_now()))
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=task_id,
            operation="plan_read",
            event_type="dryrun_plan_accessed",
            status="success",
            payload={"plan_id": plan.plan_id, "actor": "webui"}
        )

        return UnifiedResponse(
            ok=True,
            data=plan.dict()
        )

    except Exception as e:
        logger.exception(f"Error getting execution plan for task {task_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR",
            hint="Check server logs for details"
        )


@router.get("/api/dryrun/{task_id}/explain")
async def get_plan_explanation(task_id: str) -> UnifiedResponse:
    """Get natural language explanation of execution plan

    Returns:
        PlanExplanation with rationale, alternatives, and key decisions

    Example:
        GET /api/dryrun/task_123/explain

        Response:
        {
            "ok": true,
            "data": {
                "task_id": "task_123",
                "summary": "This plan will...",
                "rationale": "We chose this approach because...",
                "alternatives": [...],
                "key_decisions": [...]
            }
        }
    """
    try:
        # Get task
        task_service = TaskService()
        task = task_service.get_task(task_id)

        if not task:
            return UnifiedResponse(
                ok=False,
                error=f"Task not found: {task_id}",
                reason_code="TASK_NOT_FOUND"
            )

        # Get dry-run result
        dry_run_result = _get_dry_run_result_from_task(task)

        if not dry_run_result:
            return UnifiedResponse(
                ok=False,
                error="No dry-run plan found for this task",
                reason_code="NO_DRY_RUN_RESULT"
            )

        # Extract explanation from audit log and metadata
        audit_log = dry_run_result.get("audit_log", [])

        # Build summary from audit decisions
        key_decisions = [
            {
                "decision_type": entry.get("decision_type"),
                "decision": entry.get("decision"),
                "rationale": entry.get("rationale")
            }
            for entry in audit_log
            if entry.get("decision_type")
        ]

        # Generate summary
        graph = dry_run_result.get("graph", {})
        step_count = len(graph.get("nodes", []))
        summary = f"This execution plan consists of {step_count} steps to accomplish the task: {task.title}"

        # Build rationale from key decisions
        rationale_parts = [d["rationale"] for d in key_decisions if d.get("rationale")]
        rationale = " ".join(rationale_parts) if rationale_parts else "Plan generated based on intent analysis"

        # Extract alternatives (from review pack or metadata)
        alternatives = []
        review_pack = dry_run_result.get("review_pack_stub", {})
        if review_pack.get("requires_human_review"):
            alternatives.append("Manual review and execution recommended for high-risk operations")

        explanation = PlanExplanation(
            task_id=task_id,
            summary=summary,
            rationale=rationale,
            alternatives=alternatives,
            key_decisions=key_decisions,
            structured_fields={
                "risk_level": review_pack.get("risk_summary", {}).get("dominant_risk", "unknown"),
                "requires_review": review_pack.get("requires_human_review", False)
            }
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=task_id,
            operation="explain_read",
            event_type="dryrun_explain_accessed",
            status="success",
            payload={"actor": "webui"}
        )

        return UnifiedResponse(
            ok=True,
            data=explanation.dict()
        )

    except Exception as e:
        logger.exception(f"Error getting plan explanation for task {task_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )


@router.get("/api/dryrun/{task_id}/validate")
async def validate_execution_plan(task_id: str) -> UnifiedResponse:
    """Get validation results for execution plan

    Returns:
        ValidationResult with rule checks, failures, and suggested fixes

    Example:
        GET /api/dryrun/task_123/validate

        Response:
        {
            "ok": true,
            "data": {
                "task_id": "task_123",
                "is_valid": true,
                "checks_passed": ["Evidence check", "Risk assessment"],
                "checks_failed": [],
                "warnings": ["High risk operation detected"],
                "suggested_fixes": []
            }
        }
    """
    try:
        # Get task
        task_service = TaskService()
        task = task_service.get_task(task_id)

        if not task:
            return UnifiedResponse(
                ok=False,
                error=f"Task not found: {task_id}",
                reason_code="TASK_NOT_FOUND"
            )

        # Get dry-run result
        dry_run_result = _get_dry_run_result_from_task(task)

        if not dry_run_result:
            return UnifiedResponse(
                ok=False,
                error="No dry-run plan found for this task",
                reason_code="NO_DRY_RUN_RESULT"
            )

        # Perform validation checks
        checks_passed = []
        checks_failed = []
        warnings = []
        suggested_fixes = []

        # Check 1: Evidence refs present
        graph = dry_run_result.get("graph", {})
        nodes_without_evidence = []
        for node in graph.get("nodes", []):
            if not node.get("evidence_refs"):
                nodes_without_evidence.append(node.get("name", "unknown"))

        if nodes_without_evidence:
            checks_failed.append({
                "check": "Evidence references",
                "reason": f"Nodes without evidence: {', '.join(nodes_without_evidence)}"
            })
            suggested_fixes.append("Add evidence references to all execution nodes")
        else:
            checks_passed.append("Evidence references")

        # Check 2: Risk assessment
        review_pack = dry_run_result.get("review_pack_stub", {})
        risk_summary = review_pack.get("risk_summary", {})
        dominant_risk = risk_summary.get("dominant_risk", "unknown")

        if dominant_risk == "unknown":
            checks_failed.append({
                "check": "Risk assessment",
                "reason": "Risk level not determined"
            })
            suggested_fixes.append("Perform risk assessment on execution plan")
        else:
            checks_passed.append("Risk assessment")
            if dominant_risk in ["high", "critical"]:
                warnings.append(f"{dominant_risk.capitalize()} risk operation detected - requires approval")

        # Check 3: Constraints enforced
        metadata = dry_run_result.get("metadata", {})
        constraints = metadata.get("constraints_enforced", [])
        required_constraints = ["DE1_no_exec", "DE4_evidence_required"]

        missing_constraints = [c for c in required_constraints if c not in constraints]
        if missing_constraints:
            checks_failed.append({
                "check": "Constraint enforcement",
                "reason": f"Missing constraints: {', '.join(missing_constraints)}"
            })
        else:
            checks_passed.append("Constraint enforcement")

        # Check 4: Lineage present
        lineage = dry_run_result.get("lineage", {})
        if lineage.get("derived_from"):
            checks_passed.append("Lineage tracking")
        else:
            warnings.append("No lineage information found")

        # Determine overall validity
        is_valid = len(checks_failed) == 0

        validation = ValidationResult(
            task_id=task_id,
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            suggested_fixes=suggested_fixes
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=task_id,
            operation="validate_read",
            event_type="dryrun_validate_accessed",
            status="success" if is_valid else "warning",
            payload={
                "is_valid": is_valid,
                "checks_failed_count": len(checks_failed),
                "actor": "webui"
            }
        )

        return UnifiedResponse(
            ok=True,
            data=validation.dict()
        )

    except Exception as e:
        logger.exception(f"Error validating plan for task {task_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )


@router.post("/api/dryrun/proposal")
async def generate_execution_proposal(request: ProposalRequest = Body(...)) -> UnifiedResponse:
    """Generate new execution proposal (no actual execution)

    Creates a dry-run execution plan and stores it as a proposal
    requiring approval before execution.

    Args:
        request: ProposalRequest with task_id and params

    Returns:
        ProposalResponse with proposal_id and status="pending_review"

    Example:
        POST /api/dryrun/proposal
        {
            "task_id": "task_123",
            "params": {"mode": "full_auto"},
            "actor": "webui_user"
        }

        Response:
        {
            "ok": true,
            "data": {
                "proposal_id": "proposal_xyz",
                "task_id": "task_123",
                "status": "pending_review",
                "requires_approval": true
            }
        }
    """
    try:
        # Get task
        task_service = TaskService()
        task = task_service.get_task(request.task_id)

        if not task:
            return UnifiedResponse(
                ok=False,
                error=f"Task not found: {request.task_id}",
                reason_code="TASK_NOT_FOUND"
            )

        # Check if task has intent data
        if not task.metadata or "intent" not in task.metadata:
            return UnifiedResponse(
                ok=False,
                error="Task has no intent data for proposal generation",
                reason_code="NO_INTENT_DATA",
                hint="Task must have intent metadata to generate execution proposal"
            )

        # Extract intent from task metadata
        intent = task.metadata["intent"]

        # Run dry executor (no actual execution)
        dry_executor = DryExecutor()
        dry_run_result = dry_executor.run(intent)

        # Generate proposal ID
        from datetime import datetime
        import uuid
        proposal_id = f"proposal_{uuid.uuid4().hex[:12]}"

        # Convert to ExecutionPlan
        graph = dry_run_result.get("graph", {})
        steps = _convert_graph_to_steps(graph)
        risk_markers = _extract_risk_markers(dry_run_result)

        plan = ExecutionPlan(
            plan_id=dry_run_result.get("result_id", proposal_id),
            task_id=request.task_id,
            steps=steps,
            total_steps=len(steps),
            risk_markers=risk_markers,
            created_at=iso_z(utc_now())
        )

        # Store proposal in task metadata
        task_manager = task_service.task_manager
        conn = task_manager._get_conn()
        try:
            cursor = conn.cursor()

            # Update task metadata with proposal
            current_metadata = task.metadata or {}
            if "proposals" not in current_metadata:
                current_metadata["proposals"] = []

            current_metadata["proposals"].append({
                "proposal_id": proposal_id,
                "status": "pending_review",
                "dry_run_result": dry_run_result,
                "created_at": iso_z(utc_now()),
                "created_by": request.actor,
                "params": request.params
            })

            # Store latest dry_run_result at top level for easy access
            current_metadata["dry_run_result"] = dry_run_result

            cursor.execute(
                "UPDATE tasks SET metadata = ?, updated_at = ? WHERE task_id = ?",
                (json.dumps(current_metadata), iso_z(utc_now()), request.task_id)
            )
            conn.commit()
        finally:
            conn.close()

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=request.task_id,
            operation="proposal_created",
            event_type="dryrun_proposal_generated",
            status="success",
            payload={
                "proposal_id": proposal_id,
                "actor": request.actor,
                "step_count": len(steps),
                "requires_approval": True
            }
        )

        # Build response
        proposal = ProposalResponse(
            proposal_id=proposal_id,
            task_id=request.task_id,
            status="pending_review",
            plan=plan,
            requires_approval=True,
            created_at=iso_z(utc_now())
        )

        return UnifiedResponse(
            ok=True,
            data=proposal.dict()
        )

    except Exception as e:
        logger.exception(f"Error generating proposal for task {request.task_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )
