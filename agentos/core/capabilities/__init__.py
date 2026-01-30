"""
Capability Runner System

This module provides the execution framework for extension capabilities,
including command routing, tool execution, and result handling.
"""

from .models import (
    CommandRoute,
    ExecutionContext,
    ExecutionResult,
    CapabilityResult,
    ToolExecutionResult,
)
from .runner import CapabilityRunner
from .exceptions import (
    CapabilityError,
    ExecutionError,
    ToolNotFoundError,
    TimeoutError,
)

__all__ = [
    # Models
    "CommandRoute",
    "ExecutionContext",
    "ExecutionResult",
    "CapabilityResult",
    "ToolExecutionResult",
    # Runner
    "CapabilityRunner",
    # Exceptions
    "CapabilityError",
    "ExecutionError",
    "ToolNotFoundError",
    "TimeoutError",
]
