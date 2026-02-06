"""Data models for Chat Mode"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Dict, Any, List
from enum import Enum
import json

# Import external info models
from agentos.core.chat.models.external_info import ExternalInfoDeclaration

# Time formatting - Hard Contract (ADR-XXXX)
# Use lazy import to avoid circular dependencies
def parse_db_time(timestamp_str):
    """Lazy import to avoid circular dependency"""
    from agentos.webui.api.time_format import parse_db_time as _parse_db_time
    return _parse_db_time(timestamp_str)

def iso_z(dt):
    """Lazy import to avoid circular dependency"""
    from agentos.webui.api.time_format import iso_z as _iso_z
    return _iso_z(dt)


class ConversationMode(str, Enum):
    """Conversation mode for chat sessions.

    This enum defines different conversation contexts that affect
    UI presentation and conversation style, but NOT security controls.

    Important: conversation_mode is independent from execution_phase.
    - conversation_mode: UI/UX context (what the user is doing)
    - execution_phase: Security context (what external operations are allowed)

    Modes:
        CHAT: Free-form conversation (default)
        DISCUSSION: Structured discussion or brainstorming
        PLAN: Planning and design work
        DEVELOPMENT: Active development work
        TASK: Task-focused conversation
    """
    CHAT = "chat"
    DISCUSSION = "discussion"
    PLAN = "plan"
    DEVELOPMENT = "development"
    TASK = "task"


@dataclass
class ChatSession:
    """Represents a chat conversation session"""
    session_id: str
    title: str
    task_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

    # Epoch millisecond timestamps (Task #8: Dual Write)
    created_at_ms: Optional[int] = None
    updated_at_ms: Optional[int] = None

    # Internal flag for lazy migration (Task #9: Lazy Migration)
    # Not stored in DB, only used in-memory to signal service layer
    _needs_lazy_migration: bool = False

    @classmethod
    def from_db_row(cls, row, lazy_migrate=True) -> "ChatSession":
        """Create ChatSession from database row

        Args:
            row: Database row (sqlite3.Row or dict)
            lazy_migrate: If True, mark for lazy migration when epoch_ms is NULL (default: True)

        Reads epoch_ms fields first (preferred), falls back to TIMESTAMP fields.
        Part of Time & Timestamp Contract (ADR-XXXX).

        When lazy_migrate=True and epoch_ms fields are NULL, the session object
        will have a _needs_lazy_migration flag set. The service layer is responsible
        for detecting this flag and performing the actual database UPDATE.
        """
        from agentos.store.timestamp_utils import from_epoch_ms, to_epoch_ms

        # Convert row to dict for easier access (handles both dict and sqlite3.Row)
        if hasattr(row, 'keys'):
            row_dict = {key: row[key] for key in row.keys()}
        else:
            row_dict = dict(row)

        # Track if lazy migration needed
        needs_migration = False

        # Priority 1: Read from epoch_ms fields (if available)
        # Priority 2: Fallback to TIMESTAMP fields and convert
        if row_dict.get("created_at_ms"):
            created_at = from_epoch_ms(row_dict["created_at_ms"])
            created_at_ms = row_dict["created_at_ms"]
        else:
            created_at = parse_db_time(row_dict["created_at"])
            created_at_ms = to_epoch_ms(created_at) if created_at else None
            needs_migration = True  # NULL created_at_ms detected

        if row_dict.get("updated_at_ms"):
            updated_at = from_epoch_ms(row_dict["updated_at_ms"])
            updated_at_ms = row_dict["updated_at_ms"]
        else:
            updated_at = parse_db_time(row_dict["updated_at"])
            updated_at_ms = to_epoch_ms(updated_at) if updated_at else None
            needs_migration = True  # NULL updated_at_ms detected

        session = cls(
            session_id=row_dict["session_id"],
            title=row_dict["title"] or "Untitled Chat",
            task_id=row_dict["task_id"],
            created_at=created_at,
            updated_at=updated_at,
            metadata=json.loads(row_dict["metadata"]) if row_dict["metadata"] else {},
            created_at_ms=created_at_ms,
            updated_at_ms=updated_at_ms
        )

        # Mark for lazy migration if needed
        # This flag is used by the service layer to trigger database UPDATE
        if lazy_migrate and needs_migration and created_at_ms is not None:
            session._needs_lazy_migration = True
        else:
            session._needs_lazy_migration = False

        return session
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "task_id": self.task_id,
            "created_at": iso_z(self.created_at),
            "updated_at": iso_z(self.updated_at),
            "metadata": self.metadata
        }

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database dictionary with dual write

        Returns both old TIMESTAMP format and new epoch_ms format.
        Part of Time & Timestamp Contract (ADR-XXXX).
        """
        from agentos.store.timestamp_utils import to_epoch_ms

        return {
            "session_id": self.session_id,
            "title": self.title,
            "task_id": self.task_id,
            # Old format (backward compatibility)
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
            # New format (epoch_ms)
            "created_at_ms": self.created_at_ms or to_epoch_ms(self.created_at),
            "updated_at_ms": self.updated_at_ms or to_epoch_ms(self.updated_at),
            "metadata": json.dumps(self.metadata)
        }


