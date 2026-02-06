"""Session export utilities for Chat Mode"""

from typing import List, Dict, Any
import json
from datetime import datetime
from pathlib import Path

from agentos.core.chat.models import ChatSession, ChatMessage


class SessionExporter:
    """Export chat sessions to various formats"""
    
    @staticmethod
    def to_markdown(
        session: ChatSession,
        messages: List[ChatMessage],
        include_metadata: bool = True
    ) -> str:
        """Export session to Markdown format
        
        Args:
            session: ChatSession object
            messages: List of ChatMessage objects
            include_metadata: Whether to include session metadata
        
        Returns:
            Markdown string
        """
        lines = []
        
        # Header
        lines.append(f"# {session.title}")
        lines.append("")
        
        if include_metadata:
            lines.append("## Session Info")
            lines.append("")
            lines.append(f"- **Session ID**: `{session.session_id}`")
            lines.append(f"- **Created**: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"- **Updated**: {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"- **Messages**: {len(messages)}")
            
            if session.task_id:
                lines.append(f"- **Linked Task**: `{session.task_id}`")
            
            if session.metadata:
                lines.append("")
                lines.append("**Configuration**:")
                for key, value in session.metadata.items():
                    lines.append(f"- {key}: `{value}`")
            
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # Messages
        lines.append("## Conversation")
        lines.append("")
        
        for msg in messages:
            if msg.role == "system":
                continue  # Skip system messages in export
            
            # Role header
            if msg.role == "user":
                role_label = "👤 **User**"
            elif msg.role == "assistant":
                role_label = "🤖 **Assistant**"
            else:
                role_label = f"**{msg.role.capitalize()}**"
            
            timestamp = msg.created_at.strftime("%H:%M:%S")
            lines.append(f"### {role_label} _{timestamp}_")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            
            # Add metadata if available
            if include_metadata and msg.metadata:
                if "rag_chunks" in msg.metadata or "command" in msg.metadata:
                    lines.append("<details>")
                    lines.append("<summary>Metadata</summary>")
                    lines.append("")
                    lines.append("```json")
                    lines.append(json.dumps(msg.metadata, indent=2))
                    lines.append("```")
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"_Exported from AgentOS Chat Mode on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        
        return "\n".join(lines)
    
    @staticmethod
    def to_json(
        session: ChatSession,
        messages: List[ChatMessage],
        pretty: bool = True
    ) -> str:
        """Export session to JSON format
        
        Args:
            session: ChatSession object
            messages: List of ChatMessage objects
            pretty: Whether to pretty-print JSON
        
        Returns:
            JSON string
        """
        data = {
            "session": session.to_dict(),
            "messages": [msg.to_dict() for msg in messages],
            "export_metadata": {
                "exported_at": datetime.now().isoformat(),
                "exporter": "AgentOS Chat Mode",
                "version": "1.0"
            }
        }
        
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return json.dumps(data, ensure_ascii=False)
    
    @staticmethod
    def to_openai_format(messages: List[ChatMessage]) -> str:
        """Export messages in OpenAI API format
        
        Args:
            messages: List of ChatMessage objects
        
        Returns:
            JSON string with OpenAI-formatted messages
        """
        openai_messages = [msg.to_openai_format() for msg in messages]
        return json.dumps(openai_messages, indent=2, ensure_ascii=False)
    
    @staticmethod
    def save_to_file(
        content: str,
        filepath: Path,
        create_dirs: bool = True
    ) -> None:
        """Save exported content to file
        
        Args:
            content: Content to save
            filepath: Path to save file
            create_dirs: Whether to create parent directories
        """
        if create_dirs:
            filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
