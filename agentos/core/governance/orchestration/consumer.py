"""
Verdict Consumer

Consumes Guardian verdicts and updates task states accordingly.
Supervisor-owned component.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..guardian.models import GuardianVerdictSnapshot
from ..states import can_transition
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class VerdictConsumer:
    """
    Verdict Consumer

    Supervisor-owned component that:
    1. Receives Guardian verdicts
    2. Updates task states based on verdict status
    3. Writes audit records

    State transitions:
    - PASS -> VERIFIED
    - FAIL -> BLOCKED (or RUNNING for retry)
    - NEEDS_CHANGES -> RUNNING (with recommendations)
    """

    def __init__(self, db_path: Path):
        """
        Initialize Verdict Consumer

        Args:
            db_path: Path to database
        """
        self.db_path = db_path
        logger.info("VerdictConsumer initialized")

    def apply_verdict(self, verdict: GuardianVerdictSnapshot, complete_flow: bool = True) -> None:
        """
        Apply a Guardian verdict and update task state

        For PASS verdicts, this performs a two-step transition:
        1. VERIFYING -> GUARD_REVIEW
        2. GUARD_REVIEW -> VERIFIED (if complete_flow=True)

        Args:
            verdict: GuardianVerdictSnapshot to process
            complete_flow: If True, complete the full flow to VERIFIED for PASS verdicts

        Raises:
            Exception: If state transition fails or database error occurs
        """
        logger.info(
            f"Applying verdict {verdict.verdict_id}: "
            f"task={verdict.task_id}, status={verdict.status}"
        )

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get current task state
            current_state = self._get_task_state(cursor, verdict.task_id)

            # Determine target state based on verdict
            target_state = self._determine_target_state(verdict.status, current_state)

            # Validate transition
            if not can_transition(current_state, target_state):
                logger.error(
                    f"Invalid state transition: {current_state} -> {target_state}"
                )
                raise ValueError(
                    f"Cannot transition from {current_state} to {target_state}"
                )

            # Update task state
            self._update_task_state(cursor, verdict.task_id, target_state)

            # Write audit record
            self._write_audit(cursor, verdict, current_state, target_state)

            # For PASS verdict and complete_flow, apply second transition
            if verdict.status == "PASS" and complete_flow and target_state == "GUARD_REVIEW":
                logger.info(f"Completing flow: {target_state} -> VERIFIED")

                # Second transition: GUARD_REVIEW -> VERIFIED
                if can_transition(target_state, "VERIFIED"):
                    self._update_task_state(cursor, verdict.task_id, "VERIFIED")

                    # Write second audit record
                    import json
                    audit_data = {
                        "event_type": "GUARDIAN_FLOW_COMPLETED",
                        "task_id": verdict.task_id,
                        "verdict_id": verdict.verdict_id,
                        "state_transition": f"{target_state} -> VERIFIED",
                        "timestamp": utc_now_iso(),
                    }
                    cursor.execute(
                        """
                        INSERT INTO task_audits (
                            task_id, event_type, created_at, payload, verdict_id
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            verdict.task_id,
                            "GUARDIAN_FLOW_COMPLETED",
                            utc_now_iso(),
                            json.dumps(audit_data),
                            verdict.verdict_id,
                        ),
                    )

                    logger.info(f"Task {verdict.task_id} completed flow: {current_state} -> VERIFIED")

            conn.commit()
            final_state = self._get_task_state(cursor, verdict.task_id)
            logger.info(
                f"Verdict applied: task {verdict.task_id} "
                f"{current_state} -> {final_state}"
            )

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to apply verdict: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def _get_task_state(self, cursor: sqlite3.Cursor, task_id: str) -> str:
        """
        Get current task state

        Args:
            cursor: Database cursor
            task_id: Task ID

        Returns:
            Current task state

        Raises:
            ValueError: If task not found
        """
        cursor.execute(
            "SELECT status FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Task not found: {task_id}")

        return row["status"]

    def _determine_target_state(self, verdict_status: str, current_state: str) -> str:
        """
        Determine target state based on verdict status

        State machine flow:
        - VERIFYING -> GUARD_REVIEW (Guardian starts review)
        - GUARD_REVIEW -> VERIFIED (PASS verdict)
        - GUARD_REVIEW -> BLOCKED (FAIL verdict)
        - GUARD_REVIEW -> RUNNING (NEEDS_CHANGES verdict)

        Args:
            verdict_status: Verdict status (PASS/FAIL/NEEDS_CHANGES)
            current_state: Current task state

        Returns:
            Target state
        """
        if verdict_status == "PASS":
            # PASS verdict moves to GUARD_REVIEW first, then VERIFIED
            if current_state == "VERIFYING":
                # First transition: VERIFYING -> GUARD_REVIEW
                return "GUARD_REVIEW"
            elif current_state == "GUARD_REVIEW":
                # Second transition: GUARD_REVIEW -> VERIFIED
                return "VERIFIED"
            else:
                # If already in a later state, stay there or move to VERIFIED
                logger.warning(f"Unexpected state {current_state} for PASS verdict")
                return "GUARD_REVIEW"
        elif verdict_status == "FAIL":
            # FAIL verdict blocks the task
            return "BLOCKED"
        elif verdict_status == "NEEDS_CHANGES":
            # NEEDS_CHANGES means go back to RUNNING
            return "RUNNING"
        else:
            logger.warning(f"Unknown verdict status: {verdict_status}, defaulting to BLOCKED")
            return "BLOCKED"

    def _update_task_state(
        self, cursor: sqlite3.Cursor, task_id: str, new_state: str
    ) -> None:
        """
        Update task state in database

        Args:
            cursor: Database cursor
            task_id: Task ID
            new_state: New state
        """
        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (new_state, utc_now_iso(), task_id),
        )

        if cursor.rowcount == 0:
            raise ValueError(f"Failed to update task state: {task_id}")

    def _write_audit(
        self,
        cursor: sqlite3.Cursor,
        verdict: GuardianVerdictSnapshot,
        from_state: str,
        to_state: str,
    ) -> None:
        """
        Write audit record for verdict application

        Args:
            cursor: Database cursor
            verdict: GuardianVerdictSnapshot
            from_state: Original state
            to_state: New state
        """
        import json

        audit_data = {
            "event_type": "GUARDIAN_VERDICT_APPLIED",
            "task_id": verdict.task_id,
            "verdict_id": verdict.verdict_id,
            "guardian_code": verdict.guardian_code,
            "verdict_status": verdict.status,
            "state_transition": f"{from_state} -> {to_state}",
            "flags": verdict.flags,
            "recommendations": verdict.recommendations,
            "timestamp": utc_now_iso(),
        }

        cursor.execute(
            """
            INSERT INTO task_audits (
                task_id, event_type, created_at, payload, verdict_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                verdict.task_id,
                "GUARDIAN_VERDICT_APPLIED",
                utc_now_iso(),
                json.dumps(audit_data),
                verdict.verdict_id,
            ),
        )

        logger.debug(f"Wrote audit record for verdict {verdict.verdict_id}")
