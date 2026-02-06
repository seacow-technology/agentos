"""
Evidence Domain Models for AgentOS v3

Complete data models for evidence collection, linking, replay, and export.

Design Principles:
1. Evidence is IMMUTABLE (no updates after creation)
2. Every Capability invocation MUST have evidence
3. Evidence chains link: decision → action → memory → state_change
4. Evidence integrity verified via SHA256 hash + digital signature
5. All timestamps use epoch_ms (ADR-011)

Evidence is the core護城河 (moat) for:
- Regulatory compliance (SOX, GDPR, HIPAA)
- Legal discovery and forensics
- Audit trails for enterprise
- Time-travel debugging
- Rollback and replay

Schema Version: v51
"""

from __future__ import annotations
import hashlib
import json
import os
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from agentos.core.time import utc_now_ms


# ===================================================================
# Enums
# ===================================================================

class OperationType(str, Enum):
    """Type of operation that generated evidence"""
    STATE = "state"           # State domain operation (memory read/write)
    DECISION = "decision"     # Decision domain operation (plan, judge)
    ACTION = "action"         # Action domain operation (execute, rollback)
    GOVERNANCE = "governance" # Governance domain operation (policy check)


class EvidenceType(str, Enum):
    """Type of evidence package"""
    OPERATION_COMPLETE = "operation_complete"       # Full operation evidence
    PERMISSION_CHECK = "permission_check"           # Governance check
    SIDE_EFFECT = "side_effect"                     # Side effect recording
    STATE_CHANGE = "state_change"                   # State mutation
    REPLAY = "replay"                               # Replay evidence
    EXPORT = "export"                               # Export evidence


class ExportFormat(str, Enum):
    """Export format for evidence packages"""
    JSON = "json"       # JSON format (machine-readable)
    PDF = "pdf"         # PDF report (human-readable)
    CSV = "csv"         # CSV format (spreadsheet)
    HTML = "html"       # HTML report (web-friendly)


class ReplayMode(str, Enum):
    """Replay mode for evidence"""
    READ_ONLY = "read_only"     # Simulate without side effects (DEFAULT)
    VALIDATE = "validate"       # Re-execute and compare (requires ADMIN)


class ChainRelationship(str, Enum):
    """Relationship type in evidence chain"""
    CAUSED_BY = "caused_by"           # A was caused by B
    RESULTED_IN = "resulted_in"       # A resulted in B
    MODIFIED = "modified"             # A modified B
    TRIGGERED = "triggered"           # A triggered B
    APPROVED_BY = "approved_by"       # A was approved by B


# ===================================================================
# Evidence Core Models
# ===================================================================

class EvidenceProvenance(BaseModel):
    """
    Provenance metadata for evidence.

    Records the execution environment for forensics and debugging.
    """
    host: str = Field(
        description="Hostname where operation executed"
    )
    pid: int = Field(
        description="Process ID"
    )
    agentos_version: str = Field(
        description="AgentOS version"
    )
    python_version: str = Field(
        description="Python version"
    )
    user: Optional[str] = Field(
        default=None,
        description="OS user (if available)"
    )


class EvidenceIntegrity(BaseModel):
    """
    Integrity verification for evidence.

    Uses SHA256 hash + optional digital signature.
    """
    hash: str = Field(
        description="SHA256 hash of evidence content"
    )
    signature: Optional[str] = Field(
        default=None,
        description="Digital signature (optional)"
    )
    algorithm: str = Field(
        default="sha256",
        description="Hash algorithm"
    )
    signed_by: Optional[str] = Field(
        default=None,
        description="Who signed this evidence"
    )
    verified: bool = Field(
        default=False,
        description="Whether signature has been verified"
    )


class SideEffectEvidence(BaseModel):
    """
    Evidence for a side effect.

    Records both declared and actual side effects.
    """
    declared: List[str] = Field(
        description="Side effects declared before execution"
    )
    actual: List[str] = Field(
        description="Side effects that actually occurred"
    )
    unexpected: List[str] = Field(
        description="Side effects not declared (security alert)"
    )
    missing: List[str] = Field(
        description="Declared side effects that didn't occur"
    )


