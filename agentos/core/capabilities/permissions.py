"""
Permission System for Extension Capabilities

This module implements permission checking for extension execution,
ensuring that extensions only perform actions they have declared
in their manifest and that are allowed by the current deployment mode.

Part of PR-E3: Permissions + Deny/Audit System
"""

import logging
import os
from enum import Enum
from typing import Tuple, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================
# Permission Enumeration
# ============================================

class Permission(str, Enum):
    """
    Permission types for extension capabilities

    Each permission grants specific execution rights to extensions.
    Extensions must declare required permissions in their manifest.
    """
    # Read-only permissions
    READ_STATUS = "read_status"          # Read system/project status
    FS_READ = "fs_read"                  # Read filesystem

    # Write permissions
    FS_WRITE = "fs_write"                # Write to filesystem

    # Network permissions
    NETWORK_HTTP = "network_http"        # Make HTTP/HTTPS requests

    # Execution permissions
    BUILTIN_EXEC = "builtin.exec"        # Execute builtin capability commands
    EXEC_SHELL = "exec_shell"            # Execute shell commands


# ============================================
# Deployment Mode
# ============================================

class DeploymentMode(str, Enum):
    """
    Deployment mode determines permission strictness

    - LOCAL_LOCKED: Most restrictive, suitable for locked-down environments
    - LOCAL_OPEN: Allows all declared permissions for local single-user
    - REMOTE_EXPOSED: Strict mode for multi-user remote deployments
    """
    LOCAL_LOCKED = "local_locked"
    LOCAL_OPEN = "local_open"
    REMOTE_EXPOSED = "remote_exposed"


# ============================================
# Permission Decision
# ============================================

@dataclass
class PermissionDecision:
    """Result of permission check"""
    allowed: bool
    reason: str
    permission: Permission
    mode: DeploymentMode


# ============================================
# Permission Checker
# ============================================

