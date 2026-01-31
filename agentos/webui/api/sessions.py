"""
Sessions API - Chat session management

GET /api/sessions - List all sessions (paginated)
POST /api/sessions - Create new session
GET /api/sessions/{id} - Get session details
GET /api/sessions/{id}/messages - Get session messages (paginated)
POST /api/sessions/{id}/messages - Add message to session
DELETE /api/sessions/{id} - Delete session

Refactored in v0.3.2 (P1 Sprint):
- Replaced in-memory dict with SessionStore abstraction
- Added pagination support
- Added persistent storage (SQLite)
- Retained backward compatibility

Refactored in PR-2:
- Unified all session operations to use ChatService
- All sessions now stored in chat_sessions table (not webui_sessions)
- Mode/Phase management integrated with ChatService defaults
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

# Import ChatService as the primary data layer
from agentos.core.chat.service import ChatService
from agentos.core.chat.models import ChatSession, ChatMessage, ConversationMode

# Time formatting - Hard Contract (ADR-XXXX)
from agentos.webui.api.time_format import iso_z

# Import validation utilities
from agentos.webui.api.validation import (
    OptionalTitleField,
    ContentField,
    LimitField,
    OffsetField,
    create_metadata_validator,
    VALID_MESSAGE_ROLES,
    VALID_CONVERSATION_MODES,
    VALID_EXECUTION_PHASES,
)

router = APIRouter()

# Global ChatService instance (initialized lazily)
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get ChatService instance (lazy initialization)"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


def _get_default_language() -> str:
    """Get default language from application settings

    Returns:
        Language code (e.g., "en", "zh"), defaults to "en"
    """
    try:
        from agentos.config import load_settings
        settings = load_settings()
        language = getattr(settings, "language", "en")
        return language
    except Exception:
        return "en"


# ============================================================================
# Pydantic Models (API Layer)
# ============================================================================
# These are kept for backward compatibility with existing frontend code

class SessionResponse(BaseModel):
    """Session API response (backward compatible)"""
    id: str
    title: str
    created_at: str
    updated_at: str
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    conversation_mode: Optional[str] = None
    execution_phase: Optional[str] = None

    @classmethod
    def from_model(cls, session: ChatSession) -> "SessionResponse":
        """Convert ChatSession to API response"""
        return cls(
            id=session.session_id,
            title=session.title,
            created_at=iso_z(session.created_at),
            updated_at=iso_z(session.updated_at),
            tags=session.metadata.get("tags", []),
            metadata=session.metadata,
            conversation_mode=session.metadata.get("conversation_mode", "chat"),
            execution_phase=session.metadata.get("execution_phase", "planning")
        )


class CreateSessionRequest(BaseModel):
    """Create session request with input validation"""
    title: Optional[str] = OptionalTitleField
    tags: List[str] = []
    user_id: Optional[str] = "default"
    metadata: Optional[Dict[str, Any]] = None

    # Validate metadata to prevent injection attacks (M-5)
    _validate_metadata = create_metadata_validator()


class MessageResponse(BaseModel):
    """Message API response (backward compatible)"""
    id: str
    session_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str
    metadata: Dict[str, Any] = {}

    @classmethod
    def from_model(cls, message: ChatMessage) -> "MessageResponse":
        """Convert ChatMessage to API response"""
        return cls(
            id=message.message_id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            timestamp=iso_z(message.created_at),
            metadata=message.metadata
        )


class AddMessageRequest(BaseModel):
    """Add message request with strict validation"""
    role: str  # "user" | "assistant" | "system"
    content: str = ContentField
    metadata: Dict[str, Any] = {}

    @validator('role')
    def validate_role(cls, v):
        """Validate message role (H-1 to H-7: Prevent privilege escalation)"""
        if not v or not isinstance(v, str):
            raise ValueError("Role must be a non-empty string")

        role_normalized = v.strip().lower()

        if role_normalized not in VALID_MESSAGE_ROLES:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: {', '.join(sorted(VALID_MESSAGE_ROLES))}"
            )

        return role_normalized

    # Validate metadata to prevent injection attacks (M-5)
    _validate_metadata = create_metadata_validator()


# ============================================================================
# API Endpoints
# ============================================================================
# Session Endpoints
# ============================================================================

@router.get("")
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> List[SessionResponse]:
    """
    List all sessions (paginated)

    Query params:
    - limit: Max results (default 50, max 100)
    - offset: Skip N results (default 0)

    Returns sessions ordered by updated_at DESC
    """
    chat_service = get_chat_service()
    sessions = chat_service.list_sessions(limit=limit, offset=offset)
    return [SessionResponse.from_model(s) for s in sessions]


@router.post("")
async def create_session(req: CreateSessionRequest) -> SessionResponse:
    """Create new session using ChatService"""
    chat_service = get_chat_service()

    # Load language preference from config
    language = _get_default_language()

    # Prepare metadata
    metadata = {
        "tags": req.tags,
        "language": language  # Add language to session metadata
    }

    # Merge with any additional metadata from request
    if req.metadata:
        metadata.update(req.metadata)
        # Ensure tags from top-level field takes precedence
        metadata["tags"] = req.tags

    # ChatService.create_session automatically sets:
    # - conversation_mode: "chat" (default)
    # - execution_phase: "planning" (default, safe)
    session = chat_service.create_session(
        title=req.title or "New Session",
        metadata=metadata
    )

    return SessionResponse.from_model(session)


@router.get("/{session_id}")
async def get_session(session_id: str) -> SessionResponse:
    """Get session details using ChatService"""
    chat_service = get_chat_service()

    try:
        session = chat_service.get_session(session_id)
        return SessionResponse.from_model(session)
    except ValueError as e:
        # ChatService raises ValueError if session not found
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
) -> List[MessageResponse]:
    """
    Get session messages (paginated) using ChatService

    Query params:
    - limit: Max results (default 100, max 500)
    - offset: Skip N results (default 0)

    Returns messages ordered by created_at ASC (chronological)
    """
    chat_service = get_chat_service()

    # Verify session exists
    try:
        session = chat_service.get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    messages = chat_service.get_messages(session_id, limit=limit, offset=offset)
    return [MessageResponse.from_model(m) for m in messages]


@router.post("/{session_id}/messages")
async def add_message(session_id: str, req: AddMessageRequest) -> MessageResponse:
    """
    Add message to session using ChatService

    Body:
    - role: 'user' | 'assistant' | 'system'
    - content: Message text
    - metadata: Optional metadata (e.g., model, tokens)
    """
    chat_service = get_chat_service()

    try:
        message = chat_service.add_message(
            session_id=session_id,
            role=req.role,
            content=req.content,
            metadata=req.metadata
        )
        return MessageResponse.from_model(message)
    except ValueError as e:
        # Invalid message (e.g., bad role, empty content, session not found)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{session_id}/messages/{message_id}")
async def delete_message(session_id: str, message_id: str):
    """
    Delete a single message from a session

    Args:
        session_id: Session ID (for verification)
        message_id: Message ID to delete

    Returns:
        {"status": "deleted", "message_id": "..."}
    """
    chat_service = get_chat_service()

    try:
        # Verify session exists first
        chat_service.get_session(session_id)

        # Delete the message
        chat_service.delete_message(message_id)

        return {"status": "deleted", "message_id": message_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")


class BatchDeleteMessagesRequest(BaseModel):
    """Batch delete messages request"""
    message_ids: List[str]


@router.delete("/{session_id}/messages")
async def batch_delete_messages(session_id: str, req: BatchDeleteMessagesRequest):
    """
    Delete multiple messages from a session (batch delete)

    Body:
    - message_ids: List of message IDs to delete

    Returns:
        {
            "status": "deleted",
            "deleted_count": 5,
            "failed_ids": []
        }
    """
    chat_service = get_chat_service()

    try:
        # Verify session exists first
        chat_service.get_session(session_id)

        # Batch delete messages
        result = chat_service.delete_messages(req.message_ids)

        return {
            "status": "deleted",
            "deleted_count": result["deleted_count"],
            "failed_ids": result["failed_ids"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch delete messages: {str(e)}")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete session and all its messages using ChatService"""
    chat_service = get_chat_service()

    try:
        # Verify session exists first
        chat_service.get_session(session_id)
        # Delete the session (CASCADE deletes messages)
        chat_service.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


