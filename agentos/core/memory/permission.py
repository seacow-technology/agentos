"""Memory Permission Service - centralized capability checks

This module provides the permission checking service for Memory operations.
All Memory API calls go through this service to enforce capability-based
access control.

Design Philosophy:
- Single responsibility: Permission checking only
- Always audit: Every check is logged (success or failure)
- Fail-safe: Deny by default if capability unknown
- Performance: Lightweight checks with minimal database queries

Usage:
    from agentos.core.memory.permission import get_permission_service

    service = get_permission_service()
    service.check_capability("chat_agent", "list")  # Raises if denied

Related:
- ADR-012: Memory Capability Contract
- Task #16: Implement Memory Capability checking mechanism
"""

import sqlite3
import logging
from typing import Optional
from pathlib import Path

from agentos.core.memory.capabilities import (
    MemoryCapability,
    AgentCapabilityRecord,
    PermissionDenied,
    get_default_capability,
    CAPABILITY_MATRIX,
    READ_OPERATIONS,
    PROPOSE_OPERATIONS,
    WRITE_OPERATIONS,
    ADMIN_OPERATIONS,
)
from agentos.core.time import utc_now_ms
from agentos.core.storage.paths import component_db_path


logger = logging.getLogger(__name__)


class MemoryPermissionService:
    """Service for checking and managing Memory capabilities."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize permission service.

        Args:
            db_path: Database path (defaults to memoryos component DB)
        """
        if db_path is None:
            db_path = component_db_path("memoryos")
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def check_capability(
        self,
        agent_id: str,
        operation: str,
        context: Optional[dict] = None
    ) -> bool:
        """
        Check if agent has required capability for operation.

        This is the central permission check function. All Memory operations
        MUST call this before executing.

        Args:
            agent_id: Agent identifier (e.g., "chat_agent", "user:alice")
            operation: Operation name (list|search|get|propose|upsert|delete|etc)
            context: Optional context for audit logging

        Returns:
            True if allowed

        Raises:
            PermissionDenied: If agent lacks required capability

        Example:
            >>> service.check_capability("query_agent", "list")
            True
            >>> service.check_capability("query_agent", "upsert")
            PermissionDenied: ...
        """
        # Get agent capability
        capability = self.get_agent_capability(agent_id)

        # Check if capability allows operation
        allowed = operation in CAPABILITY_MATRIX[capability]

        # Audit log (ALWAYS log, success or failure)
        self._audit_capability_check(
            agent_id=agent_id,
            operation=operation,
            capability=capability,
            allowed=allowed,
            context=context or {}
        )

        # Raise if denied
        if not allowed:
            # Determine required capability
            required = self._get_required_capability(operation)
            raise PermissionDenied(
                agent_id=agent_id,
                operation=operation,
                capability=capability,
                required=required
            )

        return True

    def get_agent_capability(self, agent_id: str) -> MemoryCapability:
        """
        Get agent's current Memory capability.

        Resolution order:
        1. Check agent_capabilities table
        2. Check capability expiration
        3. Apply default capability based on agent_id pattern
        4. Fall back to NONE (safe default)

        Args:
            agent_id: Agent identifier

        Returns:
            MemoryCapability enum

        Example:
            >>> service.get_agent_capability("chat_agent")
            MemoryCapability.PROPOSE
            >>> service.get_agent_capability("user:alice")
            MemoryCapability.ADMIN
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            row = cursor.execute("""
                SELECT *
                FROM agent_capabilities
                WHERE agent_id = ?
            """, (agent_id,)).fetchone()

            if not row:
                # Not registered, use default
                default = get_default_capability(agent_id)
                logger.debug(f"Agent {agent_id} not registered, using default: {default.value}")
                return default

            record = AgentCapabilityRecord(
                agent_id=row["agent_id"],
                agent_type=row["agent_type"],
                memory_capability=MemoryCapability(row["memory_capability"]),
                granted_by=row["granted_by"],
                granted_at_ms=row["granted_at_ms"],
                expires_at_ms=row["expires_at_ms"],
                reason=row["reason"]
            )

            # Check expiration
            if record.is_expired:
                logger.warning(f"Agent {agent_id} capability expired, reverting to default")
                return get_default_capability(agent_id)

            return record.memory_capability

        finally:
            conn.close()

    def register_agent_capability(
        self,
        agent_id: str,
        capability: MemoryCapability,
        granted_by: str,
        agent_type: str = "unknown",
        reason: Optional[str] = None,
        expires_at_ms: Optional[int] = None
    ) -> bool:
        """
        Register or update agent capability.

        Args:
            agent_id: Agent identifier
            capability: Capability level to grant
            granted_by: Who is granting this (must have ADMIN)
            agent_type: Type of agent
            reason: Reason for granting
            expires_at_ms: Optional expiration timestamp

        Returns:
            True if successful

        Raises:
            PermissionDenied: If granted_by lacks ADMIN capability

        Example:
            >>> service.register_agent_capability(
            ...     agent_id="new_chat_agent",
            ...     capability=MemoryCapability.PROPOSE,
            ...     granted_by="system",
            ...     reason="Initial setup"
            ... )
            True
        """
        # Check if granter has ADMIN capability (system bypass)
        if granted_by != "system":
            self.check_capability(granted_by, "set_capability")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if exists
            existing = cursor.execute("""
                SELECT memory_capability
                FROM agent_capabilities
                WHERE agent_id = ?
            """, (agent_id,)).fetchone()

            old_capability = existing["memory_capability"] if existing else None

            # Upsert
            cursor.execute("""
                INSERT INTO agent_capabilities
                (agent_id, agent_type, memory_capability, granted_by, granted_at_ms, reason, expires_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    memory_capability = excluded.memory_capability,
                    granted_by = excluded.granted_by,
                    granted_at_ms = excluded.granted_at_ms,
                    reason = excluded.reason,
                    expires_at_ms = excluded.expires_at_ms,
                    agent_type = excluded.agent_type
            """, (
                agent_id,
                agent_type,
                capability.value,
                granted_by,
                utc_now_ms(),
                reason,
                expires_at_ms
            ))

            # Audit log capability change
            cursor.execute("""
                INSERT INTO agent_capability_audit
                (agent_id, old_capability, new_capability, changed_by, changed_at_ms, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                agent_id,
                old_capability,
                capability.value,
                granted_by,
                utc_now_ms(),
                reason
            ))

            conn.commit()

            logger.info(
                f"Registered capability for {agent_id}: "
                f"{old_capability or 'none'} → {capability.value} "
                f"(granted by {granted_by})"
            )

            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to register capability: {e}")
            raise

        finally:
            conn.close()

    def _get_required_capability(self, operation: str) -> MemoryCapability:
        """
        Determine minimum capability required for operation.

        Args:
            operation: Operation name

        Returns:
            Minimum required MemoryCapability
        """
        if operation in ADMIN_OPERATIONS:
            return MemoryCapability.ADMIN
        elif operation in WRITE_OPERATIONS:
            return MemoryCapability.WRITE
        elif operation in PROPOSE_OPERATIONS:
            return MemoryCapability.PROPOSE
        elif operation in READ_OPERATIONS:
            return MemoryCapability.READ
        else:
            # Unknown operations require admin (safe default)
            return MemoryCapability.ADMIN

    def _audit_capability_check(
        self,
        agent_id: str,
        operation: str,
        capability: MemoryCapability,
        allowed: bool,
        context: dict
    ):
        """
        Audit log capability check.

        This function records EVERY capability check to the audit trail,
        whether successful or denied. This provides complete visibility
        into memory access patterns.

        Args:
            agent_id: Agent identifier
            operation: Operation attempted
            capability: Agent's current capability
            allowed: Whether operation was allowed
            context: Additional context
        """
        try:
            from agentos.core.audit import emit_audit_event

            emit_audit_event(
                event_type="MEMORY_CAPABILITY_CHECK",
                metadata={
                    "agent_id": agent_id,
                    "operation": operation,
                    "capability": capability.value,
                    "allowed": allowed,
                    "context": context,
                    "timestamp_ms": utc_now_ms()
                },
                level="info" if allowed else "warning"
            )
        except Exception as e:
            # Graceful degradation - audit failures shouldn't break operations
            logger.warning(f"Failed to audit capability check: {e}")


# ============================================
# Global Singleton Instance
# ============================================

_permission_service: Optional[MemoryPermissionService] = None


def get_permission_service() -> MemoryPermissionService:
    """
    Get global MemoryPermissionService instance.

    Returns:
        Singleton MemoryPermissionService instance

    Example:
        >>> service = get_permission_service()
        >>> service.check_capability("chat_agent", "list")
    """
    global _permission_service
    if _permission_service is None:
        _permission_service = MemoryPermissionService()
    return _permission_service