class PermissionChecker:
    """
    Permission checker for extension capabilities

    Validates that extensions have required permissions and that
    those permissions are allowed in the current deployment mode.

    Example:
        >>> checker = PermissionChecker()
        >>> decision = checker.check_permission(
        ...     ext_id="tools.postman",
        ...     permission=Permission.EXEC_SHELL,
        ...     declared_permissions=["exec_shell", "network_http"],
        ...     mode=DeploymentMode.LOCAL_OPEN
        ... )
        >>> assert decision.allowed is True
    """

    def __init__(self, mode: Optional[DeploymentMode] = None):
        """
        Initialize permission checker

        Args:
            mode: Deployment mode, defaults to detection from environment
        """
        self.mode = mode or self._detect_mode()
        logger.info(f"PermissionChecker initialized in {self.mode.value} mode")

    def _detect_mode(self) -> DeploymentMode:
        """
        Detect deployment mode from environment

        Checks AGENTOS_DEPLOYMENT_MODE environment variable.
        Falls back to LOCAL_OPEN for development, LOCAL_LOCKED for production.

        Returns:
            Detected deployment mode
        """
        mode_str = os.getenv("AGENTOS_DEPLOYMENT_MODE", "").lower()

        if mode_str == "remote_exposed":
            return DeploymentMode.REMOTE_EXPOSED
        elif mode_str == "local_locked":
            return DeploymentMode.LOCAL_LOCKED
        elif mode_str == "local_open":
            return DeploymentMode.LOCAL_OPEN

        # Default based on environment
        env = os.getenv("AGENTOS_ENV", "development").lower()
        if env in ("dev", "development", "local"):
            return DeploymentMode.LOCAL_OPEN
        else:
            return DeploymentMode.LOCAL_LOCKED

    def check_permission(
        self,
        ext_id: str,
        permission: Permission,
        declared_permissions: List[str],
        mode: Optional[DeploymentMode] = None
    ) -> PermissionDecision:
        """
        Check if extension has permission to perform action

        Args:
            ext_id: Extension ID
            permission: Permission being requested
            declared_permissions: Permissions declared in manifest
            mode: Override deployment mode (default: use instance mode)

        Returns:
            PermissionDecision with allowed flag and reason

        Example:
            >>> checker = PermissionChecker()
            >>> decision = checker.check_permission(
            ...     ext_id="tools.postman",
            ...     permission=Permission.EXEC_SHELL,
            ...     declared_permissions=["exec_shell"],
            ...     mode=DeploymentMode.REMOTE_EXPOSED
            ... )
            >>> assert decision.allowed is False
            >>> assert "remote_exposed" in decision.reason.lower()
        """
        check_mode = mode or self.mode

        # Step 1: Check if permission is declared in manifest
        if permission.value not in declared_permissions:
            return PermissionDecision(
                allowed=False,
                reason=f"Permission '{permission.value}' not declared in extension manifest. "
                       f"Declared permissions: {declared_permissions}",
                permission=permission,
                mode=check_mode
            )

        # Step 2: Check mode-specific restrictions
        if check_mode == DeploymentMode.REMOTE_EXPOSED:
            # Remote exposed: deny dangerous permissions
            if permission in [Permission.EXEC_SHELL, Permission.FS_WRITE]:
                return PermissionDecision(
                    allowed=False,
                    reason=f"Permission '{permission.value}' is denied in REMOTE_EXPOSED mode. "
                           f"This mode restricts shell execution and filesystem writes for security.",
                    permission=permission,
                    mode=check_mode
                )

        elif check_mode == DeploymentMode.LOCAL_LOCKED:
            # Local locked: deny execution and write permissions by default
            if permission in [Permission.EXEC_SHELL, Permission.FS_WRITE]:
                return PermissionDecision(
                    allowed=False,
                    reason=f"Permission '{permission.value}' is denied in LOCAL_LOCKED mode. "
                           f"This mode restricts high-risk operations.",
                    permission=permission,
                    mode=check_mode
                )

        # Local open: allow all declared permissions
        # Remote exposed: allow safe permissions (read, network)
        return PermissionDecision(
            allowed=True,
            reason=f"Permission '{permission.value}' granted in {check_mode.value} mode",
            permission=permission,
            mode=check_mode
        )

    def check_permissions(
        self,
        ext_id: str,
        permissions: List[Permission],
        declared_permissions: List[str],
        mode: Optional[DeploymentMode] = None
    ) -> List[PermissionDecision]:
        """
        Check multiple permissions at once

        Args:
            ext_id: Extension ID
            permissions: List of permissions to check
            declared_permissions: Permissions declared in manifest
            mode: Override deployment mode

        Returns:
            List of PermissionDecision for each permission

        Example:
            >>> checker = PermissionChecker()
            >>> decisions = checker.check_permissions(
            ...     ext_id="tools.postman",
            ...     permissions=[Permission.EXEC_SHELL, Permission.NETWORK_HTTP],
            ...     declared_permissions=["exec_shell", "network_http"],
            ...     mode=DeploymentMode.LOCAL_OPEN
            ... )
            >>> assert all(d.allowed for d in decisions)
        """
        return [
            self.check_permission(ext_id, perm, declared_permissions, mode)
            for perm in permissions
        ]

    def get_denied_permissions(
        self,
        ext_id: str,
        permissions: List[Permission],
        declared_permissions: List[str],
        mode: Optional[DeploymentMode] = None
    ) -> List[PermissionDecision]:
        """
        Get list of denied permissions

        Args:
            ext_id: Extension ID
            permissions: List of permissions to check
            declared_permissions: Permissions declared in manifest
            mode: Override deployment mode

        Returns:
            List of denied PermissionDecision

        Example:
            >>> checker = PermissionChecker()
            >>> denied = checker.get_denied_permissions(
            ...     ext_id="tools.postman",
            ...     permissions=[Permission.EXEC_SHELL],
            ...     declared_permissions=["exec_shell"],
            ...     mode=DeploymentMode.REMOTE_EXPOSED
            ... )
            >>> assert len(denied) == 1
            >>> assert denied[0].permission == Permission.EXEC_SHELL
        """
        decisions = self.check_permissions(ext_id, permissions, declared_permissions, mode)
        return [d for d in decisions if not d.allowed]

    def has_all_permissions(
        self,
        ext_id: str,
        permissions: List[Permission],
        declared_permissions: List[str],
        mode: Optional[DeploymentMode] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if extension has all required permissions

        Args:
            ext_id: Extension ID
            permissions: List of required permissions
            declared_permissions: Permissions declared in manifest
            mode: Override deployment mode

        Returns:
            Tuple of (all_granted: bool, denial_reason: Optional[str])

        Example:
            >>> checker = PermissionChecker()
            >>> granted, reason = checker.has_all_permissions(
            ...     ext_id="tools.postman",
            ...     permissions=[Permission.EXEC_SHELL, Permission.NETWORK_HTTP],
            ...     declared_permissions=["exec_shell", "network_http"],
            ...     mode=DeploymentMode.LOCAL_OPEN
            ... )
            >>> assert granted is True
            >>> assert reason is None
        """
        denied = self.get_denied_permissions(ext_id, permissions, declared_permissions, mode)

        if denied:
            reasons = [d.reason for d in denied]
            return False, "; ".join(reasons)

        return True, None


# ============================================
# Global Permission Checker Instance
# ============================================

_global_checker: Optional[PermissionChecker] = None


def get_permission_checker() -> PermissionChecker:
    """
    Get global permission checker instance

    Returns:
        Shared PermissionChecker instance
    """
    global _global_checker
    if _global_checker is None:
        _global_checker = PermissionChecker()
    return _global_checker


def reset_permission_checker():
    """Reset global permission checker (for testing)"""
    global _global_checker
    _global_checker = None
