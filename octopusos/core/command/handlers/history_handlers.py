"""History command handlers."""

from __future__ import annotations

from agentos.core.command import (
    CommandCategory,
    CommandContext,
    CommandMetadata,
    CommandRegistry,
    CommandResult,
)


def history_list_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:list command."""
    from agentos.core.command.history import CommandHistoryService
    
    command_id = kwargs.get("command_id")
    status = kwargs.get("status")
    limit = kwargs.get("limit", 50)
    
    try:
        service = CommandHistoryService()
        entries = service.list(
            command_id=command_id,
            status=status,
            limit=limit
        )
        
        summary = f"Found {len(entries)} history entries"
        return CommandResult.success(
            data={"entries": [e.to_dict() for e in entries]},
            summary=summary
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def history_show_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:show command."""
    from agentos.core.command.history import CommandHistoryService
    
    history_id = kwargs.get("history_id")
    if not history_id:
        return CommandResult.failure("history_id is required")
    
    try:
        service = CommandHistoryService()
        entry = service.get(history_id)
        
        if not entry:
            return CommandResult.failure(f"History entry not found: {history_id}")
        
        return CommandResult.success(
            data=entry.to_dict(),
            summary=f"History: {entry.command_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def history_replay_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:replay command - re-execute a command from history."""
    from agentos.core.command.history import CommandHistoryService
    
    history_id = kwargs.get("history_id")
    if not history_id:
        return CommandResult.failure("history_id is required")
    
    try:
        service = CommandHistoryService()
        entry = service.get(history_id)
        
        if not entry:
            return CommandResult.failure(f"History entry not found: {history_id}")
        
        # Re-execute the command
        registry = CommandRegistry.get_instance()
        result = registry.execute(entry.command_id, context, **entry.args)
        
        return result
    except Exception as e:
        return CommandResult.failure(str(e))


def history_pin_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:pin command."""
    from agentos.core.command.history import CommandHistoryService
    
    history_id = kwargs.get("history_id")
    if not history_id:
        return CommandResult.failure("history_id is required")
    
    note = kwargs.get("note")
    
    try:
        service = CommandHistoryService()
        pin_id = service.pin(history_id, note=note)
        
        return CommandResult.success(
            data={"pin_id": pin_id},
            summary=f"Pinned history entry: {history_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def history_unpin_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:unpin command."""
    from agentos.core.command.history import CommandHistoryService
    
    history_id = kwargs.get("history_id")
    if not history_id:
        return CommandResult.failure("history_id is required")
    
    try:
        service = CommandHistoryService()
        service.unpin(history_id)
        
        return CommandResult.success(
            summary=f"Unpinned history entry: {history_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def history_clear_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:clear command."""
    from agentos.core.command.history import CommandHistoryService
    
    older_than_days = kwargs.get("older_than_days")
    confirmed = kwargs.get("confirmed", False)
    
    if not confirmed:
        return CommandResult.failure(
            "Clear is a dangerous operation. Use confirmed=True to proceed."
        )
    
    try:
        service = CommandHistoryService()
        service.clear(older_than_days=older_than_days)
        
        summary = "History cleared"
        if older_than_days:
            summary = f"History entries older than {older_than_days} days cleared"
        
        return CommandResult.success(summary=summary)
    except Exception as e:
        return CommandResult.failure(str(e))


def history_export_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle history:export command."""
    from pathlib import Path
    from agentos.core.command.history import CommandHistoryService
    
    output_path = kwargs.get("output_path")
    if not output_path:
        return CommandResult.failure("output_path is required")
    
    try:
        service = CommandHistoryService()
        service.export(Path(output_path))
        
        return CommandResult.success(
            summary=f"History exported to: {output_path}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def register_history_commands(registry: CommandRegistry) -> None:
    """Register all History commands to the registry.
    
    Args:
        registry: CommandRegistry instance
    """
    commands = [
        CommandMetadata(
            id="history:list",
            title="List command history",
            hint="Show recent command executions",
            category=CommandCategory.HISTORY,
            handler=history_list_handler,
        ),
        CommandMetadata(
            id="history:show",
            title="Show history entry",
            hint="View details of a history entry",
            category=CommandCategory.HISTORY,
            handler=history_show_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="history:replay",
            title="Replay command",
            hint="Re-execute a command from history",
            category=CommandCategory.HISTORY,
            handler=history_replay_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="history:pin",
            title="Pin history entry",
            hint="Pin a command to Recent",
            category=CommandCategory.HISTORY,
            handler=history_pin_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="history:unpin",
            title="Unpin history entry",
            hint="Remove pin from history entry",
            category=CommandCategory.HISTORY,
            handler=history_unpin_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="history:clear",
            title="Clear history",
            hint="Delete command history entries",
            category=CommandCategory.HISTORY,
            handler=history_clear_handler,
            dangerous=True,
        ),
        CommandMetadata(
            id="history:export",
            title="Export history",
            hint="Export history to JSON file",
            category=CommandCategory.HISTORY,
            handler=history_export_handler,
            needs_arg=True,
        ),
    ]
    
    registry.register_multiple(commands)
