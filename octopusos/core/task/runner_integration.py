"""Task Runner Integration for Multi-Repo Support

This module provides integration utilities for TaskRunner to support
multi-repository execution environments.

Key Features:
1. Build ExecutionEnv from task metadata
2. Inject repo contexts into execution pipeline
3. Path validation for file operations
4. Repo context switching during execution

Created for Phase 5.1: Runner support for cross-repository workspace selection

Usage Example:
    # In TaskRunner._execute_stage():

    from agentos.core.task.runner_integration import (
        prepare_execution_env,
        with_repo_context,
        validate_file_operation
    )

    # Prepare execution environment
    exec_env = prepare_execution_env(task)

    # Execute with repo context
    with with_repo_context(exec_env, "backend"):
        # All file operations limited to backend repo
        result = execute_task_logic(task)

    # Validate file operation before execution
    validate_file_operation(
        exec_env,
        repo_id="backend",
        file_path="src/main.py",
        operation="write"
    )
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator, Dict, Any

from agentos.core.task.models import Task
from agentos.core.task.repo_context import (
    TaskRepoContext,
    ExecutionEnv,
    PathSecurityError,
)
from agentos.core.task.task_repo_service import build_repo_contexts
from agentos.store import get_db

logger = logging.getLogger(__name__)


def prepare_execution_env(
    task: Task,
    project_id: Optional[str] = None,
    workspace_root: Optional[Path] = None,
) -> ExecutionEnv:
    """Prepare execution environment for task

    Args:
        task: Task object
        project_id: Project ID (if None, extracted from task metadata)
        workspace_root: Workspace root path (if None, uses current directory)

    Returns:
        ExecutionEnv with configured repository contexts

    Raises:
        ValueError: If configuration is invalid
    """
    # Extract project_id from task metadata if not provided
    if project_id is None:
        project_id = task.metadata.get("project_id")
        if not project_id:
            raise ValueError(
                f"Task {task.task_id} has no project_id in metadata and none provided"
            )

    # Use default workspace root if not provided
    if workspace_root is None:
        workspace_root = Path.cwd()

    # Build execution environment
    db_path = get_db()
    exec_env = build_repo_contexts(
        task_id=task.task_id,
        project_id=project_id,
        db_path=db_path,
        workspace_root=workspace_root,
    )

    logger.info(
        f"Prepared ExecutionEnv for task {task.task_id}: "
        f"{len(exec_env.repos)} repos, default={exec_env.default_repo_id}"
    )

    return exec_env


@contextmanager
def with_repo_context(
    exec_env: ExecutionEnv,
    repo_id: Optional[str] = None,
    repo_name: Optional[str] = None,
) -> Generator[TaskRepoContext, None, None]:
    """Context manager for repo-scoped execution

    Args:
        exec_env: Execution environment
        repo_id: Repository ID (takes precedence over repo_name)
        repo_name: Repository name (used if repo_id not provided)

    Yields:
        TaskRepoContext for the specified repository

    Raises:
        ValueError: If repository not found

    Example:
        with with_repo_context(exec_env, repo_name="backend") as repo:
            # Operations limited to backend repo
            file_path = repo.path / "src" / "main.py"
            repo.validate_write_access(file_path)
    """
    # Get repository context
    if repo_id:
        context = exec_env.get_repo(repo_id)
        if not context:
            raise ValueError(f"Repository {repo_id} not found in execution environment")
    elif repo_name:
        context = exec_env.get_repo_by_name(repo_name)
        if not context:
            raise ValueError(f"Repository '{repo_name}' not found in execution environment")
    else:
        # Use default repo
        context = exec_env.get_default_repo()
        if not context:
            raise ValueError("No default repository configured in execution environment")

    logger.debug(f"Entering repo context: {context.name} ({context.repo_id})")

    try:
        yield context
    finally:
        logger.debug(f"Exiting repo context: {context.name} ({context.repo_id})")


def validate_file_operation(
    exec_env: ExecutionEnv,
    file_path: str | Path,
    operation: str = "read",
    repo_id: Optional[str] = None,
) -> TaskRepoContext:
    """Validate a file operation is allowed

    Args:
        exec_env: Execution environment
        file_path: File path to validate
        operation: Operation type ("read" or "write")
        repo_id: Optional repository ID (if None, auto-detect from path)

    Returns:
        TaskRepoContext that contains the file

    Raises:
        PathSecurityError: If operation is not allowed
        ValueError: If file is outside all repositories

    Example:
        context = validate_file_operation(
            exec_env,
            "backend/src/main.py",
            operation="write"
        )
        # Now safe to perform write operation
    """
    # Resolve path
    file_path = Path(file_path)
    if not file_path.is_absolute():
        file_path = file_path.resolve()

    # Find which repo contains the file
    if repo_id:
        context = exec_env.get_repo(repo_id)
        if not context:
            raise ValueError(f"Repository {repo_id} not found")

        if not context.is_path_within_repo(file_path):
            raise PathSecurityError(
                f"File {file_path} is not within repository {repo_id}"
            )
    else:
        # Auto-detect from file path
        from agentos.core.task.task_repo_service import TaskRepoService

        db_path = get_db()
        service = TaskRepoService(db_path, Path.cwd())
        context = service.get_repo_for_file(exec_env, file_path)

        if not context:
            raise ValueError(
                f"File {file_path} is not within any configured repository"
            )

    # Validate operation
    if operation == "read":
        context.validate_read_access(file_path)
    elif operation == "write":
        context.validate_write_access(file_path)
    else:
        raise ValueError(f"Unknown operation: {operation}")

    logger.debug(
        f"Validated {operation} operation for {file_path} in repo {context.name}"
    )

    return context


def get_writable_repo_paths(exec_env: ExecutionEnv) -> Dict[str, Path]:
    """Get paths of all writable repositories

    Args:
        exec_env: Execution environment

    Returns:
        Dictionary mapping repo_id to path for writable repos

    Example:
        writable_paths = get_writable_repo_paths(exec_env)
        for repo_id, path in writable_paths.items():
            print(f"Can write to {repo_id}: {path}")
    """
    writable_repos = exec_env.list_writable_repos()
    return {repo.repo_id: repo.path for repo in writable_repos}


def get_repo_summary(exec_env: ExecutionEnv) -> Dict[str, Any]:
    """Get summary of execution environment

    Args:
        exec_env: Execution environment

    Returns:
        Dictionary with environment summary

    Example:
        summary = get_repo_summary(exec_env)
        print(f"Task {summary['task_id']} has {summary['total_repos']} repos")
        print(f"Writable repos: {summary['writable_repos']}")
    """
    all_repos = exec_env.list_repos()
    writable_repos = exec_env.list_writable_repos()

    repos_info = []
    for context in all_repos:
        repos_info.append({
            "repo_id": context.repo_id,
            "name": context.name,
            "path": str(context.path),
            "writable": context.writable,
            "scope": context.scope.value,
            "has_filters": len(context.path_filters) > 0,
        })

    return {
        "task_id": exec_env.task_id,
        "total_repos": len(all_repos),
        "writable_repos": len(writable_repos),
        "default_repo_id": exec_env.default_repo_id,
        "repos": repos_info,
    }


def safe_file_read(
    exec_env: ExecutionEnv,
    file_path: str | Path,
    repo_id: Optional[str] = None,
) -> str:
    """Safely read a file with access validation

    Args:
        exec_env: Execution environment
        file_path: File path to read
        repo_id: Optional repository ID

    Returns:
        File contents as string

    Raises:
        PathSecurityError: If read access denied
        FileNotFoundError: If file doesn't exist

    Example:
        content = safe_file_read(exec_env, "backend/src/config.py")
    """
    context = validate_file_operation(exec_env, file_path, operation="read", repo_id=repo_id)

    # Resolve relative path
    if not Path(file_path).is_absolute():
        file_path = context.get_absolute_path(file_path)

    # Read file
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def safe_file_write(
    exec_env: ExecutionEnv,
    file_path: str | Path,
    content: str,
    repo_id: Optional[str] = None,
) -> None:
    """Safely write a file with access validation

    Args:
        exec_env: Execution environment
        file_path: File path to write
        content: Content to write
        repo_id: Optional repository ID

    Raises:
        PathSecurityError: If write access denied

    Example:
        safe_file_write(
            exec_env,
            "backend/src/new_file.py",
            "print('hello')"
        )
    """
    context = validate_file_operation(exec_env, file_path, operation="write", repo_id=repo_id)

    # Resolve relative path
    if not Path(file_path).is_absolute():
        file_path = context.get_absolute_path(file_path)

    # Ensure parent directory exists
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    # Write file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Wrote file: {file_path} (repo: {context.name})")


# Example integration with TaskRunner
def example_task_execution_with_multi_repo():
    """
    Example showing how to integrate multi-repo support into task execution.

    This would be called from TaskRunner._execute_stage() or similar.
    """
    from agentos.core.task import Task

    # Mock task
    task = Task(
        task_id="task-123",
        title="Multi-repo task",
        metadata={
            "project_id": "proj-1",
        }
    )

    # Step 1: Prepare execution environment
    exec_env = prepare_execution_env(task)

    # Step 2: Get environment summary
    summary = get_repo_summary(exec_env)
    logger.info(f"Executing task with {summary['total_repos']} repositories")

    # Step 3: Execute in backend repo
    with with_repo_context(exec_env, repo_name="backend") as backend_repo:
        logger.info(f"Working in {backend_repo.name} at {backend_repo.path}")

        # Read a file
        config_content = safe_file_read(
            exec_env,
            backend_repo.path / "config.py"
        )

        # Write a file
        safe_file_write(
            exec_env,
            backend_repo.path / "output.txt",
            "Task output"
        )

    # Step 4: Read from frontend repo (read-only)
    with with_repo_context(exec_env, repo_name="frontend") as frontend_repo:
        # Can read
        index_html = safe_file_read(
            exec_env,
            frontend_repo.path / "index.html"
        )

        # Cannot write (would raise PathSecurityError if not writable)
        try:
            safe_file_write(
                exec_env,
                frontend_repo.path / "new_file.html",
                "<html></html>"
            )
        except PathSecurityError:
            logger.info("Frontend repo is read-only, cannot write")

    return "Task completed successfully"
