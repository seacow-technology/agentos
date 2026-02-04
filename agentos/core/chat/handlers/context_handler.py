"""/context command handler - Show/manage context"""

from typing import List, Dict, Any
import logging
import json

from agentos.core.chat.commands import CommandResult, get_registry

logger = logging.getLogger(__name__)


def context_handler(command: str, args: List[str], context: Dict[str, Any]) -> CommandResult:
    """Handler for /context command
    
    Usage: 
      /context show        - Show current context info
      /context show --full - Show assembled messages summary
      /context pin         - Pin last message to memory
      /context diff        - Diff last two context snapshots
      /context diff --last N - Diff last N snapshots
    """
    session_id = context.get("session_id")
    if not session_id:
        return CommandResult.error_result("No session context")
    
    if not args:
        return CommandResult.error_result("Usage: /context show|pin|diff [--full|--last N]")
    
    subcommand = args[0].lower()
    
    if subcommand == "show":
        # Check for --full flag
        full_mode = len(args) > 1 and args[1] == "--full"
        return _show_context(context, full_mode=full_mode)
    elif subcommand == "pin":
        return _pin_to_memory(context)
    elif subcommand == "diff":
        # Check for --last N flag
        last_n = None
        if len(args) > 1 and args[1] == "--last" and len(args) > 2:
            try:
                last_n = int(args[2])
            except ValueError:
                return CommandResult.error_result(f"Invalid number: {args[2]}")
        return _diff_context(context, last_n=last_n)
    else:
        return CommandResult.error_result(f"Unknown subcommand: {subcommand}")


def _show_context(context: Dict[str, Any], full_mode: bool = False) -> CommandResult:
    """Show current context information
    
    Args:
        context: Command context
        full_mode: If True, show assembled messages summary with token estimates
    """
    session_id = context.get("session_id")
    
    try:
        from agentos.core.chat.service import ChatService
        
        chat_service = context.get("chat_service") or ChatService()
        session = chat_service.get_session(session_id)
        message_count = chat_service.count_messages(session_id)
        
        # Format context info
        info_lines = [
            "**Current Context Information**",
            "",
            f"**Session ID**: {session_id[:12]}...",
            f"**Title**: {session.title}",
            f"**Messages**: {message_count}",
            "",
            "**Metadata**:",
        ]
        
        for key, value in session.metadata.items():
            info_lines.append(f"  - {key}: {value}")
        
        if session.task_id:
            info_lines.extend([
                "",
                f"**Linked Task**: {session.task_id[:12]}..."
            ])
        
        # Full mode: show assembled messages summary
        if full_mode:
            info_lines.extend([
                "",
                "=" * 60,
                "**Assembled Messages Summary**",
                "=" * 60
            ])
            
            try:
                # Get recent messages
                messages = chat_service.get_recent_messages(session_id, count=10)
                
                # Calculate token estimates
                total_tokens = 0
                by_source = {"user": 0, "assistant": 0, "system": 0, "rag": 0, "memory": 0}
                
                for msg in messages:
                    # Estimate tokens (rough: 4 chars = 1 token)
                    content_tokens = len(msg.content) // 4
                    total_tokens += content_tokens
                    
                    # Track by source
                    source = msg.metadata.get("source", msg.role) if msg.metadata else msg.role
                    if source in by_source:
                        by_source[source] += content_tokens
                    
                    # Show message summary
                    preview = msg.content[:120].replace("\n", " ")
                    if len(msg.content) > 120:
                        preview += "..."
                    
                    info_lines.append(f"\n**[{msg.role.upper()}]** ~{content_tokens} tokens")
                    info_lines.append(f"  {preview}")
                    
                    if msg.metadata:
                        meta_items = []
                        if "source" in msg.metadata:
                            meta_items.append(f"source={msg.metadata['source']}")
                        if "citations" in msg.metadata:
                            meta_items.append(f"citations={len(msg.metadata['citations'])}")
                        if meta_items:
                            info_lines.append(f"  _Meta: {', '.join(meta_items)}_")
                
                # Token summary
                info_lines.extend([
                    "",
                    "**📈 Token Budget (estimated)**",
                    f"Total: ~{total_tokens} tokens"
                ])
                for source, tokens in by_source.items():
                    if tokens > 0:
                        info_lines.append(f"  - {source.capitalize()}: ~{tokens} tokens")
            
            except Exception as e:
                info_lines.append(f"\n⚠️  Could not load message summary: {e}")
        
        info_text = "\n".join(info_lines)
        
        return CommandResult.success_result(
            message=info_text,
            data={"session": session.to_dict(), "message_count": message_count}
        )
    
    except Exception as e:
        logger.error(f"Context show failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to show context: {str(e)}")


