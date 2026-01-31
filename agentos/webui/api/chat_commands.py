"""
Chat Commands API - Slash command discovery and management

GET /api/chat/slash-commands - Get available slash commands (for autocomplete)

This API provides information about available slash commands from extensions
and built-in commands. Used by the frontend for command autocomplete and help.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import logging

from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.chat.slash_command_router import SlashCommandRouter
from agentos.core.chat.commands import get_registry as get_builtin_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (initialized on first use)
_extension_registry: Optional[ExtensionRegistry] = None
_slash_command_router: Optional[SlashCommandRouter] = None


def get_extension_registry() -> ExtensionRegistry:
    """Get or create ExtensionRegistry instance (singleton)"""
    global _extension_registry
    if _extension_registry is None:
        _extension_registry = ExtensionRegistry()
        logger.info("ExtensionRegistry initialized")
    return _extension_registry


def get_slash_command_router() -> SlashCommandRouter:
    """Get or create SlashCommandRouter instance (singleton)"""
    global _slash_command_router
    if _slash_command_router is None:
        from pathlib import Path
        from agentos.store import get_store_path

        registry = get_extension_registry()

        # Use project's store/extensions directory
        extensions_dir = get_store_path("extensions")

        _slash_command_router = SlashCommandRouter(
            registry,
            extensions_dir=Path(extensions_dir)
        )
        logger.info(f"SlashCommandRouter initialized with extensions_dir={extensions_dir}")
    return _slash_command_router


class SlashCommandInfo(BaseModel):
    """Information about a slash command"""
    name: str
    source: str  # "extension" or "builtin"
    extension_id: Optional[str] = None
    extension_name: Optional[str] = None
    summary: str
    description: str
    examples: List[str]
    enabled: bool


class SlashCommandsResponse(BaseModel):
    """Response for GET /api/chat/slash-commands"""
    commands: List[SlashCommandInfo]
    total: int


@router.post("/chat/slash-commands/refresh")
async def refresh_slash_commands():
    """Refresh slash command cache

    Forces the router to reload all commands from extensions.
    Useful after installing/uninstalling extensions without restarting server.

    Returns:
        Success message with command count
    """
    try:
        router = get_slash_command_router()
        router.refresh_cache()

        command_count = len(router.command_cache)

        return {
            "success": True,
            "message": f"Refreshed slash command cache",
            "command_count": command_count,
            "commands": list(router.command_cache.keys())
        }
    except Exception as e:
        logger.error(f"Failed to refresh slash commands: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": "Failed to refresh slash commands"
            }
        )


@router.get("/chat/slash-commands", response_model=SlashCommandsResponse)
async def get_slash_commands(
    enabled_only: bool = Query(True, description="Only return enabled commands")
):
    """Get available slash commands

    Returns list of available slash commands from both extensions and built-in commands.
    Used by frontend for command autocomplete and help display.

    Args:
        enabled_only: Only return commands from enabled extensions

    Returns:
        SlashCommandsResponse with list of commands
    """
    try:
        router = get_slash_command_router()

        # Get extension commands
        extension_commands = router.get_available_commands(enabled_only=enabled_only)

        # Convert to response format
        commands = []
        for cmd in extension_commands:
            commands.append(SlashCommandInfo(
                name=cmd.command_name,
                source="extension",
                extension_id=cmd.extension_id,
                extension_name=cmd.extension_name,
                summary=cmd.summary,
                description=cmd.description,
                examples=cmd.examples,
                enabled=cmd.enabled
            ))

        # Add built-in commands
        builtin_registry = get_builtin_registry()
        builtin_commands = builtin_registry.get_commands()

        for cmd_name in builtin_commands:
            description = builtin_registry.get_description(cmd_name)
            commands.append(SlashCommandInfo(
                name=f"/{cmd_name}",
                source="builtin",
                extension_id=None,
                extension_name=None,
                summary=description,
                description=description,
                examples=[f"/{cmd_name}"],
                enabled=True
            ))

        logger.info(f"Returning {len(commands)} slash commands")

        return SlashCommandsResponse(
            commands=sorted(commands, key=lambda c: c.name),
            total=len(commands)
        )

    except Exception as e:
        logger.error(f"Failed to get slash commands: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get slash commands: {str(e)}"
        )


@router.post("/chat/refresh-commands")
async def refresh_slash_commands():
    """Refresh slash command cache

    Should be called after:
    - Installing/uninstalling extensions
    - Enabling/disabling extensions

    Returns:
        Success message with command count
    """
    try:
        router = get_slash_command_router()
        router.refresh_cache()

        # Count available commands
        commands = router.get_available_commands(enabled_only=False)

        logger.info(f"Refreshed slash command cache: {len(commands)} commands")

        return {
            "success": True,
            "message": "Slash command cache refreshed",
            "total_commands": len(commands)
        }

    except Exception as e:
        logger.error(f"Failed to refresh slash commands: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh slash commands: {str(e)}"
        )
