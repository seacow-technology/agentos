"""Memory Proposal System - approval workflow for PROPOSE capability

This module implements the complete proposal workflow:
- Chat agents can propose memories (PROPOSE capability)
- Proposals enter pending queue
- Admins review and approve/reject (ADMIN capability)
- Only approved proposals are written to memory_items

This is the key anti-hallucination mechanism - preventing untrusted agents
from polluting the Memory system with incorrect information.

Design Philosophy:
- Defense-in-depth: Prevent hallucinations from reaching Memory
- Human-in-the-loop: Require admin approval for chat agent memories
- Auditability: Complete trail of proposals and decisions
- Graceful degradation: Notification failures don't block proposals

Related:
- ADR-012: Memory Capability Contract
- Task #16: Memory Capability checking mechanism
- Task #17: Memory Propose workflow

Usage:
    from agentos.core.memory.proposals import get_proposal_service

    # Chat agent proposes memory
    service = get_proposal_service()
    proposal_id = service.propose_memory(
        agent_id="chat_agent",
        memory_item={"scope": "global", "type": "preference", ...},
        reason="User said: call me Alice"
    )

    # Admin reviews and approves
    memory_id = service.approve_proposal(
        reviewer_id="user:admin",
        proposal_id=proposal_id,
        reason="Verified with user"
    )
"""

import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from agentos.core.memory.capabilities import MemoryCapability
from agentos.core.memory.permission import get_permission_service
from agentos.core.time import utc_now_ms
from agentos.util.ulid import ulid


logger = logging.getLogger(__name__)


