"""Chat Summarizer - Automatically generate summaries for context governance"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import hashlib
import json
from datetime import datetime, timezone

from agentos.core.chat.models import ChatMessage
from agentos.core.chat.service import ChatService
from agentos.core.chat.adapters import create_adapter
from agentos.util.ulid import ulid
from agentos.core.time import utc_now, utc_now_ms


logger = logging.getLogger(__name__)


@dataclass
class SummaryArtifact:
    """Summary artifact metadata"""
    artifact_id: str
    session_id: str
    content: str
    derived_from_msg_ids: List[str]
    tokens_saved: int
    version: int
    created_at: int  # Unix epoch ms
    metadata: Dict[str, Any]


class ChatSummarizer:
    """Generates summaries of chat history to reduce token usage"""
    
    def __init__(
        self,
        chat_service: Optional[ChatService] = None,
        db_path: Optional[str] = None
    ):
        """Initialize ChatSummarizer
        
        Args:
            chat_service: ChatService instance
            db_path: Database path (for direct artifact storage)
        """
        self.chat_service = chat_service or ChatService()
        self.db_path = db_path or self.chat_service.db_path
    
    def auto_summarize(
        self,
        session_id: str,
        message_range: tuple[int, int],
        provider: str = "local",
        model: Optional[str] = None
    ) -> SummaryArtifact:
        """Automatically generate summary for a range of messages
        
        Args:
            session_id: Chat session ID
            message_range: (start_idx, end_idx) - message indices to summarize
            provider: "local" or "cloud"
            model: Optional model override
        
        Returns:
            SummaryArtifact with summary content and metadata
        
        Raises:
            ValueError: If message range is invalid
            RuntimeError: If summary generation fails
        """
        logger.info(f"Auto-summarizing session {session_id}, range {message_range}")
        
        # 1. Load messages in range
        all_messages = self.chat_service.get_messages(session_id)
        start_idx, end_idx = message_range
        
        if start_idx < 0 or end_idx > len(all_messages) or start_idx >= end_idx:
            raise ValueError(f"Invalid message range: {message_range} (total: {len(all_messages)})")
        
        messages_to_summarize = all_messages[start_idx:end_idx]
        logger.debug(f"Loaded {len(messages_to_summarize)} messages to summarize")
        
        # 2. Calculate tokens before
        tokens_before = sum(msg.estimate_tokens() for msg in messages_to_summarize)
        
        # 3. Generate summary using LLM
        summary_text = self._generate_summary(
            messages=messages_to_summarize,
            provider=provider,
            model=model
        )
        
        # 4. Calculate tokens after
        tokens_after = int(len(summary_text) * 1.3)
        tokens_saved = tokens_before - tokens_after
        
        logger.info(f"Summary generated: {tokens_before} → {tokens_after} tokens (saved {tokens_saved})")
        
        # 5. Create artifact
        artifact_id = ulid()
        derived_from_msg_ids = [msg.message_id for msg in messages_to_summarize]
        
        # 6. Find existing summaries to determine version
        existing_summaries = self._get_existing_summaries(session_id)
        version = len(existing_summaries) + 1
        
        # 7. Store artifact in database
        created_at = utc_now_ms()
        metadata = {
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_saved,
            "message_range": message_range,
            "provider": provider,
            "model": model or self._get_default_model(provider),
            "replace_strategy": "window_replacement"
        }
        
        self._store_artifact(
            artifact_id=artifact_id,
            session_id=session_id,
            content=summary_text,
            derived_from_msg_ids=derived_from_msg_ids,
            version=version,
            created_at=created_at,
            metadata=metadata
        )
        
        return SummaryArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            content=summary_text,
            derived_from_msg_ids=derived_from_msg_ids,
            tokens_saved=tokens_saved,
            version=version,
            created_at=created_at,
            metadata=metadata
        )
    
    def _generate_summary(
        self,
        messages: List[ChatMessage],
        provider: str,
        model: Optional[str]
    ) -> str:
        """Generate summary text using LLM
        
        Args:
            messages: Messages to summarize
            provider: "local" or "cloud"
            model: Optional model override
        
        Returns:
            Summary text
        """
        # Build prompt
        conversation_text = self._format_messages_for_summary(messages)
        
        summary_prompt = f"""Please provide a concise summary of the following conversation.
Focus on:
1. Key topics discussed
2. Important decisions made
3. Action items or next steps
4. Technical details worth remembering

Keep the summary factual and preserve critical information.

Conversation:
{conversation_text}

