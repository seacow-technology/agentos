"""Intent API - Read-only endpoints for intent builder/evaluator operations

This module provides read-only API endpoints for accessing intent details,
builder explanations, evaluator diff results, and merge proposals.

Wave1-A4: Intent API for builder/evaluator

Endpoints:
    GET  /api/intent/{intent_id}                    - Get intent details
    GET  /api/intent/{intent_id}/explain            - Get builder explain output
    GET  /api/intent/{intent_id}/diff/{other_id}    - Get evaluator diff results
    POST /api/intent/{intent_id}/merge-proposal     - Generate merge proposal (no execution)

Red Lines:
    - No actual merge execution
    - All merge proposals require approval
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
from agentos.core.intent_builder.builder import IntentBuilder
from agentos.core.evaluator.engine import EvaluationResult
from agentos.core.content.registry import ContentRegistry


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


class IntentDetail(BaseModel):
    """Intent details"""
    intent_id: str
    type: str = "execution_intent"
    version: str
    nl_request: Dict[str, Any]
    scope: Dict[str, Any] = Field(default_factory=dict)
    workflows: List[Dict[str, Any]] = Field(default_factory=list)
    agents: List[Dict[str, Any]] = Field(default_factory=list)
    commands: List[Dict[str, Any]] = Field(default_factory=list)
    risk: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class BuilderExplanation(BaseModel):
    """Builder explanation output"""
    intent_id: str
    nl_input: str
    intent_structure: Dict[str, Any]
    rationale: str
    selection_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_summary: List[str] = Field(default_factory=list)


class FieldChange(BaseModel):
    """Single field change in diff"""
    field_path: str
    change_type: str  # added, removed, modified
    before_value: Optional[Any] = None
    after_value: Optional[Any] = None
    risk_hint: Optional[str] = None


class IntentDiff(BaseModel):
    """Diff between two intents"""
    intent_a_id: str
    intent_b_id: str
    changes: List[FieldChange]
    change_summary: str
    risk_assessment: str
    conflict_count: int


class MergeProposalRequest(BaseModel):
    """Request to generate merge proposal"""
    intent_id: str
    target_intent_id: str
    strategy: str = "auto"  # auto, manual, conflict_resolution
    actor: str = "webui"


class MergeProposal(BaseModel):
    """Merge proposal response"""
    proposal_id: str
    intent_a_id: str
    intent_b_id: str
    merge_strategy: str
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    merged_intent: Optional[Dict[str, Any]] = None
    requires_approval: bool = True
    status: str = "pending_review"
    created_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def _get_intent_from_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get intent from task metadata

    Args:
        task_id: Task ID

    Returns:
        Intent dict or None
    """
    task_service = TaskService()
    task = task_service.get_task(task_id)

    if not task or not task.metadata:
        return None

    return task.metadata.get("intent")


def _get_intent_from_storage(intent_id: str) -> Optional[Dict[str, Any]]:
    """Get intent from storage (task metadata or separate storage)

    Args:
        intent_id: Intent ID

    Returns:
        Intent dict or None
    """
    # First try to find task with this intent ID
    task_service = TaskService()

    # Check if intent_id is actually a task_id
    task = task_service.get_task(intent_id)
    if task:
        return _get_intent_from_task(intent_id)

    # Try to find task by searching metadata
    # Note: This is a simplified search. In production, you'd have a proper index.
    tasks = task_service.list_tasks(limit=100)
    for task in tasks:
        if task.metadata and task.metadata.get("intent", {}).get("id") == intent_id:
            return task.metadata["intent"]

    return None


def _compute_field_changes(intent_a: Dict[str, Any], intent_b: Dict[str, Any]) -> List[FieldChange]:
    """Compute field-level changes between two intents

    Args:
        intent_a: First intent
        intent_b: Second intent

    Returns:
        List of FieldChange objects
    """
    changes = []

    # Compare top-level fields
    all_keys = set(intent_a.keys()) | set(intent_b.keys())

    for key in all_keys:
        if key in ["id", "created_at", "audit"]:
            # Skip metadata fields
            continue

        val_a = intent_a.get(key)
        val_b = intent_b.get(key)

        if val_a == val_b:
            continue

        # Determine change type
        if key not in intent_a:
            change_type = "added"
            before_value = None
            after_value = val_b
        elif key not in intent_b:
            change_type = "removed"
            before_value = val_a
            after_value = None
        else:
            change_type = "modified"
            before_value = val_a
            after_value = val_b

        # Assess risk
        risk_hint = None
        if key == "risk":
            risk_hint = "Risk level changed - requires validation"
        elif key in ["workflows", "agents", "commands"]:
            risk_hint = "Execution path modified"
        elif key == "scope":
            risk_hint = "Scope changed - may affect file targets"

        changes.append(FieldChange(
            field_path=key,
            change_type=change_type,
            before_value=before_value,
            after_value=after_value,
            risk_hint=risk_hint
        ))

    return changes


