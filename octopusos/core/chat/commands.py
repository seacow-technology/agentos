"""Slash commands for Chat Mode"""

from dataclasses import dataclass
from typing import Dict, Callable, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a slash command execution"""
    success: bool
    message: str
    data: Optional[Any] = None
    should_display: bool = True  # Whether to display result in chat
    
    @classmethod
    def success_result(cls, message: str, data: Any = None) -> "CommandResult":
        """Create a success result"""
        return cls(success=True, message=message, data=data)
    
    @classmethod
    def error_result(cls, message: str) -> "CommandResult":
        """Create an error result"""
        return cls(success=False, message=message)


# Type alias for command handler
CommandHandler = Callable[[str, List[str], Dict[str, Any]], CommandResult]


class SlashCommandRegistry:
    """Registry for slash commands"""
    
    def __init__(self):
        self._commands: Dict[str, CommandHandler] = {}
        self._descriptions: Dict[str, str] = {}
    
    def register(
        self,
        command: str,
        handler: CommandHandler,
        description: str = ""
    ) -> None:
        """Register a slash command
        
        Args:
            command: Command name (without /)
            handler: Handler function
            description: Command description
        """
        self._commands[command] = handler
        self._descriptions[command] = description
        logger.debug(f"Registered slash command: /{command}")
    
    def execute(
        self,
        command: str,
        args: List[str],
        context: Dict[str, Any]
    ) -> CommandResult:
        """Execute a slash command
        
        Args:
            command: Command name (without /)
            args: Command arguments
            context: Execution context (session_id, services, etc.)
        
        Returns:
            CommandResult
        """
        if command not in self._commands:
            return CommandResult.error_result(f"Unknown command: /{command}")
        
        try:
            handler = self._commands[command]
            return handler(command, args, context)
        except Exception as e:
            logger.error(f"Command /{command} failed: {e}", exc_info=True)
            return CommandResult.error_result(f"Command failed: {str(e)}")
    
    def get_commands(self) -> List[str]:
        """Get list of registered commands"""
        return list(self._commands.keys())
    
    def get_description(self, command: str) -> str:
        """Get command description"""
        return self._descriptions.get(command, "")


# Global registry instance
_registry = SlashCommandRegistry()


def get_registry() -> SlashCommandRegistry:
    """Get the global slash command registry"""
    return _registry


def parse_command(user_input: str) -> tuple[Optional[str], List[str], Optional[str]]:
    """Parse user input for slash command
    
    Args:
        user_input: User's input string
    
    Returns:
        Tuple of (command, args, remaining_text)
        - command: Command name (without /) or None if not a command
        - args: List of arguments
        - remaining_text: Text after command (if any)
    """
    if not user_input.startswith("/"):
        return None, [], None
    
    # Remove leading /
    text = user_input[1:].strip()
    
    if not text:
        return None, [], None
    
    # Split into parts
    parts = text.split(maxsplit=1)
    command = parts[0]
    
    # Parse args and remaining text
    if len(parts) > 1:
        rest = parts[1]
        # Simple arg parsing (space-separated)
        args = rest.split()
        remaining = rest
    else:
        args = []
        remaining = None
    
    return command, args, remaining