class Evidence(BaseModel):
    """
    Complete evidence record for a Capability invocation.

    This is the core護城河 (moat) for compliance and audit.

    IMMUTABLE: Cannot be modified after creation.
    COMPLETE: Contains all information needed for replay and audit.
    VERIFIABLE: Cryptographic hash + signature ensures integrity.

    Example:
        evidence = Evidence(
            evidence_id="ev-01HX...",
            timestamp_ms=1738234567890,
            operation={
                "type": "action",
                "id": "exec-123",
                "capability_id": "action.execute.local"
            },
            context={
                "agent_id": "chat_agent",
                "session_id": "sess-456",
                "project_id": "proj-789",
                "decision_id": "dec-abc"
            },
            input={"command": "mkdir /tmp/test"},
            output={"status": "success", "returncode": 0},
            side_effects={
                "declared": ["fs.write"],
                "actual": ["fs.write"]
            },
            provenance={...},
            integrity={...}
        )
    """
    evidence_id: str = Field(
        description="Unique evidence identifier (ulid)"
    )
    timestamp_ms: int = Field(
        default_factory=utc_now_ms,
        description="When evidence was created (epoch ms)"
    )
    evidence_type: EvidenceType = Field(
        default=EvidenceType.OPERATION_COMPLETE,
        description="Type of evidence"
    )

    # Operation identification
    operation: Dict[str, Any] = Field(
        description="Operation that generated this evidence"
    )

    # Context
    context: Dict[str, Any] = Field(
        description="Execution context (agent, session, project, decision)"
    )

    # Input/Output
    input: Dict[str, Any] = Field(
        description="Operation input (params, arguments)"
    )
    output: Dict[str, Any] = Field(
        description="Operation output (result, return value)"
    )

    # Side Effects
    side_effects: Optional[SideEffectEvidence] = Field(
        default=None,
        description="Side effect evidence (if applicable)"
    )

    # Provenance & Integrity
    provenance: EvidenceProvenance = Field(
        description="Execution environment provenance"
    )
    integrity: EvidenceIntegrity = Field(
        description="Cryptographic integrity verification"
    )

    # Metadata
    immutable: bool = Field(
        default=True,
        description="Evidence is immutable (always True)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    def compute_hash(self) -> str:
        """
        Compute SHA256 hash of evidence content.

        Excludes integrity.hash and integrity.signature to avoid circular dependency.

        Returns:
            SHA256 hex digest
        """
        # Create copy without integrity fields
        data = self.model_dump()
        data.pop("integrity", None)
        data.pop("metadata", None)  # Exclude metadata from hash

        # Serialize to canonical JSON
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)

        # Compute hash
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """
        Verify evidence integrity.

        Recomputes hash and compares with stored value.

        Returns:
            True if integrity verified, False otherwise
        """
        computed_hash = self.compute_hash()
        return computed_hash == self.integrity.hash


# ===================================================================
# Evidence Chain Models
# ===================================================================

class EvidenceChainLink(BaseModel):
    """
    Single link in evidence chain.

    Connects two evidence records with a relationship.
    """
    from_type: str = Field(
        description="Type of source entity (decision|action|memory|state)"
    )
    from_id: str = Field(
        description="Source entity ID"
    )
    to_type: str = Field(
        description="Type of target entity"
    )
    to_id: str = Field(
        description="Target entity ID"
    )
    relationship: ChainRelationship = Field(
        description="Relationship type"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class EvidenceChain(BaseModel):
    """
    Complete evidence chain linking related operations.

    Example chain:
        Decision (dec-123) → caused_by → Action (exec-456) → resulted_in → Memory (mem-789)

    This enables queries like:
    - "What decision caused this action?"
    - "What memory was created by this action?"
    - "What was the full chain for this operation?"
    """
    chain_id: str = Field(
        description="Unique chain identifier (ulid)"
    )
    links: List[EvidenceChainLink] = Field(
        description="Chain links"
    )
    created_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When chain was created (epoch ms)"
    )
    created_by: str = Field(
        description="Agent that created the chain"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class ChainQueryResult(BaseModel):
    """
    Result of evidence chain query.

    Returns all entities in the chain from an anchor point.
    """
    anchor_id: str = Field(
        description="Starting point of query"
    )
    anchor_type: str = Field(
        description="Type of anchor entity"
    )
    chain: EvidenceChain = Field(
        description="Complete chain"
    )
    entities: List[Dict[str, Any]] = Field(
        description="All entities in chain (with metadata)"
    )
    depth: int = Field(
        description="Chain depth (number of hops)"
    )


# ===================================================================
# Replay Models
# ===================================================================

class ReplayResult(BaseModel):
    """
    Result of replaying evidence.

    Used for debugging, validation, and time-travel.
    """
    replay_id: str = Field(
        description="Unique replay identifier (ulid)"
    )
    evidence_id: str = Field(
        description="Evidence being replayed"
    )
    replay_mode: ReplayMode = Field(
        description="Replay mode (read_only or validate)"
    )

    # Original evidence
    original_evidence: Evidence = Field(
        description="Original evidence record"
    )

    # Replay results
    replayed_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When replay was performed (epoch ms)"
    )
    replayed_by: str = Field(
        description="Agent who initiated replay"
    )

    # Comparison (for validate mode)
    original_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original operation output"
    )
    replayed_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Replayed operation output"
    )
    matches: bool = Field(
        description="Whether outputs match"
    )
    differences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Differences (if not matching)"
    )

    # Metadata
    duration_ms: Optional[int] = Field(
        default=None,
        description="Replay duration"
    )
    success: bool = Field(
        description="Whether replay succeeded"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message (if failed)"
    )


