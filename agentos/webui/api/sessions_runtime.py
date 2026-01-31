"""
Session Runtime Configuration API

Sprint B Task #7: Provider/Model Selection

Allows updating runtime config (provider, model, temperature) for the current session.
Changes only affect future messages, not historical ones.

PR-2: Unified to use ChatService instead of SessionStore
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from agentos.core.chat.service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions")

# ChatService instance (lazy initialization)
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get ChatService singleton (lazy initialization)"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


# Request/Response Models

class RuntimeConfigRequest(BaseModel):
    """Request to update runtime configuration"""
    provider: str = Field(..., description="Provider ID (e.g., 'openai', 'ollama')")
    model: Optional[str] = Field(None, description="Model ID (e.g., 'gpt-4o-mini')")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature (0.0-2.0)")


class RuntimeConfigResponse(BaseModel):
    """Response with updated runtime configuration"""
    ok: bool
    session_id: str
    runtime: dict


# API Endpoints

@router.post("/{session_id}/runtime", response_model=RuntimeConfigResponse)
async def update_session_runtime(
    session_id: str,
    config: RuntimeConfigRequest,
):
    """
    Update runtime configuration for session

    Changes apply to future messages only (not retroactive).

    Args:
        session_id: Session ID
        config: Runtime configuration (provider, model, temperature)

    Returns:
        Updated runtime configuration

    Raises:
        404: Session not found
        400: Invalid provider or configuration
    """
    logger.info(f"Updating runtime config for session {session_id}: provider={config.provider}")

    try:
        chat_service = get_chat_service()

        # Get session
        try:
            session = chat_service.get_session(session_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )

        # Validate provider exists and is available
        # Import here to avoid circular dependency
        from agentos.webui.api.providers import get_providers_status

        providers_response = await get_providers_status()
        provider_ids = {p["id"] for p in providers_response["providers"]}

        if config.provider not in provider_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {config.provider}"
            )

        # Check provider state (warn but allow if not READY)
        provider_info = next((p for p in providers_response["providers"] if p["id"] == config.provider), None)
        if provider_info and provider_info["state"] == "DISCONNECTED":
            logger.warning(f"Provider {config.provider} is DISCONNECTED but user requested it")
            # Allow it - user may be testing or have external setup

        # Build runtime config
        runtime_config = {
            "provider": config.provider,
        }

        if config.model:
            runtime_config["model"] = config.model

        if config.temperature is not None:
            runtime_config["temperature"] = config.temperature

        # Update session metadata using ChatService
        metadata_update = {"runtime": runtime_config}
        chat_service.update_session_metadata(session_id, metadata_update)

        logger.info(f"Runtime config updated for session {session_id}: {runtime_config}")

        return RuntimeConfigResponse(
            ok=True,
            session_id=session_id,
            runtime=runtime_config,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"Failed to update runtime config for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update runtime configuration"
        )


@router.get("/{session_id}/runtime", response_model=RuntimeConfigResponse)
async def get_session_runtime(session_id: str):
    """
    Get current runtime configuration for session

    Returns:
        Current runtime configuration

    Raises:
        404: Session not found
    """
    try:
        chat_service = get_chat_service()

        # Get session
        try:
            session = chat_service.get_session(session_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )

        # Extract runtime config from metadata
        runtime_config = session.metadata.get("runtime", {}) if session.metadata else {}

        return RuntimeConfigResponse(
            ok=True,
            session_id=session_id,
            runtime=runtime_config,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get runtime config for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve runtime configuration"
        )