@dataclass
class ChatMessage:
    """Represents a single message in a chat session"""
    message_id: str
    session_id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    created_at: datetime
    metadata: Dict[str, Any]

    # Epoch millisecond timestamp (Task #8: Dual Write)
    created_at_ms: Optional[int] = None

    # Internal flag for lazy migration (Task #9: Lazy Migration)
    # Not stored in DB, only used in-memory to signal service layer
    _needs_lazy_migration: bool = False

    @classmethod
    def from_db_row(cls, row, lazy_migrate=True) -> "ChatMessage":
        """Create ChatMessage from database row

        Args:
            row: Database row (sqlite3.Row or dict)
            lazy_migrate: If True, mark for lazy migration when epoch_ms is NULL (default: True)

        Reads epoch_ms field first (preferred), falls back to TIMESTAMP field.
        Part of Time & Timestamp Contract (ADR-XXXX).

        When lazy_migrate=True and epoch_ms field is NULL, the message object
        will have a _needs_lazy_migration flag set. The service layer is responsible
        for detecting this flag and performing the actual database UPDATE.
        """
        from agentos.store.timestamp_utils import from_epoch_ms, to_epoch_ms

        # Convert row to dict for easier access (handles both dict and sqlite3.Row)
        if hasattr(row, 'keys'):
            row_dict = {key: row[key] for key in row.keys()}
        else:
            row_dict = dict(row)

        # Track if lazy migration needed
        needs_migration = False

        # Priority 1: Read from epoch_ms field (if available)
        # Priority 2: Fallback to TIMESTAMP field and convert
        if row_dict.get("created_at_ms"):
            created_at = from_epoch_ms(row_dict["created_at_ms"])
            created_at_ms = row_dict["created_at_ms"]
        else:
            created_at = parse_db_time(row_dict["created_at"])
            created_at_ms = to_epoch_ms(created_at) if created_at else None
            needs_migration = True  # NULL created_at_ms detected

        message = cls(
            message_id=row_dict["message_id"],
            session_id=row_dict["session_id"],
            role=row_dict["role"],
            content=row_dict["content"],
            created_at=created_at,
            metadata=json.loads(row_dict["metadata"]) if row_dict["metadata"] else {},
            created_at_ms=created_at_ms
        )

        # Mark for lazy migration if needed
        # This flag is used by the service layer to trigger database UPDATE
        if lazy_migrate and needs_migration and created_at_ms is not None:
            message._needs_lazy_migration = True
        else:
            message._needs_lazy_migration = False

        return message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for API/logging)"""
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": iso_z(self.created_at),
            "metadata": self.metadata
        }

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database dictionary with dual write

        Returns both old TIMESTAMP format and new epoch_ms format.
        Part of Time & Timestamp Contract (ADR-XXXX).
        """
        from agentos.store.timestamp_utils import to_epoch_ms

        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            # Old format (backward compatibility)
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            # New format (epoch_ms)
            "created_at_ms": self.created_at_ms or to_epoch_ms(self.created_at),
            "metadata": json.dumps(self.metadata)
        }

    def to_openai_format(self) -> Dict[str, str]:
        """Convert to OpenAI chat format"""
        return {
            "role": self.role,
            "content": self.content
        }
    
    def estimate_tokens(self) -> int:
        """Estimate token count (rough heuristic)"""
        # Simple heuristic: length * 1.3
        return int(len(self.content) * 1.3)


@dataclass
class ChatResponse:
    """
    Represents a chat response with external info declarations

    This model extends the basic response structure to include external
    information declarations from the LLM. These declarations enable the
    system to enforce execution phase gating and present external info
    needs to users before allowing execution.

    Attributes:
        message_id: Unique message identifier
        content: Response text content
        role: Message role (usually "assistant")
        metadata: Additional metadata (model info, tokens, etc.)
        context: Context information (tokens, RAG chunks, etc.)
        external_info: List of external information declarations
    """
    message_id: Optional[str]
    content: str
    role: Literal["system", "user", "assistant", "tool"]
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    external_info: List[ExternalInfoDeclaration] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for API/WebSocket serialization

        Returns:
            Dictionary representation with external_info serialized
        """
        return {
            "message_id": self.message_id,
            "content": self.content,
            "role": self.role,
            "metadata": self.metadata,
            "context": self.context,
            "external_info": [decl.to_dict() for decl in self.external_info]
        }

    def has_external_info_needs(self) -> bool:
        """
        Check if this response has any external information needs

        Returns:
            True if there are external info declarations, False otherwise
        """
        return len(self.external_info) > 0

    def get_critical_external_info(self) -> List[ExternalInfoDeclaration]:
        """
        Get only critical (priority=1) external info declarations

        Returns:
            List of critical declarations
        """
        return [decl for decl in self.external_info if decl.priority == 1]

    def to_user_summary(self) -> str:
        """
        Generate user-friendly summary of external info needs

        Returns:
            Human-readable summary string
        """
        if not self.external_info:
            return "No external information needed."

        summary = f"This response requires {len(self.external_info)} external information request(s):\n\n"
        for i, decl in enumerate(self.external_info, 1):
            summary += f"{i}. {decl.to_user_message()}\n\n"

        return summary.strip()
