"""
Checkpoint Manager

Manages checkpoint lifecycle with evidence-based verification for resumable execution.

Core operations:
- begin_step(): Start a new execution step
- commit_step(): Save checkpoint with evidence
- verify_checkpoint(): Verify checkpoint evidence
- get_last_verified_checkpoint(): Get last valid checkpoint
- rollback_to_checkpoint(): Restore from checkpoint

Version: 0.1.0
Task: #7 - P0-2 - CheckpointManager + EvidenceVerifier Implementation
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from .models import Checkpoint, Evidence, EvidencePack, EvidenceType, VerificationStatus
from .evidence import EvidenceVerifier, EvidenceVerificationError

# Import logging for checkpoint events
import logging as _logging
from agentos.core.time import utc_now, utc_now_iso

_logger = _logging.getLogger(__name__)


class CheckpointError(Exception):
    """Raised when checkpoint operation fails"""
    pass


class CheckpointManager:
    """
    Manages checkpoint lifecycle with evidence verification

    Provides high-level API for creating, verifying, and recovering from
    checkpoints in the recovery system.

    Examples:
        from agentos.core.storage.paths import component_db_path

        manager = CheckpointManager(db_path=str(component_db_path("agentos")))

        # Begin step
        step_id = manager.begin_step(
            task_id="task-123",
            checkpoint_type="iteration_start",
            snapshot={"iteration": 1}
        )

        # Commit checkpoint with evidence
        checkpoint = manager.commit_step(
            step_id=step_id,
            evidence_pack=EvidencePack([
                Evidence(EvidenceType.ARTIFACT_EXISTS, "Log created", {"path": "/tmp/run.log"}),
            ])
        )

        # Verify checkpoint
        is_valid = manager.verify_checkpoint(checkpoint.checkpoint_id)

        # Get last verified checkpoint
        last_checkpoint = manager.get_last_verified_checkpoint("task-123")

        # Rollback to checkpoint
        manager.rollback_to_checkpoint(checkpoint.checkpoint_id)
    """

    def __init__(
        self,
        db_path: str = None,
        base_path: Optional[Path] = None,
        auto_verify: bool = True
    ):
        """
        Initialize checkpoint manager

        Args:
            db_path: Path to SQLite database (defaults to component_db_path("agentos"))
            base_path: Base path for evidence verification
            auto_verify: Automatically verify checkpoints after creation
        """
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("agentos")
        self.db_path = Path(db_path)
        self.base_path = base_path or Path.cwd()
        self.auto_verify = auto_verify
        self.verifier = EvidenceVerifier(base_path=self.base_path)
        self._pending_steps: Dict[str, Dict[str, Any]] = {}

    @contextmanager
    def _get_connection(self):
        """Get database connection with foreign keys enabled"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def begin_step(
        self,
        task_id: str,
        checkpoint_type: str,
        snapshot: Dict[str, Any],
        work_item_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Begin a new execution step

        Creates a pending checkpoint that will be committed later with evidence.

        Args:
            task_id: Task ID
            checkpoint_type: Type of checkpoint (from schema enum)
            snapshot: State snapshot data
            work_item_id: Optional work item ID
            metadata: Optional metadata

        Returns:
            step_id: Unique identifier for this step (use in commit_step)

        Raises:
            CheckpointError: If task_id is invalid or database error

        Note:
            This does NOT create a database record yet. Call commit_step()
            to save the checkpoint with evidence.
        """
        # Generate step ID
        import time
        step_id = f"step-{task_id}-{int(time.time() * 1000000)}"

        # Store pending step
        self._pending_steps[step_id] = {
            "task_id": task_id,
            "checkpoint_type": checkpoint_type,
            "snapshot": snapshot,
            "work_item_id": work_item_id,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }

        # PR-V2: Emit checkpoint_begin event
        try:
            from agentos.core.task.event_service import TaskEventService
            service = TaskEventService()
            service.emit_event(
                task_id=task_id,
                event_type="checkpoint_begin",
                actor="checkpoint_manager",
                span_id="main",
                phase=snapshot.get("phase", "execution"),
                payload={
                    "step_id": step_id,
                    "checkpoint_type": checkpoint_type,
                    "work_item_id": work_item_id,
                    "explanation": f"Checkpoint step initiated: {checkpoint_type}"
                }
            )
        except Exception as e:
            _logger.error(f"Failed to emit checkpoint_begin event: {e}")

        return step_id

    def commit_step(
        self,
        step_id: str,
        evidence_pack: EvidencePack,
        checkpoint_id: Optional[str] = None
    ) -> Checkpoint:
        """
        Commit a step as a checkpoint with evidence

        Saves the checkpoint to database and optionally verifies evidence.

        Args:
            step_id: Step ID from begin_step()
            evidence_pack: Evidence pack for verification
            checkpoint_id: Optional checkpoint ID (generated if not provided)

        Returns:
            Checkpoint object with evidence

        Raises:
            CheckpointError: If step_id invalid, database error, or verification fails
        """
        # Get pending step
        if step_id not in self._pending_steps:
            raise CheckpointError(f"Step not found: {step_id}")

        step_data = self._pending_steps[step_id]

        # Generate checkpoint ID if not provided
        if not checkpoint_id:
            import uuid
            checkpoint_id = f"ckpt-{uuid.uuid4().hex[:16]}"

        # Get next sequence number
        sequence_number = self._get_next_sequence(step_data["task_id"])

        # Create checkpoint object
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=step_data["task_id"],
            work_item_id=step_data["work_item_id"],
            checkpoint_type=step_data["checkpoint_type"],
            sequence_number=sequence_number,
            snapshot_data=step_data["snapshot"],
            evidence_pack=evidence_pack,
            metadata=step_data["metadata"],
            created_at=step_data["created_at"],
        )

        # Save to database
        self._save_checkpoint(checkpoint)

        # PR-V2: Emit checkpoint_commit event
        try:
            from agentos.core.task.event_service import TaskEventService
            service = TaskEventService()
            service.emit_event(
                task_id=checkpoint.task_id,
                event_type="checkpoint_commit",
                actor="checkpoint_manager",
                span_id="main",
                phase=checkpoint.snapshot_data.get("phase", "execution"),
                payload={
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_type": checkpoint.checkpoint_type,
                    "sequence_number": sequence_number,
                    "work_item_id": checkpoint.work_item_id,
                    "evidence_count": len(evidence_pack.evidence_list),
                    "explanation": f"Checkpoint committed: {checkpoint.checkpoint_type} (seq={sequence_number})"
                }
            )
        except Exception as e:
            _logger.error(f"Failed to emit checkpoint_commit event: {e}")

        # Auto-verify if enabled
        if self.auto_verify:
            self.verify_checkpoint(checkpoint_id)
            # Reload checkpoint with verification results
            checkpoint = self.get_checkpoint(checkpoint_id)

        # Remove from pending
        del self._pending_steps[step_id]

        return checkpoint

    def verify_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Verify checkpoint evidence

        Args:
            checkpoint_id: Checkpoint ID to verify

        Returns:
            True if verification passed, False otherwise

        Updates checkpoint in database with verification results.
        """
        # Load checkpoint
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(f"Checkpoint not found: {checkpoint_id}")

        # Verify evidence pack
        is_verified = self.verifier.verify_evidence_pack(checkpoint.evidence_pack)

        # Update checkpoint
        checkpoint.verified = is_verified
        checkpoint.last_verified_at = utc_now()

        # Save verification results
        self._update_checkpoint_verification(checkpoint)

        # PR-V2: Emit checkpoint verification result event
        try:
            from agentos.core.task.event_service import TaskEventService
            service = TaskEventService()
            event_type = "checkpoint_verified" if is_verified else "checkpoint_invalid"
            service.emit_event(
                task_id=checkpoint.task_id,
                event_type=event_type,
                actor="checkpoint_manager",
                span_id="main",
                phase=checkpoint.snapshot_data.get("phase", "execution"),
                payload={
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_type": checkpoint.checkpoint_type,
                    "verified": is_verified,
                    "evidence_count": len(checkpoint.evidence_pack.evidence_list),
                    "explanation": f"Checkpoint verification {'passed' if is_verified else 'failed'}: {checkpoint_id}"
                }
            )
        except Exception as e:
            _logger.error(f"Failed to emit checkpoint verification event: {e}")

        return is_verified

    def get_last_verified_checkpoint(
        self,
        task_id: str,
        checkpoint_type: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """
        Get the last verified checkpoint for a task

        Args:
            task_id: Task ID
            checkpoint_type: Optional filter by checkpoint type

        Returns:
            Last verified Checkpoint or None if not found
        """
        with self._get_connection() as conn:
            query = """
                SELECT * FROM checkpoints
                WHERE task_id = ?
                ORDER BY sequence_number DESC
            """
            params = [task_id]

            if checkpoint_type:
                query = query.replace("ORDER BY", "AND checkpoint_type = ? ORDER BY")
                params.insert(1, checkpoint_type)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Find first verified checkpoint
            for row in rows:
                checkpoint = self._row_to_checkpoint(row)
                if checkpoint.verified and checkpoint.evidence_pack.is_verified():
                    return checkpoint

            return None

    def rollback_to_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Rollback to a checkpoint

        Verifies the checkpoint and returns its snapshot data for restoration.

        Args:
            checkpoint_id: Checkpoint ID to rollback to

        Returns:
            Snapshot data from checkpoint

        Raises:
            CheckpointError: If checkpoint not found or verification fails
        """
        # Load checkpoint
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(f"Checkpoint not found: {checkpoint_id}")

        # Verify before rollback
        if not checkpoint.verified:
            is_verified = self.verify_checkpoint(checkpoint_id)
            if not is_verified:
                raise CheckpointError(f"Checkpoint verification failed: {checkpoint_id}")

        # Return snapshot for restoration
        return checkpoint.snapshot_data

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get checkpoint by ID

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Checkpoint object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_checkpoint(row)

    def list_checkpoints(
        self,
        task_id: str,
        limit: int = 100,
        checkpoint_type: Optional[str] = None
    ) -> List[Checkpoint]:
        """
        List checkpoints for a task

        Args:
            task_id: Task ID
            limit: Maximum number to return
            checkpoint_type: Optional filter by type

        Returns:
            List of Checkpoint objects ordered by sequence
        """
        with self._get_connection() as conn:
            query = """
                SELECT * FROM checkpoints
                WHERE task_id = ?
            """
            params = [task_id]

            if checkpoint_type:
                query += " AND checkpoint_type = ?"
                params.append(checkpoint_type)

            query += " ORDER BY sequence_number DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_checkpoint(row) for row in rows]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _get_next_sequence(self, task_id: str) -> int:
        """Get next sequence number for task"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(sequence_number) as max_seq FROM checkpoints WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            max_seq = row["max_seq"] if row["max_seq"] is not None else 0
            return max_seq + 1

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to database"""
        # Prepare snapshot data with evidence
        snapshot_with_evidence = {
            "snapshot_data": checkpoint.snapshot_data,
            "evidence_pack": checkpoint.evidence_pack.to_dict(),
        }

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (
                    checkpoint_id, task_id, work_item_id, checkpoint_type,
                    sequence_number, snapshot_data, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.task_id,
                    checkpoint.work_item_id,
                    checkpoint.checkpoint_type,
                    checkpoint.sequence_number,
                    json.dumps(snapshot_with_evidence),
                    json.dumps(checkpoint.metadata),
                    checkpoint.created_at.isoformat() if checkpoint.created_at else utc_now_iso(),
                )
            )
            conn.commit()

    def _update_checkpoint_verification(self, checkpoint: Checkpoint) -> None:
        """Update checkpoint verification status in database"""
        # Update snapshot_data with latest evidence
        snapshot_with_evidence = {
            "snapshot_data": checkpoint.snapshot_data,
            "evidence_pack": checkpoint.evidence_pack.to_dict(),
            "verified": checkpoint.verified,
            "last_verified_at": checkpoint.last_verified_at.isoformat() if checkpoint.last_verified_at else None,
        }

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE checkpoints
                SET snapshot_data = ?
                WHERE checkpoint_id = ?
                """,
                (json.dumps(snapshot_with_evidence), checkpoint.checkpoint_id)
            )
            conn.commit()

    def _row_to_checkpoint(self, row: sqlite3.Row) -> Checkpoint:
        """Convert database row to Checkpoint object"""
        snapshot_data = json.loads(row["snapshot_data"])

        # Extract evidence pack if present
        evidence_pack_data = snapshot_data.get("evidence_pack", {})
        evidence_pack = EvidencePack.from_dict(evidence_pack_data) if evidence_pack_data else EvidencePack()

        # Extract actual snapshot data
        actual_snapshot = snapshot_data.get("snapshot_data", snapshot_data)

        # Get verification info
        verified = snapshot_data.get("verified", False)
        last_verified_at_str = snapshot_data.get("last_verified_at")
        last_verified_at = datetime.fromisoformat(last_verified_at_str) if last_verified_at_str else None

        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return Checkpoint(
            checkpoint_id=row["checkpoint_id"],
            task_id=row["task_id"],
            work_item_id=row["work_item_id"],
            checkpoint_type=row["checkpoint_type"],
            sequence_number=row["sequence_number"],
            snapshot_data=actual_snapshot,
            evidence_pack=evidence_pack,
            metadata=metadata,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            verified=verified,
            last_verified_at=last_verified_at,
        )