@router.delete("")
async def delete_all_sessions():
    """Delete all sessions (clear all history) using ChatService"""
    chat_service = get_chat_service()

    # Get all sessions
    sessions = chat_service.list_sessions(limit=1000, offset=0)

    deleted_count = 0
    for session in sessions:
        try:
            chat_service.delete_session(session.session_id)
            deleted_count += 1
        except Exception:
            # Continue deleting other sessions even if one fails
            pass

    return {
        "status": "deleted",
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} session(s)"
    }


# ============================================================================
# Mode and Phase Management (Task #3 + Task #4 Extensions)
# ============================================================================

class UpdateModeRequest(BaseModel):
    """Update conversation mode request with validation"""
    mode: str  # chat/discussion/plan/development/task

    @validator('mode')
    def validate_mode(cls, v):
        """Validate conversation mode"""
        if not v or not isinstance(v, str):
            raise ValueError("Mode must be a non-empty string")

        mode_normalized = v.strip().lower()

        if mode_normalized not in VALID_CONVERSATION_MODES:
            raise ValueError(
                f"Invalid mode '{v}'. Must be one of: {', '.join(sorted(VALID_CONVERSATION_MODES))}"
            )

        return mode_normalized


class UpdatePhaseRequest(BaseModel):
    """Update execution phase request with validation"""
    phase: str  # planning/execution
    actor: Optional[str] = "user"
    reason: Optional[str] = None
    confirmed: bool = False  # Task #4: Safety check for execution phase

    @validator('phase')
    def validate_phase(cls, v):
        """Validate execution phase"""
        if not v or not isinstance(v, str):
            raise ValueError("Phase must be a non-empty string")

        phase_normalized = v.strip().lower()

        if phase_normalized not in VALID_EXECUTION_PHASES:
            raise ValueError(
                f"Invalid phase '{v}'. Must be one of: {', '.join(sorted(VALID_EXECUTION_PHASES))}"
            )

        return phase_normalized


