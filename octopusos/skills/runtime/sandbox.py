"""Sandbox Guards - Network and Filesystem Permission Guards.

This module implements permission guards for skills:
1. NetGuard - Validates network access against allowlist
2. FsGuard - Validates filesystem access permissions

Design Principles:
- Fail-closed: Unknown/missing permissions = denied
- Allowlist-based: Explicit permission required
- Audit trail: All checks logged for security review

MVP Implementation:
- Simple domain matching for net
- Basic read/write checks for fs
- Production should integrate with OS-level sandboxing (AppArmor, SELinux, Docker)

Security Notes:
- These guards are NOT a substitute for OS-level sandboxing
- Skills can potentially bypass these guards if they're malicious
- Future: Integrate with subprocess/container isolation
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when permission check fails."""
    pass


class NetGuard:
    """Network access guard.

    Validates network operations against skill manifest permissions.
    MVP: Simple domain allowlist matching.

    Future enhancements:
    - Protocol restrictions (HTTP/HTTPS only)
    - Port restrictions
    - Rate limiting per domain
    - Integration with firewall rules

    Examples:
        >>> guard = NetGuard()
        >>> guard.check_domain("api.github.com", ["api.github.com"])  # OK
        >>> guard.check_domain("evil.com", ["api.github.com"])  # Raises PermissionDeniedError
    """

    def check_domain(self, domain: str, allow_list: List[str]) -> bool:
        """Check if domain is in allowlist.

        Args:
            domain: Domain to check (e.g., "api.github.com")
            allow_list: List of allowed domains from manifest

        Returns:
            bool: True if allowed

        Raises:
            PermissionDeniedError: If domain not in allowlist

        Security notes:
        - MVP: Exact match only
        - Production should support:
          - Wildcard subdomains (*.github.com)
          - CIDR ranges for IPs
          - TLD restrictions
        """
        if not domain:
            raise PermissionDeniedError("Empty domain not allowed")

        if not allow_list:
            raise PermissionDeniedError(f"No network permissions granted (domain: {domain})")

        # Normalize domain (lowercase, strip whitespace)
        domain = domain.strip().lower()
        allow_list = [d.strip().lower() for d in allow_list]

        if domain not in allow_list:
            logger.warning(
                f"Network permission denied: domain '{domain}' not in allowlist {allow_list}",
                extra={
                    "security_event": "net_permission_denied",
                    "domain": domain,
                    "allowlist": allow_list,
                }
            )
            raise PermissionDeniedError(
                f"Network access denied: domain '{domain}' not in allowlist. "
                f"Allowed domains: {', '.join(allow_list)}"
            )

        logger.debug(f"Network permission granted: {domain}")
        return True

    def is_allowed(self, domain: str, allow_list: List[str]) -> bool:
        """Non-throwing version of check_domain.

        Args:
            domain: Domain to check
            allow_list: List of allowed domains

        Returns:
            bool: True if allowed, False otherwise
        """
        try:
            return self.check_domain(domain, allow_list)
        except PermissionDeniedError:
            return False


class FsGuard:
    """Filesystem access guard.

    Validates filesystem operations against skill manifest permissions.
    MVP: Simple read/write boolean checks.

    Future enhancements:
    - Path-based restrictions (only /tmp, only project dir)
    - File type restrictions (no .exe, no .sh)
    - Size limits
    - Integration with chroot/mount namespaces

    Examples:
        >>> guard = FsGuard()
        >>> guard.check_write("/tmp/test.txt", write_allowed=True)  # OK
        >>> guard.check_write("/tmp/test.txt", write_allowed=False)  # Raises PermissionDeniedError
    """

    def check_read(self, path: str, read_allowed: bool) -> bool:
        """Check if read operation is allowed.

        Args:
            path: File path to read
            read_allowed: Whether read permission is granted in manifest

        Returns:
            bool: True if allowed

        Raises:
            PermissionDeniedError: If read not allowed
        """
        if not read_allowed:
            logger.warning(
                f"Filesystem read permission denied: {path}",
                extra={
                    "security_event": "fs_read_denied",
                    "path": path,
                }
            )
            raise PermissionDeniedError(
                f"Filesystem read denied: skill does not have read permission. "
                f"Path: {path}"
            )

        logger.debug(f"Filesystem read permission granted: {path}")
        return True

    def check_write(self, path: str, write_allowed: bool) -> bool:
        """Check if write operation is allowed.

        Args:
            path: File path to write
            write_allowed: Whether write permission is granted in manifest

        Returns:
            bool: True if allowed

        Raises:
            PermissionDeniedError: If write not allowed
        """
        if not write_allowed:
            logger.warning(
                f"Filesystem write permission denied: {path}",
                extra={
                    "security_event": "fs_write_denied",
                    "path": path,
                }
            )
            raise PermissionDeniedError(
                f"Filesystem write denied: skill does not have write permission. "
                f"Path: {path}"
            )

        logger.debug(f"Filesystem write permission granted: {path}")
        return True

    def is_read_allowed(self, path: str, read_allowed: bool) -> bool:
        """Non-throwing version of check_read."""
        try:
            return self.check_read(path, read_allowed)
        except PermissionDeniedError:
            return False

    def is_write_allowed(self, path: str, write_allowed: bool) -> bool:
        """Non-throwing version of check_write."""
        try:
            return self.check_write(path, write_allowed)
        except PermissionDeniedError:
            return False


__all__ = [
    "PermissionDeniedError",
    "NetGuard",
    "FsGuard",
]
