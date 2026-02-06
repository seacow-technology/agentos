"""Unified command registry for UI and CLI."""

from __future__ import annotations

import time
from typing import Callable, Optional

from .types import CommandCategory, CommandContext, CommandMetadata, CommandResult


class CommandRegistry:
    """Singleton registry for all commands.

    This registry manages command metadata and execution for UI and CLI interfaces.
    It provides:
    - Command registration and lookup
    - Command execution with context
    - Command filtering by category
    - History tracking (when history service is available)
    """

    _instance: Optional["CommandRegistry"] = None
    _commands: dict[str, CommandMetadata] = {}

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._commands = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> "CommandRegistry":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, metadata: CommandMetadata) -> None:
        """Register a command.
        
        Args:
            metadata: Command metadata including id, handler, etc.
            
        Raises:
            ValueError: If command id already registered
        """
        if metadata.id in self._commands:
            raise ValueError(f"Command {metadata.id} already registered")
        self._commands[metadata.id] = metadata

    def register_multiple(self, commands: list[CommandMetadata]) -> None:
        """Register multiple commands at once.
        
        Args:
            commands: List of command metadata
        """
        for cmd in commands:
            self.register(cmd)

    def unregister(self, command_id: str) -> None:
        """Unregister a command.
        
        Args:
            command_id: ID of command to unregister
        """
        if command_id in self._commands:
            del self._commands[command_id]

    def get_command(self, command_id: str) -> Optional[CommandMetadata]:
        """Get command metadata by id.
        
        Args:
            command_id: Command ID (e.g., "kb:search")
            
        Returns:
            CommandMetadata if found, None otherwise
        """
        return self._commands.get(command_id)

    def list_all(self) -> list[CommandMetadata]:
        """List all registered commands.
        
        Returns:
            List of all command metadata
        """
        return list(self._commands.values())

    def list_by_category(self, category: CommandCategory | str) -> list[CommandMetadata]:
        """List commands by category.
        
        Args:
            category: Command category
            
        Returns:
            List of commands in the category
        """
        if isinstance(category, str):
            category = CommandCategory(category)
        return [cmd for cmd in self._commands.values() if cmd.category == category]

    def search(self, query: str) -> list[CommandMetadata]:
        """Search commands by query string.
        
        Args:
            query: Search query
            
        Returns:
            List of matching commands
        """
        query = query.lower()
        results = []
        for cmd in self._commands.values():
            if (query in cmd.id.lower() or 
                query in cmd.title.lower() or 
                query in cmd.hint.lower()):
                results.append(cmd)
        return results

    def execute(
        self, 
        command_id: str, 
        context: Optional[CommandContext] = None,
        **kwargs
    ) -> CommandResult:
        """Execute a command.
        
        Args:
            command_id: ID of command to execute
            context: Execution context (created if not provided)
            **kwargs: Command-specific arguments
            
        Returns:
            CommandResult with execution status and data
            
        Raises:
            ValueError: If command not found
        """
        cmd = self.get_command(command_id)
        if not cmd:
            return CommandResult.failure(f"Command not found: {command_id}")

        # Create context if not provided
        if context is None:
            context = CommandContext()

        # Check required context
        if cmd.requires_context:
            missing = context.missing_keys(cmd.requires_context)
            if missing:
                return CommandResult.failure(
                    f"Missing required context: {', '.join(missing)}"
                )

        # Execute command and track timing
        start_time = time.time()
        try:
            result = cmd.handler(context, **kwargs)
            
            # Add duration if not already set
            if result.duration_ms is None:
                duration_ms = int((time.time() - start_time) * 1000)
                result.duration_ms = duration_ms

            # Record to history
            self._record_history(command_id, kwargs, result, context)

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            result = CommandResult.failure(
                error=str(e),
                duration_ms=duration_ms
            )
            
            # Record failure to history
            self._record_history(command_id, kwargs, result, context)
            
            return result

    def _record_history(
        self, 
        command_id: str, 
        args: dict, 
        result: CommandResult,
        context: CommandContext
    ) -> None:
        """Record command execution to history.
        
        Args:
            command_id: Command ID
            args: Command arguments
            result: Command result
            context: Execution context
        """
        try:
            from .history import CommandHistoryService
            
            history_service = CommandHistoryService()
            history_service.record(
                command_id=command_id,
                args=args,
                status=result.status,
                duration_ms=result.duration_ms,
                result_summary=result.summary,
                error=result.error,
                task_id=context.task_id,
                session_id=context.user_data.get("session_id"),
            )
        except Exception as e:
            # Don't fail the command if history recording fails
            print(f"Warning: Failed to record command history: {e}")

    def clear(self) -> None:
        """Clear all registered commands (mainly for testing)."""
        self._commands.clear()


# Convenience function
def get_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    return CommandRegistry.get_instance()
