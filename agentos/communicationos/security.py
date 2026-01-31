"""Security policy and permission control for CommunicationOS.

This module implements security policies and permission controls to ensure
safe operation of communication channels, especially when exposed remotely.

Design Principles:
- Secure by default: Chat-only mode with execute disabled
- Defense in depth: Multiple layers of security
- Audit logging: All violations are logged
- Fail-safe: Errors result in denial
- Remote exposure awareness: Special handling for remote mode

Security Architecture:
1. SecurityPolicy: Defines what operations are allowed
2. PolicyEnforcer: Middleware that enforces policies
3. CommandWhitelist: Restricts which commands can be executed
4. RemoteExposureDetector: Detects and warns about remote exposure
5. AdminTokenValidator: Validates admin tokens for elevated operations
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from agentos.communicationos.manifest import SecurityMode
from agentos.communicationos.message_bus import (
    Middleware,
    ProcessingContext,
    ProcessingStatus,
)
from agentos.communicationos.models import InboundMessage, OutboundMessage
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Types of operations that can be restricted.

    Attributes:
        CHAT: Chat/messaging operations (always allowed)
        EXECUTE: Execute commands or scripts
        FILE_ACCESS: Access local files
        SYSTEM_INFO: Query system information
        CONFIG_CHANGE: Change system configuration
    """
    CHAT = "chat"
    EXECUTE = "execute"
    FILE_ACCESS = "file_access"
    SYSTEM_INFO = "system_info"
    CONFIG_CHANGE = "config_change"


class ViolationType(str, Enum):
    """Types of security violations.

    Attributes:
        OPERATION_DENIED: Operation not allowed by policy
        COMMAND_NOT_WHITELISTED: Command not in whitelist
        RATE_LIMIT_EXCEEDED: Too many requests
        INVALID_TOKEN: Invalid or missing admin token
        REMOTE_EXPOSURE_WARNING: Remote exposure detected
    """
    OPERATION_DENIED = "operation_denied"
    COMMAND_NOT_WHITELISTED = "command_not_whitelisted"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    REMOTE_EXPOSURE_WARNING = "remote_exposure_warning"


