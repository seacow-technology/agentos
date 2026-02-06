"""/extract command handler - Extract requirements from conversation"""

from typing import List, Dict, Any
import logging

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService

logger = logging.getLogger(__name__)


def extract_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /extract command
    
    Usage: /extract
    
    Extracts requirements and key decisions from recent conversation
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    try:
        # Get chat service
        chat_service = context.get("chat_service") or ChatService()
        
        # Get recent messages
        messages = chat_service.get_recent_messages(session_id, count=20)
        
        if not messages:
            return CommandResult.error_result("No messages to extract from")
        
        # Build extraction (simple version - in production, use LLM)
        requirements = []
        decisions = []
        
        for msg in messages:
            content = msg.content.lower()
            
            # Simple heuristics for requirements
            if any(keyword in content for keyword in ["need to", "should", "must", "require"]):
                preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                requirements.append(preview)
            
            # Simple heuristics for decisions
            if any(keyword in content for keyword in ["decided", "will use", "going with", "choose"]):
                preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                decisions.append(preview)
        
        # Format result
        result_lines = [
            "**Requirements Extraction**",
            "",
            "## Requirements",
        ]
        
        if requirements:
            for i, req in enumerate(requirements, 1):
                result_lines.append(f"{i}. {req}")
        else:
            result_lines.append("_(No requirements detected)_")
        
        result_lines.extend([
            "",
            "## Key Decisions",
        ])
        
        if decisions:
            for i, dec in enumerate(decisions, 1):
                result_lines.append(f"{i}. {dec}")
        else:
            result_lines.append("_(No decisions detected)_")
        
        result_text = "\n".join(result_lines)
        
        logger.info(f"Extracted requirements for session {session_id}: {len(requirements)} reqs, {len(decisions)} decisions")
        
        return CommandResult.success_result(
            message=result_text,
            data={
                "requirements": requirements,
                "decisions": decisions,
                "session_id": session_id
            }
        )
    
    except Exception as e:
        logger.error(f"Extract command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to extract requirements: {str(e)}")


def register_extract_command():
    """Register /extract command"""
    registry = get_registry()
    registry.register(
        "extract",
        extract_handler,
        "Extract requirements from conversation"
    )
