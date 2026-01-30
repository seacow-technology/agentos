"""Help command handler"""

from typing import List, Dict, Any
from agentos.core.chat.commands import CommandResult, get_registry


def handle_help_command(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handle /help command

    Args:
        command: Command name
        args: Command arguments
        context: Execution context (may contain 'router' for extension commands)

    Returns:
        CommandResult with help information
    """
    registry = get_registry()
    commands = sorted(registry.get_commands())

    if not commands:
        return CommandResult.success_result("No commands registered.")

    # Core Commands section
    help_text = "**Core Commands:**\n\n"

    # Built-in commands with descriptions
    command_docs = {
        "summary": "Generate a summary of the conversation",
        "extract": "Extract entities or facts from the conversation",
        "task": "Manage tasks in the current session",
        "model": "Switch between local and cloud models",
        "context": "Show context information for the current session",
        "stream": "Toggle streaming mode for responses",
        "export": "Export conversation history",
        "help": "Show this help message"
    }

    for cmd in commands:
        description = command_docs.get(cmd, registry.get_description(cmd) or "No description")
        help_text += f"- **/{cmd}** - {description}\n"

    # Extension Commands section
    router = context.get('router')
    if router:
        try:
            extension_commands = router.get_available_commands(enabled_only=True)

            if extension_commands:
                help_text += "\n**Extension Commands:**\n\n"

                for cmd_info in extension_commands:
                    # Format: - /command - Description (Extension Name)
                    description = cmd_info.summary or cmd_info.description or "No description"
                    extension_label = cmd_info.extension_name
                    help_text += f"- **{cmd_info.command_name}** - {description} ({extension_label})\n"
        except Exception as e:
            # If router fails, just skip extension commands
            pass

    help_text += "\n**Usage:**\n"
    help_text += "Type `/command_name` followed by any arguments.\n"
    help_text += "Example: `/model cloud`"

    return CommandResult.success_result(help_text)


def register_help_command():
    """Register the help command"""
    registry = get_registry()
    registry.register(
        command="help",
        handler=handle_help_command,
        description="Show help information for available commands"
    )