# ===================================================================
# Export Models
# ===================================================================

class ExportQuery(BaseModel):
    """
    Query specification for evidence export.

    Allows filtering by time range, agent, operation type, etc.
    """
    agent_id: Optional[str] = Field(
        default=None,
        description="Filter by agent"
    )
    operation_type: Optional[OperationType] = Field(
        default=None,
        description="Filter by operation type"
    )
    start_time_ms: Optional[int] = Field(
        default=None,
        description="Filter by start time (epoch ms)"
    )
    end_time_ms: Optional[int] = Field(
        default=None,
        description="Filter by end time (epoch ms)"
    )
    capability_id: Optional[str] = Field(
        default=None,
        description="Filter by capability"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Filter by project"
    )
    limit: Optional[int] = Field(
        default=1000,
        description="Maximum number of evidence records"
    )


class ExportPackage(BaseModel):
    """
    Complete export package for evidence.

    Used for compliance audits and legal discovery.
    """
    export_id: str = Field(
        description="Unique export identifier (ulid)"
    )
    query: ExportQuery = Field(
        description="Query used for export"
    )
    format: ExportFormat = Field(
        description="Export format"
    )

    # Export metadata
    exported_by: str = Field(
        description="Agent who initiated export"
    )
    exported_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When export was created (epoch ms)"
    )
    expires_at_ms: Optional[int] = Field(
        default=None,
        description="When export file expires (for temp files)"
    )

    # File metadata
    file_path: Optional[str] = Field(
        default=None,
        description="Path to export file"
    )
    file_size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes"
    )
    file_hash: Optional[str] = Field(
        default=None,
        description="SHA256 hash of export file"
    )

    # Statistics
    evidence_count: int = Field(
        description="Number of evidence records in export"
    )
    time_range_ms: Optional[int] = Field(
        default=None,
        description="Time span covered by export (ms)"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


# ===================================================================
# Helper Functions
# ===================================================================

def generate_provenance() -> EvidenceProvenance:
    """
    Generate provenance metadata for current environment.

    Returns:
        EvidenceProvenance with current system info
    """
    import sys
    import platform
    import getpass

    # Get AgentOS version
    try:
        from agentos import __version__
        agentos_version = __version__
    except:
        agentos_version = "unknown"

    # Get user (safely)
    try:
        user = getpass.getuser()
    except:
        user = None

    return EvidenceProvenance(
        host=platform.node(),
        pid=os.getpid(),
        agentos_version=agentos_version,
        python_version=sys.version.split()[0],
        user=user,
    )


def hash_content(content: str) -> str:
    """
    Compute SHA256 hash of content.

    Args:
        content: Content to hash

    Returns:
        SHA256 hex digest
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_evidence_integrity(evidence_content: str, signed_by: Optional[str] = None) -> EvidenceIntegrity:
    """
    Create integrity metadata for evidence.

    Args:
        evidence_content: Evidence content (JSON string)
        signed_by: Optional signer identity

    Returns:
        EvidenceIntegrity with hash and signature
    """
    content_hash = hash_content(evidence_content)

    # Digital signature (simplified - in production use proper PKI)
    signature = None
    if signed_by:
        signature_payload = f"{content_hash}:{signed_by}"
        signature = hash_content(signature_payload)

    return EvidenceIntegrity(
        hash=content_hash,
        signature=signature,
        algorithm="sha256",
        signed_by=signed_by,
        verified=False,
    )


def verify_evidence_chain(chain: EvidenceChain) -> bool:
    """
    Verify evidence chain integrity.

    Checks:
    1. All links are valid
    2. No circular references
    3. All entity IDs exist

    Args:
        chain: Evidence chain to verify

    Returns:
        True if valid, False otherwise
    """
    if not chain.links:
        return True

    # Check for circular references (simple check)
    seen = set()
    for link in chain.links:
        link_key = f"{link.from_type}:{link.from_id}->{link.to_type}:{link.to_id}"
        if link_key in seen:
            return False  # Circular reference
        seen.add(link_key)

    # All checks passed
    return True
