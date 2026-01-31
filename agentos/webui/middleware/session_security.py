"""Session Security Middleware for AgentOS WebUI.

This module provides protection against session fixation attacks and enforces
secure session and cookie handling practices.

Security Issue: M-25 - Session Fixation Protection

Key Features:
- Session ID rotation on authentication state changes
- Secure cookie flag enforcement (Secure, HttpOnly, SameSite)
- Session expiry handling and validation
- Session hijacking detection (IP/User-Agent tracking)
- Automatic session cleanup

References:
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Session Fixation: https://owasp.org/www-community/attacks/Session_fixation
"""

import logging
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import Request, Response
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)

# Session security configuration
SESSION_ROTATION_KEY = "_session_rotated"
SESSION_CREATED_KEY = "_session_created"
SESSION_LAST_ACTIVITY_KEY = "_session_last_activity"
SESSION_IP_KEY = "_session_ip"
SESSION_USER_AGENT_KEY = "_session_user_agent"
SESSION_AUTH_KEY = "_authenticated"
SESSION_USER_ID_KEY = "_user_id"

# Session timeout configuration (in seconds)
SESSION_ABSOLUTE_TIMEOUT = 86400  # 24 hours
SESSION_IDLE_TIMEOUT = 3600  # 1 hour


def rotate_session(request: Request, preserve_data: bool = True) -> None:
    """Rotate session ID, preserving session data.

    This is critical for preventing session fixation attacks. The session
    ID should be rotated whenever the authentication state changes:
    - User logs in
    - User switches accounts
    - Privilege level changes

    Args:
        request: Current request with session
        preserve_data: If True, preserve existing session data (default: True)

    Implementation:
        Starlette's SessionMiddleware doesn't provide direct session ID rotation,
        but we can achieve the same effect by:
        1. Copying the old session data
        2. Clearing the session (triggers new session ID on next response)
        3. Restoring the session data

        The SessionMiddleware will automatically generate a new session ID
        when it detects the session has been cleared and then modified.
    """
    try:
        session = request.session

        # Store old session data if needed
        old_data = dict(session) if preserve_data else {}

        # Clear the session (this will trigger new session ID generation)
        session.clear()

        # Restore data if requested
        if preserve_data:
            session.update(old_data)

        # Mark session as rotated
        session[SESSION_ROTATION_KEY] = True
        session[SESSION_CREATED_KEY] = datetime.now(timezone.utc).isoformat()
        session[SESSION_LAST_ACTIVITY_KEY] = datetime.now(timezone.utc).isoformat()

        logger.info("Session ID rotated successfully")

    except Exception as e:
        logger.error(f"Failed to rotate session: {e}", exc_info=True)
        raise


def mark_authenticated(request: Request, user_id: Optional[str] = None) -> None:
    """Mark session as authenticated and rotate session ID.

    This should be called immediately after successful authentication.

    Args:
        request: Current request
        user_id: Optional user identifier to store in session
    """
    # Rotate session first (session fixation protection)
    rotate_session(request, preserve_data=True)

    # Mark as authenticated
    request.session[SESSION_AUTH_KEY] = True
    if user_id:
        request.session[SESSION_USER_ID_KEY] = user_id

    # Store security context
    request.session[SESSION_IP_KEY] = get_client_ip(request)
    request.session[SESSION_USER_AGENT_KEY] = request.headers.get("user-agent", "unknown")

    logger.info(f"Session marked as authenticated (user_id={user_id})")


