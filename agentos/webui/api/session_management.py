"""Session Management API Endpoints

Provides endpoints for session management and security operations.

Security Issue: M-25 - Session Fixation and Session Management

Endpoints:
- GET /api/session/info - Get current session information
- POST /api/session/rotate - Manually rotate session ID
- POST /api/session/refresh - Refresh session activity timestamp
- DELETE /api/session - Destroy current session
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from agentos.webui.middleware.session_security import (
    rotate_session,
    mark_unauthenticated,
    get_session_info,
    validate_session_integrity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionInfoResponse(BaseModel):
    """Response model for session information"""
    ok: bool
    data: Dict[str, Any]
    hint: str = None


class SessionRotateResponse(BaseModel):
    """Response model for session rotation"""
    ok: bool
    message: str
    rotated: bool


@router.get("/api/session/info", response_model=SessionInfoResponse)
async def get_session_information(request: Request):
    """Get information about the current session.

    Returns:
        Session metadata including:
        - Authentication status
        - Creation time
        - Last activity time
        - Session age
        - Whether session has been rotated

    Security:
        Does not expose sensitive session data (tokens, keys, etc.)
        Only returns metadata for monitoring and debugging
    """
    try:
        info = get_session_info(request)

        return SessionInfoResponse(
            ok=True,
            data=info,
            hint="Session information retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Failed to get session info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to retrieve session information",
                "hint": str(e),
                "reason_code": "SESSION_INFO_ERROR"
            }
        )


@router.post("/api/session/rotate", response_model=SessionRotateResponse)
async def rotate_session_id(request: Request):
    """Manually rotate the session ID.

    This endpoint allows explicit session rotation for security purposes.
    The session ID will be regenerated while preserving session data.

    Use Cases:
    - After successful login (should be automatic)
    - After privilege escalation
    - After security-sensitive operations
    - Manual security refresh

    Security:
        Session fixation protection: Rotating the session ID prevents
        session fixation attacks where an attacker tries to use a
        known session ID.

    Returns:
        Confirmation that session was rotated
    """
    try:
        # Rotate the session
        rotate_session(request, preserve_data=True)

        return SessionRotateResponse(
            ok=True,
            message="Session ID rotated successfully",
            rotated=True
        )

    except Exception as e:
        logger.error(f"Failed to rotate session: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to rotate session",
                "hint": str(e),
                "reason_code": "SESSION_ROTATION_ERROR"
            }
        )


@router.post("/api/session/refresh")
async def refresh_session_activity(request: Request):
    """Refresh session activity timestamp.

    Updates the last activity timestamp to prevent idle timeout.
    This can be called periodically by the frontend to keep sessions alive.

    Use Cases:
    - Long-running operations
    - Keeping user sessions active during extended work
    - Preventing unexpected timeouts

    Returns:
        Updated session information
    """
    try:
        # Validate session (this updates last_activity automatically)
        is_valid = validate_session_integrity(request)

        if not is_valid:
            raise HTTPException(
                status_code=401,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Session expired or invalid",
                    "hint": "Please login again",
                    "reason_code": "SESSION_EXPIRED"
                }
            )

        # Get updated session info
        info = get_session_info(request)

        return {
            "ok": True,
            "data": info,
            "message": "Session refreshed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh session: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to refresh session",
                "hint": str(e),
                "reason_code": "SESSION_REFRESH_ERROR"
            }
        )


@router.delete("/api/session")
async def destroy_session(request: Request):
    """Destroy the current session.

    Clears all session data and invalidates the session.
    The user will need to re-authenticate.

    Use Cases:
    - User logout
    - Security-triggered session termination
    - Manual session cleanup

    Returns:
        Confirmation that session was destroyed
    """
    try:
        # Clear the session
        mark_unauthenticated(request)

        return {
            "ok": True,
            "message": "Session destroyed successfully",
            "hint": "You will need to login again to access protected resources"
        }

    except Exception as e:
        logger.error(f"Failed to destroy session: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to destroy session",
                "hint": str(e),
                "reason_code": "SESSION_DESTROY_ERROR"
            }
        )


@router.get("/api/session/validate")
async def validate_session(request: Request):
    """Validate the current session.

    Checks session integrity including:
    - Expiration (absolute and idle timeout)
    - IP address consistency
    - User-Agent consistency

    Returns:
        Validation result and session status
    """
    try:
        is_valid = validate_session_integrity(request)

        if not is_valid:
            return {
                "ok": False,
                "valid": False,
                "error": "Session is invalid or expired",
                "hint": "Please login again",
                "reason_code": "SESSION_INVALID"
            }

        info = get_session_info(request)

        return {
            "ok": True,
            "valid": True,
            "data": info,
            "message": "Session is valid"
        }

    except Exception as e:
        logger.error(f"Failed to validate session: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to validate session",
                "hint": str(e),
                "reason_code": "SESSION_VALIDATION_ERROR"
            }
        )
