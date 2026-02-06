"""Workspace Layout and Management

Provides workspace layout specification, conflict checking, and validation
for multi-repository project workspaces.
"""

from agentos.core.workspace.layout import WorkspaceLayout, WorkspaceRoot
from agentos.core.workspace.validation import (
    ValidationResult,
    Conflict,
    ConflictType,
    WorkspaceValidator,
)

__all__ = [
    "WorkspaceLayout",
    "WorkspaceRoot",
    "ValidationResult",
    "Conflict",
    "ConflictType",
    "WorkspaceValidator",
]
