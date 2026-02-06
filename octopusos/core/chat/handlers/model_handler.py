"""/model command handler - Switch model routing"""

from typing import List, Dict, Any
import logging

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService

logger = logging.getLogger(__name__)


def model_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /model command
    
    Usage: /model local|cloud
    
    Switches between local and cloud model routing
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    if not args:
        return CommandResult.error_result("Usage: /model local|cloud")
    
    mode = args[0].lower()
    if mode not in ["local", "cloud"]:
        return CommandResult.error_result(f"Invalid mode: {mode}. Use 'local' or 'cloud'")
    
    try:
        # Update session metadata
        chat_service = context.get("chat_service") or ChatService()
        
        metadata_update = {
            "model_route": mode,
            "provider": "ollama" if mode == "local" else "openai"
        }
        
        chat_service.update_session_metadata(session_id, metadata_update)
        
        emoji = "●" if mode == "local" else "☁️"
        logger.info(f"Switched to {mode} model for session {session_id}")
        
        return CommandResult.success_result(
            message=f"{emoji} Switched to **{mode}** model routing",
            data={"mode": mode, "session_id": session_id}
        )
    
    except Exception as e:
        logger.error(f"Model command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to switch model: {str(e)}")


def register_model_command():
    """Register /model command"""
    registry = get_registry()
    registry.register(
        "model",
        model_handler,
        "Switch between local and cloud models"
    )
