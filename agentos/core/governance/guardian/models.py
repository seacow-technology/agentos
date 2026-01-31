"""
Guardian Data Models

Defines the core data structures for Guardian assignments and verdicts.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal
from datetime import datetime, timezone
import uuid
from agentos.core.time import utc_now_iso


# VerdictStatus type definition
VerdictStatus = Literal["PASS", "FAIL", "NEEDS_CHANGES"]


@dataclass(frozen=True)
class GuardianAssignment:
    """
    Guardian Assignment Record

    Represents the assignment of a Guardian to verify a task.
    Immutable once created (frozen=True).
    """

    assignment_id: str
    task_id: str
    guardian_code: str
    created_at: str
    reason: Dict[str, Any]

    @classmethod
    def create(
        cls,
        task_id: str,
        guardian_code: str,
        reason: Dict[str, Any],
    ) -> "GuardianAssignment":
        """
        Create a new Guardian assignment

        Args:
            task_id: Task to verify
            guardian_code: Guardian identifier
            reason: Assignment reason (e.g., findings that triggered it)

        Returns:
            New GuardianAssignment instance
        """
        return cls(
            assignment_id=f"assignment_{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            guardian_code=guardian_code,
            created_at=utc_now_iso(),
            reason=reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "guardian_code": self.guardian_code,
            "created_at": self.created_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GuardianVerdictSnapshot:
    """
    Guardian Verdict Snapshot

    Immutable record of a Guardian's verification result.
    This is the governance contract - once written, it's a fact.
    """

    verdict_id: str
    assignment_id: str
    task_id: str
    guardian_code: str
    status: VerdictStatus
    flags: List[Dict[str, Any]]
    evidence: Dict[str, Any]
    recommendations: List[str]
    created_at: str

    @classmethod
    def create(
        cls,
        assignment_id: str,
        task_id: str,
        guardian_code: str,
        status: VerdictStatus,
        flags: List[Dict[str, Any]],
        evidence: Dict[str, Any],
        recommendations: List[str],
    ) -> "GuardianVerdictSnapshot":
        """
        Create a new Guardian verdict

        Args:
            assignment_id: Related assignment ID
            task_id: Task being verified
            guardian_code: Guardian that produced this verdict
            status: PASS | FAIL | NEEDS_CHANGES
            flags: List of issues/concerns found
            evidence: Evidence data (test results, logs, etc.)
            recommendations: Suggested actions

        Returns:
            New GuardianVerdictSnapshot instance
        """
        return cls(
            verdict_id=f"verdict_{uuid.uuid4().hex[:12]}",
            assignment_id=assignment_id,
            task_id=task_id,
            guardian_code=guardian_code,
            status=status,
            flags=flags,
            evidence=evidence,
            recommendations=recommendations,
            created_at=utc_now_iso(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "verdict_id": self.verdict_id,
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "guardian_code": self.guardian_code,
            "status": self.status,
            "flags": self.flags,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


def validate_verdict_snapshot(obj: Dict[str, Any]) -> None:
    """
    Validate verdict snapshot schema

    Raises ValueError if the verdict doesn't conform to the expected schema.

    Args:
        obj: Dictionary to validate

    Raises:
        ValueError: If validation fails
    """
    required_fields = [
        "verdict_id",
        "assignment_id",
        "task_id",
        "guardian_code",
        "status",
        "flags",
        "evidence",
        "recommendations",
        "created_at",
    ]

    # Check required fields
    for field in required_fields:
        if field not in obj:
            raise ValueError(f"Missing required field: {field}")

    # Validate status
    valid_statuses = ["PASS", "FAIL", "NEEDS_CHANGES"]
    if obj["status"] not in valid_statuses:
        raise ValueError(
            f"Invalid status: {obj['status']}. Must be one of {valid_statuses}"
        )

    # Validate types
    if not isinstance(obj["flags"], list):
        raise ValueError("flags must be a list")
    if not isinstance(obj["evidence"], dict):
        raise ValueError("evidence must be a dict")
    if not isinstance(obj["recommendations"], list):
        raise ValueError("recommendations must be a list")