def _generate_change_summary(changes: List[FieldChange]) -> str:
    """Generate human-readable change summary

    Args:
        changes: List of field changes

    Returns:
        Summary string
    """
    if not changes:
        return "No changes detected"

    added = sum(1 for c in changes if c.change_type == "added")
    removed = sum(1 for c in changes if c.change_type == "removed")
    modified = sum(1 for c in changes if c.change_type == "modified")

    parts = []
    if added:
        parts.append(f"{added} field(s) added")
    if removed:
        parts.append(f"{removed} field(s) removed")
    if modified:
        parts.append(f"{modified} field(s) modified")

    return ", ".join(parts)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/intent/{intent_id}")
async def get_intent_detail(intent_id: str) -> UnifiedResponse:
    """Get intent details

    Returns:
        IntentDetail with full intent structure

    Example:
        GET /api/intent/intent_abc123

        Response:
        {
            "ok": true,
            "data": {
                "intent_id": "intent_abc123",
                "type": "execution_intent",
                "version": "0.9.1",
                "nl_request": {...},
                "scope": {...},
                ...
            }
        }
    """
    try:
        # Get intent from storage
        intent = _get_intent_from_storage(intent_id)

        if not intent:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {intent_id}",
                reason_code="INTENT_NOT_FOUND",
                hint="Verify the intent ID exists"
            )

        # Convert to IntentDetail
        detail = IntentDetail(
            intent_id=intent.get("id", intent_id),
            type=intent.get("type", "execution_intent"),
            version=intent.get("version", "0.9.1"),
            nl_request=intent.get("nl_request", {}),
            scope=intent.get("scope", {}),
            workflows=intent.get("workflows", []),
            agents=intent.get("agents", []),
            commands=intent.get("commands", []),
            risk=intent.get("risk", {}),
            constraints=intent.get("constraints", {}),
            created_at=intent.get("created_at", iso_z(utc_now()))
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=intent_id,
            operation="intent_read",
            event_type="intent_accessed",
            status="success",
            payload={"intent_id": intent_id, "actor": "webui"}
        )

        return UnifiedResponse(
            ok=True,
            data=detail.dict()
        )

    except Exception as e:
        logger.exception(f"Error getting intent detail for {intent_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )


@router.get("/api/intent/{intent_id}/explain")
async def get_builder_explanation(intent_id: str) -> UnifiedResponse:
    """Get builder explain output (NL input → intent structure → rationale)

    Returns:
        BuilderExplanation with natural language rationale

    Example:
        GET /api/intent/intent_abc123/explain

        Response:
        {
            "ok": true,
            "data": {
                "intent_id": "intent_abc123",
                "nl_input": "Deploy the authentication service",
                "intent_structure": {...},
                "rationale": "Selected deployment workflow based on...",
                "selection_decisions": [...]
            }
        }
    """
    try:
        # Get intent from storage
        intent = _get_intent_from_storage(intent_id)

        if not intent:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {intent_id}",
                reason_code="INTENT_NOT_FOUND"
            )

        # Extract NL input
        nl_request = intent.get("nl_request", {})
        nl_input = nl_request.get("request", "")

        # Extract selection evidence
        selection_evidence = intent.get("selection_evidence", {})
        workflows = selection_evidence.get("workflows", [])
        agents = selection_evidence.get("agents", [])
        commands = selection_evidence.get("commands", [])

        # Build selection decisions
        selection_decisions = []

        for wf in workflows:
            selection_decisions.append({
                "type": "workflow",
                "selected": wf.get("id"),
                "reason": wf.get("selection_reason", "Matched based on intent keywords"),
                "evidence": wf.get("evidence_refs", [])
            })

        for agent in agents:
            selection_decisions.append({
                "type": "agent",
                "selected": agent.get("id"),
                "reason": agent.get("selection_reason", "Required for workflow execution"),
                "evidence": agent.get("evidence_refs", [])
            })

        for cmd in commands:
            selection_decisions.append({
                "type": "command",
                "selected": cmd.get("id"),
                "reason": cmd.get("selection_reason", "Part of agent capability"),
                "evidence": cmd.get("evidence_refs", [])
            })

        # Build rationale
        rationale_parts = []
        if workflows:
            rationale_parts.append(f"Selected {len(workflows)} workflow(s) based on intent analysis.")
        if agents:
            rationale_parts.append(f"Identified {len(agents)} agent(s) required for execution.")
        if commands:
            rationale_parts.append(f"Mapped to {len(commands)} command(s) for implementation.")

        rationale = " ".join(rationale_parts) if rationale_parts else "Intent built from natural language input"

        # Extract evidence summary
        evidence_summary = []
        for decision in selection_decisions:
            if decision.get("evidence"):
                evidence_summary.extend(decision["evidence"])

        explanation = BuilderExplanation(
            intent_id=intent.get("id", intent_id),
            nl_input=nl_input,
            intent_structure={
                "workflows": len(intent.get("workflows", [])),
                "agents": len(intent.get("agents", [])),
                "commands": len(intent.get("commands", [])),
                "risk_level": intent.get("risk", {}).get("overall", "unknown")
            },
            rationale=rationale,
            selection_decisions=selection_decisions,
            evidence_summary=list(set(evidence_summary))  # Deduplicate
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=intent_id,
            operation="explain_read",
            event_type="intent_explain_accessed",
            status="success",
            payload={"intent_id": intent_id, "actor": "webui"}
        )

        return UnifiedResponse(
            ok=True,
            data=explanation.dict()
        )

    except Exception as e:
        logger.exception(f"Error getting builder explanation for {intent_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )


@router.get("/api/intent/{intent_id}/diff/{other_id}")
async def get_intent_diff(intent_id: str, other_id: str) -> UnifiedResponse:
    """Get evaluator diff results (field-level changes with before/after values)

    Returns:
        IntentDiff with field-level changes and risk hints

    Example:
        GET /api/intent/intent_abc123/diff/intent_xyz789

        Response:
        {
            "ok": true,
            "data": {
                "intent_a_id": "intent_abc123",
                "intent_b_id": "intent_xyz789",
                "changes": [
                    {
                        "field_path": "risk.overall",
                        "change_type": "modified",
                        "before_value": "low",
                        "after_value": "high",
                        "risk_hint": "Risk level changed - requires validation"
                    }
                ],
                "change_summary": "1 field(s) modified",
                "risk_assessment": "high",
                "conflict_count": 0
            }
        }
    """
    try:
        # Get both intents
        intent_a = _get_intent_from_storage(intent_id)
        intent_b = _get_intent_from_storage(other_id)

        if not intent_a:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {intent_id}",
                reason_code="INTENT_NOT_FOUND"
            )

        if not intent_b:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {other_id}",
                reason_code="INTENT_NOT_FOUND"
            )

        # Compute field changes
        changes = _compute_field_changes(intent_a, intent_b)

        # Generate summary
        change_summary = _generate_change_summary(changes)

        # Assess risk
        risk_a = intent_a.get("risk", {}).get("overall", "low")
        risk_b = intent_b.get("risk", {}).get("overall", "low")

        risk_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_risk = max(risk_levels.get(risk_a, 1), risk_levels.get(risk_b, 1))
        risk_assessment = [k for k, v in risk_levels.items() if v == max_risk][0]

        # Count conflicts (simplified - in production, use ConflictDetector)
        conflict_count = sum(1 for c in changes if c.risk_hint and "conflict" in c.risk_hint.lower())

        diff = IntentDiff(
            intent_a_id=intent_id,
            intent_b_id=other_id,
            changes=changes,
            change_summary=change_summary,
            risk_assessment=risk_assessment,
            conflict_count=conflict_count
        )

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=intent_id,
            operation="diff_read",
            event_type="intent_diff_accessed",
            status="success",
            payload={
                "intent_a_id": intent_id,
                "intent_b_id": other_id,
                "change_count": len(changes),
                "actor": "webui"
            }
        )

        return UnifiedResponse(
            ok=True,
            data=diff.dict()
        )

    except Exception as e:
        logger.exception(f"Error computing diff between {intent_id} and {other_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )


@router.post("/api/intent/{intent_id}/merge-proposal")
async def generate_merge_proposal(
    intent_id: str,
    request: MergeProposalRequest = Body(...)
) -> UnifiedResponse:
    """Generate merge proposal (no actual merge execution)

    Creates a merge plan between two intents and stores it as a proposal
    requiring approval.

    Args:
        intent_id: Source intent ID (from URL path)
        request: MergeProposalRequest with target_intent_id and strategy

    Returns:
        MergeProposal with proposal_id and status="pending_review"

    Example:
        POST /api/intent/intent_abc123/merge-proposal
        {
            "intent_id": "intent_abc123",
            "target_intent_id": "intent_xyz789",
            "strategy": "auto",
            "actor": "webui_user"
        }

        Response:
        {
            "ok": true,
            "data": {
                "proposal_id": "merge_proposal_123",
                "intent_a_id": "intent_abc123",
                "intent_b_id": "intent_xyz789",
                "merge_strategy": "auto",
                "conflicts": [],
                "requires_approval": true,
                "status": "pending_review"
            }
        }
    """
    try:
        # Get both intents
        intent_a = _get_intent_from_storage(intent_id)
        intent_b = _get_intent_from_storage(request.target_intent_id)

        if not intent_a:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {intent_id}",
                reason_code="INTENT_NOT_FOUND"
            )

        if not intent_b:
            return UnifiedResponse(
                ok=False,
                error=f"Intent not found: {request.target_intent_id}",
                reason_code="INTENT_NOT_FOUND"
            )

        # Compute changes and detect conflicts
        changes = _compute_field_changes(intent_a, intent_b)

        # Identify conflicts (simplified - in production, use ConflictDetector)
        conflicts = []
        for change in changes:
            if change.risk_hint and any(word in change.risk_hint.lower() for word in ["conflict", "incompatible"]):
                conflicts.append({
                    "field": change.field_path,
                    "type": "value_conflict",
                    "description": change.risk_hint,
                    "resolution": "manual"
                })

        # Check for structural conflicts
        if "scope" in [c.field_path for c in changes]:
            conflicts.append({
                "field": "scope",
                "type": "scope_conflict",
                "description": "Scopes differ - may target different files",
                "resolution": "requires_review"
            })

        # Attempt simple merge (for auto strategy)
        merged_intent = None
        if request.strategy == "auto" and not conflicts:
            # Simple merge: take latest values
            merged_intent = dict(intent_a)  # Copy base
            merged_intent["id"] = f"merged_{intent_id[:8]}_{request.target_intent_id[:8]}"
            merged_intent["merged_from"] = [intent_id, request.target_intent_id]

            # Apply changes from intent_b
            for change in changes:
                if change.change_type in ["added", "modified"]:
                    merged_intent[change.field_path] = change.after_value

        # Generate proposal ID
        import uuid
        proposal_id = f"merge_proposal_{uuid.uuid4().hex[:12]}"

        # Create proposal
        proposal = MergeProposal(
            proposal_id=proposal_id,
            intent_a_id=intent_id,
            intent_b_id=request.target_intent_id,
            merge_strategy=request.strategy,
            conflicts=conflicts,
            merged_intent=merged_intent,
            requires_approval=True,
            status="pending_review",
            created_at=iso_z(utc_now())
        )

        # Store proposal (in task metadata or separate storage)
        # For now, we'll try to find the task and store it there
        task_service = TaskService()
        task = task_service.get_task(intent_id)

        if task:
            task_manager = task_service.task_manager
            conn = task_manager._get_conn()
            try:
                cursor = conn.cursor()

                # Update task metadata with merge proposal
                current_metadata = task.metadata or {}
                if "merge_proposals" not in current_metadata:
                    current_metadata["merge_proposals"] = []

                current_metadata["merge_proposals"].append({
                    "proposal_id": proposal_id,
                    "intent_a_id": intent_id,
                    "intent_b_id": request.target_intent_id,
                    "strategy": request.strategy,
                    "conflicts": conflicts,
                    "merged_intent": merged_intent,
                    "status": "pending_review",
                    "created_at": iso_z(utc_now()),
                    "created_by": request.actor
                })

                cursor.execute(
                    "UPDATE tasks SET metadata = ?, updated_at = ? WHERE task_id = ?",
                    (json.dumps(current_metadata), iso_z(utc_now()), intent_id)
                )
                conn.commit()
            finally:
                conn.close()

        # Record audit
        audit_service = TaskAuditService()
        audit_service.record_operation(
            task_id=intent_id,
            operation="merge_proposal_created",
            event_type="intent_merge_proposal_generated",
            status="success",
            payload={
                "proposal_id": proposal_id,
                "intent_a_id": intent_id,
                "intent_b_id": request.target_intent_id,
                "conflict_count": len(conflicts),
                "actor": request.actor
            }
        )

        return UnifiedResponse(
            ok=True,
            data=proposal.dict()
        )

    except Exception as e:
        logger.exception(f"Error generating merge proposal for {intent_id}")
        return UnifiedResponse(
            ok=False,
            error=str(e),
            reason_code="INTERNAL_ERROR"
        )
