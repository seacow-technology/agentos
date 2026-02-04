"""AgentOS Marketplace - Capability Registry and Discovery.

This package implements the Marketplace Registry (Phase F2), which serves as
a capability ledger that records:
1. WHO published the capability (publisher identity)
2. WHAT was published (complete manifest)
3. WHERE it came from (source/signature)

The Registry is intentionally minimal:
- NO trust scoring (handled by Phase F3)
- NO recommendations
- NO authorization decisions
- ONLY registration, query, and history tracking

Key Components:
- MarketplaceRegistry: Core registry operations
- CapabilityManifest: Manifest data model and validation
- MarketplaceGovernance: Platform self-regulation (Phase F5)
"""

from agentos.marketplace.manifest import (
    CapabilityManifest,
    load_manifest,
    validate_manifest,
    normalize_manifest,
)
from agentos.marketplace.registry import (
    MarketplaceRegistry,
    RegistryError,
    VersionConflictError,
    PublisherNotFoundError,
    CapabilityNotFoundError,
)
from agentos.marketplace.governance import (
    MarketplaceGovernance,
    GovernanceError,
    PermissionDeniedError,
    InvalidActionError,
    TargetNotFoundError,
    GovernanceAction,
    CapabilityFlag,
    GovernanceStatus,
    get_governance,
)

__all__ = [
    "MarketplaceRegistry",
    "RegistryError",
    "VersionConflictError",
    "PublisherNotFoundError",
    "CapabilityNotFoundError",
    "CapabilityManifest",
    "load_manifest",
    "validate_manifest",
    "normalize_manifest",
    "MarketplaceGovernance",
    "GovernanceError",
    "PermissionDeniedError",
    "InvalidActionError",
    "TargetNotFoundError",
    "GovernanceAction",
    "CapabilityFlag",
    "GovernanceStatus",
    "get_governance",
]
