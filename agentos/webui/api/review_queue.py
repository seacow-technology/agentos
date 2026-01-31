"""
Review Queue API - Human review interface for BrainOS improvement proposals

This module provides REST API endpoints for humans to review and approve/reject
BrainOS-generated improvement proposals for classifier modifications.

Endpoints:
- GET /api/v3/review-queue - Get pending proposals (paginated)
- GET /api/v3/review-queue/{proposal_id} - Get detailed proposal with evidence
- POST /api/v3/review-queue/{proposal_id}/approve - Approve proposal
- POST /api/v3/review-queue/{proposal_id}/reject - Reject proposal
- POST /api/v3/review-queue/{proposal_id}/defer - Defer proposal

Design Philosophy:
- Human-in-the-loop: All proposals require explicit human approval
- Evidence-driven: Show statistical evidence and decision comparison data
- Audit trail: All review actions logged to audit system
- Immutability: Reviewed proposals cannot be modified
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.core.audit import log_audit_event
from agentos.core.time import utc_now
from agentos.core.brain.improvement_proposal import (
    ChangeType,
    ProposalStatus,
    RiskLevel,
)
from agentos.core.brain.improvement_proposal_store import get_store
from agentos.core.chat.decision_comparator import get_comparator
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class ApproveProposalRequest(BaseModel):
    """Request to approve a proposal"""
    reviewed_by: str = Field(..., description="Username of reviewer")
    notes: Optional[str] = Field(None, description="Optional review notes")


class RejectProposalRequest(BaseModel):
    """Request to reject a proposal"""
    reviewed_by: str = Field(..., description="Username of reviewer")
    reason: str = Field(..., description="Reason for rejection")


class DeferProposalRequest(BaseModel):
    """Request to defer a proposal"""
    reviewed_by: str = Field(..., description="Username of reviewer")
    reason: str = Field(..., description="Reason for deferring")


def parse_time_range(
    time_range: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> tuple[datetime, datetime]:
    """
    Parse time range string and return start/end datetime objects

    Args:
        time_range: Preset time range (24h, 7d, 30d, custom)
        start_time: Optional custom start time (ISO format)
        end_time: Optional custom end time (ISO format)

    Returns:
        (start_datetime, end_datetime)

    Raises:
        ValueError: If time range is invalid or custom times are missing
    """
    now = utc_now()

    if time_range == "24h":
        return now - timedelta(hours=24), now
    elif time_range == "7d":
        return now - timedelta(days=7), now
    elif time_range == "30d":
        return now - timedelta(days=30), now
    elif time_range == "custom":
        if not start_time or not end_time:
            raise ValueError("Custom time range requires both start_time and end_time")

        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

            # Ensure timezone awareness
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            return start_dt, end_dt
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid datetime format: {e}")
    else:
        raise ValueError(f"Invalid time_range: {time_range}. Must be one of: 24h, 7d, 30d, custom")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("")
async def list_review_queue(
    status: Optional[str] = Query(None, description="Filter by status (pending/accepted/rejected/deferred)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (LOW/MEDIUM/HIGH)"),
    change_type: Optional[str] = Query(None, description="Filter by change type"),
    time_range: str = Query("30d", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)"),
    limit: int = Query(50, description="Maximum results", ge=1, le=200),
    offset: int = Query(0, description="Offset for pagination", ge=0),
) -> Dict[str, Any]:
    """
    Get list of improvement proposals for review

    Returns paginated list of proposals with basic information and filters.
    Default view shows pending proposals awaiting review.

    Returns:
        {
            "ok": true,
            "data": {
                "items": [
                    {
                        "proposal_id": "BP-017A3C",
                        "scope": "EXTERNAL_FACT / recency",
                        "change_type": "expand_keyword",
                        "description": "Add time-sensitive keywords",
                        "status": "pending",
                        "risk_level": "LOW",
                        "improvement_rate": 0.18,
                        "samples": 312,
                        "recommendation": "Promote to v2",
                        "created_at": "2026-01-31T10:00:00Z",
                        "reviewed_by": null,
                        "reviewed_at": null,
                        "affected_version_id": "v1-active",
                        "shadow_version_id": "v2-shadow-a"
                    },
                    ...
                ],
                "total_count": 15,
                "pending_count": 8,
                "limit": 50,
                "offset": 0,
                "filters": {
                    "status": "pending",
                    "risk_level": null,
                    "change_type": null,
                    "time_range": "30d"
                }
            },
            "error": null
        }
    """
    try:
        store = get_store()

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = ProposalStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: pending, accepted, rejected, deferred, implemented"
                )

        # Parse change_type filter
        change_type_filter = None
        if change_type:
            try:
                change_type_filter = ChangeType(change_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid change_type: {change_type}"
                )

        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Query proposals
        proposals = await store.query_proposals(
            status=status_filter,
            change_type=change_type_filter,
            time_range=(start_dt, end_dt),
            limit=limit + offset,  # Fetch extra for pagination
        )

        # Filter by risk level if specified
        if risk_level:
            try:
                risk_filter = RiskLevel(risk_level.upper())
                proposals = [
                    p for p in proposals
                    if p.evidence.risk == risk_filter
                ]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid risk_level: {risk_level}. Must be one of: LOW, MEDIUM, HIGH"
                )

        # Apply pagination
        total_count = len(proposals)
        paginated_proposals = proposals[offset:offset + limit]

        # Get pending count
        pending_proposals = await store.get_pending_proposals(limit=1000)
        pending_count = len(pending_proposals)

        # Transform to response format
        items = []
        for proposal in paginated_proposals:
            items.append({
                "proposal_id": proposal.proposal_id,
                "scope": proposal.scope,
                "change_type": proposal.change_type.value,
                "description": proposal.description,
                "status": proposal.status.value,
                "risk_level": proposal.evidence.risk.value,
                "improvement_rate": proposal.evidence.improvement_rate,
                "samples": proposal.evidence.samples,
                "recommendation": proposal.recommendation.value,
                "created_at": iso_z(proposal.created_at),
                "reviewed_by": proposal.reviewed_by,
                "reviewed_at": iso_z(proposal.reviewed_at) if proposal.reviewed_at else None,
                "affected_version_id": proposal.affected_version_id,
                "shadow_version_id": proposal.shadow_version_id,
            })

        return {
            "ok": True,
            "data": {
                "items": items,
                "total_count": total_count,
                "pending_count": pending_count,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status,
                    "risk_level": risk_level,
                    "change_type": change_type,
                    "time_range": time_range,
                },
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list review queue: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.get("/{proposal_id}")
async def get_proposal_details(
    proposal_id: str,
) -> Dict[str, Any]:
    """
    Get detailed proposal information with evidence

    Returns complete proposal details including:
    - Full evidence and statistics
    - Decision comparison metrics (from DecisionComparator)
    - Proposal history (audit trail)

    Returns:
        {
            "ok": true,
            "data": {
                "proposal": {
                    "proposal_id": "BP-017A3C",
                    "scope": "EXTERNAL_FACT / recency",
                    "change_type": "expand_keyword",
                    "description": "Add time-sensitive keywords",
                    "status": "pending",
                    "recommendation": "Promote to v2",
                    "reasoning": "Shadow shows 18% improvement over 312 samples",
                    "affected_version_id": "v1-active",
                    "shadow_version_id": "v2-shadow-a",
                    "created_at": "2026-01-31T10:00:00Z",
                    "reviewed_by": null,
                    "reviewed_at": null,
                    "review_notes": null,
                    "metadata": {}
                },
                "evidence": {
                    "samples": 312,
                    "improvement_rate": 0.18,
                    "shadow_accuracy": 0.92,
                    "active_accuracy": 0.78,
                    "error_reduction": -0.25,
                    "risk": "LOW",
                    "confidence_score": 0.95,
                    "time_range_start": "2026-01-01T00:00:00Z",
                    "time_range_end": "2026-01-31T00:00:00Z"
                },
                "decision_comparison": {
                    "active": {
                        "version": "v1-active",
                        "avg_score": 0.78,
                        "decision_distribution": {...},
                        "info_need_distribution": {...}
                    },
                    "shadow": {
                        "version": "v2-shadow-a",
                        "avg_score": 0.92,
                        "decision_distribution": {...},
                        "info_need_distribution": {...}
                    },
                    "comparison": {
                        "improvement_rate": 0.18,
                        "sample_count": 312,
                        "divergence_rate": 0.48,
                        "better_count": 220,
                        "worse_count": 50,
                        "neutral_count": 42
                    }
                },
                "history": [
                    {
                        "history_id": "hist_123",
                        "action": "created",
                        "actor": null,
                        "timestamp": "2026-01-31T10:00:00Z",
                        "previous_status": null,
                        "new_status": "pending",
                        "notes": "Proposal created: Add time-sensitive keywords"
                    }
                ]
            },
            "error": null
        }
    """
    try:
        store = get_store()

        # Get proposal
        proposal = await store.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(
                status_code=404,
                detail=f"Proposal {proposal_id} not found"
            )

        # Get proposal history
        history = await store.get_proposal_history(proposal_id)

        # Get decision comparison data if shadow version exists
        decision_comparison = None
        if proposal.shadow_version_id:
            try:
                comparator = get_comparator()
                comparison = comparator.compare_versions(
                    active_version=proposal.affected_version_id,
                    shadow_version=proposal.shadow_version_id,
                    time_range=(
                        proposal.evidence.time_range_start,
                        proposal.evidence.time_range_end,
                    ) if proposal.evidence.time_range_start and proposal.evidence.time_range_end else None,
                    limit=1000,
                )
                decision_comparison = comparison
            except Exception as e:
                logger.warning(f"Failed to get decision comparison: {e}")
                # Continue without comparison data

        # Build response
        response = {
            "proposal": {
                "proposal_id": proposal.proposal_id,
                "scope": proposal.scope,
                "change_type": proposal.change_type.value,
                "description": proposal.description,
                "status": proposal.status.value,
                "recommendation": proposal.recommendation.value,
                "reasoning": proposal.reasoning,
                "affected_version_id": proposal.affected_version_id,
                "shadow_version_id": proposal.shadow_version_id,
                "created_at": iso_z(proposal.created_at),
                "reviewed_by": proposal.reviewed_by,
                "reviewed_at": iso_z(proposal.reviewed_at) if proposal.reviewed_at else None,
                "review_notes": proposal.review_notes,
                "implemented_at": iso_z(proposal.implemented_at) if proposal.implemented_at else None,
                "metadata": proposal.metadata,
            },
            "evidence": proposal.evidence.to_dict(),
            "decision_comparison": decision_comparison,
            "history": history,
        }

        return {
            "ok": True,
            "data": response,
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get proposal details: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    request: ApproveProposalRequest,
) -> Dict[str, Any]:
    """
    Approve an improvement proposal

    Marks proposal as accepted and records reviewer information.
    Logs action to audit trail.

    Returns:
        {
            "ok": true,
            "data": {
                "proposal_id": "BP-017A3C",
                "status": "accepted",
                "reviewed_by": "admin",
                "reviewed_at": "2026-01-31T11:00:00Z",
                "review_notes": "Looks good, proceed with implementation"
            },
            "error": null
        }
    """
    try:
        store = get_store()

        # Accept proposal
        proposal = await store.accept_proposal(
            proposal_id=proposal_id,
            reviewed_by=request.reviewed_by,
            notes=request.notes,
        )

        # Log audit event
        log_audit_event(
            event_type="PROPOSAL_APPROVED",
            metadata={
                "proposal_id": proposal_id,
                "reviewed_by": request.reviewed_by,
                "scope": proposal.scope,
                "change_type": proposal.change_type.value,
                "improvement_rate": proposal.evidence.improvement_rate,
                "risk_level": proposal.evidence.risk.value,
                "notes": request.notes,
            },
            level="info",
        )

        logger.info(f"Proposal {proposal_id} approved by {request.reviewed_by}")

        return {
            "ok": True,
            "data": {
                "proposal_id": proposal.proposal_id,
                "status": proposal.status.value,
                "reviewed_by": proposal.reviewed_by,
                "reviewed_at": iso_z(proposal.reviewed_at),
                "review_notes": proposal.review_notes,
            },
            "error": None,
        }

    except ValueError as e:
        logger.error(f"Invalid approval request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to approve proposal: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
) -> Dict[str, Any]:
    """
    Reject an improvement proposal

    Marks proposal as rejected with reason.
    Logs action to audit trail.

    Returns:
        {
            "ok": true,
            "data": {
                "proposal_id": "BP-017A3C",
                "status": "rejected",
                "reviewed_by": "admin",
                "reviewed_at": "2026-01-31T11:00:00Z",
                "review_notes": "Risk too high for production deployment"
            },
            "error": null
        }
    """
    try:
        store = get_store()

        # Reject proposal
        proposal = await store.reject_proposal(
            proposal_id=proposal_id,
            reviewed_by=request.reviewed_by,
            reason=request.reason,
        )

        # Log audit event
        log_audit_event(
            event_type="PROPOSAL_REJECTED",
            metadata={
                "proposal_id": proposal_id,
                "reviewed_by": request.reviewed_by,
                "scope": proposal.scope,
                "change_type": proposal.change_type.value,
                "reason": request.reason,
            },
            level="info",
        )

        logger.info(f"Proposal {proposal_id} rejected by {request.reviewed_by}")

        return {
            "ok": True,
            "data": {
                "proposal_id": proposal.proposal_id,
                "status": proposal.status.value,
                "reviewed_by": proposal.reviewed_by,
                "reviewed_at": iso_z(proposal.reviewed_at),
                "review_notes": proposal.review_notes,
            },
            "error": None,
        }

    except ValueError as e:
        logger.error(f"Invalid rejection request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reject proposal: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.post("/{proposal_id}/defer")
async def defer_proposal(
    proposal_id: str,
    request: DeferProposalRequest,
) -> Dict[str, Any]:
    """
    Defer an improvement proposal for later review

    Marks proposal as deferred with reason.
    Logs action to audit trail.

    Returns:
        {
            "ok": true,
            "data": {
                "proposal_id": "BP-017A3C",
                "status": "deferred",
                "reviewed_by": "admin",
                "reviewed_at": "2026-01-31T11:00:00Z",
                "review_notes": "Need more data before making decision"
            },
            "error": null
        }
    """
    try:
        store = get_store()

        # Defer proposal
        proposal = await store.defer_proposal(
            proposal_id=proposal_id,
            reviewed_by=request.reviewed_by,
            reason=request.reason,
        )

        # Log audit event
        log_audit_event(
            event_type="PROPOSAL_DEFERRED",
            metadata={
                "proposal_id": proposal_id,
                "reviewed_by": request.reviewed_by,
                "scope": proposal.scope,
                "change_type": proposal.change_type.value,
                "reason": request.reason,
            },
            level="info",
        )

        logger.info(f"Proposal {proposal_id} deferred by {request.reviewed_by}")

        return {
            "ok": True,
            "data": {
                "proposal_id": proposal.proposal_id,
                "status": proposal.status.value,
                "reviewed_by": proposal.reviewed_by,
                "reviewed_at": iso_z(proposal.reviewed_at),
                "review_notes": proposal.review_notes,
            },
            "error": None,
        }

    except ValueError as e:
        logger.error(f"Invalid defer request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to defer proposal: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }
