"""
Extension Audit Events

Defines audit event types and data structures for extension execution.
Integrates with the existing audit system in agentos.core.audit.

Part of PR-E3: Permissions + Deny/Audit System
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# ============================================
# Audit Event Types
# ============================================

class ExtensionAuditEventType(str, Enum):
    """
    Audit event types for extension system

    These events track the complete lifecycle of extension execution,
    from routing to completion or denial.
    """
    # Command routing
    EXT_CMD_ROUTED = "EXT_CMD_ROUTED"              # Slash command routed to extension

    # Execution lifecycle
    EXT_RUN_STARTED = "EXT_RUN_STARTED"            # Extension execution started
    EXT_RUN_FINISHED = "EXT_RUN_FINISHED"          # Extension execution completed
    EXT_RUN_DENIED = "EXT_RUN_DENIED"              # Extension execution denied by permissions

    # Permission checks
    EXT_PERMISSION_CHECK = "EXT_PERMISSION_CHECK"  # Permission check performed


# ============================================
# Audit Decision
# ============================================

class AuditDecision(str, Enum):
    """Decision result for audit events"""
    ALLOW = "allow"
    DENY = "deny"
    SKIP = "skip"


# ============================================
# Audit Event Data Class
# ============================================

@dataclass
class ExtensionAuditEvent:
    """
    Audit event for extension execution

    Contains all relevant information about an extension action,
    including permissions, arguments, and execution results.

    Example:
        >>> event = ExtensionAuditEvent(
        ...     event_type=ExtensionAuditEventType.EXT_RUN_STARTED,
        ...     ext_id="tools.postman",
        ...     action="/postman get",
        ...     permissions_requested=["exec_shell", "network_http"],
        ...     decision=AuditDecision.ALLOW,
        ...     session_id="session_123"
        ... )
    """
    # Event identification (required fields first)
    event_type: ExtensionAuditEventType
    ext_id: str
    action: str  # e.g., "/postman get collection-abc"

    # Timestamp with default
    timestamp: datetime = field(default_factory=utc_now)

    # Optional fields
    args_hash: Optional[str] = None  # SHA256 of arguments (for privacy)

    # Permission tracking
    permissions_requested: List[str] = field(default_factory=list)
    decision: AuditDecision = AuditDecision.ALLOW
    reason_code: Optional[str] = None  # Denial/error reason

    # Execution results (for finished events)
    stdout_hash: Optional[str] = None  # SHA256 of stdout
    stderr_hash: Optional[str] = None  # SHA256 of stderr
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None

    # Context
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    user_id: str = "default"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for storage

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        # Convert enums to strings
        data["event_type"] = self.event_type.value
        data["decision"] = self.decision.value
        # Convert timestamp to ISO format
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """
        Serialize to JSON string

        Returns:
            JSON representation
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def hash_data(data: str) -> str:
        """
        Hash sensitive data for privacy

        Args:
            data: Data to hash

        Returns:
            SHA256 hex digest

        Example:
            >>> hash_val = ExtensionAuditEvent.hash_data("sensitive-api-key")
            >>> assert len(hash_val) == 64
        """
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @classmethod
    def create_routed(
        cls,
        ext_id: str,
        action: str,
        args: List[str],
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> "ExtensionAuditEvent":
        """
        Create EXT_CMD_ROUTED event

        Args:
            ext_id: Extension ID
            action: Command action
            args: Command arguments
            session_id: Chat session ID
            project_id: Project ID

        Returns:
            Audit event
        """
        args_str = " ".join(args) if args else ""
        args_hash = cls.hash_data(args_str) if args_str else None

        return cls(
            event_type=ExtensionAuditEventType.EXT_CMD_ROUTED,
            ext_id=ext_id,
            action=action,
            args_hash=args_hash,
            session_id=session_id,
            project_id=project_id,
            decision=AuditDecision.ALLOW
        )

    @classmethod
    def create_started(
        cls,
        ext_id: str,
        action: str,
        permissions_requested: List[str],
        run_id: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> "ExtensionAuditEvent":
        """
        Create EXT_RUN_STARTED event

        Args:
            ext_id: Extension ID
            action: Command action
            permissions_requested: Permissions being used
            run_id: Execution run ID
            session_id: Chat session ID
            project_id: Project ID

        Returns:
            Audit event
        """
        return cls(
            event_type=ExtensionAuditEventType.EXT_RUN_STARTED,
            ext_id=ext_id,
            action=action,
            permissions_requested=permissions_requested,
            decision=AuditDecision.ALLOW,
            run_id=run_id,
            session_id=session_id,
            project_id=project_id
        )

    @classmethod
    def create_finished(
        cls,
        ext_id: str,
        action: str,
        permissions_requested: List[str],
        run_id: str,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> "ExtensionAuditEvent":
        """
        Create EXT_RUN_FINISHED event

        Args:
            ext_id: Extension ID
            action: Command action
            permissions_requested: Permissions used
            run_id: Execution run ID
            stdout: Standard output
            stderr: Standard error
            exit_code: Process exit code
            duration_ms: Execution duration in milliseconds
            session_id: Chat session ID
            project_id: Project ID

        Returns:
            Audit event
        """
        return cls(
            event_type=ExtensionAuditEventType.EXT_RUN_FINISHED,
            ext_id=ext_id,
            action=action,
            permissions_requested=permissions_requested,
            decision=AuditDecision.ALLOW,
            run_id=run_id,
            stdout_hash=cls.hash_data(stdout) if stdout else None,
            stderr_hash=cls.hash_data(stderr) if stderr else None,
            exit_code=exit_code,
            duration_ms=duration_ms,
            session_id=session_id,
            project_id=project_id
        )

    @classmethod
    def create_denied(
        cls,
        ext_id: str,
        action: str,
        permissions_requested: List[str],
        reason_code: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> "ExtensionAuditEvent":
        """
        Create EXT_RUN_DENIED event

        Args:
            ext_id: Extension ID
            action: Command action
            permissions_requested: Permissions that were denied
            reason_code: Reason for denial
            session_id: Chat session ID
            project_id: Project ID

        Returns:
            Audit event
        """
        return cls(
            event_type=ExtensionAuditEventType.EXT_RUN_DENIED,
            ext_id=ext_id,
            action=action,
            permissions_requested=permissions_requested,
            decision=AuditDecision.DENY,
            reason_code=reason_code,
            session_id=session_id,
            project_id=project_id
        )


# ============================================
# Update core audit module
# ============================================

# Add extension event types to core audit system
# These constants are registered in agentos.core.audit module

EXT_CMD_ROUTED = "EXT_CMD_ROUTED"
EXT_RUN_STARTED = "EXT_RUN_STARTED"
EXT_RUN_FINISHED = "EXT_RUN_FINISHED"
EXT_RUN_DENIED = "EXT_RUN_DENIED"
EXT_PERMISSION_CHECK = "EXT_PERMISSION_CHECK"