@router.patch("/{session_id}/mode")
async def update_conversation_mode(session_id: str, req: UpdateModeRequest) -> Dict[str, Any]:
    """
    Update conversation mode for a session (Task #4 Enhanced)

    This updates the UI/UX context for the conversation.
    It does NOT affect security controls (execution_phase).

    Body:
    - mode: Conversation mode (chat/discussion/plan/development/task)

    Returns:
        {
            "ok": true,
            "session": {
                "session_id": "...",
                "conversation_mode": "development",
                "execution_phase": "planning",
                "title": "...",
                "metadata": {...}
            }
        }

    Raises:
        400: Invalid mode value with valid options
        404: Session not found
    """
    chat_service = get_chat_service()

    # Validate mode using ConversationMode enum
    try:
        ConversationMode(req.mode)
    except ValueError:
        valid_modes = [m.value for m in ConversationMode]
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid conversation mode",
                "mode": req.mode,
                "valid_modes": valid_modes
            }
        )

    # Verify session exists
    try:
        session = chat_service.get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    try:
        # Update mode using ChatService
        chat_service.update_conversation_mode(session_id, req.mode)

        # Fetch updated session
        updated_session = chat_service.get_session(session_id)

        # Return enhanced response with both mode and phase
        return {
            "ok": True,
            "session": {
                "session_id": updated_session.session_id,
                "conversation_mode": updated_session.metadata.get("conversation_mode"),
                "execution_phase": updated_session.metadata.get("execution_phase"),
                "title": updated_session.title,
                "metadata": updated_session.metadata
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mode: {str(e)}")


@router.get("/{session_id}/memory-status")
async def get_memory_status(session_id: str):
    """
    Get memory context status for a session (Task #9)

    Returns:
        {
            "memory_count": 3,
            "has_preferred_name": true,
            "preferred_name": "胖哥",
            "memory_types": {"preference": 2, "fact": 1},
            "last_updated": "2025-01-31T10:00:00Z"
        }
    """
    import logging
    logger = logging.getLogger(__name__)

    chat_service = get_chat_service()

    try:
        # Get session to find project_id
        try:
            session = chat_service.get_session(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        project_id = session.metadata.get("project_id")

        # Load memories using MemoryService
        from agentos.core.memory.service import MemoryService
        memory_service = MemoryService()

        if project_id:
            # List memories for this project with high confidence threshold
            memories = memory_service.list(
                project_id=project_id,
                limit=100
            )
        else:
            # No project context - return empty
            memories = []

        # Extract preferred_name
        preferred_name = None
        for mem in memories:
            if mem.get("type") == "preference":
                content = mem.get("content", {})
                if isinstance(content, dict) and content.get("key") == "preferred_name":
                    preferred_name = content.get("value")
                    break

        # Count by type
        type_counts = {}
        for mem in memories:
            mem_type = mem.get("type", "unknown")
            type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

        from agentos.core.time import utc_now_iso

        return {
            "memory_count": len(memories),
            "has_preferred_name": preferred_name is not None,
            "preferred_name": preferred_name,
            "memory_types": type_counts,
            "last_updated": utc_now_iso()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory status: {e}", exc_info=True)
        return {
            "memory_count": 0,
            "has_preferred_name": False,
            "memory_types": {},
            "error": str(e)
        }


@router.patch("/{session_id}/phase")
async def update_execution_phase(session_id: str, req: UpdatePhaseRequest) -> Dict[str, Any]:
    """
    Update execution phase for a session (Task #4 Enhanced)

    This changes the security context for external operations.
    All phase changes are audited for security and compliance.

    Body:
    - phase: Execution phase (planning/execution)
    - actor: Who initiated the change (default: "user")
    - reason: Optional reason for the change
    - confirmed: Required=true for execution phase (safety check)

    Returns:
        {
            "ok": true,
            "session": {
                "session_id": "...",
                "conversation_mode": "development",
                "execution_phase": "execution",
                "title": "...",
                "metadata": {...}
            },
            "audit_id": "audit_abc123def456"
        }

    Raises:
        400: Invalid phase, missing confirmation
        403: Current mode blocks phase change (plan mode blocks execution)
        404: Session not found
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Phase update request: session={session_id}, phase={req.phase}, actor={req.actor}, confirmed={req.confirmed}")

    chat_service = get_chat_service()

    # Validate phase
    valid_phases = ["planning", "execution"]
    if req.phase not in valid_phases:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid execution phase",
                "phase": req.phase,
                "valid_phases": valid_phases
            }
        )

    # Verify session exists
    try:
        session = chat_service.get_session(session_id)
    except ValueError as e:
        logger.error(f"Session not found: {session_id}, error: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Session not found",
                "session_id": session_id,
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database error",
                "session_id": session_id,
                "message": str(e)
            }
        )

    # Task #4: Check if current mode allows phase change
    current_mode = session.metadata.get("conversation_mode", "chat")
    if current_mode == ConversationMode.PLAN.value and req.phase == "execution":
        logger.warning(f"Phase change blocked: mode={current_mode}, requested_phase={req.phase}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Mode 'plan' blocks execution phase",
                "current_mode": current_mode,
                "requested_phase": req.phase,
                "hint": "Change conversation_mode first, then update execution_phase"
            }
        )

    # Task #4: Require confirmation for execution phase (safety check)
    if req.phase == "execution" and not req.confirmed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Confirmation required for execution phase",
                "phase": req.phase,
                "confirmed": req.confirmed,
                "hint": "Set confirmed=true to proceed with execution phase"
            }
        )

    try:
        # Update phase using ChatService (with audit logging)
        chat_service.update_execution_phase(
            session_id,
            req.phase,
            actor=req.actor,
            reason=req.reason
        )

        # Fetch updated session
        updated_session = chat_service.get_session(session_id)

        # Task #4: Emit additional audit event for API tracking (best effort)
        audit_id = None
        try:
            from agentos.core.capabilities.audit import emit_audit_event

            audit_id = emit_audit_event(
                event_type="execution_phase_changed",
                details={
                    "session_id": session_id,
                    "new_phase": req.phase,
                    "confirmed": req.confirmed,
                    "actor": req.actor,
                    "reason": req.reason or "No reason provided",
                    "source": "PATCH /api/sessions/{session_id}/phase"
                },
                task_id=session.task_id,
                level="info"
            )
        except Exception as audit_error:
            # Graceful degradation - audit failure shouldn't break the API
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to emit audit event for phase change: {audit_error}")

        # Task #4: Return enhanced response with audit_id
        return {
            "ok": True,
            "session": {
                "session_id": updated_session.session_id,
                "conversation_mode": updated_session.metadata.get("conversation_mode"),
                "execution_phase": updated_session.metadata.get("execution_phase"),
                "title": updated_session.title,
                "metadata": updated_session.metadata
            },
            "audit_id": audit_id
        }

    except ValueError as e:
        logger.error(f"Validation error updating phase: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation error",
                "message": str(e),
                "session_id": session_id,
                "requested_phase": req.phase
            }
        )
    except Exception as e:
        logger.error(f"Failed to update phase for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": f"Failed to update phase: {str(e)}",
                "session_id": session_id,
                "requested_phase": req.phase
            }
        )
