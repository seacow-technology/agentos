"""
Escalation Engine - AgentOS v3

权限升级请求引擎：
1. 创建escalation请求
2. 审批/拒绝请求
3. 临时授权管理
4. 请求过期处理

Design Philosophy:
- 请求必须有充分理由（防止滥用）
- 临时授权有时限（默认24h）
- 完整审计追踪
- 自动过期清理
"""

import logging
import sqlite3
import secrets
from typing import List, Dict, Any, Optional

from agentos.core.time import utc_now_ms
from agentos.core.agent.models import EscalationRequest, EscalationStatus


logger = logging.getLogger(__name__)


class EscalationEngine:
    """
    Escalation request management engine.

    Handles:
    - Creating escalation requests
    - Approving/denying requests
    - Temporary capability grants
    - Request expiration

    Usage:
        engine = EscalationEngine()

        # Create request
        request_id = engine.create_request(
            agent_id="chat_agent",
            capability_id="action.execute.local",
            reason="Need to execute validation script for user request"
        )

        # Admin approves
        engine.approve_request(
            request_id=request_id,
            reviewer_id="admin:alice",
            grant_duration_ms=3600000  # 1 hour
        )

        # Or admin denies
        engine.deny_request(
            request_id=request_id,
            reviewer_id="admin:alice",
            reason="Insufficient justification"
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize escalation engine.

        Args:
            db_path: Optional database path
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path

        logger.info("EscalationEngine initialized")

    def create_request(
        self,
        agent_id: str,
        capability_id: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create escalation request.

        Args:
            agent_id: Agent requesting capability
            capability_id: Capability requested
            reason: Reason for request (min 10 chars)
            context: Additional context

        Returns:
            Request ID

        Raises:
            ValueError: If reason is too short
        """
        # Validate reason
        if len(reason) < 10:
            raise ValueError(
                f"Escalation reason too short ({len(reason)} chars), "
                f"minimum 10 characters required"
            )

        # Generate request ID
        request_id = f"escalation-{secrets.token_hex(8)}"

        # Create request
        now_ms = utc_now_ms()
        request = EscalationRequest(
            request_id=request_id,
            agent_id=agent_id,
            requested_capability=capability_id,
            reason=reason,
            status=EscalationStatus.PENDING,
            requested_at_ms=now_ms,
            context=context or {},
        )

        # Store request
        self._store_request(request)

        # Notify admins (placeholder)
        self._notify_admins(request)

        logger.info(
            f"Escalation request created: {request_id} for {agent_id} -> {capability_id}"
        )

        return request_id

    def approve_request(
        self,
        request_id: str,
        reviewer_id: str,
        grant_duration_ms: Optional[int] = None,
        governance_engine: Optional[Any] = None,
    ) -> bool:
        """
        Approve escalation request and grant capability.

        Args:
            request_id: Request identifier
            reviewer_id: Admin reviewing request
            grant_duration_ms: How long grant is valid (default: 24h)
            governance_engine: Optional governance engine for permission check

        Returns:
            True if approved

        Raises:
            ValueError: If request not found or not pending
            InsufficientPermissionError: If reviewer lacks permission
        """
        # Check permission (if governance engine provided)
        if governance_engine:
            from agentos.core.agent.agent_tier import InsufficientPermissionError

            perm_result = governance_engine.check_permission(
                agent_id=reviewer_id,
                capability_id="governance.escalation.approve",
                context={"request_id": request_id},
            )

            if not perm_result.allowed:
                raise InsufficientPermissionError(
                    f"User '{reviewer_id}' lacks permission to approve escalations. "
                    f"Reason: {perm_result.reason}"
                )

        # Get request
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Escalation request not found: {request_id}")

        if request.status != EscalationStatus.PENDING:
            raise ValueError(
                f"Request {request_id} is not pending (status={request.status.value})"
            )

        # Update request status
        now_ms = utc_now_ms()
        request.status = EscalationStatus.APPROVED
        request.reviewed_by = reviewer_id
        request.reviewed_at_ms = now_ms

        self._update_request(request)

        # Grant capability
        from agentos.core.capability.registry import get_capability_registry

        registry = get_capability_registry(self.db_path)

        if grant_duration_ms is None:
            grant_duration_ms = 24 * 60 * 60 * 1000  # Default: 24h

        expires_at_ms = now_ms + grant_duration_ms

        registry.grant_capability(
            agent_id=request.agent_id,
            capability_id=request.requested_capability,
            granted_by=reviewer_id,
            expires_at_ms=expires_at_ms,
            reason=f"Escalation request approved: {request_id}",
            metadata={"escalation_request_id": request_id},
        )

        logger.info(
            f"Escalation approved: {request_id} by {reviewer_id}, "
            f"granted {request.requested_capability} to {request.agent_id} "
            f"until {expires_at_ms}"
        )

        return True

    def deny_request(
        self,
        request_id: str,
        reviewer_id: str,
        reason: str,
        governance_engine: Optional[Any] = None,
    ) -> bool:
        """
        Deny escalation request.

        Args:
            request_id: Request identifier
            reviewer_id: Admin reviewing request
            reason: Reason for denial
            governance_engine: Optional governance engine for permission check

        Returns:
            True if denied

        Raises:
            ValueError: If request not found or not pending
            InsufficientPermissionError: If reviewer lacks permission
        """
        # Check permission (if governance engine provided)
        if governance_engine:
            from agentos.core.agent.agent_tier import InsufficientPermissionError

            perm_result = governance_engine.check_permission(
                agent_id=reviewer_id,
                capability_id="governance.escalation.deny",
                context={"request_id": request_id},
            )

            if not perm_result.allowed:
                raise InsufficientPermissionError(
                    f"User '{reviewer_id}' lacks permission to deny escalations. "
                    f"Reason: {perm_result.reason}"
                )

        # Get request
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Escalation request not found: {request_id}")

        if request.status != EscalationStatus.PENDING:
            raise ValueError(
                f"Request {request_id} is not pending (status={request.status.value})"
            )

        # Update request status
        now_ms = utc_now_ms()
        request.status = EscalationStatus.DENIED
        request.reviewed_by = reviewer_id
        request.reviewed_at_ms = now_ms
        request.deny_reason = reason

        self._update_request(request)

        logger.info(
            f"Escalation denied: {request_id} by {reviewer_id}, reason: {reason}"
        )

        return True

    def cancel_request(self, request_id: str, agent_id: str) -> bool:
        """
        Cancel pending escalation request.

        Args:
            request_id: Request identifier
            agent_id: Agent canceling (must match request agent)

        Returns:
            True if cancelled

        Raises:
            ValueError: If request not found, not pending, or wrong agent
        """
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Escalation request not found: {request_id}")

        if request.agent_id != agent_id:
            raise ValueError(
                f"Agent {agent_id} cannot cancel request owned by {request.agent_id}"
            )

        if request.status != EscalationStatus.PENDING:
            raise ValueError(
                f"Request {request_id} is not pending (status={request.status.value})"
            )

        # Update status
        request.status = EscalationStatus.CANCELLED
        self._update_request(request)

        logger.info(f"Escalation cancelled: {request_id} by {agent_id}")

        return True

    def get_request(self, request_id: str) -> Optional[EscalationRequest]:
        """
        Get escalation request by ID.

        Args:
            request_id: Request identifier

        Returns:
            EscalationRequest or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT request_id, agent_id, requested_capability, reason, status,
                   requested_at_ms, reviewed_by, reviewed_at_ms, deny_reason
            FROM escalation_requests
            WHERE request_id = ?
            """,
            (request_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        request = EscalationRequest(
            request_id=row["request_id"],
            agent_id=row["agent_id"],
            requested_capability=row["requested_capability"],
            reason=row["reason"],
            status=EscalationStatus(row["status"]),
            requested_at_ms=row["requested_at_ms"],
            reviewed_by=row["reviewed_by"],
            reviewed_at_ms=row["reviewed_at_ms"],
            deny_reason=row["deny_reason"],
        )

        return request

    def list_pending_requests(self) -> List[EscalationRequest]:
        """
        List all pending escalation requests.

        Returns:
            List of EscalationRequest objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT request_id, agent_id, requested_capability, reason, status,
                   requested_at_ms, reviewed_by, reviewed_at_ms, deny_reason
            FROM escalation_requests
            WHERE status = 'pending'
            ORDER BY requested_at_ms ASC
            """
        )

        rows = cursor.fetchall()
        conn.close()

        requests = []
        for row in rows:
            request = EscalationRequest(
                request_id=row["request_id"],
                agent_id=row["agent_id"],
                requested_capability=row["requested_capability"],
                reason=row["reason"],
                status=EscalationStatus(row["status"]),
                requested_at_ms=row["requested_at_ms"],
                reviewed_by=row["reviewed_by"],
                reviewed_at_ms=row["reviewed_at_ms"],
                deny_reason=row["deny_reason"],
            )
            requests.append(request)

        return requests

    def list_agent_requests(
        self, agent_id: str, include_completed: bool = False
    ) -> List[EscalationRequest]:
        """
        List escalation requests for agent.

        Args:
            agent_id: Agent identifier
            include_completed: Include approved/denied/expired requests

        Returns:
            List of EscalationRequest objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if include_completed:
            cursor.execute(
                """
                SELECT request_id, agent_id, requested_capability, reason, status,
                       requested_at_ms, reviewed_by, reviewed_at_ms, deny_reason
                FROM escalation_requests
                WHERE agent_id = ?
                ORDER BY requested_at_ms DESC
                """,
                (agent_id,),
            )
        else:
            cursor.execute(
                """
                SELECT request_id, agent_id, requested_capability, reason, status,
                       requested_at_ms, reviewed_by, reviewed_at_ms, deny_reason
                FROM escalation_requests
                WHERE agent_id = ? AND status = 'pending'
                ORDER BY requested_at_ms DESC
                """,
                (agent_id,),
            )

        rows = cursor.fetchall()
        conn.close()

        requests = []
        for row in rows:
            request = EscalationRequest(
                request_id=row["request_id"],
                agent_id=row["agent_id"],
                requested_capability=row["requested_capability"],
                reason=row["reason"],
                status=EscalationStatus(row["status"]),
                requested_at_ms=row["requested_at_ms"],
                reviewed_by=row["reviewed_by"],
                reviewed_at_ms=row["reviewed_at_ms"],
                deny_reason=row["deny_reason"],
            )
            requests.append(request)

        return requests

    def expire_old_requests(self, max_age_ms: int = 7 * 24 * 60 * 60 * 1000) -> int:
        """
        Expire old pending requests.

        Args:
            max_age_ms: Maximum age in milliseconds (default: 7 days)

        Returns:
            Number of requests expired
        """
        cutoff_ms = utc_now_ms() - max_age_ms

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE escalation_requests
            SET status = 'expired'
            WHERE status = 'pending' AND requested_at_ms < ?
            """,
            (cutoff_ms,),
        )

        expired_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Expired {expired_count} old escalation requests")

        return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get escalation engine statistics.

        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Count by status
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM escalation_requests
            GROUP BY status
            """
        )

        status_counts = {}
        for row in cursor.fetchall():
            status_counts[row["status"]] = row["count"]

        # Pending requests by agent
        cursor.execute(
            """
            SELECT agent_id, COUNT(*) as count
            FROM escalation_requests
            WHERE status = 'pending'
            GROUP BY agent_id
            ORDER BY count DESC
            LIMIT 10
            """
        )

        top_agents = []
        for row in cursor.fetchall():
            top_agents.append(
                {"agent_id": row["agent_id"], "pending_count": row["count"]}
            )

        # Recent approvals
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM escalation_requests
            WHERE status = 'approved' AND reviewed_at_ms > ?
            """,
            (utc_now_ms() - 24 * 60 * 60 * 1000,),  # Last 24h
        )
        recent_approvals = cursor.fetchone()["count"]

        conn.close()

        return {
            "status_counts": status_counts,
            "top_agents_with_pending": top_agents,
            "recent_approvals_24h": recent_approvals,
        }

    def _store_request(self, request: EscalationRequest):
        """Store escalation request to database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO escalation_requests (
                request_id, agent_id, requested_capability, reason, status,
                requested_at_ms, reviewed_by, reviewed_at_ms, deny_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.request_id,
                request.agent_id,
                request.requested_capability,
                request.reason,
                request.status.value,
                request.requested_at_ms,
                request.reviewed_by,
                request.reviewed_at_ms,
                request.deny_reason,
            ),
        )

        conn.commit()
        conn.close()

    def _update_request(self, request: EscalationRequest):
        """Update escalation request in database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE escalation_requests
            SET status = ?, reviewed_by = ?, reviewed_at_ms = ?, deny_reason = ?
            WHERE request_id = ?
            """,
            (
                request.status.value,
                request.reviewed_by,
                request.reviewed_at_ms,
                request.deny_reason,
                request.request_id,
            ),
        )

        conn.commit()
        conn.close()

    def _notify_admins(self, request: EscalationRequest):
        """
        Notify admins of new escalation request.

        TODO: Implement actual notification (email, webhook, etc.)
        """
        logger.info(
            f"[NOTIFY] New escalation request: {request.request_id} from {request.agent_id}"
        )
        # Placeholder for notification logic

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
