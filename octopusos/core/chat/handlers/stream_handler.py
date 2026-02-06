"""/stream command handler - Toggle streaming mode"""

from typing import List, Dict, Any
import logging

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService

logger = logging.getLogger(__name__)


def stream_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /stream command
    
    Usage: /stream on|off
    
    Toggles streaming mode for model responses
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    if not args:
        # Show current status
        chat_service = context.get("chat_service") or ChatService()
        session = chat_service.get_session(session_id)
        stream_enabled = session.metadata.get("stream_enabled", False)
        status = "**enabled**" if stream_enabled else "**disabled**"
        return CommandResult.success_result(
            message=f"Streaming is currently {status}.\n\nUse `/stream on` or `/stream off` to toggle.",
            data={"stream_enabled": stream_enabled}
        )
    
    mode = args[0].lower()
    if mode not in ["on", "off"]:
        return CommandResult.error_result(f"Invalid mode: {mode}. Use 'on' or 'off'")
    
    try:
        # Update session metadata
        chat_service = context.get("chat_service") or ChatService()
        
        stream_enabled = (mode == "on")
        metadata_update = {
            "stream_enabled": stream_enabled
        }
        
        chat_service.update_session_metadata(session_id, metadata_update)
        
        emoji = "⚡" if stream_enabled else "📝"
        logger.info(f"Set streaming to {mode} for session {session_id}")
        
        return CommandResult.success_result(
            message=f"{emoji} Streaming mode **{mode}**",
            data={"stream_enabled": stream_enabled}
        )
    
    except Exception as e:
        logger.error(f"Stream command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to toggle streaming: {str(e)}")


def register_stream_command():
    """Register /stream command"""
    registry = get_registry()
    registry.register(
        "stream",
        stream_handler,
        "Toggle streaming mode for responses"
    )
