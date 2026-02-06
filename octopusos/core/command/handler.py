"""Abstract command handler interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .types import CommandContext, CommandResult


class CommandHandler(ABC):
    """Abstract base class for command handlers.
    
    All command handlers must implement the execute method.
    """

    @abstractmethod
    def execute(self, context: CommandContext, **kwargs) -> CommandResult:
        """Execute the command.
        
        Args:
            context: Command execution context
            **kwargs: Command-specific arguments
            
        Returns:
            CommandResult with execution status and data
        """
        pass

    def validate_args(self, **kwargs) -> tuple[bool, str | None]:
        """Validate command arguments.
        
        Args:
            **kwargs: Command arguments to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def get_help(self) -> str:
        """Get help text for the command.
        
        Returns:
            Help text string
        """
        return self.__doc__ or "No help available"
