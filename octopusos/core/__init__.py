"""Core module"""

# Export capability registry and audit system
from agentos.core.capability_registry import (
    get_capability_registry,
    CapabilityRegistry,
    Capability,
    RuntimePreset,
    RuntimeDependency,
    CapabilityKind,
    RiskLevel,
)

from agentos.core.audit import (
    log_audit_event,
    get_audit_events,
    get_snippet_audit_trail,
    get_preview_audit_trail,
    get_task_audits,
    # Event type constants
    SNIPPET_CREATED,
    SNIPPET_UPDATED,
    SNIPPET_DELETED,
    SNIPPET_USED_IN_TASK,
    PREVIEW_SESSION_CREATED,
    PREVIEW_SESSION_OPENED,
    PREVIEW_SESSION_EXPIRED,
    PREVIEW_RUNTIME_SELECTED,
    PREVIEW_DEP_INJECTED,
    TASK_MATERIALIZED_FROM_SNIPPET,
)

__all__ = [
    # Capability Registry
    "get_capability_registry",
    "CapabilityRegistry",
    "Capability",
    "RuntimePreset",
    "RuntimeDependency",
    "CapabilityKind",
    "RiskLevel",
    # Audit System
    "log_audit_event",
    "get_audit_events",
    "get_snippet_audit_trail",
    "get_preview_audit_trail",
    "get_task_audits",
    # Event Types
    "SNIPPET_CREATED",
    "SNIPPET_UPDATED",
    "SNIPPET_DELETED",
    "SNIPPET_USED_IN_TASK",
    "PREVIEW_SESSION_CREATED",
    "PREVIEW_SESSION_OPENED",
    "PREVIEW_SESSION_EXPIRED",
    "PREVIEW_RUNTIME_SELECTED",
    "PREVIEW_DEP_INJECTED",
    "TASK_MATERIALIZED_FROM_SNIPPET",
]
