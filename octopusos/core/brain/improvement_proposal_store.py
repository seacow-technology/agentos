"""
ImprovementProposal Storage Service

Provides storage and query operations for ImprovementProposal data.
Uses unified database access through registry_db.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from uuid import uuid4

from agentos.core.db import registry_db
from agentos.core.brain.improvement_proposal import (
    ImprovementProposal,
    ProposalStatus,
    ChangeType,
    validate_proposal_immutability,
)

logger = logging.getLogger(__name__)


class ImprovementProposalStore:
    """Storage service for ImprovementProposal.

    Provides CRUD operations and querying capabilities for improvement proposals.
    Ensures immutability constraints are enforced at storage layer.
    """

    def __init__(self):
        """Initialize the store."""
        pass

    async def save_proposal(self, proposal: ImprovementProposal) -> str:
        """Save or update improvement proposal.

        For updates, validates immutability constraints.

        Args:
            proposal: ImprovementProposal to save

        Returns:
            proposal_id: Proposal ID

        Raises:
            ValueError: If immutability constraints are violated
        """
        # Check if proposal already exists
        existing = await self.get_proposal(proposal.proposal_id)

        if existing:
            # Validate immutability
            validate_proposal_immutability(existing, proposal)

            # Update existing proposal
            self._update_proposal(proposal)
            logger.info(f"Updated proposal: {proposal.proposal_id}")
        else:
            # Insert new proposal
            self._insert_proposal(proposal)

            # Record creation in history
            await self._record_history(
                proposal_id=proposal.proposal_id,
                action="created",
                actor=None,
                previous_status=None,
                new_status=proposal.status.value,
                notes=f"Proposal created: {proposal.description}",
            )

            logger.info(f"Created proposal: {proposal.proposal_id}")

        return proposal.proposal_id

    def _insert_proposal(self, proposal: ImprovementProposal) -> None:
        """Insert a new proposal into database.

        Args:
            proposal: ImprovementProposal to insert
        """
        sql = """
        INSERT INTO improvement_proposals (
            proposal_id, scope, change_type, description,
            evidence, recommendation, reasoning,
            affected_version_id, shadow_version_id,
            status, created_at, reviewed_by, reviewed_at,
            review_notes, implemented_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with registry_db.transaction() as conn:
            conn.execute(
                sql,
                (
                    proposal.proposal_id,
                    proposal.scope,
                    proposal.change_type.value,
                    proposal.description,
                    json.dumps(proposal.evidence.to_dict()),
                    proposal.recommendation.value,
                    proposal.reasoning,
                    proposal.affected_version_id,
                    proposal.shadow_version_id,
                    proposal.status.value,
                    proposal.created_at.isoformat(),
                    proposal.reviewed_by,
                    proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
                    proposal.review_notes,
                    proposal.implemented_at.isoformat() if proposal.implemented_at else None,
                    json.dumps(proposal.metadata),
                ),
            )

    def _update_proposal(self, proposal: ImprovementProposal) -> None:
        """Update an existing proposal in database.

        Args:
            proposal: ImprovementProposal to update
        """
        sql = """
        UPDATE improvement_proposals
        SET scope = ?,
            change_type = ?,
            description = ?,
            evidence = ?,
            recommendation = ?,
            reasoning = ?,
            affected_version_id = ?,
            shadow_version_id = ?,
            status = ?,
            reviewed_by = ?,
            reviewed_at = ?,
            review_notes = ?,
            implemented_at = ?,
            metadata = ?
        WHERE proposal_id = ?
        """

        with registry_db.transaction() as conn:
            conn.execute(
                sql,
                (
                    proposal.scope,
                    proposal.change_type.value,
                    proposal.description,
                    json.dumps(proposal.evidence.to_dict()),
                    proposal.recommendation.value,
                    proposal.reasoning,
                    proposal.affected_version_id,
                    proposal.shadow_version_id,
                    proposal.status.value,
                    proposal.reviewed_by,
                    proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
                    proposal.review_notes,
                    proposal.implemented_at.isoformat() if proposal.implemented_at else None,
                    json.dumps(proposal.metadata),
                    proposal.proposal_id,
                ),
            )

    async def get_proposal(self, proposal_id: str) -> Optional[ImprovementProposal]:
        """Get proposal by ID.

        Args:
            proposal_id: Proposal ID

        Returns:
            ImprovementProposal if found, None otherwise
        """
        sql = """
        SELECT proposal_id, scope, change_type, description,
               evidence, recommendation, reasoning,
               affected_version_id, shadow_version_id,
               status, created_at, reviewed_by, reviewed_at,
               review_notes, implemented_at, metadata
        FROM improvement_proposals
        WHERE proposal_id = ?
        """

        row = registry_db.query_one(sql, (proposal_id,))

        if not row:
            return None

        return self._row_to_proposal(row)

    def _row_to_proposal(self, row) -> ImprovementProposal:
        """Convert database row to ImprovementProposal.

        Args:
            row: Database row

        Returns:
            ImprovementProposal instance
        """
        data = {
            "proposal_id": row["proposal_id"],
            "scope": row["scope"],
            "change_type": row["change_type"],
            "description": row["description"],
            "evidence": json.loads(row["evidence"]),
            "recommendation": row["recommendation"],
            "reasoning": row["reasoning"],
            "affected_version_id": row["affected_version_id"],
            "shadow_version_id": row["shadow_version_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "reviewed_by": row["reviewed_by"],
            "reviewed_at": row["reviewed_at"],
            "review_notes": row["review_notes"],
            "implemented_at": row["implemented_at"],
            "metadata": json.loads(row["metadata"]),
        }

        return ImprovementProposal.from_dict(data)

    async def query_proposals(
        self,
        status: Optional[ProposalStatus] = None,
        change_type: Optional[ChangeType] = None,
        affected_version_id: Optional[str] = None,
        shadow_version_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 100,
    ) -> List[ImprovementProposal]:
        """Query proposals with filters.

        Args:
            status: Filter by status
            change_type: Filter by change type
            affected_version_id: Filter by affected version
            shadow_version_id: Filter by shadow version
            time_range: Filter by creation time range (start, end)
            limit: Maximum number of results

        Returns:
            List of ImprovementProposal instances
        """
        # Build query
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        if change_type:
            conditions.append("change_type = ?")
            params.append(change_type.value)

        if affected_version_id:
            conditions.append("affected_version_id = ?")
            params.append(affected_version_id)

        if shadow_version_id:
            conditions.append("shadow_version_id = ?")
            params.append(shadow_version_id)

        if time_range:
            conditions.append("created_at >= ? AND created_at <= ?")
            params.extend([time_range[0].isoformat(), time_range[1].isoformat()])

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
        SELECT proposal_id, scope, change_type, description,
               evidence, recommendation, reasoning,
               affected_version_id, shadow_version_id,
               status, created_at, reviewed_by, reviewed_at,
               review_notes, implemented_at, metadata
        FROM improvement_proposals
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """
        params.append(limit)

        rows = registry_db.query_all(sql, tuple(params))

        return [self._row_to_proposal(row) for row in rows]

    async def list_proposals(
        self,
        status: Optional[str] = None,
        shadow_version_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ImprovementProposal]:
        """List proposals with optional filters.

        Args:
            status: Filter by status string (e.g., "accepted", "pending")
            shadow_version_id: Filter by shadow version ID
            limit: Maximum number of results

        Returns:
            List of ImprovementProposal instances
        """
        # Convert status string to enum if provided
        status_enum = ProposalStatus(status) if status else None

        return await self.query_proposals(
            status=status_enum,
            shadow_version_id=shadow_version_id,
            limit=limit,
        )

    async def get_pending_proposals(self, limit: int = 100) -> List[ImprovementProposal]:
        """Get all pending proposals awaiting review.

        Args:
            limit: Maximum number of results

        Returns:
            List of pending proposals
        """
        return await self.query_proposals(status=ProposalStatus.PENDING, limit=limit)

    async def accept_proposal(
        self,
        proposal_id: str,
        reviewed_by: str,
        notes: Optional[str] = None,
    ) -> ImprovementProposal:
        """Accept a proposal.

        Args:
            proposal_id: Proposal ID
            reviewed_by: User accepting the proposal
            notes: Optional review notes

        Returns:
            Updated proposal

        Raises:
            ValueError: If proposal not found or not pending
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        old_status = proposal.status.value
        proposal.accept(reviewed_by, notes)

        await self.save_proposal(proposal)

        # Record in history
        await self._record_history(
            proposal_id=proposal_id,
            action="accepted",
            actor=reviewed_by,
            previous_status=old_status,
            new_status=proposal.status.value,
            notes=notes or "Proposal accepted",
        )

        logger.info(f"Accepted proposal: {proposal_id} by {reviewed_by}")
        return proposal

    async def reject_proposal(
        self,
        proposal_id: str,
        reviewed_by: str,
        reason: str,
    ) -> ImprovementProposal:
        """Reject a proposal.

        Args:
            proposal_id: Proposal ID
            reviewed_by: User rejecting the proposal
            reason: Reason for rejection

        Returns:
            Updated proposal

        Raises:
            ValueError: If proposal not found or not pending
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        old_status = proposal.status.value
        proposal.reject(reviewed_by, reason)

        await self.save_proposal(proposal)

        # Record in history
        await self._record_history(
            proposal_id=proposal_id,
            action="rejected",
            actor=reviewed_by,
            previous_status=old_status,
            new_status=proposal.status.value,
            notes=reason,
        )

        logger.info(f"Rejected proposal: {proposal_id} by {reviewed_by}")
        return proposal

    async def defer_proposal(
        self,
        proposal_id: str,
        reviewed_by: str,
        reason: str,
    ) -> ImprovementProposal:
        """Defer a proposal for later review.

        Args:
            proposal_id: Proposal ID
            reviewed_by: User deferring the proposal
            reason: Reason for deferring

        Returns:
            Updated proposal

        Raises:
            ValueError: If proposal not found or not pending
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        old_status = proposal.status.value
        proposal.defer(reviewed_by, reason)

        await self.save_proposal(proposal)

        # Record in history
        await self._record_history(
            proposal_id=proposal_id,
            action="deferred",
            actor=reviewed_by,
            previous_status=old_status,
            new_status=proposal.status.value,
            notes=reason,
        )

        logger.info(f"Deferred proposal: {proposal_id} by {reviewed_by}")
        return proposal

    async def mark_implemented(
        self,
        proposal_id: str,
    ) -> ImprovementProposal:
        """Mark proposal as implemented.

        Args:
            proposal_id: Proposal ID

        Returns:
            Updated proposal

        Raises:
            ValueError: If proposal not found or not accepted
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        old_status = proposal.status.value
        proposal.mark_implemented()

        await self.save_proposal(proposal)

        # Record in history
        await self._record_history(
            proposal_id=proposal_id,
            action="implemented",
            actor=proposal.reviewed_by,
            previous_status=old_status,
            new_status=proposal.status.value,
            notes="Proposal implemented in production",
        )

        logger.info(f"Marked proposal as implemented: {proposal_id}")
        return proposal

    async def _record_history(
        self,
        proposal_id: str,
        action: str,
        actor: Optional[str],
        previous_status: Optional[str],
        new_status: str,
        notes: Optional[str] = None,
    ) -> None:
        """Record proposal history entry.

        Args:
            proposal_id: Proposal ID
            action: Action performed
            actor: User who performed the action
            previous_status: Previous status
            new_status: New status
            notes: Optional notes
        """
        history_id = str(uuid4())

        sql = """
        INSERT INTO proposal_history (
            history_id, proposal_id, action, actor,
            timestamp, previous_status, new_status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        with registry_db.transaction() as conn:
            conn.execute(
                sql,
                (
                    history_id,
                    proposal_id,
                    action,
                    actor,
                    datetime.now().isoformat(),
                    previous_status,
                    new_status,
                    notes,
                ),
            )

    async def get_proposal_history(
        self, proposal_id: str
    ) -> List[Dict[str, Any]]:
        """Get history for a proposal.

        Args:
            proposal_id: Proposal ID

        Returns:
            List of history entries
        """
        sql = """
        SELECT history_id, proposal_id, action, actor,
               timestamp, previous_status, new_status, notes
        FROM proposal_history
        WHERE proposal_id = ?
        ORDER BY timestamp DESC
        """

        rows = registry_db.query_all(sql, (proposal_id,))

        return [
            {
                "history_id": row["history_id"],
                "proposal_id": row["proposal_id"],
                "action": row["action"],
                "actor": row["actor"],
                "timestamp": row["timestamp"],
                "previous_status": row["previous_status"],
                "new_status": row["new_status"],
                "notes": row["notes"],
            }
            for row in rows
        ]

    async def count_proposals_by_status(self) -> Dict[str, int]:
        """Count proposals by status.

        Returns:
            Dictionary with counts: {"pending": N, "accepted": M, ...}
        """
        sql = """
        SELECT status, COUNT(*) as count
        FROM improvement_proposals
        GROUP BY status
        """

        rows = registry_db.query_all(sql)

        result = {
            "pending": 0,
            "accepted": 0,
            "rejected": 0,
            "deferred": 0,
            "implemented": 0,
        }

        for row in rows:
            result[row["status"]] = row["count"]

        return result


# Singleton instance
_store = ImprovementProposalStore()


def get_store() -> ImprovementProposalStore:
    """Get singleton store instance."""
    return _store
