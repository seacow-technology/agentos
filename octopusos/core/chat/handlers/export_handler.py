"""/export command handler - Export chat session"""

from typing import List, Dict, Any
import logging
from pathlib import Path
from datetime import datetime

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.chat.service import ChatService
from agentos.core.chat.export import SessionExporter

logger = logging.getLogger(__name__)


def export_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /export command
    
    Usage: /export [markdown|json|openai]
    
    Exports current session to specified format (default: markdown)
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    # Parse format argument
    format_type = "markdown"
    if args:
        format_type = args[0].lower()
        if format_type not in ["markdown", "json", "openai"]:
            return CommandResult.error_result(f"Invalid format: {format_type}. Use 'markdown', 'json', or 'openai'")
    
    try:
        # Get chat service
        chat_service = context.get("chat_service") or ChatService()
        
        # Get session and messages
        session = chat_service.get_session(session_id)
        messages = chat_service.get_messages(session_id)
        
        if not messages:
            return CommandResult.error_result("No messages to export")
        
        # Export to specified format
        exporter = SessionExporter()
        
        if format_type == "markdown":
            content = exporter.to_markdown(session, messages, include_metadata=True)
            ext = "md"
        elif format_type == "json":
            content = exporter.to_json(session, messages, pretty=True)
            ext = "json"
        else:  # openai
            content = exporter.to_openai_format(messages)
            ext = "json"
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in session.title if c.isalnum() or c in (' ', '-', '_'))[:30]
        filename = f"chat_{safe_title}_{timestamp}.{ext}"
        
        # Save to exports directory
        export_dir = Path.cwd() / "exports" / "chat_sessions"
        filepath = export_dir / filename
        
        exporter.save_to_file(content, filepath, create_dirs=True)
        
        logger.info(f"Exported session {session_id} to {filepath}")
        
        return CommandResult.success_result(
            message=f"✓ Session exported to:\n`{filepath}`\n\n**Format**: {format_type}\n**Messages**: {len(messages)}",
            data={
                "filepath": str(filepath),
                "format": format_type,
                "message_count": len(messages)
            }
        )
    
    except Exception as e:
        logger.error(f"Export command failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to export session: {str(e)}")


def register_export_command():
    """Register /export command"""
    registry = get_registry()
    registry.register(
        "export",
        export_handler,
        "Export session to Markdown/JSON"
    )
