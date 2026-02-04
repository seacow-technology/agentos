"""
Federation Trust System

Cross-system trust federation for AgentOS (Phase G).

Modules:
- evidence_schema: Trust evidence data structures (Phase G1)
- evidence_export: Trust evidence exporter (Phase G1)
- verification: Federation verification engine (Phase G2)
- verification_result: Verification result data structures (Phase G2)
- mapping_rules: Trust mapping rules and constraints (Phase G3)
- trust_mapping: Trust mapper for remote trust translation (Phase G3)
- lifecycle: Federated trust lifecycle management (Phase G4)

Phase G Components:
- G1: Trust Evidence Export (evidence_schema.py, evidence_export.py)
- G2: Federation Verification (verification.py, verification_result.py)
- G3: Trust Mapping (trust_mapping.py)
- G4: Federated Trust Lifecycle (lifecycle.py)
"""

from .evidence_schema import (
    TrustEvidence,
    GovernanceCapabilities,
    PolicyEngine,
    SandboxCapability,
    RiskScoring,
    TrustEvolution,
    ExecutionSample,
    AuditIntegrity,
    validate_evidence,
    ValidationError,
)

from .evidence_export import TrustEvidenceExporter

from .mapping_rules import (
    MappingRule,
    StateMapping,
    TierMapping,
    SandboxConstraint
)

from .trust_mapping import (
    TrustMapper,
    RemoteTrustEvidence,
    MappingResult
)

from .verification import FederationVerifier
from .verification_result import (
    VerificationResult,
    VerificationStatus,
    DimensionResult
)

from .lifecycle import (
    FederatedTrust,
    TrustLifecycle,
    TrustLevel,
    TrustStatus,
    FederatedTrustError,
    TrustExpiredError,
    TrustRevokedError,
    TrustNotFoundError,
    establish_trust,
    renew_trust,
    revoke_trust,
    downgrade_trust,
    check_expiration,
)

__all__ = [
    # Evidence Schema (G1)
    "TrustEvidence",
    "GovernanceCapabilities",
    "PolicyEngine",
    "SandboxCapability",
    "RiskScoring",
    "TrustEvolution",
    "ExecutionSample",
    "AuditIntegrity",
    "validate_evidence",
    "ValidationError",
    # Evidence Export (G1)
    "TrustEvidenceExporter",
    # Verification (G2)
    "FederationVerifier",
    "VerificationResult",
    "VerificationStatus",
    "DimensionResult",
    # Rules (G3)
    "MappingRule",
    "StateMapping",
    "TierMapping",
    "SandboxConstraint",
    # Mapper (G3)
    "TrustMapper",
    "RemoteTrustEvidence",
    "MappingResult",
    # Lifecycle (G4)
    "FederatedTrust",
    "TrustLifecycle",
    "TrustLevel",
    "TrustStatus",
    "FederatedTrustError",
    "TrustExpiredError",
    "TrustRevokedError",
    "TrustNotFoundError",
    "establish_trust",
    "renew_trust",
    "revoke_trust",
    "downgrade_trust",
    "check_expiration",
]
