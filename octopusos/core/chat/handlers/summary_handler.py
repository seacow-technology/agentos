"""/summary command handler - Summarize recent conversation"""

from typing import List, Dict, Any
import logging

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService

logger = logging.getLogger(__name__)


def summary_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /summary command
    
    Usage: /summary [N]
    
    Summarizes the last N rounds of conversation (default: 10)
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    # Parse count argument
    count = 10
    if args:
        try:
            count = int(args[0])
        except ValueError:
            return CommandResult.error_result(f"Invalid count: {args[0]}")
    
    try:
        # Get chat service
        chat_service = context.get("chat_service") or ChatService()
        
        # Get recent messages
        messages = chat_service.get_recent_messages(session_id, count=count * 2)  # Each round = user + assistant
        
        if not messages:
            return CommandResult.error_result("No messages to summarize")
        
        # Build summary (simple version for now)
        summary_lines = [
            f"**Conversation Summary** (last {len(messages)} messages):",
            ""
        ]
        
        for msg in messages:
            if msg.role == "user":
                preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                summary_lines.append(f"👤 User: {preview}")
            elif msg.role == "assistant":
                preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                summary_lines.append(f"🤖 Assistant: {preview}")
        
        summary_text = "\n".join(summary_lines)
        
        logger.info(f"Generated summary for session {session_id}: {len(messages)} messages")
        
        return CommandResult.success_result(
            message=summary_text,
            data={"message_count": len(messages), "session_id": session_id}
        )
    
    except Exception as e:
        logger.error(f"Summary command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to generate summary: {str(e)}")


def register_summary_command():
    """Register /summary command"""
    registry = get_registry()
    registry.register(
        "summary",
        summary_handler,
        "Summarize recent conversation"
    )
