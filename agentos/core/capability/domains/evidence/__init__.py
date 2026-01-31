"""
Evidence Domain for AgentOS v3

Complete evidence collection, linking, replay, and export system.

This is the護城河 (moat) for:
- Regulatory compliance (SOX, GDPR, HIPAA)
- Legal discovery and forensics
- Audit trails for enterprise
- Time-travel debugging
- Rollback and replay

Capabilities:
1. evidence.collect (EC-001) - Automatic evidence collection
2. evidence.link (EC-002) - Evidence chain linking
3. evidence.replay (EC-003) - Read-only replay
4. evidence.export (EC-004) - Audit report export
5. evidence.verify (EC-005) - Integrity verification

Example:
    from agentos.core.capability.domains.evidence import (
        get_evidence_collector,
        get_evidence_link_graph,
        get_replay_engine,
        get_export_engine,
    )

    # Collect evidence
    collector = get_evidence_collector()
    evidence_id = collector.collect(...)

    # Link evidence
    graph = get_evidence_link_graph()
    chain_id = graph.link(decision_id="...", action_id="...")

    # Replay evidence
    replay = get_replay_engine()
    result = replay.replay(evidence_id="...", mode=ReplayMode.READ_ONLY)

    # Export evidence
    export = get_export_engine()
    export_id = export.export(query=ExportQuery(...), format=ExportFormat.PDF)
"""

from agentos.core.capability.domains.evidence.models import (
    Evidence,
    EvidenceType,
    OperationType,
    EvidenceChain,
    EvidenceChainLink,
    ChainRelationship,
    ChainQueryResult,
    ReplayResult,
    ReplayMode,
    ExportQuery,
    ExportPackage,
    ExportFormat,
    SideEffectEvidence,
    EvidenceProvenance,
    EvidenceIntegrity,
    generate_provenance,
    hash_content,
)

from agentos.core.capability.domains.evidence.evidence_collector import (
    EvidenceCollector,
    get_evidence_collector,
    EvidenceCollectionError,
    EvidenceNotFoundError,
    EvidenceImmutableError,
)

from agentos.core.capability.domains.evidence.evidence_link_graph import (
    EvidenceLinkGraph,
    get_evidence_link_graph,
    ChainNotFoundError,
    CircularChainError,
    InvalidLinkError,
)

from agentos.core.capability.domains.evidence.replay_engine import (
    ReplayEngine,
    get_replay_engine,
    ReplayError,
    InvalidReplayModeError,
    PermissionDeniedForValidateError,
)

from agentos.core.capability.domains.evidence.export_engine import (
    ExportEngine,
    get_export_engine,
    ExportError,
    UnsupportedFormatError,
    ExportNotFoundError,
)

__all__ = [
    # Models
    "Evidence",
    "EvidenceType",
    "OperationType",
    "EvidenceChain",
    "EvidenceChainLink",
    "ChainRelationship",
    "ChainQueryResult",
    "ReplayResult",
    "ReplayMode",
    "ExportQuery",
    "ExportPackage",
    "ExportFormat",
    "SideEffectEvidence",
    "EvidenceProvenance",
    "EvidenceIntegrity",
    "generate_provenance",
    "hash_content",
    # Evidence Collector
    "EvidenceCollector",
    "get_evidence_collector",
    "EvidenceCollectionError",
    "EvidenceNotFoundError",
    "EvidenceImmutableError",
    # Evidence Link Graph
    "EvidenceLinkGraph",
    "get_evidence_link_graph",
    "ChainNotFoundError",
    "CircularChainError",
    "InvalidLinkError",
    # Replay Engine
    "ReplayEngine",
    "get_replay_engine",
    "ReplayError",
    "InvalidReplayModeError",
    "PermissionDeniedForValidateError",
    # Export Engine
    "ExportEngine",
    "get_export_engine",
    "ExportError",
    "UnsupportedFormatError",
    "ExportNotFoundError",
]