Summary:"""
        
        # Prepare messages in OpenAI format
        llm_messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes conversations concisely while preserving important details."},
            {"role": "user", "content": summary_prompt}
        ]
        
        # Select model
        if not model:
            model = self._get_default_model(provider)
        
        # Generate using adapter
        try:
            adapter = create_adapter(provider=provider, model=model)
            summary = adapter.generate(
                messages=llm_messages,
                temperature=0.3,  # Lower temperature for factual summaries
                max_tokens=1000
            )
            return summary.strip()
        
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Fallback: simple truncation summary
            return self._fallback_summary(messages)
    
    def _format_messages_for_summary(self, messages: List[ChatMessage]) -> str:
        """Format messages for summary prompt
        
        Args:
            messages: Messages to format
        
        Returns:
            Formatted conversation text
        """
        lines = []
        for msg in messages:
            role_label = msg.role.upper()
            # Truncate very long messages
            content = msg.content[:1000] + "..." if len(msg.content) > 1000 else msg.content
            lines.append(f"{role_label}: {content}")
        
        return "\n\n".join(lines)
    
    def _fallback_summary(self, messages: List[ChatMessage]) -> str:
        """Generate fallback summary without LLM
        
        Args:
            messages: Messages to summarize
        
        Returns:
            Simple summary text
        """
        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        
        summary_parts = [
            f"Summary of {len(messages)} messages:",
            f"- {len(user_msgs)} user messages",
            f"- {len(assistant_msgs)} assistant responses"
        ]
        
        # Add first and last message preview
        if messages:
            first_preview = messages[0].content[:100]
            last_preview = messages[-1].content[:100]
            summary_parts.extend([
                f"- First message: {first_preview}...",
                f"- Last message: {last_preview}..."
            ])
        
        return "\n".join(summary_parts)
    
    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider
        
        Args:
            provider: "local" or "cloud"
        
        Returns:
            Model name
        """
        if provider == "local":
            return "qwen2.5:14b"
        else:
            return "gpt-4o-mini"
    
    def _get_existing_summaries(self, session_id: str) -> List[str]:
        """Get existing summary artifact IDs for session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of artifact IDs
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT artifact_id
                FROM artifacts
                WHERE session_id = ? AND artifact_type = 'summary'
                ORDER BY created_at ASC
            """, (session_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row["artifact_id"] for row in rows]
        
        except Exception as e:
            logger.warning(f"Failed to query existing summaries: {e}")
            return []
    
    def _store_artifact(
        self,
        artifact_id: str,
        session_id: str,
        content: str,
        derived_from_msg_ids: List[str],
        version: int,
        created_at: int,
        metadata: Dict[str, Any]
    ):
        """Store summary artifact in database
        
        Args:
            artifact_id: Artifact ID (ULID)
            session_id: Session ID
            content: Summary text
            derived_from_msg_ids: List of message IDs this summary is derived from
            version: Artifact version
            created_at: Unix epoch ms
            metadata: Additional metadata
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store lineage in metadata
            full_metadata = {
                **metadata,
                "derived_from_msg_ids": derived_from_msg_ids
            }
            
            cursor.execute("""
                INSERT INTO artifacts (
                    artifact_id, artifact_type, session_id, task_id,
                    title, content, content_json, version,
                    created_at, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact_id,
                "summary",
                session_id,
                None,  # task_id (optional)
                f"Summary v{version}",
                content,
                None,  # content_json
                version,
                created_at,
                "system",
                json.dumps(full_metadata)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored artifact {artifact_id} (summary v{version})")
        
        except Exception as e:
            logger.error(f"Failed to store artifact: {e}")
            raise RuntimeError(f"Artifact storage failed: {e}")
    
    def get_summary(self, artifact_id: str) -> Optional[SummaryArtifact]:
        """Retrieve a summary artifact by ID
        
        Args:
            artifact_id: Artifact ID
        
        Returns:
            SummaryArtifact or None if not found
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT *
                FROM artifacts
                WHERE artifact_id = ? AND artifact_type = 'summary'
            """, (artifact_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            
            return SummaryArtifact(
                artifact_id=row["artifact_id"],
                session_id=row["session_id"],
                content=row["content"],
                derived_from_msg_ids=metadata.get("derived_from_msg_ids", []),
                tokens_saved=metadata.get("tokens_saved", 0),
                version=row["version"],
                created_at=row["created_at"],
                metadata=metadata
            )
        
        except Exception as e:
            logger.error(f"Failed to retrieve artifact: {e}")
            return None
    
    def list_summaries(self, session_id: str) -> List[SummaryArtifact]:
        """List all summaries for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of SummaryArtifacts
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT *
                FROM artifacts
                WHERE session_id = ? AND artifact_type = 'summary'
                ORDER BY created_at ASC
            """, (session_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            summaries = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                summaries.append(SummaryArtifact(
                    artifact_id=row["artifact_id"],
                    session_id=row["session_id"],
                    content=row["content"],
                    derived_from_msg_ids=metadata.get("derived_from_msg_ids", []),
                    tokens_saved=metadata.get("tokens_saved", 0),
                    version=row["version"],
                    created_at=row["created_at"],
                    metadata=metadata
                ))
            
            return summaries
        
        except Exception as e:
            logger.error(f"Failed to list summaries: {e}")
            return []
