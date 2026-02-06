"""Task Launcher: In-process task triggering for event-driven execution

This module provides in-process task triggering capabilities, enabling immediate
task execution without waiting for the 30-second orchestrator polling loop.

Key Features:
- Same-process async execution (no subprocess overhead)
- Immediate state transitions (DRAFT -> APPROVED -> QUEUED -> RUNNING)
- Background thread execution to avoid blocking WebSocket
- Task #1 (PR-A): Chat auto-trigger runner implementation

Architecture:
- Uses threading to run TaskRunner in background
- Communicates via shared database (no IPC needed)
- Minimal latency (~5s target for state transitions)

Created for: Task #1 - PR-A (Event-driven Chat → Runner)
"""

import logging
import threading
from typing import Optional
from pathlib import Path

from agentos.core.task.service import TaskService
from agentos.core.runner.task_runner import TaskRunner

logger = logging.getLogger(__name__)


class TaskLauncher:
    """In-process task launcher for immediate execution

    Provides event-driven task triggering without waiting for orchestrator polling.
    Designed for chat-triggered tasks that need immediate feedback.
    """

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        policy_path: Optional[Path] = None,
        use_real_pipeline: bool = False,
    ):
        """Initialize task launcher

        Args:
            repo_path: Repository path for pipeline execution
            policy_path: Sandbox policy path
            use_real_pipeline: If True, use real ModePipelineRunner
        """
        self.repo_path = repo_path or Path(".")
        self.policy_path = policy_path
        self.use_real_pipeline = use_real_pipeline
        self.task_service = TaskService()

        # Thread pool for background execution
        self._active_threads = {}

        logger.info(
            f"TaskLauncher initialized: repo={self.repo_path}, "
            f"real_pipeline={use_real_pipeline}"
        )

    def launch_task(self, task_id: str, actor: str = "chat_launcher") -> bool:
        """Launch a task for immediate execution

        This method:
        1. Validates task exists and is in DRAFT state
        2. Transitions: DRAFT -> APPROVED -> QUEUED
        3. Spawns background thread to run task
        4. Returns immediately without blocking

        Args:
            task_id: Task ID to launch
            actor: Actor triggering the launch (for audit trail)

        Returns:
            True if task was successfully launched, False otherwise

        Raises:
            ValueError: If task doesn't exist or is not in DRAFT state
        """
        logger.info(f"Launching task {task_id} (actor={actor})")

        try:
            # 1. Validate task exists
            task = self.task_service.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # 2. Check task is in DRAFT state
            if task.status.upper() != "DRAFT":
                raise ValueError(
                    f"Task {task_id} is not in DRAFT state (current: {task.status})"
                )

            # 3. Approve task (DRAFT -> APPROVED)
            logger.info(f"Approving task {task_id}")
            self.task_service.approve_task(
                task_id=task_id,
                actor=actor,
                reason="Auto-approved by chat launcher"
            )

            # 4. Queue task (APPROVED -> QUEUED)
            logger.info(f"Queueing task {task_id}")
            self.task_service.queue_task(
                task_id=task_id,
                actor=actor,
                reason="Auto-queued by chat launcher"
            )

            # 5. Launch task in background thread
            logger.info(f"Starting background runner for task {task_id}")
            self._start_background_runner(task_id)

            logger.info(f"Task {task_id} launched successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to launch task {task_id}: {e}", exc_info=True)
            return False

    def _start_background_runner(self, task_id: str):
        """Start TaskRunner in background thread

        Args:
            task_id: Task ID to run
        """
        # Create runner instance
        runner = TaskRunner(
            repo_path=self.repo_path,
            policy_path=self.policy_path,
            use_real_pipeline=self.use_real_pipeline
        )

        # Define thread target
        def run_task_wrapper():
            """Wrapper function for thread execution"""
            try:
                logger.info(f"Background runner started for task {task_id}")
                runner.run_task(task_id)
                logger.info(f"Background runner finished for task {task_id}")
            except Exception as e:
                logger.error(
                    f"Background runner failed for task {task_id}: {e}",
                    exc_info=True
                )
            finally:
                # Clean up thread reference
                if task_id in self._active_threads:
                    del self._active_threads[task_id]

        # Start thread
        thread = threading.Thread(
            target=run_task_wrapper,
            name=f"TaskRunner-{task_id[:8]}",
            daemon=True  # Allow process to exit even if thread is running
        )
        thread.start()

        # Track active thread
        self._active_threads[task_id] = thread

        logger.info(
            f"Started background thread for task {task_id}: {thread.name}"
        )

    def is_task_running(self, task_id: str) -> bool:
        """Check if task has an active runner thread

        Args:
            task_id: Task ID to check

        Returns:
            True if task has active runner thread, False otherwise
        """
        thread = self._active_threads.get(task_id)
        return thread is not None and thread.is_alive()

    def get_active_tasks(self) -> list[str]:
        """Get list of task IDs with active runner threads

        Returns:
            List of task IDs
        """
        # Clean up dead threads
        dead_tasks = [
            tid for tid, thread in self._active_threads.items()
            if not thread.is_alive()
        ]
        for tid in dead_tasks:
            del self._active_threads[tid]

        return list(self._active_threads.keys())


# Global launcher instance (singleton)
_launcher: Optional[TaskLauncher] = None


def get_launcher() -> TaskLauncher:
    """Get or create global TaskLauncher instance (singleton)

    Returns:
        TaskLauncher instance
    """
    global _launcher
    if _launcher is None:
        _launcher = TaskLauncher()
        logger.info("Created global TaskLauncher instance")
    return _launcher


def launch_task_async(task_id: str, actor: str = "chat_launcher") -> bool:
    """Convenience function to launch task using global launcher

    Args:
        task_id: Task ID to launch
        actor: Actor triggering the launch

    Returns:
        True if task was successfully launched, False otherwise
    """
    launcher = get_launcher()
    return launcher.launch_task(task_id, actor)
