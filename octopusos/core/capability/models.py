"""
Capability Models for AgentOS v3

This module defines the core data models for the v3 Capability system,
including the 5 Domains and 27 atomic Capabilities.

Design Philosophy (from ADR-013):
- Capability-based security (Linux CAP_* inspired)
- Golden Path enforcement: State→Decision→Governance→Action→State→Evidence
- Forbidden paths blocked: Action直接→State, Decision直接→Action
- Every operation requires explicit Capability grant

Five Domains:
1. State Domain (6 capabilities): Memory, Task State, Project State
2. Decision Domain (5 capabilities): Plan, Approve, Freeze, Classify
3. Action Domain (6 capabilities): Execute, FileWrite, NetworkCall, DBWrite
4. Governance Domain (5 capabilities): PolicyCheck, AuditLog, RiskGate
5. Evidence Domain (5 capabilities): Record, Verify, Chain, Query
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class CapabilityDomain(str, Enum):
    """
    Five domains in AgentOS v3 architecture.

    Each domain has specific responsibilities and can only call
    specific other domains (Golden Path).
    """
    STATE = "state"           # State management (Memory, Task, Project)
    DECISION = "decision"     # Decision-making (Plan, Approve, Freeze)
    ACTION = "action"         # Actions (Execute, Write, Network, DB)
    GOVERNANCE = "governance" # Governance (Policy, Audit, Risk)
    EVIDENCE = "evidence"     # Evidence (Record, Verify, Chain, Query)


class CapabilityLevel(str, Enum):
    """
    Capability permission levels (hierarchical).

    Inspired by Linux capabilities model.
    """
    NONE = "none"       # No permission (lockout)
    READ = "read"       # Read-only operations
    PROPOSE = "propose" # Can propose changes (requires approval)
    WRITE = "write"     # Can write directly
    ADMIN = "admin"     # Full control including deletion


class RiskLevel(str, Enum):
    """Risk classification for capabilities"""
    LOW = "low"           # Read-only, no side effects
    MEDIUM = "medium"     # Limited side effects, reversible
    HIGH = "high"         # Significant side effects (writes, deletes)
    CRITICAL = "critical" # Dangerous operations (irreversible actions)


class SideEffectType(str, Enum):
    """Types of side effects a capability can produce"""
    PERSISTENT_STATE_MUTATION = "persistent_state_mutation"
    EXTERNAL_CALL = "external_call"
    IRREVERSIBLE_ACTION = "irreversible_action"
    FILE_SYSTEM_WRITE = "file_system_write"
    DATABASE_WRITE = "database_write"
    NETWORK_REQUEST = "network_request"
    MEMORY_MUTATION = "memory_mutation"
    TASK_STATE_CHANGE = "task_state_change"
    PROJECT_STATE_CHANGE = "project_state_change"


class CostModel(BaseModel):
    """Cost estimation for capability invocation"""
    estimated_tokens: Optional[int] = Field(
        default=None,
        description="Estimated token cost (for LLM calls)"
    )
    estimated_time_ms: Optional[int] = Field(
        default=None,
        description="Estimated execution time in milliseconds"
    )
    estimated_api_calls: Optional[int] = Field(
        default=None,
        description="Estimated number of API calls"
    )


class CapabilityDefinition(BaseModel):
    """
    Complete definition of an atomic Capability.

    All 27 capabilities must define these 5 mandatory fields:
    1. capability_id: Unique identifier
    2. domain: Which domain it belongs to
    3. risk_level: Risk classification
    4. requires: Dependencies (other capabilities needed)
    5. produces_side_effects: List of side effects

    Example:
        {
            "capability_id": "state.memory.read",
            "domain": "state",
            "level": "read",
            "risk_level": "low",
            "requires": [],
            "produces_side_effects": []
        }
    """
    capability_id: str = Field(
        description="Unique capability identifier (format: domain.category.operation)"
    )
    domain: CapabilityDomain = Field(
        description="Domain this capability belongs to"
    )
    level: CapabilityLevel = Field(
        description="Permission level required"
    )
    risk_level: RiskLevel = Field(
        description="Risk classification"
    )
    name: str = Field(
        description="Human-readable name"
    )
    description: str = Field(
        description="What this capability does"
    )
    requires: List[str] = Field(
        default_factory=list,
        description="List of capability_ids that must be granted before this one"
    )
    produces_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects this capability produces"
    )
    cost_model: Optional[CostModel] = Field(
        default=None,
        description="Cost estimation for invocation"
    )
    allowed_call_targets: List[CapabilityDomain] = Field(
        default_factory=list,
        description="Which domains this capability can call (Golden Path)"
    )
    forbidden_call_targets: List[CapabilityDomain] = Field(
        default_factory=list,
        description="Which domains this capability CANNOT call"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    version: str = Field(
        default="1.0.0",
        description="Capability definition version"
    )

    def allows_call_to(self, target_domain: CapabilityDomain) -> bool:
        """
        Check if this capability can call into target domain.

        Implements Golden Path enforcement.
        """
        if target_domain in self.forbidden_call_targets:
            return False
        if self.allowed_call_targets:
            return target_domain in self.allowed_call_targets
        return True  # No restrictions if allowed_call_targets is empty


class CapabilityGrant(BaseModel):
    """
    Record of a capability grant to an agent.

    Stored in capability_grants table.
    """
    grant_id: str = Field(
        description="Unique grant identifier (ulid)"
    )
    agent_id: str = Field(
        description="Agent identifier receiving the grant"
    )
    capability_id: str = Field(
        description="Capability being granted"
    )
    granted_by: str = Field(
        description="Who granted this capability (user_id or agent_id)"
    )
    granted_at_ms: int = Field(
        description="When granted (epoch milliseconds)"
    )
    expires_at_ms: Optional[int] = Field(
        default=None,
        description="Optional expiration time (epoch ms, None = never expires)"
    )
    scope: Optional[str] = Field(
        default=None,
        description="Optional scope restriction (e.g., 'project:proj-123')"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason for grant"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional grant metadata"
    )


class CapabilityInvocation(BaseModel):
    """
    Record of a capability invocation (audit trail).

    Stored in capability_invocations table.
    """
    invocation_id: int = Field(
        description="Auto-incremented invocation ID"
    )
    agent_id: str = Field(
        description="Agent invoking the capability"
    )
    capability_id: str = Field(
        description="Capability being invoked"
    )
    operation: str = Field(
        description="Specific operation within capability"
    )
    allowed: bool = Field(
        description="Whether invocation was allowed (True) or denied (False)"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for denial (if allowed=False)"
    )
    context_json: Optional[str] = Field(
        default=None,
        description="Execution context as JSON"
    )
    timestamp_ms: int = Field(
        description="Invocation timestamp (epoch milliseconds)"
    )


class CallStackEntry(BaseModel):
    """
    Entry in the call stack for path validation.

    Used by PathValidator to track execution flow.
    """
    capability_id: str = Field(
        description="Capability being called"
    )
    domain: CapabilityDomain = Field(
        description="Domain of the capability"
    )
    agent_id: str = Field(
        description="Agent making the call"
    )
    operation: str = Field(
        description="Operation being performed"
    )
    timestamp_ms: int = Field(
        description="Call timestamp (epoch milliseconds)"
    )
    parent_invocation_id: Optional[int] = Field(
        default=None,
        description="Parent invocation ID (for nested calls)"
    )


class PathValidationResult(BaseModel):
    """
    Result of path validation check.

    Returned by PathValidator.
    """
    valid: bool = Field(
        description="Whether the call path is valid"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for validation failure (if valid=False)"
    )
    violated_rule: Optional[str] = Field(
        default=None,
        description="Which rule was violated (e.g., 'decision->action_forbidden')"
    )
    call_stack: List[CallStackEntry] = Field(
        default_factory=list,
        description="Current call stack"
    )


# ===================================================================
# 27 Capability Definitions (5 Domains)
# ===================================================================

def get_default_capabilities() -> List[CapabilityDefinition]:
    """
    Get all 27 default capability definitions for AgentOS v3.

    Organized by 5 domains:
    - State Domain: 6 capabilities
    - Decision Domain: 5 capabilities
    - Action Domain: 6 capabilities
    - Governance Domain: 5 capabilities
    - Evidence Domain: 5 capabilities

    Returns:
        List of 27 CapabilityDefinition objects
    """
    capabilities = []

    # ===================================================================
    # DOMAIN 1: STATE (6 capabilities)
    # ===================================================================

    # 1.1 Memory Read
    capabilities.append(CapabilityDefinition(
        capability_id="state.memory.read",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Memory Read",
        description="Read from external memory (MemoryOS)",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.DECISION, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 1.2 Memory Write
    capabilities.append(CapabilityDefinition(
        capability_id="state.memory.write",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="Memory Write",
        description="Write to external memory (requires governance approval)",
        requires=["state.memory.read"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION, SideEffectType.MEMORY_MUTATION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=20),
        version="1.0.0"
    ))

    # 1.3 Task State Read
    capabilities.append(CapabilityDefinition(
        capability_id="state.task.read",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Task State Read",
        description="Read task state from task service",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.DECISION, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=5),
        version="1.0.0"
    ))

    # 1.4 Task State Write
    capabilities.append(CapabilityDefinition(
        capability_id="state.task.write",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.HIGH,
        name="Task State Write",
        description="Modify task state (requires frozen plan)",
        requires=["state.task.read", "decision.plan.freeze"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION, SideEffectType.TASK_STATE_CHANGE],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=15),
        version="1.0.0"
    ))

    # 1.5 Project State Read
    capabilities.append(CapabilityDefinition(
        capability_id="state.project.read",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Project State Read",
        description="Read project configuration and state",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.DECISION, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=5),
        version="1.0.0"
    ))

    # 1.6 Project State Write
    capabilities.append(CapabilityDefinition(
        capability_id="state.project.write",
        domain=CapabilityDomain.STATE,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.HIGH,
        name="Project State Write",
        description="Modify project configuration (admin only)",
        requires=["state.project.read"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION, SideEffectType.PROJECT_STATE_CHANGE],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=20),
        version="1.0.0"
    ))

    # ===================================================================
    # DOMAIN 2: DECISION (5 capabilities)
    # ===================================================================

    # 2.1 Plan Create
    capabilities.append(CapabilityDefinition(
        capability_id="decision.plan.create",
        domain=CapabilityDomain.DECISION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="Plan Create",
        description="Create execution plan (not yet frozen)",
        requires=["state.memory.read", "state.task.read"],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],  # Cannot execute before freeze
        cost_model=CostModel(estimated_tokens=500, estimated_time_ms=200),
        version="1.0.0"
    ))

    # 2.2 Plan Freeze
    capabilities.append(CapabilityDefinition(
        capability_id="decision.plan.freeze",
        domain=CapabilityDomain.DECISION,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.HIGH,
        name="Plan Freeze",
        description="Freeze plan (make immutable, enable Action execution)",
        requires=["decision.plan.create", "governance.policy.check"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 2.3 Decision Approve
    capabilities.append(CapabilityDefinition(
        capability_id="decision.approval.approve",
        domain=CapabilityDomain.DECISION,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.HIGH,
        name="Decision Approve",
        description="Approve proposed decisions (governance gate)",
        requires=["governance.policy.check"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=5),
        version="1.0.0"
    ))

    # 2.4 Decision Classify
    capabilities.append(CapabilityDefinition(
        capability_id="decision.infoneed.classify",
        domain=CapabilityDomain.DECISION,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Decision Classify",
        description="Classify InfoNeed type (read-only decision)",
        requires=["state.memory.read"],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_tokens=100, estimated_time_ms=150),
        version="1.0.0"
    ))

    # 2.5 Decision Rollback
    capabilities.append(CapabilityDefinition(
        capability_id="decision.plan.rollback",
        domain=CapabilityDomain.DECISION,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.CRITICAL,
        name="Decision Rollback",
        description="Rollback a frozen decision (emergency only)",
        requires=["decision.plan.freeze", "governance.risk.gate"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION, SideEffectType.IRREVERSIBLE_ACTION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=50),
        version="1.0.0"
    ))

    # ===================================================================
    # DOMAIN 3: ACTION (6 capabilities)
    # ===================================================================

    # 3.1 Action Execute
    capabilities.append(CapabilityDefinition(
        capability_id="action.execute",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.HIGH,
        name="Action Execute",
        description="Execute action (requires frozen plan)",
        requires=["decision.plan.freeze", "governance.policy.check"],
        produces_side_effects=[SideEffectType.IRREVERSIBLE_ACTION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],  # Must record evidence
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],  # Cannot bypass governance
        cost_model=CostModel(estimated_time_ms=500),
        version="1.0.0"
    ))

    # 3.2 File Write
    capabilities.append(CapabilityDefinition(
        capability_id="action.file.write",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.HIGH,
        name="File Write",
        description="Write to filesystem",
        requires=["action.execute"],
        produces_side_effects=[SideEffectType.FILE_SYSTEM_WRITE, SideEffectType.IRREVERSIBLE_ACTION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_time_ms=20),
        version="1.0.0"
    ))

    # 3.3 File Delete
    capabilities.append(CapabilityDefinition(
        capability_id="action.file.delete",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.CRITICAL,
        name="File Delete",
        description="Delete files (irreversible)",
        requires=["action.execute", "governance.risk.gate"],
        produces_side_effects=[SideEffectType.FILE_SYSTEM_WRITE, SideEffectType.IRREVERSIBLE_ACTION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 3.4 Network Call
    capabilities.append(CapabilityDefinition(
        capability_id="action.network.call",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.HIGH,
        name="Network Call",
        description="Make external network requests",
        requires=["action.execute"],
        produces_side_effects=[SideEffectType.EXTERNAL_CALL, SideEffectType.NETWORK_REQUEST],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_time_ms=300, estimated_api_calls=1),
        version="1.0.0"
    ))

    # 3.5 Database Write
    capabilities.append(CapabilityDefinition(
        capability_id="action.database.write",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.HIGH,
        name="Database Write",
        description="Write to database (non-state tables)",
        requires=["action.execute"],
        produces_side_effects=[SideEffectType.DATABASE_WRITE, SideEffectType.PERSISTENT_STATE_MUTATION],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_time_ms=15),
        version="1.0.0"
    ))

    # 3.6 LLM Call
    capabilities.append(CapabilityDefinition(
        capability_id="action.llm.call",
        domain=CapabilityDomain.ACTION,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="LLM Call",
        description="Call external LLM API",
        requires=["action.execute"],
        produces_side_effects=[SideEffectType.EXTERNAL_CALL, SideEffectType.NETWORK_REQUEST],
        allowed_call_targets=[CapabilityDomain.GOVERNANCE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_tokens=1000, estimated_time_ms=500, estimated_api_calls=1),
        version="1.0.0"
    ))

    # ===================================================================
    # DOMAIN 4: GOVERNANCE (5 capabilities)
    # ===================================================================

    # 4.1 Policy Check
    capabilities.append(CapabilityDefinition(
        capability_id="governance.policy.check",
        domain=CapabilityDomain.GOVERNANCE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Policy Check",
        description="Check if operation meets policy requirements",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.EVIDENCE],  # Can query state for checks
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 4.2 Audit Log
    capabilities.append(CapabilityDefinition(
        capability_id="governance.audit.log",
        domain=CapabilityDomain.GOVERNANCE,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="Audit Log",
        description="Write to audit trail",
        requires=[],
        produces_side_effects=[SideEffectType.DATABASE_WRITE],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION, CapabilityDomain.DECISION],
        cost_model=CostModel(estimated_time_ms=5),
        version="1.0.0"
    ))

    # 4.3 Risk Gate
    capabilities.append(CapabilityDefinition(
        capability_id="governance.risk.gate",
        domain=CapabilityDomain.GOVERNANCE,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.HIGH,
        name="Risk Gate",
        description="Approve high-risk operations",
        requires=["governance.policy.check"],
        produces_side_effects=[SideEffectType.PERSISTENT_STATE_MUTATION],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=15),
        version="1.0.0"
    ))

    # 4.4 Budget Enforce
    capabilities.append(CapabilityDefinition(
        capability_id="governance.budget.enforce",
        domain=CapabilityDomain.GOVERNANCE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.MEDIUM,
        name="Budget Enforce",
        description="Enforce token/cost budgets",
        requires=["governance.policy.check"],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=5),
        version="1.0.0"
    ))

    # 4.5 Compliance Check
    capabilities.append(CapabilityDefinition(
        capability_id="governance.compliance.check",
        domain=CapabilityDomain.GOVERNANCE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Compliance Check",
        description="Verify compliance with regulations (GDPR, SOC2)",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.STATE, CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.ACTION],
        cost_model=CostModel(estimated_time_ms=20),
        version="1.0.0"
    ))

    # ===================================================================
    # DOMAIN 5: EVIDENCE (5 capabilities)
    # ===================================================================

    # 5.1 Evidence Record
    capabilities.append(CapabilityDefinition(
        capability_id="evidence.record",
        domain=CapabilityDomain.EVIDENCE,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="Evidence Record",
        description="Record execution evidence (logs, artifacts)",
        requires=[],
        produces_side_effects=[SideEffectType.DATABASE_WRITE, SideEffectType.FILE_SYSTEM_WRITE],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],  # Can only call itself
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION, CapabilityDomain.ACTION, CapabilityDomain.GOVERNANCE],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 5.2 Evidence Verify
    capabilities.append(CapabilityDefinition(
        capability_id="evidence.verify",
        domain=CapabilityDomain.EVIDENCE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Evidence Verify",
        description="Verify evidence integrity (checksums, signatures)",
        requires=["evidence.record"],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION, CapabilityDomain.ACTION, CapabilityDomain.GOVERNANCE],
        cost_model=CostModel(estimated_time_ms=15),
        version="1.0.0"
    ))

    # 5.3 Evidence Chain
    capabilities.append(CapabilityDefinition(
        capability_id="evidence.chain",
        domain=CapabilityDomain.EVIDENCE,
        level=CapabilityLevel.WRITE,
        risk_level=RiskLevel.MEDIUM,
        name="Evidence Chain",
        description="Create evidence chain (linking related evidence)",
        requires=["evidence.record"],
        produces_side_effects=[SideEffectType.DATABASE_WRITE],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION, CapabilityDomain.ACTION, CapabilityDomain.GOVERNANCE],
        cost_model=CostModel(estimated_time_ms=10),
        version="1.0.0"
    ))

    # 5.4 Evidence Query
    capabilities.append(CapabilityDefinition(
        capability_id="evidence.query",
        domain=CapabilityDomain.EVIDENCE,
        level=CapabilityLevel.READ,
        risk_level=RiskLevel.LOW,
        name="Evidence Query",
        description="Query historical evidence",
        requires=[],
        produces_side_effects=[],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION, CapabilityDomain.ACTION, CapabilityDomain.GOVERNANCE],
        cost_model=CostModel(estimated_time_ms=20),
        version="1.0.0"
    ))

    # 5.5 Evidence Export
    capabilities.append(CapabilityDefinition(
        capability_id="evidence.export",
        domain=CapabilityDomain.EVIDENCE,
        level=CapabilityLevel.ADMIN,
        risk_level=RiskLevel.MEDIUM,
        name="Evidence Export",
        description="Export evidence for external audit",
        requires=["evidence.query", "evidence.verify"],
        produces_side_effects=[SideEffectType.FILE_SYSTEM_WRITE],
        allowed_call_targets=[CapabilityDomain.EVIDENCE],
        forbidden_call_targets=[CapabilityDomain.STATE, CapabilityDomain.DECISION, CapabilityDomain.ACTION, CapabilityDomain.GOVERNANCE],
        cost_model=CostModel(estimated_time_ms=100),
        version="1.0.0"
    ))

    return capabilities


# Validation
def validate_capability_definition(cap: CapabilityDefinition) -> tuple[bool, Optional[str]]:
    """
    Validate that a capability definition is complete.

    All 27 capabilities must have:
    1. capability_id (non-empty)
    2. domain (valid enum)
    3. risk_level (valid enum)
    4. requires (list, can be empty)
    5. produces_side_effects (list, can be empty)

    Returns:
        (is_valid, error_message)
    """
    if not cap.capability_id:
        return False, "capability_id is required"

    if cap.domain not in CapabilityDomain:
        return False, f"Invalid domain: {cap.domain}"

    if cap.risk_level not in RiskLevel:
        return False, f"Invalid risk_level: {cap.risk_level}"

    if not isinstance(cap.requires, list):
        return False, "requires must be a list"

    if not isinstance(cap.produces_side_effects, list):
        return False, "produces_side_effects must be a list"

    # Validate capability_id format: domain.category.operation
    parts = cap.capability_id.split(".")
    if len(parts) < 3:
        return False, f"capability_id must be in format 'domain.category.operation', got: {cap.capability_id}"

    if parts[0] != cap.domain.value:
        return False, f"capability_id domain '{parts[0]}' does not match domain field '{cap.domain.value}'"

    return True, None
