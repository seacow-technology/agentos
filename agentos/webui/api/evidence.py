"""
Evidence API - Checkpoint Evidence Viewer Endpoints

GET /api/checkpoints/{checkpoint_id}/evidence - Get checkpoint evidence details

PR-V6: Evidence Drawer (Trusted Progress Viewer)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from agentos.core.checkpoints.manager import CheckpointManager
from agentos.core.checkpoints.evidence import EvidenceVerifier
from agentos.core.checkpoints.models import EvidenceType, VerificationStatus
from agentos.store import get_db_path
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


router = APIRouter()


class EvidenceItemResponse(BaseModel):
    """Single evidence item response"""

    type: str = Field(description="Evidence type: artifact, command, db_row, timestamp")
    description: str = Field(description="Human-readable description")
    verified: bool = Field(description="Whether this evidence passed verification")
    verification_status: str = Field(description="Verification status: verified, failed, pending")
    verification_error: Optional[str] = Field(None, description="Error message if verification failed")
    verified_at: Optional[str] = Field(None, description="When verification was performed")

    # Type-specific details
    details: Dict[str, Any] = Field(default_factory=dict, description="Type-specific evidence details")


class CheckpointEvidenceResponse(BaseModel):
    """Complete checkpoint evidence response"""

    checkpoint_id: str
    task_id: str
    checkpoint_type: str
    sequence_number: int
    status: str = Field(description="Overall status: verified, invalid, pending")
    items: List[EvidenceItemResponse] = Field(description="List of evidence items")
    summary: Dict[str, Any] = Field(description="Verification summary statistics")
    created_at: str
    last_verified_at: Optional[str] = None


@router.get("/checkpoints/{checkpoint_id}/evidence")
async def get_checkpoint_evidence(checkpoint_id: str) -> CheckpointEvidenceResponse:
    """
    Get checkpoint evidence details for Evidence Drawer

    Args:
        checkpoint_id: Checkpoint ID to retrieve evidence for

    Returns:
        CheckpointEvidenceResponse with:
        - Overall verification status (verified/invalid/pending)
        - List of evidence items with details
        - Verification summary statistics

    Example:
        GET /api/checkpoints/ckpt_abc123/evidence

    Response:
        {
          "checkpoint_id": "ckpt_abc123",
          "task_id": "task_xyz",
          "checkpoint_type": "iteration_complete",
          "sequence_number": 5,
          "status": "verified",
          "items": [
            {
              "type": "artifact",
              "description": "Output file exists",
              "verified": true,
              "verification_status": "verified",
              "details": {
                "path": "/tmp/output.txt",
                "sha256": "abc123...",
                "size_bytes": 1024
              }
            },
            {
              "type": "command",
              "description": "Test suite passed",
              "verified": true,
              "verification_status": "verified",
              "details": {
                "command": "pytest tests/",
                "exit_code": 0,
                "stdout_preview": "All tests passed (10/10)",
                "duration_ms": 1250
              }
            }
          ],
          "summary": {
            "total": 2,
            "verified": 2,
            "failed": 0,
            "pending": 0
          },
          "created_at": "2026-01-30T10:30:00Z",
          "last_verified_at": "2026-01-30T10:30:05Z"
        }
    """
    try:
        # Initialize checkpoint manager
        manager = CheckpointManager(db_path=str(get_db_path()))

        # Get checkpoint
        checkpoint = manager.get_checkpoint(checkpoint_id)

        if not checkpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint not found: {checkpoint_id}"
            )

        # Build evidence items
        evidence_items = []
        evidence_pack = checkpoint.evidence_pack

        for evidence in evidence_pack.evidence_list:
            # Build type-specific details
            details = _build_evidence_details(evidence)

            evidence_items.append(EvidenceItemResponse(
                type=evidence.evidence_type if isinstance(evidence.evidence_type, str) else evidence.evidence_type.value,
                description=evidence.description or _get_default_description(evidence.evidence_type),
                verified=evidence.verified,
                verification_status=evidence.verification_status.value if hasattr(evidence.verification_status, 'value') else str(evidence.verification_status),
                verification_error=evidence.verification_error,
                verified_at=iso_z(evidence.verified_at) if evidence.verified_at else None,
                details=details
            ))

        # Determine overall status
        summary = evidence_pack.verification_summary()
        overall_status = _determine_overall_status(checkpoint, summary)

        return CheckpointEvidenceResponse(
            checkpoint_id=checkpoint.checkpoint_id,
            task_id=checkpoint.task_id,
            checkpoint_type=checkpoint.checkpoint_type,
            sequence_number=checkpoint.sequence_number,
            status=overall_status,
            items=evidence_items,
            summary=summary,
            created_at=iso_z(checkpoint.created_at) if checkpoint.created_at else iso_z(utc_now()),
            last_verified_at=iso_z(checkpoint.last_verified_at) if checkpoint.last_verified_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get checkpoint evidence: {str(e)}"
        )


def _build_evidence_details(evidence) -> Dict[str, Any]:
    """
    Build type-specific evidence details for display

    Args:
        evidence: Evidence object

    Returns:
        Dictionary with type-specific details
    """
    evidence_type_str = evidence.evidence_type
    if hasattr(evidence.evidence_type, 'value'):
        evidence_type_str = evidence.evidence_type.value

    expected = evidence.expected or {}
    metadata = evidence.metadata or {}

    if evidence_type_str == EvidenceType.ARTIFACT_EXISTS.value:
        return {
            "path": expected.get("path", ""),
            "type": expected.get("type", "any"),
            "exists": evidence.verified
        }

    elif evidence_type_str == EvidenceType.FILE_SHA256.value:
        return {
            "path": expected.get("path", ""),
            "sha256": expected.get("sha256", ""),
            "sha256_short": expected.get("sha256", "")[:16] + "..." if expected.get("sha256") else ""
        }

    elif evidence_type_str == EvidenceType.COMMAND_EXIT.value:
        return {
            "command": metadata.get("command", "Unknown command"),
            "exit_code": expected.get("exit_code", -1),
            "stdout_preview": _truncate_text(metadata.get("stdout", ""), 200),
            "stderr_preview": _truncate_text(metadata.get("stderr", ""), 200),
            "timeout": metadata.get("timeout")
        }

    elif evidence_type_str == EvidenceType.DB_ROW.value:
        return {
            "table": expected.get("table", ""),
            "where": expected.get("where", {}),
            "values": expected.get("values", {}),
            "db_path": metadata.get("db_path", "registry")  # Use registry_db.get_db() in verification
        }

    else:
        # Generic details for unknown types
        return {
            "expected": expected,
            "metadata": metadata
        }


def _get_default_description(evidence_type) -> str:
    """
    Get default description for evidence type

    Args:
        evidence_type: EvidenceType enum or string

    Returns:
        Human-readable description
    """
    evidence_type_str = evidence_type
    if hasattr(evidence_type, 'value'):
        evidence_type_str = evidence_type.value

    descriptions = {
        EvidenceType.ARTIFACT_EXISTS.value: "Artifact exists on filesystem",
        EvidenceType.FILE_SHA256.value: "File content hash verification",
        EvidenceType.COMMAND_EXIT.value: "Command execution verification",
        EvidenceType.DB_ROW.value: "Database row assertion"
    }

    return descriptions.get(evidence_type_str, "Evidence verification")


def _determine_overall_status(checkpoint, summary: Dict[str, Any]) -> str:
    """
    Determine overall checkpoint status from verification summary

    Args:
        checkpoint: Checkpoint object
        summary: Verification summary dict

    Returns:
        Status string: "verified", "invalid", or "pending"
    """
    if not checkpoint.verified and summary.get("verified", 0) == 0:
        return "pending"

    if checkpoint.verified and summary.get("failed", 0) == 0:
        return "verified"

    if summary.get("failed", 0) > 0:
        return "invalid"

    return "pending"


def _truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to max length with ellipsis

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length] + "..."


# ============================================
# Health Check
# ============================================

@router.get("/evidence/health")
async def evidence_health_check() -> Dict[str, str]:
    """
    Health check for evidence API

    Returns:
        Status message
    """
    return {
        "status": "ok",
        "service": "evidence_api",
        "version": "v0.32",
        "pr": "PR-V6"
    }
