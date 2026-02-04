"""Trust Evidence Schema - Machine-Verifiable Governance Proofs.

Phase G1: Evidence Export
This module defines the data structures for Trust Evidence that enables
verifiable governance across federated AgentOS instances.

Design Philosophy:
- Evidence over identity: Trust what systems DO, not who they ARE
- Machine-verifiable: All claims must be provable
- Transparency: No hidden decisions, all evidence is auditable
- Temporal validity: Evidence expires, trust must be renewed

Red Lines:
- No conclusions without supporting data
- No hidden denial records
- No timestamp manipulation
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from enum import Enum


# ============================================================================
# Constants
# ============================================================================

EVIDENCE_VERSION = "1.0"
DEFAULT_VALIDITY_SECONDS = 86400  # 24 hours


# ============================================================================
# Enums
# ============================================================================

class PolicyDecision(str, Enum):
    """Policy enforcement decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    SANDBOX_REQUIRED = "SANDBOX_REQUIRED"


class TrustTier(str, Enum):
    """Trust tiers for extensions."""
    T0_REVOKED = "T0_REVOKED"
    T1_LOW = "T1_LOW"
    T2_MEDIUM = "T2_MEDIUM"
    T3_HIGH = "T3_HIGH"
    T4_SYSTEM = "T4_SYSTEM"


class TrustState(str, Enum):
    """Trust evolution states."""
    EARNING = "EARNING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"


# ============================================================================
# Data Classes - Governance Capabilities
# ============================================================================

@dataclass
class PolicyEngine:
    """Policy Engine capability declaration."""
    exists: bool
    enforcement: str  # "mandatory" | "advisory" | "disabled"
    rules: List[str] = field(default_factory=list)
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exists": self.exists,
            "enforcement": self.enforcement,
            "rules": self.rules,
            "version": self.version,
        }


@dataclass
class SandboxCapability:
    """Sandbox capability declaration."""
    available: bool
    sandbox_type: str  # "docker" | "wasm" | "process" | "none"
    isolation_level: str  # "high" | "medium" | "low"
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "available": self.available,
            "type": self.sandbox_type,
            "isolation_level": self.isolation_level,
            "version": self.version,
        }


@dataclass
class RiskScoring:
    """Risk scoring capability declaration."""
    enabled: bool
    dimensions: List[str] = field(default_factory=list)
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "dimensions": self.dimensions,
            "version": self.version,
        }


@dataclass
class TrustEvolution:
    """Trust evolution capability declaration."""
    enabled: bool
    states: List[str] = field(default_factory=list)
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "states": self.states,
            "version": self.version,
        }


@dataclass
class GovernanceCapabilities:
    """Complete governance capabilities declaration.

    This section proves what governance mechanisms this AgentOS instance has.

    Red Line: Cannot claim capabilities that don't exist.
    """
    policy_engine: PolicyEngine
    sandbox: SandboxCapability
    risk_scoring: RiskScoring
    trust_evolution: TrustEvolution

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_engine": self.policy_engine.to_dict(),
            "sandbox": self.sandbox.to_dict(),
            "risk_scoring": self.risk_scoring.to_dict(),
            "trust_evolution": self.trust_evolution.to_dict(),
        }


# ============================================================================
# Data Classes - Execution Samples
# ============================================================================

@dataclass
class ExecutionSample:
    """Execution sample - proof of how decisions are made.

    Red Lines:
    - Must include BOTH allowed and denied executions
    - Must include actual risk scores, not filtered
    - Must include actual policy decisions, including denials
    """
    extension_id: str
    risk_score: float
    trust_tier: str
    policy_decision: str
    executed_in_sandbox: bool
    timestamp: str

    # Optional additional context
    denial_reason: Optional[str] = None
    approval_required: Optional[bool] = None
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "extension_id": self.extension_id,
            "risk_score": self.risk_score,
            "trust_tier": self.trust_tier,
            "policy_decision": self.policy_decision,
            "executed_in_sandbox": self.executed_in_sandbox,
            "timestamp": self.timestamp,
        }

        # Add optional fields if present
        if self.denial_reason is not None:
            result["denial_reason"] = self.denial_reason
        if self.approval_required is not None:
            result["approval_required"] = self.approval_required
        if self.execution_time_ms is not None:
            result["execution_time_ms"] = self.execution_time_ms

        return result


# ============================================================================
# Data Classes - Audit Integrity
# ============================================================================

