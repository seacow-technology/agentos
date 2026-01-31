"""Memory Capability System - OS-level permission controls

This module defines the capability-based permission model for Memory operations.
Inspired by Linux capabilities (CAP_*), it provides hierarchical access control
for memory read/write/propose/delete operations.

Design Philosophy:
- Simple: Capability enum with clear hierarchy
- Safe: Default to NONE (deny by default)
- Auditable: Every capability check is logged
- Flexible: Pattern-based defaults for agent types

Usage:
    from agentos.core.memory.capabilities import MemoryCapability

    # Check if capability allows operation
    cap = MemoryCapability.READ
    can_read = cap.can_perform("list")  # True
    can_write = cap.can_perform("upsert")  # False

Related:
- ADR-012: Memory Capability Contract
- Task #16: Implement Memory Capability checking mechanism
"""

from enum import Enum
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass


class MemoryCapability(str, Enum):
    """
    Memory operation capability levels (hierarchical).

    Inspired by Linux capabilities, this defines what operations
    an agent can perform on the Memory system.

    Hierarchy:
        NONE < READ < PROPOSE < WRITE < ADMIN

    Design Principle:
    - NONE: Complete lockout (for untrusted agents)
    - READ: Query-only access (for search/analysis agents)
    - PROPOSE: Can suggest memories but requires approval (for chat agents)
    - WRITE: Can directly write memories (for user-explicit agents)
    - ADMIN: Full control including deletion and capability management
    """

    NONE = "none"       # No access to Memory
    READ = "read"       # Read-only: list, search, get, build_context
    PROPOSE = "propose" # Propose + Read: can create proposals (requires approval)
    WRITE = "write"     # Write + Propose + Read: can directly upsert/update
    ADMIN = "admin"     # Admin + Write + Propose + Read: full control

    def can_perform(self, operation: str) -> bool:
        """
        Check if this capability allows the operation.

        Args:
            operation: Operation name (list|search|get|propose|upsert|delete|set_capability)

        Returns:
            True if capability level allows the operation

        Example:
            >>> MemoryCapability.READ.can_perform("list")
            True
            >>> MemoryCapability.READ.can_perform("upsert")
            False
            >>> MemoryCapability.WRITE.can_perform("list")
            True  # WRITE inherits READ operations
        """
        return operation in CAPABILITY_MATRIX[self]

    def __lt__(self, other):
        """Capability hierarchy for comparison."""
        if not isinstance(other, MemoryCapability):
            return NotImplemented
        levels = [self.NONE, self.READ, self.PROPOSE, self.WRITE, self.ADMIN]
        return levels.index(self) < levels.index(other)

    def __le__(self, other):
        """Capability hierarchy for comparison."""
        if not isinstance(other, MemoryCapability):
            return NotImplemented
        levels = [self.NONE, self.READ, self.PROPOSE, self.WRITE, self.ADMIN]
        return levels.index(self) <= levels.index(other)

    def __gt__(self, other):
        """Capability hierarchy for comparison."""
        if not isinstance(other, MemoryCapability):
            return NotImplemented
        levels = [self.NONE, self.READ, self.PROPOSE, self.WRITE, self.ADMIN]
        return levels.index(self) > levels.index(other)

    def __ge__(self, other):
        """Capability hierarchy for comparison."""
        if not isinstance(other, MemoryCapability):
            return NotImplemented
        levels = [self.NONE, self.READ, self.PROPOSE, self.WRITE, self.ADMIN]
        return levels.index(self) >= levels.index(other)


# ============================================
# Operation Categories
# ============================================

# READ operations (query-only, no modification)
READ_OPERATIONS: Set[str] = {"list", "search", "get", "build_context"}

# PROPOSE operations (create proposals)
PROPOSE_OPERATIONS: Set[str] = {"propose"}

# WRITE operations (direct modification)
WRITE_OPERATIONS: Set[str] = {"upsert", "update"}

# ADMIN operations (destructive and permission management)
ADMIN_OPERATIONS: Set[str] = {"delete", "set_capability", "approve_proposal", "reject_proposal"}


# ============================================
# Capability Matrix (Hierarchical)
# ============================================

CAPABILITY_MATRIX: Dict[MemoryCapability, Set[str]] = {
    MemoryCapability.NONE: set(),
    MemoryCapability.READ: READ_OPERATIONS,
    MemoryCapability.PROPOSE: READ_OPERATIONS | PROPOSE_OPERATIONS,
    MemoryCapability.WRITE: READ_OPERATIONS | PROPOSE_OPERATIONS | WRITE_OPERATIONS,
    MemoryCapability.ADMIN: READ_OPERATIONS | PROPOSE_OPERATIONS | WRITE_OPERATIONS | ADMIN_OPERATIONS
}


