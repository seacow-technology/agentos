"""Checkpoint models and types."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List


class CheckpointType(Enum):
    """Types of checkpoints."""
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    ARTIFACT_SAVED = "artifact_saved"
    STATE_SNAPSHOT = "state_snapshot"


class EvidenceType(Enum):
    """Types of evidence."""
    ARTIFACT_EXISTS = "artifact_exists"
    FILE_SHA256 = "file_sha256"
    COMMAND_EXIT = "command_exit"
    DB_ROW = "db_row"


class VerificationStatus(Enum):
    """Verification status."""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class Evidence:
    """Evidence for checkpoint verification.

    Evidence provides proof that a checkpoint is valid and can be restored.
    """

    evidence_type: str  # e.g., "artifact_exists", "command_exit", "file_hash"
    description: str = ""
    expected: Dict[str, Any] = field(default_factory=dict)
    payload: Optional[Dict[str, Any]] = None  # For backward compatibility
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata (e.g., db_path)

    # Verification results
    verified: bool = False
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verification_error: Optional[str] = None
    verified_at: Optional[datetime] = None

    def __post_init__(self):
        # Backward compatibility: if payload is provided, use it as expected
        if self.payload is not None and not self.expected:
            self.expected = self.payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        # Convert evidence_type to string if it's an enum
        evidence_type_str = self.evidence_type
        if isinstance(self.evidence_type, Enum):
            evidence_type_str = self.evidence_type.value

        return {
            "evidence_type": evidence_type_str,
            "description": self.description,
            "expected": self.expected,
            "metadata": self.metadata,
            "verified": self.verified,
            "verification_status": self.verification_status.value if isinstance(self.verification_status, Enum) else self.verification_status,
            "verification_error": self.verification_error,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        """Create from dictionary."""
        # Handle backward compatibility
        payload = data.get("payload", data.get("expected", {}))

        # Convert evidence_type string to enum if needed
        evidence_type = data["evidence_type"]
        if isinstance(evidence_type, str):
            try:
                evidence_type = EvidenceType(evidence_type)
            except ValueError:
                # Keep as string if not a valid enum value
                pass

        return cls(
            evidence_type=evidence_type,
            description=data.get("description", ""),
            expected=data.get("expected", payload),
            metadata=data.get("metadata", {}),
            verified=data.get("verified", False),
            verification_status=VerificationStatus(data["verification_status"]) if "verification_status" in data else VerificationStatus.PENDING,
            verification_error=data.get("verification_error"),
            verified_at=datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None
        )


@dataclass
class EvidencePack:
    """Collection of evidence for checkpoint verification."""

    evidence_list: List[Evidence] = field(default_factory=list)
    require_all: bool = True  # All evidence must pass
    allow_partial: bool = False  # Allow partial verification
    min_verified: int = 0  # Minimum number of evidence that must pass

    def add_evidence(self, evidence: Evidence):
        """Add evidence to the pack."""
        self.evidence_list.append(evidence)

    def is_verified(self) -> bool:
        """Check if evidence pack verification passed.

        Returns True if:
        - require_all=True: All evidence verified
        - allow_partial=True and min_verified met: At least min_verified evidence passed
        """
        verified_count = sum(1 for e in self.evidence_list if e.verified)

        if self.require_all:
            return all(e.verified for e in self.evidence_list)
        elif self.allow_partial:
            return verified_count >= self.min_verified
        else:
            return all(e.verified for e in self.evidence_list)

    def verification_summary(self) -> Dict[str, Any]:
        """Get verification summary statistics.

        Returns:
            Dictionary with counts: total, verified, failed, pending
        """
        total = len(self.evidence_list)
        verified = sum(1 for e in self.evidence_list if e.verification_status == VerificationStatus.VERIFIED)
        failed = sum(1 for e in self.evidence_list if e.verification_status == VerificationStatus.FAILED)
        pending = sum(1 for e in self.evidence_list if e.verification_status == VerificationStatus.PENDING)

        return {
            "total": total,
            "verified": verified,
            "failed": failed,
            "pending": pending
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evidence_list": [e.to_dict() for e in self.evidence_list],
            "require_all": self.require_all,
            "allow_partial": self.allow_partial,
            "min_verified": self.min_verified
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidencePack":
        """Create from dictionary."""
        evidence_list = [Evidence.from_dict(e) for e in data.get("evidence_list", [])]
        return cls(
            evidence_list=evidence_list,
            require_all=data.get("require_all", True),
            allow_partial=data.get("allow_partial", False),
            min_verified=data.get("min_verified", 0)
        )


@dataclass
class Checkpoint:
    """Checkpoint for task recovery."""

    checkpoint_id: str
    task_id: str
    checkpoint_type: str
    sequence_number: int
    snapshot_data: Dict[str, Any]

    # Optional fields
    work_item_id: Optional[str] = None
    evidence_pack: EvidencePack = field(default_factory=EvidencePack)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    # Verification
    verified: bool = False
    last_verified_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "work_item_id": self.work_item_id,
            "checkpoint_type": self.checkpoint_type,
            "sequence_number": self.sequence_number,
            "snapshot_data": self.snapshot_data,
            "evidence_pack": self.evidence_pack.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified": self.verified,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None
        }
