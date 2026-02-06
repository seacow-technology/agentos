"""Task Runner Audit Integration

This module provides integration points for TaskRunner to record audits and artifacts
during task execution across multiple repositories.

Usage:
    from agentos.core.task.runner_audit_integration import TaskRunnerAuditor

    # Initialize auditor
    auditor = TaskRunnerAuditor(task_id="task-123")

    # Record operation
    auditor.record_start(exec_env)

    # Record repository changes
    for repo_context in exec_env.repos.values():
        auditor.record_repo_changes(repo_context, commit_hash="abc123...")

    # Record completion
    auditor.record_completion(exec_env, status="success")

Created for Phase 5.2: Cross-repository audit trail
"""

import logging
from pathlib import Path
from typing import Optional, List

from agentos.core.task.repo_context import TaskRepoContext, ExecutionEnv
from agentos.core.task.audit_service import TaskAuditService
from agentos.core.task.artifact_service import TaskArtifactService
from agentos.core.infra.git_client import GitClient

logger = logging.getLogger(__name__)


class TaskRunnerAuditor:
    """Auditor for task runner operations

    Coordinates audit and artifact recording during task execution.

    Attributes:
        task_id: Task ID
        audit_service: TaskAuditService instance
        artifact_service: TaskArtifactService instance
    """

    def __init__(self, task_id: str):
        """Initialize auditor

        Args:
            task_id: Task ID
        """
        self.task_id = task_id
        self.audit_service = TaskAuditService()
        self.artifact_service = TaskArtifactService()

    def record_start(self, exec_env: ExecutionEnv) -> None:
        """Record task execution start

        Args:
            exec_env: Execution environment
        """
        # Record task-level audit (no repo_id)
        self.audit_service.record_operation(
            task_id=self.task_id,
            operation="task_start",
            event_type="task_execution_start",
            level="info",
            status="success",
            payload={
                "repos": [ctx.repo_id for ctx in exec_env.repos.values()],
                "repo_count": len(exec_env.repos),
            },
        )

        logger.info(f"Recorded task start: task={self.task_id}, repos={len(exec_env.repos)}")

    def record_repo_read(
        self,
        repo_context: TaskRepoContext,
        files_read: Optional[List[str]] = None,
    ) -> None:
        """Record repository read operation

        Args:
            repo_context: Repository context
            files_read: List of files read (optional)
        """
        self.audit_service.record_operation(
            task_id=self.task_id,
            repo_id=repo_context.repo_id,
            operation="read",
            event_type="repo_read",
            level="info",
            status="success",
            files_changed=files_read or [],
        )

        logger.debug(
            f"Recorded repo read: task={self.task_id}, repo={repo_context.repo_id}, "
            f"files={len(files_read or [])}"
        )

    def record_repo_write(
        self,
        repo_context: TaskRepoContext,
        files_written: Optional[List[str]] = None,
    ) -> None:
        """Record repository write operation

        Args:
            repo_context: Repository context
            files_written: List of files written (optional)
        """
        self.audit_service.record_operation(
            task_id=self.task_id,
            repo_id=repo_context.repo_id,
            operation="write",
            event_type="repo_write",
            level="info",
            status="success",
            files_changed=files_written or [],
        )

        logger.debug(
            f"Recorded repo write: task={self.task_id}, repo={repo_context.repo_id}, "
            f"files={len(files_written or [])}"
        )

    def record_repo_changes(
        self,
        repo_context: TaskRepoContext,
        commit_hash: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> None:
        """Record Git changes for a repository

        Captures:
        - Git status and diff summaries
        - Changed files and line counts
        - Creates commit artifact reference (if commit_hash provided)

        Args:
            repo_context: Repository context
            commit_hash: Commit hash (optional, will be queried if not provided)
            commit_message: Commit message (for artifact summary)
        """
        # Query commit hash if not provided
        if commit_hash is None:
            try:
                git_client = GitClient(repo_context.path)
                commit_hash = git_client.get_head_sha()
            except Exception as e:
                logger.warning(f"Could not get commit hash for {repo_context.repo_id}: {e}")
                commit_hash = None

        # Record Git changes audit
        audit = self.audit_service.record_git_changes(
            task_id=self.task_id,
            repo_context=repo_context,
            operation="commit",
            commit_hash=commit_hash,
        )

        logger.info(
            f"Recorded Git changes: task={self.task_id}, repo={repo_context.repo_id}, "
            f"commit={commit_hash[:8] if commit_hash else 'none'}, "
            f"files={len(audit.files_changed)}, +{audit.lines_added}/-{audit.lines_deleted}"
        )

        # Create commit artifact reference
        if commit_hash:
            summary = commit_message or f"Changes for task {self.task_id}"
            self.artifact_service.create_commit_ref(
                task_id=self.task_id,
                repo_id=repo_context.repo_id,
                commit_hash=commit_hash,
                summary=summary,
                metadata={
                    "files_changed": audit.files_changed,
                    "lines_added": audit.lines_added,
                    "lines_deleted": audit.lines_deleted,
                },
            )

            logger.info(
                f"Created commit artifact: task={self.task_id}, repo={repo_context.repo_id}, "
                f"commit={commit_hash[:8]}"
            )

    def record_repo_push(
        self,
        repo_context: TaskRepoContext,
        branch: str,
        remote: str = "origin",
    ) -> None:
        """Record repository push operation

        Args:
            repo_context: Repository context
            branch: Branch name
            remote: Remote name (default: origin)
        """
        self.audit_service.record_operation(
            task_id=self.task_id,
            repo_id=repo_context.repo_id,
            operation="push",
            event_type="repo_push",
            level="info",
            status="success",
            payload={
                "branch": branch,
                "remote": remote,
            },
        )

        logger.info(
            f"Recorded repo push: task={self.task_id}, repo={repo_context.repo_id}, "
            f"branch={branch}, remote={remote}"
        )

    def record_completion(
        self,
        exec_env: ExecutionEnv,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Record task execution completion

        Args:
            exec_env: Execution environment
            status: Completion status (success, failed, partial)
            error_message: Error message (if failed)
        """
        # Record task-level audit
        level = "info" if status == "success" else "error"

        self.audit_service.record_operation(
            task_id=self.task_id,
            operation="task_complete",
            event_type="task_execution_complete",
            level=level,
            status=status,
            error_message=error_message,
            payload={
                "repos": [ctx.repo_id for ctx in exec_env.repos.values()],
                "repo_count": len(exec_env.repos),
            },
        )

        logger.info(
            f"Recorded task completion: task={self.task_id}, status={status}, "
            f"repos={len(exec_env.repos)}"
        )

    def record_error(
        self,
        error_message: str,
        repo_context: Optional[TaskRepoContext] = None,
        operation: str = "execute",
    ) -> None:
        """Record task execution error

        Args:
            error_message: Error message
            repo_context: Repository context (optional)
            operation: Operation that failed
        """
        self.audit_service.record_operation(
            task_id=self.task_id,
            repo_id=repo_context.repo_id if repo_context else None,
            operation=operation,
            event_type=f"repo_{operation}_error" if repo_context else f"{operation}_error",
            level="error",
            status="failed",
            error_message=error_message,
        )

        logger.error(
            f"Recorded error: task={self.task_id}, "
            f"repo={repo_context.repo_id if repo_context else 'none'}, "
            f"operation={operation}, error={error_message}"
        )


def get_latest_commit(repo_path: Path) -> Optional[str]:
    """Get latest commit hash for a repository

    Helper function for TaskRunner integration.

    Args:
        repo_path: Repository path

    Returns:
        Commit hash (SHA), or None if error
    """
    try:
        git_client = GitClient(repo_path)
        return git_client.get_head_sha()
    except Exception as e:
        logger.warning(f"Could not get latest commit for {repo_path}: {e}")
        return None


def has_uncommitted_changes(repo_path: Path) -> bool:
    """Check if repository has uncommitted changes

    Helper function for TaskRunner integration.

    Args:
        repo_path: Repository path

    Returns:
        True if there are uncommitted changes
    """
    try:
        git_client = GitClient(repo_path)
        status = git_client.status()
        return status["is_dirty"] or len(status["untracked_files"]) > 0
    except Exception as e:
        logger.warning(f"Could not check changes for {repo_path}: {e}")
        return False


# Example integration with TaskRunner
# This is a placeholder showing how to integrate with the actual TaskRunner
"""
def execute_task(task: Task):
    # Prepare execution environment
    exec_env = prepare_execution_env(task)

    # Initialize auditor
    auditor = TaskRunnerAuditor(task.task_id)

    try:
        # Record start
        auditor.record_start(exec_env)

        # Execute task
        result = run_task(task, exec_env)

        # Record changes for each repository
        for repo_context in exec_env.repos.values():
            if has_uncommitted_changes(repo_context.path):
                # Commit changes
                git_client = GitClient(repo_context.path)
                git_client.add_all()
                commit_hash = git_client.commit(f"Task {task.task_id}: {task.title}")

                # Record changes and create artifact
                auditor.record_repo_changes(
                    repo_context=repo_context,
                    commit_hash=commit_hash,
                    commit_message=f"Task {task.task_id}: {task.title}"
                )

        # Record completion
        auditor.record_completion(exec_env, status="success")

        return result

    except Exception as e:
        # Record error
        auditor.record_error(str(e))
        auditor.record_completion(exec_env, status="failed", error_message=str(e))
        raise
"""
