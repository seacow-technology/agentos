"""
Admin Token Management - Simplified token validation for high-risk operations

This module provides a simple admin token validation system for PR-3.
Future versions can upgrade to JWT with expiry and claims.

Features:
- Environment variable-based token validation
- Simple string comparison (secure for MVP)
- Ready for JWT upgrade in future PRs

Usage:
    import os
    from agentos.core.capabilities.admin_token import AdminTokenManager

    # Set admin token in environment
    os.environ["AGENTOS_ADMIN_TOKEN"] = "my-secure-token"

    # Create manager
    manager = AdminTokenManager()

    # Validate token
    if manager.validate_token("my-secure-token"):
        print("Token valid!")
    else:
        print("Token invalid!")
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class AdminTokenManager:
    """
    Admin token manager for high-risk operation approval

    PR-3 Implementation:
    - Simple environment variable-based validation
    - Uses AGENTOS_ADMIN_TOKEN env var
    - Constant-time string comparison

    Future Enhancements (PR-4+):
    - JWT with expiry
    - Token claims (user_id, permissions, etc.)
    - Token revocation
    - Audit trail for token usage
    """

    ENV_VAR_NAME = "AGENTOS_ADMIN_TOKEN"

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize admin token manager

        Args:
            secret_key: Optional secret key (reserved for future JWT implementation)
        """
        self.secret_key = secret_key
        self._load_token()

    def _load_token(self):
        """Load admin token from environment variable"""
        self._admin_token = os.environ.get(self.ENV_VAR_NAME)

        if not self._admin_token:
            logger.warning(
                f"Admin token not set. Set {self.ENV_VAR_NAME} environment variable "
                f"to enable admin-protected operations."
            )

    def validate_token(self, token: str) -> bool:
        """
        Validate admin token

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if not self._admin_token:
            logger.warning("No admin token configured - validation failed")
            return False

        if not token:
            return False

        # Constant-time comparison to prevent timing attacks
        return self._constant_time_compare(token, self._admin_token)

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks

        Args:
            a: First string
            b: Second string

        Returns:
            True if strings are equal
        """
        if len(a) != len(b):
            return False

        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)

        return result == 0

    def is_configured(self) -> bool:
        """
        Check if admin token is configured

        Returns:
            True if admin token is set
        """
        return self._admin_token is not None

    def generate_token(self, user_id: str, expiry_minutes: int = 60) -> str:
        """
        Generate admin token (FUTURE - Not implemented in PR-3)

        This is a placeholder for future JWT implementation.

        Args:
            user_id: User identifier
            expiry_minutes: Token expiry in minutes

        Returns:
            Generated token

        Raises:
            NotImplementedError: Not implemented in PR-3
        """
        raise NotImplementedError(
            "Token generation not implemented in PR-3. "
            "Use environment variable AGENTOS_ADMIN_TOKEN instead."
        )

    def revoke_token(self, token: str):
        """
        Revoke admin token (FUTURE - Not implemented in PR-3)

        This is a placeholder for future revocation system.

        Args:
            token: Token to revoke

        Raises:
            NotImplementedError: Not implemented in PR-3
        """
        raise NotImplementedError(
            "Token revocation not implemented in PR-3."
        )


# Global singleton instance
_token_manager: Optional[AdminTokenManager] = None


def get_admin_token_manager() -> AdminTokenManager:
    """
    Get global admin token manager instance

    Returns:
        AdminTokenManager singleton
    """
    global _token_manager
    if _token_manager is None:
        _token_manager = AdminTokenManager()
    return _token_manager


def validate_admin_token(token: str) -> bool:
    """
    Convenience function to validate admin token

    Args:
        token: Token to validate

    Returns:
        True if token is valid
    """
    manager = get_admin_token_manager()
    return manager.validate_token(token)
