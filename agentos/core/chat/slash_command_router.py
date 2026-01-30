"""Slash command router for extension capabilities

This module routes slash commands (e.g., /postman, /hello) to extension capabilities.
It integrates with the ExtensionRegistry to discover available commands and route
them to appropriate extension runners.

Architecture:
- SlashCommandRouter: Main router class that discovers and routes commands
- CommandRoute: Data class representing a routed command
- CommandParser: Parser for command strings and arguments
- CommandInfo: Information about available commands (for autocomplete)

Example:
    router = SlashCommandRouter(registry)

    # Check if message is a slash command
    if router.is_slash_command("/postman get https://api.example.com"):
        route = router.route("/postman get https://api.example.com")
        if route:
            # Execute the command via capability runner
            result = execute_capability(route)
"""

import logging
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.models import CapabilityType, ExtensionRecord

logger = logging.getLogger(__name__)


@dataclass
class CommandRoute:
    """Represents a routed slash command

    Attributes:
        command_name: The slash command (e.g., "/postman")
        extension_id: Extension providing this command (e.g., "tools.postman")
        extension_name: Human-readable extension name
        extension_enabled: Whether the extension is enabled
        capability_name: The capability name (e.g., "tools.postman")
        action_id: The action within the capability (e.g., "get", "test")
        runner: The runner to execute (e.g., "exec.postman_cli")
        args: Parsed command arguments
        raw_args: Raw argument string (unparsed)
        description: Action description
        usage_doc: Usage documentation from docs/USAGE.md
        examples: List of example commands
    """
    command_name: str
    extension_id: str
    extension_name: str
    extension_enabled: bool
    capability_name: str
    action_id: Optional[str]
    runner: str
    args: List[str]
    raw_args: str
    description: str
    usage_doc: Optional[str] = None
    examples: List[str] = None


@dataclass
class CommandInfo:
    """Information about an available slash command

    Used for command autocomplete and help display.
    """
    command_name: str
    extension_id: str
    extension_name: str
    summary: str
    description: str
    examples: List[str]
    enabled: bool


class CommandParser:
    """Parser for slash command strings

    Parses command strings into command name, action, and arguments.
    Handles quoted arguments and special characters.

    Example:
        parser = CommandParser()

        # Simple command
        cmd = parser.parse("/postman get https://api.example.com")
        # cmd.command = "/postman"
        # cmd.action = "get"
        # cmd.args = ["https://api.example.com"]

        # Complex command with flags
        cmd = parser.parse('/postman test "./collection.json" --env dev')
        # cmd.command = "/postman"
        # cmd.action = "test"
        # cmd.args = ["./collection.json", "--env", "dev"]
    """

    def parse(self, message: str) -> Optional[Dict[str, Any]]:
        """Parse slash command message

        Args:
            message: User message starting with /

        Returns:
            Dict with command, action, args, and raw_args, or None if invalid
        """
        if not message.strip().startswith('/'):
            return None

        # Remove leading slash and whitespace
        text = message.strip()[1:]

        if not text:
            return None

        try:
            # Use shlex for proper quoted string handling
            parts = shlex.split(text)
        except ValueError as e:
            # Malformed command (unclosed quotes, etc.)
            logger.warning(f"Failed to parse command: {e}")
            # Fallback to simple split
            parts = text.split()

        if not parts:
            return None

        command = parts[0]

        # Determine action and args
        # Action is optional - some commands might not have sub-actions
        action = None
        args = []

        if len(parts) > 1:
            # Check if second part looks like an action (no special chars)
            second_part = parts[1]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', second_part):
                # Looks like an action
                action = second_part
                args = parts[2:] if len(parts) > 2 else []
            else:
                # Not an action, treat everything as args
                args = parts[1:]

        # Get raw args (everything after command and optional action)
        if action:
            raw_args = text.split(maxsplit=2)[2] if len(text.split(maxsplit=2)) > 2 else ""
        else:
            raw_args = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""

        return {
            'command': f"/{command}",
            'action': action,
            'args': args,
            'raw_args': raw_args
        }