def _pin_to_memory(context: Dict[str, Any]) -> CommandResult:
    """Pin last assistant message to memory"""
    session_id = context.get("session_id")
    
    try:
        from agentos.core.chat.service import ChatService
        from agentos.core.memory.service import MemoryService
        
        chat_service = context.get("chat_service") or ChatService()
        memory_service = context.get("memory_service") or MemoryService()
        
        # Get last assistant message
        messages = chat_service.get_recent_messages(session_id, count=10)
        assistant_messages = [m for m in messages if m.role == "assistant"]
        
        if not assistant_messages:
            return CommandResult.error_result("No assistant messages to pin")
        
        last_message = assistant_messages[-1]
        
        # Get session for project_id
        session = chat_service.get_session(session_id)
        project_id = session.metadata.get("project_id", "default")
        
        # Create memory item
        memory_item = {
            "scope": "project",
            "type": "decision",
            "content": {
                "summary": last_message.content[:200],
                "details": last_message.content
            },
            "tags": ["chat", "pinned"],
            "sources": [session_id],
            "project_id": project_id,
            "confidence": 0.9
        }

        memory_id = memory_service.upsert("webui_chat", memory_item)

        logger.info(f"Pinned message {last_message.message_id} to memory: {memory_id}")
        
        return CommandResult.success_result(
            message=f"✓ Pinned message to Memory: **{memory_id[:12]}...**",
            data={"memory_id": memory_id, "message_id": last_message.message_id}
        )
    
    except Exception as e:
        logger.error(f"Context pin failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to pin to memory: {str(e)}")


def _diff_context(context: Dict[str, Any], last_n: int = None) -> CommandResult:
    """Show context diff between snapshots
    
    Args:
        context: Command context
        last_n: If specified, show diffs for last N snapshots
    """
    session_id = context.get("session_id")
    
    try:
        from agentos.core.chat.service import ChatService
        from agentos.core.chat.context_diff import ContextDiffer
        
        chat_service = context.get("chat_service") or ChatService()
        db_path = chat_service.db_path
        
        differ = ContextDiffer(db_path=db_path)
        
        # List available snapshots
        snapshots = differ.list_snapshots(session_id, limit=20)
        
        if len(snapshots) < 2:
            return CommandResult.error_result(
                f"Need at least 2 snapshots to diff (found {len(snapshots)}). "
                "Send a few messages first."
            )
        
        # If last_n specified, show multiple diffs
        if last_n and last_n > 1:
            if last_n > len(snapshots):
                last_n = len(snapshots)
            
            result_lines = [
                f"**Context Diffs (Last {last_n} Snapshots)**",
                ""
            ]
            
            for i in range(min(last_n - 1, len(snapshots) - 1)):
                curr_snapshot_id = snapshots[i]["snapshot_id"]
                prev_snapshot_id = snapshots[i + 1]["snapshot_id"]
                
                diff = differ.diff(prev_snapshot_id, curr_snapshot_id)
                
                result_lines.extend([
                    f"**Diff #{i + 1}** ({prev_snapshot_id[:8]} → {curr_snapshot_id[:8]})",
                    diff.format_summary(),
                    ""
                ])
            
            return CommandResult.success_result(
                message="\n".join(result_lines),
                data={"session_id": session_id, "diff_count": last_n - 1}
            )
        
        # Default: diff last two snapshots
        diff = differ.diff_last_two(session_id)
        
        if not diff:
            return CommandResult.error_result("Could not compute diff")
        
        # Format result
        result_lines = [
            diff.format_summary(),
            "",
            "**Token Breakdown**:"
        ]
        
        for source_type, values in diff.breakdown.items():
            if values["delta"] != 0:
                sign = "+" if values["delta"] >= 0 else ""
                result_lines.append(
                    f"  - {source_type.capitalize()}: {values['prev']} → {values['curr']} "
                    f"({sign}{values['delta']})"
                )
        
        return CommandResult.success_result(
            message="\n".join(result_lines),
            data=diff.to_dict()
        )
    
    except Exception as e:
        logger.error(f"Context diff failed: {e}", exc_info=True)
        return CommandResult.error_result(f"Failed to diff context: {str(e)}")


def register_context_command():
    """Register /context command"""
    registry = get_registry()
    registry.register(
        "context",
        context_handler,
        "Show or manage conversation context"
    )