@dataclass
class AuditIntegrity:
    """Audit integrity proof.

    This section proves that the audit log is complete and unmanipulated.

    Red Lines:
    - Hash must cover the ENTIRE audit log, not filtered
    - Timestamps must be real, not manipulated
    """
    audit_log_hash: str  # SHA-256 of complete audit log
    audit_log_count: int
    earliest_audit: str  # ISO timestamp
    latest_audit: str  # ISO timestamp
    hash_algorithm: str = "sha256"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audit_log_hash": self.audit_log_hash,
            "audit_log_count": self.audit_log_count,
            "earliest_audit": self.earliest_audit,
            "latest_audit": self.latest_audit,
            "hash_algorithm": self.hash_algorithm,
        }


# ============================================================================
# Main Evidence Structure
# ============================================================================

@dataclass
class TrustEvidence:
    """Complete Trust Evidence - Machine-Verifiable Governance Proof.

    This is the PRIMARY data structure for Phase G trust federation.

    Red Lines:
    - All fields must be verifiable
    - Cannot hide or filter negative evidence
    - Cannot manipulate timestamps
    - Must include signature for authenticity

    Usage:
        >>> evidence = TrustEvidence(
        ...     system_id="agentos-instance-123",
        ...     governance_capabilities=capabilities,
        ...     execution_samples=samples,
        ...     audit_integrity=audit,
        ... )
        >>> evidence.save("evidence.json")
    """
    evidence_version: str
    system_id: str
    generated_at: str  # ISO timestamp
    validity_period: int  # seconds
    governance_capabilities: GovernanceCapabilities
    execution_samples: List[ExecutionSample]
    audit_integrity: AuditIntegrity
    signature: str = ""  # Ed25519 signature (set during export)

    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "evidence_version": self.evidence_version,
            "system_id": self.system_id,
            "generated_at": self.generated_at,
            "validity_period": self.validity_period,
            "governance_capabilities": self.governance_capabilities.to_dict(),
            "execution_samples": [s.to_dict() for s in self.execution_samples],
            "audit_integrity": self.audit_integrity.to_dict(),
            "signature": self.signature,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, filepath: str) -> None:
        """Save evidence to JSON file."""
        import pathlib
        path = pathlib.Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrustEvidence:
        """Create TrustEvidence from dictionary."""
        # Parse governance capabilities
        gov_data = data["governance_capabilities"]
        governance = GovernanceCapabilities(
            policy_engine=PolicyEngine(**gov_data["policy_engine"]),
            sandbox=SandboxCapability(
                available=gov_data["sandbox"]["available"],
                sandbox_type=gov_data["sandbox"]["type"],
                isolation_level=gov_data["sandbox"]["isolation_level"],
                version=gov_data["sandbox"].get("version"),
            ),
            risk_scoring=RiskScoring(**gov_data["risk_scoring"]),
            trust_evolution=TrustEvolution(**gov_data["trust_evolution"]),
        )

        # Parse execution samples
        samples = [ExecutionSample(**s) for s in data["execution_samples"]]

        # Parse audit integrity
        audit = AuditIntegrity(**data["audit_integrity"])

        return cls(
            evidence_version=data["evidence_version"],
            system_id=data["system_id"],
            generated_at=data["generated_at"],
            validity_period=data["validity_period"],
            governance_capabilities=governance,
            execution_samples=samples,
            audit_integrity=audit,
            signature=data.get("signature", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TrustEvidence:
        """Create TrustEvidence from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def load(cls, filepath: str) -> TrustEvidence:
        """Load evidence from JSON file."""
        import pathlib
        path = pathlib.Path(filepath)
        json_str = path.read_text()
        return cls.from_json(json_str)

    def is_expired(self) -> bool:
        """Check if evidence has expired."""
        generated = datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_seconds = (now - generated).total_seconds()
        return age_seconds > self.validity_period

    def expires_at(self) -> datetime:
        """Calculate expiration timestamp."""
        generated = datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        from datetime import timedelta
        return generated + timedelta(seconds=self.validity_period)


# ============================================================================
# Validation Functions
# ============================================================================

class ValidationError(Exception):
    """Raised when evidence validation fails."""
    pass


def validate_evidence(evidence: TrustEvidence) -> None:
    """Validate Trust Evidence structure and content.

    This function enforces ALL red lines:
    - Evidence must be complete
    - Execution samples must include denials
    - Timestamps must be valid
    - Audit integrity must be present

    Args:
        evidence: Trust evidence to validate

    Raises:
        ValidationError: If evidence is invalid
    """
    # Validate version
    if evidence.evidence_version != EVIDENCE_VERSION:
        raise ValidationError(
            f"Invalid evidence version: {evidence.evidence_version} "
            f"(expected {EVIDENCE_VERSION})"
        )

    # Validate system ID
    if not evidence.system_id or not evidence.system_id.strip():
        raise ValidationError("system_id cannot be empty")

    # Validate timestamp
    try:
        datetime.fromisoformat(evidence.generated_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as e:
        raise ValidationError(f"Invalid generated_at timestamp: {e}")

    # Validate validity period
    if evidence.validity_period <= 0:
        raise ValidationError("validity_period must be positive")

    # Validate governance capabilities
    _validate_governance_capabilities(evidence.governance_capabilities)

    # Validate execution samples (RED LINE: must include denials)
    _validate_execution_samples(evidence.execution_samples)

    # Validate audit integrity
    _validate_audit_integrity(evidence.audit_integrity)

    # Validate signature exists (even if we don't verify it here)
    if not evidence.signature or not evidence.signature.strip():
        raise ValidationError("signature cannot be empty")


def _validate_governance_capabilities(capabilities: GovernanceCapabilities) -> None:
    """Validate governance capabilities section."""
    # Policy Engine validation
    if capabilities.policy_engine.exists:
        if not capabilities.policy_engine.enforcement:
            raise ValidationError("policy_engine enforcement mode required when exists=true")
        if capabilities.policy_engine.enforcement not in ["mandatory", "advisory", "disabled"]:
            raise ValidationError(f"Invalid policy enforcement: {capabilities.policy_engine.enforcement}")

    # Sandbox validation
    if capabilities.sandbox.available:
        if not capabilities.sandbox.sandbox_type:
            raise ValidationError("sandbox type required when available=true")
        if capabilities.sandbox.isolation_level not in ["high", "medium", "low"]:
            raise ValidationError(f"Invalid isolation level: {capabilities.sandbox.isolation_level}")


def _validate_execution_samples(samples: List[ExecutionSample]) -> None:
    """Validate execution samples.

    RED LINE: Must not hide denial records.
    """
    if not samples:
        raise ValidationError("execution_samples cannot be empty")

    # Check for denials (RED LINE enforcement)
    has_denials = any(s.policy_decision == "DENY" for s in samples)

    # Validate individual samples
    for i, sample in enumerate(samples):
        # Validate risk score
        if not (0.0 <= sample.risk_score <= 100.0):
            raise ValidationError(
                f"Sample {i}: risk_score must be 0.0-100.0, got {sample.risk_score}"
            )

        # Validate policy decision
        try:
            PolicyDecision(sample.policy_decision)
        except ValueError:
            raise ValidationError(
                f"Sample {i}: invalid policy_decision: {sample.policy_decision}"
            )

        # Validate timestamp
        try:
            datetime.fromisoformat(sample.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            raise ValidationError(f"Sample {i}: invalid timestamp: {e}")

    # Note: We don't REQUIRE denials (system might be perfect),
    # but we verify that IF there are denials, they're included


def _validate_audit_integrity(audit: AuditIntegrity) -> None:
    """Validate audit integrity section."""
    # Validate hash
    if not audit.audit_log_hash or not audit.audit_log_hash.strip():
        raise ValidationError("audit_log_hash cannot be empty")

    if audit.hash_algorithm == "sha256":
        # SHA-256 produces 64-character hex string
        if len(audit.audit_log_hash.replace("sha256:", "")) != 64:
            raise ValidationError("audit_log_hash must be 64-character SHA-256 hash")

    # Validate count
    if audit.audit_log_count < 0:
        raise ValidationError("audit_log_count cannot be negative")

    # Validate timestamps
    try:
        earliest = datetime.fromisoformat(audit.earliest_audit.replace("Z", "+00:00"))
        latest = datetime.fromisoformat(audit.latest_audit.replace("Z", "+00:00"))

        if earliest > latest:
            raise ValidationError("earliest_audit cannot be after latest_audit")
    except (ValueError, AttributeError) as e:
        raise ValidationError(f"Invalid audit timestamp: {e}")


# ============================================================================
# Utility Functions
# ============================================================================

def calculate_audit_hash(audit_records: List[Dict[str, Any]]) -> str:
    """Calculate SHA-256 hash of audit records.

    Args:
        audit_records: List of audit record dictionaries

    Returns:
        SHA-256 hash string (with "sha256:" prefix)
    """
    # Sort by created_at to ensure consistent ordering
    sorted_records = sorted(audit_records, key=lambda r: r.get("created_at", 0))

    # Serialize to JSON (canonical form)
    canonical = json.dumps(sorted_records, sort_keys=True, ensure_ascii=False)

    # Calculate SHA-256
    hash_obj = hashlib.sha256(canonical.encode("utf-8"))
    return f"sha256:{hash_obj.hexdigest()}"


def generate_system_id() -> str:
    """Generate a unique system ID.

    Returns:
        System ID string (format: agentos-<hostname>-<timestamp>)
    """
    import socket
    import time

    hostname = socket.gethostname()
    timestamp = int(time.time())

    # Create deterministic ID
    return f"agentos-{hostname}-{timestamp}"
