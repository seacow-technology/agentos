"""
Self-check API - System health diagnostics

Provides comprehensive health checks for AgentOS:
- Runtime environment
- Provider connectivity
- Context availability
- Chat pipeline readiness

Sprint B Task #7 implementation
"""

from fastapi import APIRouter
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from agentos.selfcheck import SelfCheckRunner
from agentos.webui.middleware import sanitize_response
from agentos.core.chat.health_checker import ChatHealthChecker

router = APIRouter()


class SelfCheckRequest(BaseModel):
    """Self-check request parameters"""
    session_id: Optional[str] = None
    include_network: bool = False
    include_context: bool = True


class CheckActionResponse(BaseModel):
    """Action that can be taken to fix an issue"""
    label: str
    method: Optional[str] = None
    path: Optional[str] = None
    ui: Optional[str] = None


class CheckItemResponse(BaseModel):
    """Single check item response"""
    id: str
    group: str
    name: str
    status: str
    detail: str
    hint: Optional[str] = None
    actions: List[CheckActionResponse] = []


class SelfCheckResponse(BaseModel):
    """Self-check response"""
    summary: str
    ts: str
    items: List[CheckItemResponse]
    version: str = "unknown"


class ChatHealthResponse(BaseModel):
    """Lightweight chat health response"""
    is_healthy: bool
    provider_available: bool
    provider_name: Optional[str] = None
    storage_ok: bool = True
    issues: List[str] = []
    hints: List[str] = []


@router.post("")
async def run_selfcheck(request: SelfCheckRequest) -> SelfCheckResponse:
    """
    Run comprehensive self-check

    Checks:
    - Runtime: version, paths, permissions
    - Providers: local & cloud status (uses cached status by default)
    - Context: memory, RAG, session binding
    - Chat: pipeline readiness (optional)

    Query parameters:
    - session_id: Check context binding for specific session
    - include_network: If true, actively probe cloud providers (may cost API calls)
    - include_context: If true, check memory/RAG/session availability

    Returns:
    - summary: "OK", "WARN", or "FAIL"
    - ts: ISO timestamp
    - items: List of check results with actionable hints

    Security:
    - No secrets are exposed in responses
    - All sensitive data is masked
    """
    runner = SelfCheckRunner()

    result = await runner.run(
        session_id=request.session_id,
        include_network=request.include_network,
        include_context=request.include_context,
    )

    # Convert to response format
    items = [
        CheckItemResponse(
            id=item.id,
            group=item.group,
            name=item.name,
            status=item.status,
            detail=item.detail,
            hint=item.hint,
            actions=[
                CheckActionResponse(
                    label=action.label,
                    method=action.method,
                    path=action.path,
                    ui=action.ui,
                )
                for action in item.actions
            ],
        )
        for item in result.items
    ]

    response = SelfCheckResponse(
        summary=result.summary,
        ts=result.ts,
        items=items,
        version=result.version,
    )

    # Apply sanitization as safety net
    return sanitize_response(response.model_dump())


@router.get("/chat-health")
async def check_chat_health() -> ChatHealthResponse:
    """
    Lightweight health check for Chat functionality

    This is NOT a comprehensive system diagnostic.
    It only checks the minimum requirements for Chat to work:
    - At least ONE usable LLM provider (uses cache only, no network calls)
    - Storage is accessible

    For full system diagnostics, use POST /api/selfcheck instead.

    Returns:
        ChatHealthResponse with lightweight health status
    """
    checker = ChatHealthChecker()
    status = await checker.check()

    return ChatHealthResponse(
        is_healthy=status.is_healthy,
        provider_available=status.provider_available,
        provider_name=status.provider_name,
        storage_ok=status.storage_ok,
        issues=status.issues,
        hints=status.hints
    )