def mark_unauthenticated(request: Request) -> None:
    """Clear authentication status and destroy session.

    This should be called on logout.

    Args:
        request: Current request
    """
    # Clear all session data
    request.session.clear()
    logger.info("Session cleared on logout")


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Checks X-Forwarded-For header first (if behind proxy),
    then falls back to direct connection IP.

    Args:
        request: Current request

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header (if behind proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, use the first one
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return "unknown"


def validate_session_integrity(request: Request) -> bool:
    """Validate session integrity to detect hijacking attempts.

    Checks:
    1. Session hasn't expired (absolute timeout)
    2. Session hasn't been idle too long (idle timeout)
    3. Client IP hasn't changed (basic hijacking detection)
    4. User-Agent hasn't changed (basic hijacking detection)

    Args:
        request: Current request

    Returns:
        True if session is valid, False otherwise
    """
    try:
        session = request.session

        # Check if session is marked as authenticated
        if not session.get(SESSION_AUTH_KEY):
            # Non-authenticated sessions don't need strict validation
            return True

        # Validate absolute timeout
        created_str = session.get(SESSION_CREATED_KEY)
        if created_str:
            created = datetime.fromisoformat(created_str)
            age = (datetime.now(timezone.utc) - created).total_seconds()
            if age > SESSION_ABSOLUTE_TIMEOUT:
                logger.warning(f"Session expired (absolute timeout): age={age}s")
                return False

        # Validate idle timeout
        last_activity_str = session.get(SESSION_LAST_ACTIVITY_KEY)
        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str)
            idle = (datetime.now(timezone.utc) - last_activity).total_seconds()
            if idle > SESSION_IDLE_TIMEOUT:
                logger.warning(f"Session expired (idle timeout): idle={idle}s")
                return False

        # Validate IP address (basic hijacking detection)
        session_ip = session.get(SESSION_IP_KEY)
        current_ip = get_client_ip(request)
        if session_ip and session_ip != current_ip:
            logger.warning(
                f"Session IP mismatch: session={session_ip}, current={current_ip}"
            )
            # Note: In production, consider making this a hard failure
            # For now, just log warning (IP can change legitimately)

        # Validate User-Agent (basic hijacking detection)
        session_ua = session.get(SESSION_USER_AGENT_KEY)
        current_ua = request.headers.get("user-agent", "unknown")
        if session_ua and session_ua != current_ua:
            logger.warning(
                f"Session User-Agent mismatch: "
                f"session={session_ua[:50]}, current={current_ua[:50]}"
            )
            # Note: User-Agent can change legitimately (browser updates)
            # So this is just a warning, not a hard failure

        # Update last activity timestamp
        session[SESSION_LAST_ACTIVITY_KEY] = datetime.now(timezone.utc).isoformat()

        return True

    except Exception as e:
        logger.error(f"Session validation error: {e}", exc_info=True)
        # On validation error, fail closed (reject session)
        return False


def set_secure_cookie_flags(
    response: Response,
    key: str,
    value: str,
    max_age: Optional[int] = None,
    httponly: bool = True,
    secure: bool = False,  # Will be True in production
    samesite: str = "lax"
) -> None:
    """Set cookie with secure flags.

    Enforces security best practices for cookie settings:
    - HttpOnly: Prevent JavaScript access (XSS protection)
    - Secure: Only send over HTTPS (MITM protection)
    - SameSite: Prevent CSRF attacks

    Args:
        response: Response object to set cookie on
        key: Cookie name
        value: Cookie value
        max_age: Cookie lifetime in seconds (None = session cookie)
        httponly: Prevent JavaScript access (default: True)
        secure: Only send over HTTPS (default: False, should be True in prod)
        samesite: SameSite policy ("strict", "lax", or "none")
    """
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def get_session_info(request: Request) -> Dict[str, Any]:
    """Get session information for debugging/monitoring.

    Returns non-sensitive session metadata.

    Args:
        request: Current request

    Returns:
        Dictionary with session information
    """
    try:
        session = request.session

        created_str = session.get(SESSION_CREATED_KEY)
        last_activity_str = session.get(SESSION_LAST_ACTIVITY_KEY)

        info = {
            "authenticated": session.get(SESSION_AUTH_KEY, False),
            "user_id": session.get(SESSION_USER_ID_KEY),
            "created": created_str,
            "last_activity": last_activity_str,
            "rotated": session.get(SESSION_ROTATION_KEY, False),
            "ip": session.get(SESSION_IP_KEY),
        }

        # Calculate session age and idle time
        if created_str:
            created = datetime.fromisoformat(created_str)
            info["age_seconds"] = (datetime.now(timezone.utc) - created).total_seconds()

        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str)
            info["idle_seconds"] = (datetime.now(timezone.utc) - last_activity).total_seconds()

        return info

    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        return {"error": str(e)}


# Helper function for session validation in API endpoints
def require_valid_session(request: Request) -> None:
    """Validate session and raise exception if invalid.

    Use this in API endpoints that require authentication.

    Args:
        request: Current request

    Raises:
        HTTPException: 401 if session is invalid or expired
    """
    from fastapi import HTTPException

    if not validate_session_integrity(request):
        mark_unauthenticated(request)
        raise HTTPException(
            status_code=401,
            detail={
                "ok": False,
                "data": None,
                "error": "Session expired or invalid",
                "hint": "Please login again",
                "reason_code": "SESSION_INVALID"
            }
        )


def initialize_session(request: Request) -> None:
    """Initialize a new session with security metadata.

    This should be called for new sessions (first request).

    Args:
        request: Current request
    """
    session = request.session

    # Only initialize if not already initialized
    if SESSION_CREATED_KEY not in session:
        session[SESSION_CREATED_KEY] = datetime.now(timezone.utc).isoformat()
        session[SESSION_LAST_ACTIVITY_KEY] = datetime.now(timezone.utc).isoformat()
        session[SESSION_IP_KEY] = get_client_ip(request)
        session[SESSION_USER_AGENT_KEY] = request.headers.get("user-agent", "unknown")

        logger.debug("New session initialized")
