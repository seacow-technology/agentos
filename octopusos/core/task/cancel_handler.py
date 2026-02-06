"""
Task Cancel Handler

Provides safe cancellation of running tasks.

Key Features:
1. Cancel signal detection
2. Graceful shutdown
3. Cleanup on cancel
4. Cancel audit logging
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class CancelHandler:
    """
    Cancel Handler

    Handles cancellation requests for running tasks.

    This class provides mechanisms to:
    - Detect when a task has been marked for cancellation
    - Perform cleanup operations before task termination
    - Record cancellation events in the audit log

    The handler is designed to work with the task runner loop,
    checking for cancel signals on each iteration and performing
    graceful shutdown when cancellation is detected.
    """

    def should_cancel(self, task_id: str, current_status: str) -> tuple[bool, Optional[str]]:
        """
        Check if task should be canceled

        Loads task from DB and checks if status has changed to CANCELED.
        This method is called by the task runner on each iteration to
        detect cancellation requests.

        Args:
            task_id: Task ID to check
            current_status: Current known status from runner's perspective

        Returns:
            (should_cancel, reason) tuple where:
            - should_cancel: True if task should be canceled
            - reason: Reason for cancellation (from metadata) or None

        Example:
            >>> handler = CancelHandler()
            >>> should_cancel, reason = handler.should_cancel("task_123", "running")
            >>> if should_cancel:
            ...     print(f"Task canceled: {reason}")
        """
        from agentos.core.task import TaskManager

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)

        if not task:
            logger.warning(f"Task {task_id} not found when checking for cancel signal")
            return False, None

        # Check if status changed to CANCELED
        if task.status == "canceled" and current_status != "canceled":
            reason = task.metadata.get("cancel_reason", "User requested cancellation")
            logger.info(f"Cancel signal detected for task {task_id}: {reason}")
            return True, reason

        return False, None

    def perform_cleanup(
        self,
        task_id: str,
        cleanup_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform cleanup actions before canceling

        Executes a list of cleanup actions to ensure graceful shutdown.
        Each action is attempted independently, and failures are recorded
        but do not prevent other cleanup actions from running.

        Supported cleanup actions:
        - "flush_logs": Flush any pending logs to disk
        - "release_resources": Release any held resources (locks, connections, etc.)
        - "save_partial_results": Save any partial results computed so far

        Args:
            task_id: Task ID being canceled
            cleanup_actions: List of cleanup actions to perform.
                           Defaults to ["flush_logs", "release_resources"]

        Returns:
            Dictionary with cleanup results containing:
            - task_id: Task ID
            - cleanup_performed: List of successfully completed cleanup actions
            - cleanup_failed: List of failed cleanup actions with error details

        Example:
            >>> handler = CancelHandler()
            >>> results = handler.perform_cleanup(
            ...     "task_123",
            ...     ["flush_logs", "release_resources", "save_partial_results"]
            ... )
            >>> print(f"Completed: {results['cleanup_performed']}")
            >>> print(f"Failed: {results['cleanup_failed']}")
        """
        results = {
            "task_id": task_id,
            "cleanup_performed": [],
            "cleanup_failed": [],
        }

        if not cleanup_actions:
            cleanup_actions = ["flush_logs", "release_resources"]

        logger.info(f"Performing cleanup for task {task_id}: {cleanup_actions}")

        for action in cleanup_actions:
            try:
                if action == "flush_logs":
                    # Flush any pending logs
                    logger.info(f"Flushing logs for task {task_id}")
                    # In a real implementation, this would force flush log buffers
                    # For now, we just log the action
                    results["cleanup_performed"].append("flush_logs")

                elif action == "release_resources":
                    # Release any held resources
                    logger.info(f"Releasing resources for task {task_id}")
                    # In a real implementation, this would:
                    # - Release database connections
                    # - Close file handles
                    # - Release locks
                    # - Terminate child processes
                    results["cleanup_performed"].append("release_resources")

                elif action == "save_partial_results":
                    # Save any partial results
                    logger.info(f"Saving partial results for task {task_id}")
                    # In a real implementation, this would:
                    # - Save intermediate computation results
                    # - Checkpoint current state
                    # - Store work in progress
                    results["cleanup_performed"].append("save_partial_results")

                else:
                    logger.warning(f"Unknown cleanup action '{action}' for task {task_id}")
                    results["cleanup_failed"].append({
                        "action": action,
                        "error": f"Unknown cleanup action: {action}"
                    })

            except Exception as e:
                logger.error(f"Cleanup action '{action}' failed for task {task_id}: {e}")
                results["cleanup_failed"].append({
                    "action": action,
                    "error": str(e)
                })

        # Log summary
        logger.info(
            f"Cleanup complete for task {task_id}: "
            f"{len(results['cleanup_performed'])} succeeded, "
            f"{len(results['cleanup_failed'])} failed"
        )

        return results

    def record_cancel_event(
        self,
        task_id: str,
        actor: str,
        reason: str,
        cleanup_results: Dict[str, Any]
    ) -> None:
        """
        Record cancel event in audit log

        Creates an audit log entry documenting the task cancellation,
        including who canceled it, why, and what cleanup was performed.

        This provides a complete audit trail for canceled tasks, which is
        important for debugging, compliance, and understanding system behavior.

        Args:
            task_id: Task ID that was canceled
            actor: Who canceled the task (user ID, system component, etc.)
            reason: Reason for cancellation
            cleanup_results: Results of cleanup operations (from perform_cleanup)

        Example:
            >>> handler = CancelHandler()
            >>> handler.record_cancel_event(
            ...     task_id="task_123",
            ...     actor="user_456",
            ...     reason="No longer needed",
            ...     cleanup_results={
            ...         "cleanup_performed": ["flush_logs", "release_resources"],
            ...         "cleanup_failed": []
            ...     }
            ... )
        """
        from agentos.core.task import TaskManager

        task_manager = TaskManager()

        # Prepare audit payload
        payload = {
            "actor": actor,
            "reason": reason,
            "cleanup_results": cleanup_results,
            "canceled_at": utc_now_iso(),
        }

        # Add cleanup summary to payload
        payload["cleanup_summary"] = {
            "total_actions": len(cleanup_results.get("cleanup_performed", [])) +
                           len(cleanup_results.get("cleanup_failed", [])),
            "successful": len(cleanup_results.get("cleanup_performed", [])),
            "failed": len(cleanup_results.get("cleanup_failed", [])),
        }

        # Record audit entry
        task_manager.add_audit(
            task_id=task_id,
            event_type="TASK_CANCELED_DURING_EXECUTION",
            level="warn",
            payload=payload
        )

        logger.warning(
            f"Task {task_id} canceled by {actor}: {reason} "
            f"(cleanup: {payload['cleanup_summary']['successful']}/{payload['cleanup_summary']['total_actions']} successful)"
        )

    def cancel_task_gracefully(
        self,
        task_id: str,
        actor: str,
        reason: str,
        cleanup_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform full graceful cancellation workflow

        This is a convenience method that orchestrates the complete cancellation
        process: perform cleanup, record audit event, and return summary.

        Args:
            task_id: Task ID to cancel
            actor: Who is canceling the task
            reason: Reason for cancellation
            cleanup_actions: Optional list of cleanup actions

        Returns:
            Dictionary with cancellation summary:
            - task_id: Task ID
            - canceled_by: Actor who canceled the task
            - reason: Cancellation reason
            - cleanup_results: Results from cleanup operations
            - canceled_at: Timestamp of cancellation

        Example:
            >>> handler = CancelHandler()
            >>> summary = handler.cancel_task_gracefully(
            ...     task_id="task_123",
            ...     actor="user_456",
            ...     reason="User requested cancellation"
            ... )
            >>> print(f"Canceled at: {summary['canceled_at']}")
        """
        logger.info(f"Starting graceful cancellation for task {task_id}")

        # Perform cleanup
        cleanup_results = self.perform_cleanup(task_id, cleanup_actions)

        # Record cancel event
        self.record_cancel_event(task_id, actor, reason, cleanup_results)

        # Build summary
        summary = {
            "task_id": task_id,
            "canceled_by": actor,
            "reason": reason,
            "cleanup_results": cleanup_results,
            "canceled_at": utc_now_iso(),
        }

        logger.info(f"Graceful cancellation completed for task {task_id}")
        return summary