class ProposalStatus:
    """Proposal status constants"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryProposalService:
    """Service for managing Memory proposals (PROPOSE capability workflow)"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("memoryos")
        self.db_path = db_path
        self.permission_service = get_permission_service()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def propose_memory(
        self,
        agent_id: str,
        memory_item: dict,
        reason: Optional[str] = None
    ) -> str:
        """
        Create a memory proposal (requires PROPOSE capability).

        The proposal enters pending state and requires admin approval
        before being written to memory_items.

        Args:
            agent_id: Agent proposing the memory
            memory_item: MemoryItem dict to propose
            reason: Optional reason for the proposal

        Returns:
            proposal_id

        Raises:
            PermissionDenied: If agent lacks PROPOSE capability

        Example:
            >>> service.propose_memory(
            ...     agent_id="chat_agent",
            ...     memory_item={
            ...         "scope": "global",
            ...         "type": "preference",
            ...         "content": {"key": "preferred_name", "value": "Alice"}
            ...     },
            ...     reason="User said: 'call me Alice'"
            ... )
            '01HX123...'
        """
        # Permission check
        self.permission_service.check_capability(agent_id, "propose")

        proposal_id = ulid()
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Insert proposal
            cursor.execute("""
                INSERT INTO memory_proposals
                (proposal_id, proposed_by, proposed_at_ms, memory_item, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                proposal_id,
                agent_id,
                utc_now_ms(),
                json.dumps(memory_item),
                ProposalStatus.PENDING,
                json.dumps({"reason": reason} if reason else {})
            ))

            conn.commit()

            logger.info(
                f"Memory proposal created: {proposal_id} by {agent_id} "
                f"(type: {memory_item.get('type')}, scope: {memory_item.get('scope')})"
            )

            # Trigger notification (non-blocking)
            try:
                self._notify_admins_new_proposal(proposal_id, agent_id, memory_item)
            except Exception as e:
                logger.warning(f"Failed to notify admins: {e}")

            # Audit event
            self._audit_proposal_event(
                event_type="memory_proposal_created",
                proposal_id=proposal_id,
                agent_id=agent_id,
                memory_item=memory_item
            )

            return proposal_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create proposal: {e}")
            raise

        finally:
            conn.close()

    def approve_proposal(
        self,
        reviewer_id: str,
        proposal_id: str,
        reason: Optional[str] = None
    ) -> str:
        """
        Approve a proposal and write to memory_items (requires ADMIN capability).

        This is the critical step where a proposed memory becomes real.
        The reviewer's ADMIN capability is used to write to memory_items.

        Args:
            reviewer_id: Who is approving (must have ADMIN)
            proposal_id: Proposal to approve
            reason: Optional reason for approval

        Returns:
            memory_id (the created memory item ID)

        Raises:
            PermissionDenied: If reviewer lacks ADMIN capability
            ValueError: If proposal not found or not pending

        Example:
            >>> service.approve_proposal(
            ...     reviewer_id="user:admin",
            ...     proposal_id="01HX123...",
            ...     reason="Verified with user"
            ... )
            'mem-abc123...'
        """
        # Permission check
        self.permission_service.check_capability(reviewer_id, "approve_proposal")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get proposal
            row = cursor.execute("""
                SELECT * FROM memory_proposals WHERE proposal_id = ?
            """, (proposal_id,)).fetchone()

            if not row:
                raise ValueError(f"Proposal not found: {proposal_id}")

            if row["status"] != ProposalStatus.PENDING:
                raise ValueError(
                    f"Proposal {proposal_id} is not pending (status: {row['status']})"
                )

            # Parse memory item
            memory_item = json.loads(row["memory_item"])

            # Write to memory_items using MemoryService
            # (use reviewer's ADMIN capability for the write)
            from agentos.core.memory.service import MemoryService
            memory_service = MemoryService(db_path=self.db_path)

            memory_id = memory_service.upsert(
                agent_id=reviewer_id,  # Use reviewer's capability
                memory_item=memory_item
            )

            # Update proposal status
            cursor.execute("""
                UPDATE memory_proposals
                SET status = ?,
                    reviewed_by = ?,
                    reviewed_at_ms = ?,
                    review_reason = ?,
                    resulting_memory_id = ?
                WHERE proposal_id = ?
            """, (
                ProposalStatus.APPROVED,
                reviewer_id,
                utc_now_ms(),
                reason,
                memory_id,
                proposal_id
            ))

            conn.commit()

            logger.info(
                f"Proposal {proposal_id} approved by {reviewer_id} "
                f"(memory_id: {memory_id})"
            )

            # Audit event
            self._audit_proposal_event(
                event_type="memory_proposal_approved",
                proposal_id=proposal_id,
                agent_id=row["proposed_by"],
                reviewer_id=reviewer_id,
                memory_id=memory_id
            )

            return memory_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to approve proposal: {e}")
            raise

        finally:
            conn.close()

    def reject_proposal(
        self,
        reviewer_id: str,
        proposal_id: str,
        reason: str
    ) -> bool:
        """
        Reject a proposal (requires ADMIN capability).

        Args:
            reviewer_id: Who is rejecting (must have ADMIN)
            proposal_id: Proposal to reject
            reason: Reason for rejection (required)

        Returns:
            True if successful

        Raises:
            PermissionDenied: If reviewer lacks ADMIN capability
            ValueError: If proposal not found or not pending, or reason empty

        Example:
            >>> service.reject_proposal(
            ...     reviewer_id="user:admin",
            ...     proposal_id="01HX123...",
            ...     reason="Hallucinated information - user never said this"
            ... )
            True
        """
        # Permission check
        self.permission_service.check_capability(reviewer_id, "reject_proposal")

        if not reason or not reason.strip():
            raise ValueError("Rejection reason is required")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get proposal
            row = cursor.execute("""
                SELECT * FROM memory_proposals WHERE proposal_id = ?
            """, (proposal_id,)).fetchone()

            if not row:
                raise ValueError(f"Proposal not found: {proposal_id}")

            if row["status"] != ProposalStatus.PENDING:
                raise ValueError(
                    f"Proposal {proposal_id} is not pending (status: {row['status']})"
                )

            # Update proposal status
            cursor.execute("""
                UPDATE memory_proposals
                SET status = ?,
                    reviewed_by = ?,
                    reviewed_at_ms = ?,
                    review_reason = ?
                WHERE proposal_id = ?
            """, (
                ProposalStatus.REJECTED,
                reviewer_id,
                utc_now_ms(),
                reason,
                proposal_id
            ))

            conn.commit()

            logger.info(
                f"Proposal {proposal_id} rejected by {reviewer_id} "
                f"(reason: {reason})"
            )

            # Audit event
            self._audit_proposal_event(
                event_type="memory_proposal_rejected",
                proposal_id=proposal_id,
                agent_id=row["proposed_by"],
                reviewer_id=reviewer_id,
                reason=reason
            )

            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to reject proposal: {e}")
            raise

        finally:
            conn.close()

    def list_proposals(
        self,
        agent_id: str,
        status: Optional[str] = None,
        proposed_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List proposals (requires READ capability).

        Args:
            agent_id: Agent requesting list
            status: Filter by status (pending/approved/rejected)
            proposed_by: Filter by proposer
            limit: Max results
            offset: Pagination offset

        Returns:
            List of proposal dicts

        Raises:
            PermissionDenied: If agent lacks READ capability

        Example:
            >>> service.list_proposals("user:admin", status="pending")
            [{"proposal_id": "01HX...", "status": "pending", ...}, ...]
        """
        # Permission check (need at least READ to view proposals)
        self.permission_service.check_capability(agent_id, "list")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM memory_proposals WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if proposed_by:
                query += " AND proposed_by = ?"
                params.append(proposed_by)

            query += " ORDER BY proposed_at_ms DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            proposals = []
            for row in rows:
                proposals.append({
                    "proposal_id": row["proposal_id"],
                    "proposed_by": row["proposed_by"],
                    "proposed_at_ms": row["proposed_at_ms"],
                    "memory_item": json.loads(row["memory_item"]),
                    "status": row["status"],
                    "reviewed_by": row["reviewed_by"],
                    "reviewed_at_ms": row["reviewed_at_ms"],
                    "review_reason": row["review_reason"],
                    "resulting_memory_id": row["resulting_memory_id"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                })

            return proposals

        finally:
            conn.close()

    def get_proposal(self, agent_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get proposal by ID (requires READ capability).

        Args:
            agent_id: Agent requesting the proposal
            proposal_id: Proposal ID

        Returns:
            Proposal dict or None if not found

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        self.permission_service.check_capability(agent_id, "get")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            row = cursor.execute("""
                SELECT * FROM memory_proposals WHERE proposal_id = ?
            """, (proposal_id,)).fetchone()

            if not row:
                return None

            return {
                "proposal_id": row["proposal_id"],
                "proposed_by": row["proposed_by"],
                "proposed_at_ms": row["proposed_at_ms"],
                "memory_item": json.loads(row["memory_item"]),
                "status": row["status"],
                "reviewed_by": row["reviewed_by"],
                "reviewed_at_ms": row["reviewed_at_ms"],
                "review_reason": row["review_reason"],
                "resulting_memory_id": row["resulting_memory_id"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }

        finally:
            conn.close()

    def get_proposal_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get proposal statistics (requires READ capability).

        Args:
            agent_id: Agent requesting stats

        Returns:
            Stats dict with counts by status

        Raises:
            PermissionDenied: If agent lacks READ capability
        """
        self.permission_service.check_capability(agent_id, "list")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Count by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM memory_proposals
                GROUP BY status
            """)
            rows = cursor.fetchall()

            stats = {
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "total": 0
            }

            for row in rows:
                stats[row["status"]] = row["count"]
                stats["total"] += row["count"]

            return stats

        finally:
            conn.close()

    def _notify_admins_new_proposal(
        self,
        proposal_id: str,
        agent_id: str,
        memory_item: dict
    ):
        """
        Notify admins of new proposal (placeholder for notification system).

        This is a hook for future notification integration. For now, just log.

        Args:
            proposal_id: Proposal ID
            agent_id: Agent who proposed
            memory_item: Memory item details
        """
        # TODO: Integrate with notification system when available
        # For now, just log
        logger.info(
            f"[NOTIFICATION] New memory proposal {proposal_id} from {agent_id} "
            f"requires review (type: {memory_item.get('type')}, "
            f"scope: {memory_item.get('scope')})"
        )

    def _audit_proposal_event(
        self,
        event_type: str,
        proposal_id: str,
        agent_id: str,
        **kwargs
    ):
        """
        Audit proposal events.

        Records all proposal lifecycle events for auditability.

        Args:
            event_type: Event type (memory_proposal_created|approved|rejected)
            proposal_id: Proposal ID
            agent_id: Agent ID
            **kwargs: Additional event details
        """
        try:
            from agentos.core.audit import emit_audit_event

            emit_audit_event(
                event_type=event_type,
                metadata={
                    "proposal_id": proposal_id,
                    "agent_id": agent_id,
                    "timestamp_ms": utc_now_ms(),
                    **kwargs
                },
                level="info"
            )
        except Exception as e:
            # Graceful degradation - audit failures shouldn't block operations
            logger.warning(f"Failed to audit proposal event: {e}")


# ============================================
# Global Singleton Instance
# ============================================

_proposal_service: Optional[MemoryProposalService] = None


def get_proposal_service() -> MemoryProposalService:
    """
    Get global MemoryProposalService instance.

    Returns:
        Singleton MemoryProposalService instance

    Example:
        >>> service = get_proposal_service()
        >>> proposal_id = service.propose_memory(...)
    """
    global _proposal_service
    if _proposal_service is None:
        _proposal_service = MemoryProposalService()
    return _proposal_service
