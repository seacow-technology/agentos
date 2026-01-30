"""
Run Store - In-Memory Implementation

Provides thread-safe storage for run records with automatic cleanup.
"""

import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from .models import RunStatus, RunRecord

logger = logging.getLogger(__name__)


class RunStore:
    """
    In-memory run store with automatic cleanup

    Features:
    - Thread-safe operations
    - Automatic cleanup of old runs (1 hour retention)
    - Progress tracking
    - Query by run_id
    """

    def __init__(self, retention_hours: int = 1):
        """
        Initialize run store

        Args:
            retention_hours: How long to keep run records (default: 1 hour)
        """
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self.retention_hours = retention_hours
        logger.info(f"RunStore initialized (retention: {retention_hours}h)")

    def create_run(
        self,
        extension_id: str,
        action_id: str,
        metadata: Optional[Dict] = None
    ) -> RunRecord:
        """
        Create a new run record

        Args:
            extension_id: Extension being executed
            action_id: Action being executed
            metadata: Optional metadata

        Returns:
            Newly created RunRecord
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"

        run = RunRecord(
            run_id=run_id,
            extension_id=extension_id,
            action_id=action_id,
            status=RunStatus.PENDING,
            progress_pct=0,
            metadata=metadata or {},
            created_at=datetime.now()
        )

        with self._lock:
            self._runs[run_id] = run

        logger.info(f"Created run: {run_id} ({extension_id}/{action_id})")
        return run

    def update_progress(
        self,
        run_id: str,
        stage: str,
        progress_pct: int,
        message: Optional[str] = None
    ) -> bool:
        """
        Update run progress

        Args:
            run_id: Run identifier
            stage: Current stage name
            progress_pct: Progress percentage (0-100)
            message: Optional progress message

        Returns:
            True if updated, False if run not found
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                logger.warning(f"Run not found for progress update: {run_id}")
                return False

            # Update progress
            run.progress_pct = progress_pct
            run.current_stage = stage

            # Add stage to history
            stage_entry = {
                "stage": stage,
                "progress_pct": progress_pct,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            run.stages.append(stage_entry)

            # Update status to RUNNING if still PENDING
            if run.status == RunStatus.PENDING:
                run.status = RunStatus.RUNNING
                run.started_at = datetime.now()

            logger.debug(f"Progress update: {run_id} - {stage} ({progress_pct}%)")
            return True

    def update_output(
        self,
        run_id: str,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None
    ) -> bool:
        """
        Update run output

        Args:
            run_id: Run identifier
            stdout: Standard output to append
            stderr: Standard error to append

        Returns:
            True if updated, False if run not found
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                logger.warning(f"Run not found for output update: {run_id}")
                return False

            if stdout:
                run.stdout += stdout
            if stderr:
                run.stderr += stderr

            return True

    def complete_run(
        self,
        run_id: str,
        status: RunStatus,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None
    ) -> bool:
        """
        Mark run as complete

        Args:
            run_id: Run identifier
            status: Final status (SUCCEEDED, FAILED, TIMEOUT, CANCELED)
            error: Optional error message
            stdout: Final stdout to append
            stderr: Final stderr to append

        Returns:
            True if updated, False if run not found
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                logger.warning(f"Run not found for completion: {run_id}")
                return False

            # Update status and outputs
            run.status = status
            run.error = error
            run.ended_at = datetime.now()

            if stdout:
                run.stdout += stdout
            if stderr:
                run.stderr += stderr

            # Set progress to 100% if succeeded
            if status == RunStatus.SUCCEEDED:
                run.progress_pct = 100

            logger.info(f"Run completed: {run_id} - {status.value}")
            return True

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """
        Get run by ID

        Args:
            run_id: Run identifier

        Returns:
            RunRecord if found, None otherwise
        """
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        extension_id: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 100
    ) -> List[RunRecord]:
        """
        List runs with optional filtering

        Args:
            extension_id: Filter by extension
            status: Filter by status
            limit: Maximum number of runs to return

        Returns:
            List of RunRecords matching filters
        """
        with self._lock:
            runs = list(self._runs.values())

            # Apply filters
            if extension_id:
                runs = [r for r in runs if r.extension_id == extension_id]
            if status:
                runs = [r for r in runs if r.status == status]

            # Sort by creation time (newest first)
            runs.sort(key=lambda r: r.created_at, reverse=True)

            # Apply limit
            return runs[:limit]

    def cleanup_old_runs(self) -> int:
        """
        Remove runs older than retention period

        Returns:
            Number of runs removed
        """
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        removed = 0

        with self._lock:
            to_remove = [
                run_id
                for run_id, run in self._runs.items()
                if run.created_at < cutoff and run.is_terminal
            ]

            for run_id in to_remove:
                del self._runs[run_id]
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} old runs")

        return removed

    def cancel_run(self, run_id: str) -> bool:
        """
        Cancel a running execution

        Args:
            run_id: Run identifier

        Returns:
            True if canceled, False if run not found or already terminal
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                logger.warning(f"Run not found for cancellation: {run_id}")
                return False

            if run.is_terminal:
                logger.warning(f"Cannot cancel terminal run: {run_id}")
                return False

            run.status = RunStatus.CANCELED
            run.ended_at = datetime.now()
            logger.info(f"Run canceled: {run_id}")
            return True

    def get_stats(self) -> Dict:
        """
        Get store statistics

        Returns:
            Dictionary with store stats
        """
        with self._lock:
            total = len(self._runs)
            by_status = {}
            for status in RunStatus:
                count = sum(1 for r in self._runs.values() if r.status == status)
                if count > 0:
                    by_status[status.value] = count

            return {
                "total_runs": total,
                "by_status": by_status,
                "retention_hours": self.retention_hours
            }
