"""
Rate Limiting Middleware with Test Bypass

Implements rate limiting with configurable bypass mechanisms for testing:
- Environment variable controls (RATE_LIMIT_ENABLED, AGENTOS_TEST_MODE)
- Localhost exemption (127.0.0.1, ::1, localhost)
- Test token bypass (X-Test-Token header)

Production environments remain protected by default.

L-1 Implementation: Test Environment Rate Limit Bypass
"""

import os
import logging
import time
from typing import Optional

from fastapi import Request
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _is_true(v: str | None) -> bool:
    """Helper to parse boolean environment variables"""
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


# Rate limiting configuration
RATE_LIMIT_ENABLED = _is_true(os.getenv("RATE_LIMIT_ENABLED", "true"))
AGENTOS_TEST_MODE = _is_true(os.getenv("AGENTOS_TEST_MODE", "false"))
TEST_BYPASS_TOKEN = os.getenv("TEST_BYPASS_TOKEN")  # Optional security token for CI/staging

# Log configuration at module load
logger.info(
    f"Rate limit configuration: "
    f"enabled={RATE_LIMIT_ENABLED}, "
    f"test_mode={AGENTOS_TEST_MODE}, "
    f"bypass_token_set={TEST_BYPASS_TOKEN is not None}"
)


def should_bypass_rate_limit(request: Request) -> bool:
    """
    Determine if rate limiting should be bypassed for this request.

    Bypass conditions (checked in order):
    1. RATE_LIMIT_ENABLED=false - Global disable
    2. AGENTOS_TEST_MODE=true - Test mode disable
    3. Localhost requests (127.0.0.1, ::1, localhost) - Development exemption
    4. X-Test-Token header matches TEST_BYPASS_TOKEN - CI/staging exemption

    Args:
        request: The incoming HTTP request

    Returns:
        True if rate limiting should be bypassed, False otherwise
    """
    # 1) Global disable via environment variable
    if not RATE_LIMIT_ENABLED:
        logger.debug(f"Rate limit bypassed for {request.url.path}: RATE_LIMIT_ENABLED=false")
        return True

    # 2) Test mode disable
    if AGENTOS_TEST_MODE:
        logger.debug(f"Rate limit bypassed for {request.url.path}: AGENTOS_TEST_MODE=true")
        return True

    # 3) Localhost exemption (development environment, ONLY for direct connections)
    # SECURITY: If reverse proxy headers exist (X-Forwarded-For/X-Real-IP),
    # REFUSE localhost bypass to prevent全站绕过 in production behind proxy.
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    x_real_ip = request.headers.get("X-Real-IP")

    if x_forwarded_for or x_real_ip:
        # Reverse proxy detected - DO NOT allow localhost bypass
        # (request.client.host would be proxy's IP, not real client)
        logger.debug(
            f"Rate limit NOT bypassed for {request.url.path}: "
            f"reverse proxy detected (X-Forwarded-For={x_forwarded_for}, X-Real-IP={x_real_ip})"
        )
    else:
        # Direct connection - safe to check localhost
        client_host = getattr(request.client, "host", None) if request.client else None
        if client_host in ("127.0.0.1", "localhost", "::1"):
            logger.debug(f"Rate limit bypassed for {request.url.path}: localhost direct connection ({client_host})")
            return True

    # 4) Test token exemption (CI/staging environment)
    if TEST_BYPASS_TOKEN:
        request_token = request.headers.get("X-Test-Token")
        if request_token == TEST_BYPASS_TOKEN:
            logger.debug(f"Rate limit bypassed for {request.url.path}: valid X-Test-Token")
            return True

    # No bypass conditions met
    return False


def get_rate_limit_key(request: Request) -> str:
    """
    Custom key function for slowapi that implements bypass logic.

    This function replaces the default get_remote_address() function.
    When bypass conditions are met, it returns a unique key that will never
    hit rate limits. Otherwise, it returns the client's remote address.

    Args:
        request: The incoming HTTP request

    Returns:
        A unique key for rate limiting (either bypass key or client address)
    """
    if should_bypass_rate_limit(request):
        # Return a unique key that will never hit rate limits
        # Using timestamp ensures each request gets a different key
        return f"bypass_{time.time()}_{id(request)}"

    # Normal rate limiting based on remote address
    return get_remote_address(request)
