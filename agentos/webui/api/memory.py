"""
Memory API - Memory search and management

GET /api/memory/search - Search memory
POST /api/memory/upsert - Upsert memory item
GET /api/memory/{id} - Get memory item details
GET /api/memory/timeline - Memory timeline (audit trail)

Memory Proposal Endpoints (Task #17):
POST /api/memory/propose - Propose a memory (requires PROPOSE capability)
GET /api/memory/proposals - List proposals
GET /api/memory/proposals/{id} - Get proposal details
POST /api/memory/proposals/{id}/approve - Approve proposal (requires ADMIN)
POST /api/memory/proposals/{id}/reject - Reject proposal (requires ADMIN)
GET /api/memory/proposals/stats - Get proposal statistics
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import json
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now
from agentos.core.memory.service import MemoryService
from agentos.core.memory.proposals import get_proposal_service
from agentos.core.memory.capabilities import PermissionDenied


router = APIRouter()


class MemoryItem(BaseModel):
    """Memory item model"""
    id: str
    namespace: str
    key: str
    value: str
    source: Optional[str] = None  # task_id or session_id
    source_type: Optional[str] = None  # "task" | "session" | "manual"
    created_at: str
    ttl: Optional[int] = None  # seconds
    metadata: Dict[str, Any] = {}


class UpsertMemoryRequest(BaseModel):
    """Upsert memory request"""
    namespace: str
    key: str
    value: str
    source: Optional[str] = None
    source_type: Optional[str] = None
    ttl: Optional[int] = None
    metadata: Dict[str, Any] = {}


# In-memory store (TODO: integrate with MemoryOS)
_memory: Dict[str, MemoryItem] = {}


@router.get("/search")
async def search_memory(
    q: Optional[str] = Query(None, description="Search query"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> List[MemoryItem]:
    """
    Search memory items

    Args:
        q: Search query (matches key or value)
        namespace: Filter by namespace
        limit: Maximum results

    Returns:
        List of memory items
    """
    items = list(_memory.values())

    # Apply filters
    if namespace:
        items = [m for m in items if m.namespace == namespace]
    if q:
        q_lower = q.lower()
        items = [m for m in items if q_lower in m.key.lower() or q_lower in m.value.lower()]

    # Sort by created_at (newest first) and limit
    items = sorted(items, key=lambda m: m.created_at, reverse=True)[:limit]

    return items


@router.post("/upsert")
async def upsert_memory(req: UpsertMemoryRequest) -> MemoryItem:
    """
    Upsert memory item

    Args:
        req: Upsert request

    Returns:
        Created/updated memory item
    """
    # Generate ID from namespace + key
    item_id = f"{req.namespace}:{req.key}"

    item = MemoryItem(
        id=item_id,
        namespace=req.namespace,
        key=req.key,
        value=req.value,
        source=req.source,
        source_type=req.source_type,
        created_at=iso_z(utc_now()),
        ttl=req.ttl,
        metadata=req.metadata,
    )

    _memory[item_id] = item

    return item


@router.get("/{item_id}")
async def get_memory(item_id: str) -> MemoryItem:
    """Get memory item by ID"""
    if item_id not in _memory:
        raise HTTPException(status_code=404, detail="Memory item not found")

    return _memory[item_id]


@router.get("/{item_id}/history")
async def get_memory_history(item_id: str) -> List[Dict[str, Any]]:
    """
    Get version history for a memory item.

    Returns all versions in the conflict resolution chain, from oldest to newest.

    Args:
        item_id: Memory ID to get history for

    Returns:
        List of memory items in version order
    """
    try:
        memory_service = MemoryService()
        history = memory_service.get_version_history(item_id)

        if not history:
            raise HTTPException(status_code=404, detail="Memory item not found")

        # Format for API response
        formatted_history = []
        for mem in history:
            content = mem.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {}

            formatted_history.append({
                "id": mem["id"],
                "value": content.get("value") or content.get("summary", "") or str(content),
                "content": content,
                "confidence": mem.get("confidence", 0.5),
                "version": mem.get("version", 1),
                "is_active": mem.get("is_active", True),
                "supersedes": mem.get("supersedes"),
                "superseded_by": mem.get("superseded_by"),
                "superseded_at": mem.get("superseded_at"),
                "created_at": mem["created_at"],
                "updated_at": mem.get("updated_at", mem["created_at"]),
            })

        return formatted_history

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch version history: {str(e)}")


class TimelineItem(BaseModel):
    """Timeline item model for audit trail"""
    id: str
    timestamp: str
    key: str
    value: str
    type: str
    source: str  # rule_extraction | explicit | system
    confidence: float
    is_active: bool
    version: int
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    scope: str
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TimelineResponse(BaseModel):
    """Timeline response with pagination"""
    items: List[TimelineItem]
    total: int
    page: int
    has_more: bool


@router.get("/timeline", response_model=TimelineResponse)
async def get_memory_timeline(
    scope: Optional[str] = Query(None, description="Filter by scope (global/project/task/agent)"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    mem_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(50, ge=1, le=200, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> TimelineResponse:
    """
    Get memory timeline (chronological history)

    Returns memory items sorted by creation time (newest first),
    including both active and superseded memories for audit trail.

    This is a read-only view for auditability, consistent with AgentOS Logs/Audit style.

    Query params:
        scope: Filter by scope (global/project/task/agent)
        project_id: Filter by project
        mem_type: Filter by memory type
        limit: Max items per page (default 50, max 200)
        offset: Pagination offset

    Returns:
        TimelineResponse with items, total count, and pagination info
    """
    try:
        memory_service = MemoryService()
        conn = memory_service._get_connection()
        cursor = conn.cursor()

        # Build query
        query = "SELECT * FROM memory_items WHERE 1=1"
        params = []

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if mem_type:
            query += " AND type = ?"
            params.append(mem_type)

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated items (newest first)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Format timeline items
        items = []
        for row in rows:
            mem = memory_service._row_to_dict(row)

            # Determine source
            sources = mem.get("sources", [])
            if sources:
                source = sources[0].get("type", "system")
            else:
                source = "system"

            # Extract key/value from content
            content = mem.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {}

            key = content.get("key", mem.get("type", "unknown"))
            value = content.get("value") or content.get("summary", "") or str(content)

            # Check active status from metadata
            metadata = {}
            if isinstance(mem.get("metadata"), dict):
                metadata = mem["metadata"]

            is_active = metadata.get("is_active", True)
            version = metadata.get("version", 1)
            supersedes = metadata.get("supersedes")
            superseded_by = metadata.get("superseded_by")

            items.append(TimelineItem(
                id=mem["id"],
                timestamp=mem["created_at"],
                key=key,
                value=value,
                type=mem["type"],
                source=source,
                confidence=mem.get("confidence", 0.5),
                is_active=is_active,
                version=version,
                supersedes=supersedes,
                superseded_by=superseded_by,
                scope=mem["scope"],
                project_id=mem.get("project_id"),
                metadata=metadata
            ))

        conn.close()

        # Calculate pagination
        page = (offset // limit) + 1
        has_more = (offset + limit) < total

        return TimelineResponse(
            items=items,
            total=total,
            page=page,
            has_more=has_more
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch timeline: {str(e)}")


# ============================================
# Memory Proposal Endpoints (Task #17)
# ============================================

class ProposeMemoryRequest(BaseModel):
    """Propose memory request"""
    agent_id: str
    memory_item: Dict[str, Any]
    reason: Optional[str] = None


class ProposalResponse(BaseModel):
    """Proposal response"""
    proposal_id: str
    status: str


class ApproveProposalRequest(BaseModel):
    """Approve proposal request"""
    reviewer_id: str
    reason: Optional[str] = None


class RejectProposalRequest(BaseModel):
    """Reject proposal request"""
    reviewer_id: str
    reason: str


@router.post("/propose", response_model=ProposalResponse)
async def propose_memory(req: ProposeMemoryRequest) -> ProposalResponse:
    """
    Propose a memory (requires PROPOSE capability).

    This allows chat agents to suggest memories without directly writing them.
    The proposal enters pending queue for admin review.

    Args:
        req: Propose memory request with agent_id, memory_item, and reason

    Returns:
        ProposalResponse with proposal_id and status

    Raises:
        HTTPException 403: If agent lacks PROPOSE capability
        HTTPException 500: On internal error
    """
    try:
        proposal_service = get_proposal_service()
        proposal_id = proposal_service.propose_memory(
            agent_id=req.agent_id,
            memory_item=req.memory_item,
            reason=req.reason
        )
        return ProposalResponse(proposal_id=proposal_id, status="pending")

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to propose memory: {str(e)}")


@router.get("/proposals")
async def list_proposals(
    agent_id: str = Query(..., description="Agent ID (requires READ capability)"),
    status: Optional[str] = Query(None, description="Filter by status (pending/approved/rejected)"),
    proposed_by: Optional[str] = Query(None, description="Filter by proposer"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> Dict[str, Any]:
    """
    List memory proposals (requires READ capability).

    Args:
        agent_id: Agent requesting list
        status: Filter by status
        proposed_by: Filter by proposer
        limit: Max results
        offset: Pagination offset

    Returns:
        Dict with proposals list and total count

    Raises:
        HTTPException 403: If agent lacks READ capability
        HTTPException 500: On internal error
    """
    try:
        proposal_service = get_proposal_service()
        proposals = proposal_service.list_proposals(
            agent_id=agent_id,
            status=status,
            proposed_by=proposed_by,
            limit=limit,
            offset=offset
        )
        return {"proposals": proposals, "total": len(proposals)}

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list proposals: {str(e)}")


@router.get("/proposals/stats")
async def get_proposal_stats(
    agent_id: str = Query(..., description="Agent ID (requires READ capability)")
) -> Dict[str, Any]:
    """
    Get proposal statistics (requires READ capability).

    Args:
        agent_id: Agent requesting stats

    Returns:
        Stats dict with counts by status

    Raises:
        HTTPException 403: If agent lacks READ capability
        HTTPException 500: On internal error
    """
    try:
        proposal_service = get_proposal_service()
        stats = proposal_service.get_proposal_stats(agent_id)
        return stats

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    agent_id: str = Query(..., description="Agent ID (requires READ capability)")
) -> Dict[str, Any]:
    """
    Get proposal by ID (requires READ capability).

    Args:
        proposal_id: Proposal ID
        agent_id: Agent requesting the proposal

    Returns:
        Proposal dict

    Raises:
        HTTPException 403: If agent lacks READ capability
        HTTPException 404: If proposal not found
        HTTPException 500: On internal error
    """
    try:
        proposal_service = get_proposal_service()
        proposal = proposal_service.get_proposal(agent_id, proposal_id)

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        return proposal

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get proposal: {str(e)}")


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    req: ApproveProposalRequest
) -> Dict[str, Any]:
    """
    Approve a proposal (requires ADMIN capability).

    This writes the proposed memory to memory_items using the reviewer's
    ADMIN capability.

    Args:
        proposal_id: Proposal to approve
        req: Approve request with reviewer_id and optional reason

    Returns:
        Dict with memory_id and status

    Raises:
        HTTPException 403: If reviewer lacks ADMIN capability
        HTTPException 404: If proposal not found
        HTTPException 400: If proposal not pending
        HTTPException 500: On internal error
    """
    try:
        proposal_service = get_proposal_service()
        memory_id = proposal_service.approve_proposal(
            reviewer_id=req.reviewer_id,
            proposal_id=proposal_id,
            reason=req.reason
        )
        return {"memory_id": memory_id, "status": "approved"}

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        # Proposal not found or not pending
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve proposal: {str(e)}")


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    req: RejectProposalRequest
) -> Dict[str, Any]:
    """
    Reject a proposal (requires ADMIN capability).

    Args:
        proposal_id: Proposal to reject
        req: Reject request with reviewer_id and reason

    Returns:
        Dict with status and success flag

    Raises:
        HTTPException 403: If reviewer lacks ADMIN capability
        HTTPException 404: If proposal not found
        HTTPException 400: If proposal not pending or reason empty
        HTTPException 500: On internal error
    """
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    try:
        proposal_service = get_proposal_service()
        success = proposal_service.reject_proposal(
            reviewer_id=req.reviewer_id,
            proposal_id=proposal_id,
            reason=req.reason
        )
        return {"status": "rejected", "success": success}

    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        # Proposal not found or not pending
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject proposal: {str(e)}")