class SlashCommandRouter:
    """Router for slash commands to extension capabilities

    Discovers slash_command capabilities from installed extensions and
    routes user commands to the appropriate extension capability.

    Features:
    - Automatic command discovery from extensions
    - Command caching for performance
    - Support for multi-action commands
    - Usage documentation loading
    - Command validation and error handling

    Example:
        registry = ExtensionRegistry()
        router = SlashCommandRouter(registry)

        # Route a command
        route = router.route("/postman get https://api.example.com")
        if route:
            if not route.extension_enabled:
                print("Extension is disabled")
            else:
                # Execute via capability runner
                execute_capability(route)
        else:
            print("Command not found")
    """

    def __init__(self, registry: ExtensionRegistry, extensions_dir: Optional[Path] = None):
        """Initialize router

        Args:
            registry: ExtensionRegistry instance
            extensions_dir: Directory where extensions are installed
                          (defaults to ~/.agentos/extensions)
        """
        self.registry = registry
        self.parser = CommandParser()

        # Set extensions directory
        if extensions_dir is None:
            from pathlib import Path
            home = Path.home()
            self.extensions_dir = home / ".agentos" / "extensions"
        else:
            self.extensions_dir = extensions_dir

        # Command cache: {"/command_name": (extension_id, capability_config)}
        self.command_cache: Dict[str, tuple] = {}

        # Refresh cache on initialization
        self.refresh_cache()

    def is_slash_command(self, message: str) -> bool:
        """Check if message is a slash command

        Args:
            message: User message

        Returns:
            True if message starts with /
        """
        return message.strip().startswith('/')

    def route(self, message: str) -> Optional[CommandRoute]:
        """Route slash command to extension capability

        Args:
            message: User message (slash command)

        Returns:
            CommandRoute if command is found, None otherwise
        """
        # Parse command
        parsed = self.parser.parse(message)
        if not parsed:
            logger.warning(f"Failed to parse command: {message}")
            return None

        command_name = parsed['command']
        action_id = parsed['action']
        args = parsed['args']
        raw_args = parsed['raw_args']

        # Look up command in cache
        if command_name not in self.command_cache:
            logger.info(f"Command not found: {command_name}")
            return None

        extension_id, capability_config = self.command_cache[command_name]

        # Get extension record
        extension = self.registry.get_extension(extension_id)
        if not extension:
            logger.error(f"Extension not found in registry: {extension_id}")
            return None

        # Parse commands.yaml to get action details
        action_info = self._find_action(extension_id, capability_config, action_id)
        if not action_info:
            # If no action specified and command has a default action, use it
            if not action_id and capability_config.get('default_action'):
                action_id = capability_config['default_action']
                action_info = self._find_action(extension_id, capability_config, action_id)

            if not action_info:
                logger.warning(
                    f"Action not found: {action_id} for command {command_name}"
                )
                # Return route with minimal info (runner can handle)
                action_info = {
                    'id': action_id or 'default',
                    'description': capability_config.get('description', ''),
                    'runner': capability_config.get('runner', 'default')
                }

        # Load usage documentation
        usage_doc = self._load_usage_doc(extension_id)

        # Build route
        route = CommandRoute(
            command_name=command_name,
            extension_id=extension_id,
            extension_name=extension.name,
            extension_enabled=extension.enabled,
            capability_name=capability_config.get('name', extension_id),
            action_id=action_id,
            runner=action_info.get('runner', 'default'),
            args=args,
            raw_args=raw_args,
            description=action_info.get('description', ''),
            usage_doc=usage_doc,
            examples=capability_config.get('examples', [])
        )

        logger.info(
            f"Routed command: {command_name} -> {extension_id}.{action_id} "
            f"(enabled={route.extension_enabled})"
        )

        return route

    def get_available_commands(self, enabled_only: bool = True) -> List[CommandInfo]:
        """Get all available slash commands

        Args:
            enabled_only: Only return commands from enabled extensions

        Returns:
            List of CommandInfo objects
        """
        commands = []

        for command_name, (extension_id, capability_config) in self.command_cache.items():
            extension = self.registry.get_extension(extension_id)
            if not extension:
                continue

            if enabled_only and not extension.enabled:
                continue

            commands.append(CommandInfo(
                command_name=command_name,
                extension_id=extension_id,
                extension_name=extension.name,
                summary=capability_config.get('summary', ''),
                description=capability_config.get('description', ''),
                examples=capability_config.get('examples', []),
                enabled=extension.enabled
            ))

        return sorted(commands, key=lambda c: c.command_name)

    def refresh_cache(self):
        """Refresh command cache from registry

        Should be called when:
        - Extensions are installed/uninstalled
        - Extensions are enabled/disabled
        """
        logger.info("Refreshing slash command cache")

        self.command_cache.clear()

        # Get all installed extensions (both enabled and disabled)
        extensions = self.registry.list_extensions()

        for extension in extensions:
            # Find slash_command capabilities
            for capability in extension.capabilities:
                if capability.type == CapabilityType.SLASH_COMMAND:
                    # Load commands.yaml for this capability
                    commands_config = self._load_commands_config(extension.id)

                    if commands_config and 'slash_commands' in commands_config:
                        for cmd_config in commands_config['slash_commands']:
                            command_name = cmd_config.get('name')
                            if command_name:
                                self.command_cache[command_name] = (
                                    extension.id,
                                    cmd_config
                                )
                                logger.debug(
                                    f"Cached command: {command_name} -> {extension.id}"
                                )

        logger.info(f"Cached {len(self.command_cache)} slash commands")

    def _load_commands_config(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """Load commands.yaml for an extension

        Args:
            extension_id: Extension ID

        Returns:
            Parsed YAML dict or None if not found
        """
        # Try standard location first: commands/commands.yaml
        commands_path = self.extensions_dir / extension_id / "commands" / "commands.yaml"

        # Fallback to legacy location: commands.yaml (root level)
        if not commands_path.exists():
            commands_path = self.extensions_dir / extension_id / "commands.yaml"

        if not commands_path.exists():
            logger.debug(f"No commands.yaml found for {extension_id}")
            return None

        try:
            with open(commands_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load commands.yaml for {extension_id}: {e}")
            return None

    def _find_action(
        self,
        extension_id: str,
        capability_config: Dict[str, Any],
        action_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find action details in capability config

        Args:
            extension_id: Extension ID
            capability_config: Command configuration from commands.yaml
            action_id: Action ID to find

        Returns:
            Action info dict or None
        """
        if not action_id:
            return None

        # Support two formats:
        # 1. New format: actions directly under command config
        # 2. Old format: actions under maps_to
        actions = capability_config.get('actions', [])
        if not actions:
            maps_to = capability_config.get('maps_to', {})
            actions = maps_to.get('actions', [])

        for action in actions:
            if action.get('id') == action_id:
                return action

        return None

    def _load_usage_doc(self, extension_id: str) -> Optional[str]:
        """Load usage documentation for an extension

        Args:
            extension_id: Extension ID

        Returns:
            Usage documentation content or None
        """
        docs_path = self.extensions_dir / extension_id / "docs" / "USAGE.md"

        if not docs_path.exists():
            logger.debug(f"No USAGE.md found for {extension_id}")
            return None

        try:
            with open(docs_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load USAGE.md for {extension_id}: {e}")
            return None


def build_command_not_found_response(command_name: str) -> Dict[str, Any]:
    """Build response for unknown command

    Args:
        command_name: The command that was not found

    Returns:
        Response dict with error message
    """
    return {
        "type": "extension_prompt",
        "command": command_name,
        "message": (
            f"Command '{command_name}' is not available. "
            "This command may require an extension to be installed."
        ),
        "suggestion": {
            "action": "search_extensions",
            "query": command_name.lstrip('/')
        }
    }


def build_extension_disabled_response(route: CommandRoute) -> Dict[str, Any]:
    """Build response for disabled extension

    Args:
        route: Command route with disabled extension

    Returns:
        Response dict with enable prompt
    """
    return {
        "type": "extension_prompt",
        "command": route.command_name,
        "message": (
            f"Command '{route.command_name}' is available but the "
            f"'{route.extension_name}' extension is currently disabled."
        ),
        "extension_info": {
            "id": route.extension_id,
            "name": route.extension_name,
            "status": "disabled"
        },
        "action": {
            "type": "enable_extension",
            "extension_id": route.extension_id,
            "label": f"Enable {route.extension_name}"
        }
    }
