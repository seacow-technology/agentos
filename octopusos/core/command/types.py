"""Command system types and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class CommandCategory(str, Enum):
    """Command categories for organization."""
    KB = "kb"
    MEMORY = "memory"
    TASK = "task"
    SYSTEM = "system"
    HISTORY = "history"
    MODEL = "model"
    CHAT = "chat"


class CommandStatus(str, Enum):
    """Command execution status."""
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass
class CommandMetadata:
    """Metadata for a command.
    
    Attributes:
        id: Unique command identifier (e.g., "kb:search", "mem:add")
        title: Display title for the command
        hint: Hint text shown in command palette
        category: Command category for organization
        handler: Callable function that executes the command
        needs_arg: Whether command requires additional argument (two-step mode)
        requires_context: List of required context keys (e.g., ["project_id", "task_id"])
        dangerous: Whether command requires confirmation before execution
        help_text: Detailed help documentation for the command
    """
    id: str
    title: str
    hint: str
    category: CommandCategory
    handler: Callable
    needs_arg: bool = False
    requires_context: list[str] = field(default_factory=list)
    dangerous: bool = False
    help_text: Optional[str] = None

    def __post_init__(self):
        """Validate command metadata."""
        if not self.id:
            raise ValueError("Command id cannot be empty")
        if ":" not in self.id:
            raise ValueError(f"Command id must contain ':' separator (got: {self.id})")
        if not callable(self.handler):
            raise ValueError(f"Handler for {self.id} must be callable")


@dataclass
class CommandResult:
    """Result of a command execution.
    
    Attributes:
        status: Execution status (success/failure/cancelled)
        data: Result data (can be any type)
        error: Error message if status is failure
        summary: Human-readable summary of the result
        duration_ms: Execution duration in milliseconds
    """
    status: CommandStatus
    data: Any = None
    error: Optional[str] = None
    summary: Optional[str] = None
    duration_ms: Optional[int] = None

    @classmethod
    def success(cls, data: Any = None, summary: str = None, duration_ms: int = None) -> "CommandResult":
        """Create a success result."""
        return cls(status=CommandStatus.SUCCESS, data=data, summary=summary, duration_ms=duration_ms)

    @classmethod
    def failure(cls, error: str, duration_ms: int = None) -> "CommandResult":
        """Create a failure result."""
        return cls(status=CommandStatus.FAILURE, error=error, duration_ms=duration_ms)

    @classmethod
    def cancelled(cls) -> "CommandResult":
        """Create a cancelled result."""
        return cls(status=CommandStatus.CANCELLED)

    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == CommandStatus.SUCCESS

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "summary": self.summary,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CommandContext:
    """Context passed to command handlers.
    
    Attributes:
        project_id: Current project ID (if any)
        task_id: Current task ID (if any)
        scope: Current memory scope (if any)
        user_data: Additional user data
    """
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    scope: Optional[str] = None
    user_data: dict = field(default_factory=dict)

    def has_required(self, keys: list[str]) -> bool:
        """Check if all required context keys are present."""
        for key in keys:
            if not getattr(self, key, None):
                return False
        return True

    def missing_keys(self, keys: list[str]) -> list[str]:
        """Get list of missing required keys."""
        return [key for key in keys if not getattr(self, key, None)]
