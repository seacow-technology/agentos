"""
Verification Result Data Structures for Federation Verification.

Phase G2 - Federation Verification
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timezone


class VerificationStatus(Enum):
    """Verification status for remote trust evidence."""

    ACCEPT = "ACCEPT"  # All verification dimensions passed
    LIMITED_TRUST = "LIMITED_TRUST"  # Partial verification passed
    REJECT = "REJECT"  # Critical verification dimensions failed


@dataclass
class DimensionResult:
    """Result of a single verification dimension."""

    dimension: str
    passed: bool
    reason: str
    score: float = 0.0  # 0-100
    details: Optional[Dict] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "dimension": self.dimension,
            "passed": self.passed,
            "reason": self.reason,
            "score": self.score,
            "details": self.details or {}
        }


@dataclass
class VerificationResult:
    """Complete verification result for remote trust evidence."""

    status: VerificationStatus
    dimensions: Dict[str, DimensionResult]
    recommended_initial_trust: int  # 0-100
    overall_score: float  # 0-100
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str = ""
    evidence_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "dimensions": {
                name: result.to_dict()
                for name, result in self.dimensions.items()
            },
            "recommended_initial_trust": self.recommended_initial_trust,
            "overall_score": self.overall_score,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "evidence_id": self.evidence_id
        }

    def is_accept(self) -> bool:
        """Check if verification is accepted."""
        return self.status == VerificationStatus.ACCEPT

    def is_reject(self) -> bool:
        """Check if verification is rejected."""
        return self.status == VerificationStatus.REJECT

    def is_limited_trust(self) -> bool:
        """Check if verification is limited trust."""
        return self.status == VerificationStatus.LIMITED_TRUST

    def get_failed_dimensions(self) -> Dict[str, DimensionResult]:
        """Get all failed verification dimensions."""
        return {
            name: result
            for name, result in self.dimensions.items()
            if not result.passed
        }

    def get_passed_dimensions(self) -> Dict[str, DimensionResult]:
        """Get all passed verification dimensions."""
        return {
            name: result
            for name, result in self.dimensions.items()
            if result.passed
        }