# ============================================
# Agent Capability Record
# ============================================

@dataclass
class AgentCapabilityRecord:
    """
    Agent capability record from database.

    Represents a capability grant stored in agent_capabilities table.
    """
    agent_id: str
    agent_type: str
    memory_capability: MemoryCapability
    granted_by: str
    granted_at_ms: int
    expires_at_ms: Optional[int] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_expired(self) -> bool:
        """Check if capability has expired."""
        if self.expires_at_ms is None:
            return False
        from agentos.core.time import utc_now_ms
        return utc_now_ms() > self.expires_at_ms


# ============================================
# Permission Denied Exception
# ============================================

class PermissionDenied(Exception):
    """
    Raised when agent lacks required capability for operation.

    This exception is raised by permission checks when an agent attempts
    an operation that exceeds its capability level.

    Example:
        >>> raise PermissionDenied(
        ...     agent_id="chat_agent",
        ...     operation="upsert",
        ...     capability=MemoryCapability.PROPOSE,
        ...     required=MemoryCapability.WRITE
        ... )
    """

    def __init__(
        self,
        agent_id: str,
        operation: str,
        capability: MemoryCapability,
        required: MemoryCapability
    ):
        self.agent_id = agent_id
        self.operation = operation
        self.capability = capability
        self.required = required

        super().__init__(
            f"Permission denied: Agent '{agent_id}' has capability '{capability.value}' "
            f"but operation '{operation}' requires capability >= '{required.value}'"
        )


# ============================================
# Default Capability Rules
# ============================================

DEFAULT_CAPABILITIES: Dict[str, MemoryCapability] = {
    # Tier 1: READ-ONLY agents
    "query_agent": MemoryCapability.READ,
    "analysis_agent": MemoryCapability.READ,
    "monitoring_agent": MemoryCapability.READ,
    "explanation_agent": MemoryCapability.READ,

    # Tier 2: PROPOSE agents (require approval)
    "chat_agent": MemoryCapability.PROPOSE,
    "extraction_agent": MemoryCapability.PROPOSE,
    "suggestion_agent": MemoryCapability.PROPOSE,
    "learning_agent": MemoryCapability.PROPOSE,

    # Tier 3: WRITE agents (direct write)
    "user_explicit_agent": MemoryCapability.WRITE,
    "system_config": MemoryCapability.WRITE,
    "import_agent": MemoryCapability.WRITE,
    "task_artifact_agent": MemoryCapability.WRITE,

    # Tier 4: ADMIN agents (full control)
    "system": MemoryCapability.ADMIN,
}


def get_default_capability(agent_id: str) -> MemoryCapability:
    """
    Get default capability based on agent_id pattern.

    Default rules:
    - user:* → ADMIN (all human users have admin access)
    - system → ADMIN (system operations)
    - *_readonly → READ (naming convention)
    - chat_agent → PROPOSE
    - query_agent → READ
    - test_* → WRITE (test agents need write for integration tests)
    - unknown → NONE (fail-safe: deny by default)

    Args:
        agent_id: Agent identifier

    Returns:
        Default MemoryCapability

    Example:
        >>> get_default_capability("user:alice")
        MemoryCapability.ADMIN
        >>> get_default_capability("query_readonly")
        MemoryCapability.READ
        >>> get_default_capability("unknown_agent")
        MemoryCapability.NONE
    """
    # Check exact match
    if agent_id in DEFAULT_CAPABILITIES:
        return DEFAULT_CAPABILITIES[agent_id]

    # Pattern rules (in priority order)
    if agent_id.startswith("user:"):
        return MemoryCapability.ADMIN

    if agent_id == "system":
        return MemoryCapability.ADMIN

    if agent_id.endswith("_readonly"):
        return MemoryCapability.READ

    if agent_id.startswith("test_"):
        return MemoryCapability.WRITE

    if agent_id.startswith("monitor_"):
        return MemoryCapability.READ

    # Safe default: NONE (deny by default)
    return MemoryCapability.NONE


# ============================================
# Convenience Constants
# ============================================

CAP_NONE = MemoryCapability.NONE
CAP_READ = MemoryCapability.READ
CAP_PROPOSE = MemoryCapability.PROPOSE
CAP_WRITE = MemoryCapability.WRITE
CAP_ADMIN = MemoryCapability.ADMIN
