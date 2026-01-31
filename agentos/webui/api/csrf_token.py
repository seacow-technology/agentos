"""CSRF Token API - Provides CSRF tokens for frontend consumption

This module provides an endpoint for clients to retrieve CSRF tokens
for use in POST/PUT/DELETE/PATCH requests.

Created to support Gate v1.1 validation and frontend CSRF protection.
"""

from fastapi import APIRouter, Request
from typing import Dict

from agentos.webui.middleware.csrf import get_csrf_token

router = APIRouter()


@router.get("/csrf-token")
async def get_csrf_token_endpoint(request: Request) -> Dict[str, str]:
    """Get CSRF token for current session.

    This endpoint provides a CSRF token that must be included in the
    X-CSRF-Token header for all state-changing requests (POST/PUT/DELETE/PATCH).

    The token is tied to the user's session and must be refreshed if the session expires.

    Returns:
        {
            "csrf_token": "..." # Token to include in X-CSRF-Token header
        }

    Example:
        GET /api/csrf-token
        Response: {"csrf_token": "abc123..."}

        Then use in subsequent requests:
        POST /api/tasks
        Headers: {"X-CSRF-Token": "abc123..."}
    """
    token = get_csrf_token(request)
    return {
        "csrf_token": token
    }