@dataclass
class SecurityPolicy:
    """Security policy configuration for a channel.

    Attributes:
        mode: Security mode (chat_only or chat_exec_restricted)
        chat_only: If True, only chat operations allowed (default: True)
        allow_execute: If True, allow execute operations (default: False)
        allowed_commands: Whitelist of allowed command prefixes
        require_admin_token: If True, require admin token for elevated operations
        admin_token_hash: SHA-256 hash of admin token (if required)
        allowed_operations: Set of allowed operation types
        rate_limit_per_minute: Maximum requests per minute
        block_on_violation: If True, block message processing on violation
    """
    mode: SecurityMode = SecurityMode.CHAT_ONLY
    chat_only: bool = True
    allow_execute: bool = False
    allowed_commands: List[str] = field(default_factory=lambda: ["/session", "/help"])
    require_admin_token: bool = False
    admin_token_hash: Optional[str] = None
    allowed_operations: Set[OperationType] = field(
        default_factory=lambda: {OperationType.CHAT}
    )
    rate_limit_per_minute: int = 20
    block_on_violation: bool = True

    def __post_init__(self):
        """Validate and normalize policy after initialization."""
        # Ensure chat_only and allow_execute are consistent with mode
        if self.mode == SecurityMode.CHAT_ONLY:
            self.chat_only = True
            self.allow_execute = False
        elif self.mode == SecurityMode.CHAT_EXEC_RESTRICTED:
            self.chat_only = False
            # allow_execute can be True or False in this mode

        # Ensure CHAT is always in allowed_operations
        if OperationType.CHAT not in self.allowed_operations:
            self.allowed_operations.add(OperationType.CHAT)

        # If execute is not allowed, remove it from allowed_operations
        if not self.allow_execute:
            self.allowed_operations.discard(OperationType.EXECUTE)

    @classmethod
    def from_manifest_defaults(cls, security_defaults: Dict) -> SecurityPolicy:
        """Create policy from manifest security_defaults.

        Args:
            security_defaults: Security defaults from ChannelManifest

        Returns:
            SecurityPolicy instance
        """
        mode = SecurityMode(security_defaults.get("mode", "chat_only"))
        allow_execute = security_defaults.get("allow_execute", False)
        allowed_commands = security_defaults.get("allowed_commands", ["/session", "/help"])
        rate_limit = security_defaults.get("rate_limit_per_minute", 20)

        allowed_ops = {OperationType.CHAT}
        if allow_execute:
            allowed_ops.add(OperationType.EXECUTE)

        return cls(
            mode=mode,
            chat_only=(mode == SecurityMode.CHAT_ONLY),
            allow_execute=allow_execute,
            allowed_commands=allowed_commands,
            allowed_operations=allowed_ops,
            rate_limit_per_minute=rate_limit,
        )

    @classmethod
    def default_policy(cls) -> SecurityPolicy:
        """Create default security policy (most restrictive).

        Returns:
            SecurityPolicy with chat_only=True, allow_execute=False
        """
        return cls(
            mode=SecurityMode.CHAT_ONLY,
            chat_only=True,
            allow_execute=False,
            allowed_commands=["/session", "/help"],
            allowed_operations={OperationType.CHAT},
            rate_limit_per_minute=20,
            block_on_violation=True,
        )

    def is_operation_allowed(self, operation: OperationType) -> bool:
        """Check if an operation is allowed by this policy.

        Args:
            operation: Operation type to check

        Returns:
            True if operation is allowed, False otherwise
        """
        return operation in self.allowed_operations

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the whitelist.

        Args:
            command: Command to check (e.g., "/session", "/execute")

        Returns:
            True if command is whitelisted, False otherwise
        """
        command = command.strip().lower()

        # Check if command starts with any whitelisted prefix
        for allowed_prefix in self.allowed_commands:
            if command.startswith(allowed_prefix.lower()):
                return True

        return False

    def validate_admin_token(self, token: Optional[str]) -> bool:
        """Validate admin token.

        Args:
            token: Token to validate

        Returns:
            True if token is valid or not required, False otherwise
        """
        if not self.require_admin_token:
            return True

        if not token or not self.admin_token_hash:
            return False

        # Hash the provided token and compare
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(token_hash, self.admin_token_hash)

    def to_dict(self) -> Dict:
        """Convert policy to dictionary representation.

        Returns:
            Dictionary representation of policy
        """
        return {
            "mode": self.mode.value,
            "chat_only": self.chat_only,
            "allow_execute": self.allow_execute,
            "allowed_commands": self.allowed_commands,
            "require_admin_token": self.require_admin_token,
            "allowed_operations": [op.value for op in self.allowed_operations],
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "block_on_violation": self.block_on_violation,
        }


@dataclass
class SecurityViolation:
    """Record of a security violation.

    Attributes:
        violation_type: Type of violation
        channel_id: Channel where violation occurred
        user_key: User who triggered violation
        message_id: Message ID that triggered violation
        operation: Operation that was attempted
        command: Command that was attempted (if applicable)
        details: Additional details about the violation
        timestamp_ms: When violation occurred (epoch ms)
        blocked: Whether the operation was blocked
    """
    violation_type: ViolationType
    channel_id: str
    user_key: str
    message_id: str
    operation: Optional[str] = None
    command: Optional[str] = None
    details: Optional[str] = None
    timestamp_ms: int = field(default_factory=utc_now_ms)
    blocked: bool = True

    def to_dict(self) -> Dict:
        """Convert violation to dictionary representation.

        Returns:
            Dictionary representation of violation
        """
        return {
            "violation_type": self.violation_type.value,
            "channel_id": self.channel_id,
            "user_key": self.user_key,
            "message_id": self.message_id,
            "operation": self.operation,
            "command": self.command,
            "details": self.details,
            "timestamp_ms": self.timestamp_ms,
            "blocked": self.blocked,
        }


class RemoteExposureDetector:
    """Detector for remote exposure scenarios.

    This detector checks if the system is likely exposed to remote access
    and warns users about security implications.
    """

    @staticmethod
    def is_remote_exposed() -> bool:
        """Check if system is likely exposed remotely.

        This is a heuristic check based on environment variables and
        network configuration. Returns True if remote exposure is detected.

        Returns:
            True if remote exposure detected, False otherwise
        """
        # Check for common remote exposure indicators
        remote_indicators = [
            os.getenv("AGENTOS_REMOTE_MODE", "").lower() == "true",
            os.getenv("RAILWAY_ENVIRONMENT") is not None,
            os.getenv("HEROKU_APP_NAME") is not None,
            os.getenv("VERCEL") is not None,
            os.getenv("AWS_EXECUTION_ENV") is not None,
            os.getenv("KUBERNETES_SERVICE_HOST") is not None,
        ]

        return any(remote_indicators)

    @staticmethod
    def get_exposure_warning() -> str:
        """Get warning message for remote exposure.

        Returns:
            Warning message string
        """
        return (
            "⚠️ SECURITY WARNING: Remote Exposure Detected\n\n"
            "This system appears to be exposed remotely. For security:\n"
            "- Ensure admin token is configured if execute is enabled\n"
            "- Review security policies for all channels\n"
            "- Monitor audit logs for suspicious activity\n"
            "- Consider using VPN or IP whitelisting\n\n"
            "See documentation for remote deployment security best practices."
        )


class PolicyEnforcer(Middleware):
    """Middleware that enforces security policies.

    This middleware intercepts messages and checks them against the
    security policy for the channel. Violations are logged and can
    optionally block message processing.

    Architecture:
    - Checks every inbound message against policy
    - Validates commands against whitelist
    - Logs all violations to audit trail
    - Can block processing based on policy
    """

    def __init__(
        self,
        default_policy: Optional[SecurityPolicy] = None,
        audit_store: Optional[object] = None,
        enable_remote_warnings: bool = True,
    ):
        """Initialize the policy enforcer.

        Args:
            default_policy: Default policy to use (if None, uses most restrictive)
            audit_store: Optional audit store for logging violations
            enable_remote_warnings: If True, warn about remote exposure
        """
        self.default_policy = default_policy or SecurityPolicy.default_policy()
        self.channel_policies: Dict[str, SecurityPolicy] = {}
        self.audit_store = audit_store
        self.enable_remote_warnings = enable_remote_warnings
        self.violations: List[SecurityViolation] = []

        # Check for remote exposure on initialization
        if self.enable_remote_warnings and RemoteExposureDetector.is_remote_exposed():
            logger.warning(RemoteExposureDetector.get_exposure_warning())

    def set_channel_policy(self, channel_id: str, policy: SecurityPolicy) -> None:
        """Set security policy for a specific channel.

        Args:
            channel_id: Channel identifier
            policy: Security policy to apply
        """
        self.channel_policies[channel_id] = policy
        logger.info(f"Set security policy for channel {channel_id}: {policy.mode.value}")

    def get_policy_for_channel(self, channel_id: str) -> SecurityPolicy:
        """Get security policy for a channel.

        Args:
            channel_id: Channel identifier

        Returns:
            SecurityPolicy for the channel (or default if not found)
        """
        return self.channel_policies.get(channel_id, self.default_policy)

    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process inbound message and enforce security policy.

        Args:
            message: InboundMessage to check
            context: Processing context

        Returns:
            Updated context (possibly with REJECT status)
        """
        policy = self.get_policy_for_channel(message.channel_id)

        # Add policy info to context metadata
        context.metadata["security_policy"] = policy.to_dict()

        # Check if message contains a command
        text = message.text or ""
        if text.strip().startswith("/"):
            command = text.strip().split()[0].lower()

            # Check if command is whitelisted
            if not policy.is_command_allowed(command):
                violation = SecurityViolation(
                    violation_type=ViolationType.COMMAND_NOT_WHITELISTED,
                    channel_id=message.channel_id,
                    user_key=message.user_key,
                    message_id=message.message_id,
                    command=command,
                    details=f"Command '{command}' not in whitelist: {policy.allowed_commands}",
                    blocked=policy.block_on_violation,
                )

                self._log_violation(violation)

                if policy.block_on_violation:
                    context.status = ProcessingStatus.REJECT
                    context.error = f"Command not allowed: {command}"
                    context.metadata["security_violation"] = violation.to_dict()

                    logger.warning(
                        f"Blocked command '{command}' from {message.channel_id}:{message.user_key}"
                    )

        # Check for execute-related operations
        # This is a simple heuristic - in production, you'd have more sophisticated detection
        execute_keywords = ["execute", "run", "exec", "system", "shell", "command"]
        lower_text = text.lower()

        if any(keyword in lower_text for keyword in execute_keywords):
            if not policy.is_operation_allowed(OperationType.EXECUTE):
                violation = SecurityViolation(
                    violation_type=ViolationType.OPERATION_DENIED,
                    channel_id=message.channel_id,
                    user_key=message.user_key,
                    message_id=message.message_id,
                    operation=OperationType.EXECUTE.value,
                    details="Execute operation not allowed by policy",
                    blocked=policy.block_on_violation,
                )

                self._log_violation(violation)

                # Don't block - just log warning
                # The actual execution will be blocked by backend if attempted
                context.metadata["execute_warning"] = True

                logger.warning(
                    f"Execute keyword detected in message from "
                    f"{message.channel_id}:{message.user_key} - "
                    f"policy does not allow execute"
                )

        return context

    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process outbound message (minimal checking needed).

        Args:
            message: OutboundMessage to check
            context: Processing context

        Returns:
            Updated context
        """
        # Outbound messages are generally safe, but we add policy info
        policy = self.get_policy_for_channel(message.channel_id)
        context.metadata["security_policy"] = policy.to_dict()

        return context

    def _log_violation(self, violation: SecurityViolation) -> None:
        """Log a security violation.

        Args:
            violation: Security violation to log
        """
        # Add to in-memory list
        self.violations.append(violation)

        # Keep only last 1000 violations in memory
        if len(self.violations) > 1000:
            self.violations = self.violations[-1000:]

        # Log to audit store if available
        if self.audit_store and hasattr(self.audit_store, "log_security_violation"):
            try:
                self.audit_store.log_security_violation(violation.to_dict())
            except Exception as e:
                logger.warning(f"Failed to log violation to audit store: {e}")

        # Always log to application logger
        logger.warning(
            f"Security violation: {violation.violation_type.value} - "
            f"{violation.channel_id}:{violation.user_key} - "
            f"{violation.details}"
        )

    def get_violations(
        self,
        channel_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get recent security violations.

        Args:
            channel_id: Optional channel to filter by
            limit: Maximum number of violations to return

        Returns:
            List of violation dictionaries
        """
        violations = self.violations

        if channel_id:
            violations = [v for v in violations if v.channel_id == channel_id]

        # Return most recent first
        violations = list(reversed(violations))[:limit]

        return [v.to_dict() for v in violations]

    def get_stats(self) -> Dict:
        """Get security statistics.

        Returns:
            Dictionary with security stats
        """
        total = len(self.violations)

        by_type = {}
        by_channel = {}
        blocked_count = 0

        for v in self.violations:
            # Count by type
            vtype = v.violation_type.value
            by_type[vtype] = by_type.get(vtype, 0) + 1

            # Count by channel
            by_channel[v.channel_id] = by_channel.get(v.channel_id, 0) + 1

            # Count blocked
            if v.blocked:
                blocked_count += 1

        return {
            "total_violations": total,
            "blocked_count": blocked_count,
            "by_type": by_type,
            "by_channel": by_channel,
            "policies_configured": len(self.channel_policies),
        }


def generate_admin_token() -> tuple[str, str]:
    """Generate a new admin token and its hash.

    Returns:
        Tuple of (token, token_hash)
    """
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash
