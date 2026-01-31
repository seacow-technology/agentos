"""Multi-Repository Task Execution Example

This example demonstrates how to create and execute tasks across multiple repositories.

Created for Phase 5.1: Runner support for cross-repository workspace selection
"""

from pathlib import Path
from datetime import datetime, timezone

from agentos.core.task.models import Task, TaskRepoScope, RepoScopeType
from agentos.core.task.task_repo_service import TaskRepoService
from agentos.core.task.runner_integration import (
    prepare_execution_env,
    with_repo_context,
    safe_file_read,
    safe_file_write,
    get_repo_summary,
    validate_file_operation,
)
from agentos.core.task.repo_context import PathSecurityError
from agentos.schemas.project import RepoSpec
from agentos.store import get_db


def example_1_basic_multi_repo():
    """Example 1: Basic multi-repository task"""
    print("=" * 60)
    print("Example 1: Basic Multi-Repository Task")
    print("=" * 60)

    # Setup (normally would be in database)
    db_path = get_db()
    workspace_root = Path.cwd()

    # Create task
    task = Task(
        task_id="task-example-1",
        title="Process backend and frontend",
        metadata={
            "project_id": "example-project",
            "description": "Read from backend, process, write to frontend"
        }
    )

    # Configure repository scopes
    service = TaskRepoService(db_path, workspace_root)

    # Backend: full access (read + write)
    backend_scope = TaskRepoScope(
        task_id=task.task_id,
        repo_id="repo-backend",
        scope=RepoScopeType.FULL,
    )
    print(f"✓ Configured backend: {backend_scope.scope.value} scope")

    # Frontend: read-only access
    frontend_scope = TaskRepoScope(
        task_id=task.task_id,
        repo_id="repo-frontend",
        scope=RepoScopeType.READ_ONLY,
    )
    print(f"✓ Configured frontend: {frontend_scope.scope.value} scope")

    # Prepare execution environment
    exec_env = prepare_execution_env(task, workspace_root=workspace_root)

    # Get summary
    summary = get_repo_summary(exec_env)
    print(f"\nExecution Environment:")
    print(f"  - Total repositories: {summary['total_repos']}")
    print(f"  - Writable repositories: {summary['writable_repos']}")
    print(f"  - Default repository: {summary['default_repo_id']}")

    print("\nRepositories:")
    for repo in summary['repos']:
        print(f"  - {repo['name']}: {repo['scope']} ({'writable' if repo['writable'] else 'read-only'})")

    print("\n" + "=" * 60 + "\n")


def example_2_path_filtered_access():
    """Example 2: Path-filtered repository access"""
    print("=" * 60)
    print("Example 2: Path-Filtered Repository Access")
    print("=" * 60)

    db_path = get_db()
    workspace_root = Path.cwd()

    task = Task(
        task_id="task-example-2",
        title="Limited scope task",
        metadata={"project_id": "example-project"}
    )

    service = TaskRepoService(db_path, workspace_root)

    # Backend: only access src/ directory
    backend_scope = TaskRepoScope(
        task_id=task.task_id,
        repo_id="repo-backend",
        scope=RepoScopeType.PATHS,
        path_filters=[
            "src/**",      # All files in src/
            "*.md",        # Markdown at root
            "**/*.json"    # JSON files anywhere
        ],
    )

    exec_env = prepare_execution_env(task, workspace_root=workspace_root)

    # Test path validation
    backend_ctx = exec_env.get_repo_by_name("backend")

    print("\nPath Filter: src/**, *.md, **/*.json")
    print("\nAllowed paths:")
    allowed_paths = [
        "src/main.py",
        "src/api/routes.py",
        "README.md",
        "config.json",
        "data/settings.json"
    ]
    for path in allowed_paths:
        is_allowed = backend_ctx.is_path_allowed(path) if backend_ctx else False
        print(f"  ✓ {path}: {is_allowed}")

    print("\nDisallowed paths:")
    disallowed_paths = [
        "tests/test_main.py",
        "docs/guide.txt",
        "scripts/deploy.sh"
    ]
    for path in disallowed_paths:
        is_allowed = backend_ctx.is_path_allowed(path) if backend_ctx else False
        print(f"  ✗ {path}: {is_allowed}")

    print("\n" + "=" * 60 + "\n")


def example_3_cross_repo_operations():
    """Example 3: Cross-repository file operations"""
    print("=" * 60)
    print("Example 3: Cross-Repository File Operations")
    print("=" * 60)

    db_path = get_db()
    workspace_root = Path.cwd()

    task = Task(
        task_id="task-example-3",
        title="Cross-repo data processing",
        metadata={"project_id": "example-project"}
    )

    exec_env = prepare_execution_env(task, workspace_root=workspace_root)

    print("\nSimulated cross-repo operations:")

    # Simulate: Read from frontend
    print("\n1. Reading configuration from frontend repo...")
    try:
        with with_repo_context(exec_env, repo_name="frontend") as frontend:
            print(f"   Context: {frontend.name} at {frontend.path}")
            print(f"   Access: {'writable' if frontend.writable else 'read-only'}")
            # In real scenario: content = safe_file_read(exec_env, "frontend/config.json")
            content = '{"theme": "dark", "language": "en"}'
            print(f"   ✓ Read: {content}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Simulate: Process data
    print("\n2. Processing data...")
    processed = content.replace("dark", "light")
    print(f"   ✓ Processed: {processed}")

    # Simulate: Write to backend
    print("\n3. Writing results to backend repo...")
    try:
        with with_repo_context(exec_env, repo_name="backend") as backend:
            print(f"   Context: {backend.name} at {backend.path}")
            print(f"   Access: {'writable' if backend.writable else 'read-only'}")
            # In real scenario: safe_file_write(exec_env, "backend/output.json", processed)
            print(f"   ✓ Would write to: backend/output.json")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 60 + "\n")


def example_4_security_validation():
    """Example 4: Security validation and error handling"""
    print("=" * 60)
    print("Example 4: Security Validation")
    print("=" * 60)

    db_path = get_db()
    workspace_root = Path.cwd()

    task = Task(
        task_id="task-example-4",
        title="Security test task",
        metadata={"project_id": "example-project"}
    )

    # Configure read-only frontend
    service = TaskRepoService(db_path, workspace_root)
    frontend_scope = TaskRepoScope(
        task_id=task.task_id,
        repo_id="repo-frontend",
        scope=RepoScopeType.READ_ONLY,
    )

    exec_env = prepare_execution_env(task, workspace_root=workspace_root)
    frontend_ctx = exec_env.get_repo_by_name("frontend")

    print("\nSecurity Tests:")

    # Test 1: Directory traversal
    print("\n1. Directory Traversal Attack:")
    print("   Attempting to access: ../../etc/passwd")
    if frontend_ctx:
        is_within = frontend_ctx.is_path_within_repo("../../etc/passwd")
        print(f"   Result: {'✗ BLOCKED' if not is_within else '✓ ALLOWED'} (is_within_repo={is_within})")

    # Test 2: Write to read-only repo
    print("\n2. Write to Read-Only Repository:")
    print("   Attempting to write to: frontend/new_file.html")
    if frontend_ctx:
        try:
            frontend_ctx.validate_write_access("new_file.html")
            print("   Result: ✓ ALLOWED")
        except PathSecurityError as e:
            print(f"   Result: ✗ BLOCKED - {e}")

    # Test 3: Read from read-only repo (should succeed)
    print("\n3. Read from Read-Only Repository:")
    print("   Attempting to read: frontend/index.html")
    if frontend_ctx:
        try:
            frontend_ctx.validate_read_access("index.html")
            print("   Result: ✓ ALLOWED")
        except PathSecurityError as e:
            print(f"   Result: ✗ BLOCKED - {e}")

    print("\n" + "=" * 60 + "\n")


def example_5_repo_context_switching():
    """Example 5: Repository context switching"""
    print("=" * 60)
    print("Example 5: Repository Context Switching")
    print("=" * 60)

    db_path = get_db()
    workspace_root = Path.cwd()

    task = Task(
        task_id="task-example-5",
        title="Multi-repo workflow",
        metadata={"project_id": "example-project"}
    )

    exec_env = prepare_execution_env(task, workspace_root=workspace_root)

    print("\nContext Switching Workflow:")

    # Step 1: Work in backend
    print("\n1. Backend Repository:")
    with with_repo_context(exec_env, repo_name="backend") as backend:
        print(f"   Entered context: {backend.name}")
        print(f"   Working directory: {backend.path}")
        print(f"   Permissions: {'read-write' if backend.writable else 'read-only'}")
        print("   Operations: Reading API configuration...")
        print("   ✓ Completed backend operations")

    # Step 2: Work in frontend
    print("\n2. Frontend Repository:")
    with with_repo_context(exec_env, repo_name="frontend") as frontend:
        print(f"   Entered context: {frontend.name}")
        print(f"   Working directory: {frontend.path}")
        print(f"   Permissions: {'read-write' if frontend.writable else 'read-only'}")
        print("   Operations: Reading UI templates...")
        print("   ✓ Completed frontend operations")

    # Step 3: Work in docs
    print("\n3. Documentation Repository:")
    with with_repo_context(exec_env, repo_name="docs") as docs:
        print(f"   Entered context: {docs.name}")
        print(f"   Working directory: {docs.path}")
        print(f"   Permissions: {'read-write' if docs.writable else 'read-only'}")
        print("   Operations: Updating documentation...")
        print("   ✓ Completed documentation operations")

    print("\n✓ All contexts completed successfully")
    print("\n" + "=" * 60 + "\n")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("Multi-Repository Task Execution Examples")
    print("=" * 60 + "\n")

    try:
        example_1_basic_multi_repo()
        example_2_path_filtered_access()
        example_3_cross_repo_operations()
        example_4_security_validation()
        example_5_repo_context_switching()

        print("✓ All examples completed successfully!")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
