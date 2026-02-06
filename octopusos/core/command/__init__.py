"""Unified command system for AgentOS.

This module provides a unified command registry and execution system
that can be used by UI and CLI interfaces.
"""

from .handler import CommandHandler
from .registry import CommandRegistry, get_registry
from .types import (
    CommandCategory,
    CommandContext,
    CommandMetadata,
    CommandResult,
    CommandStatus,
)

__all__ = [
    "CommandHandler",
    "CommandRegistry",
    "get_registry",
    "CommandCategory",
    "CommandContext",
    "CommandMetadata",
    "CommandResult",
    "CommandStatus",
]
