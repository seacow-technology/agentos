"""Multi-Repository Project Usage Example

Demonstrates how to use the multi-repo project management API.
"""

import tempfile
from pathlib import Path

from agentos.core.project.repository import (
    ProjectRepository,
    RepoContext,
    RepoRegistry,
)
from agentos.schemas.project import Project, RepoRole, RepoSpec


def example_basic_crud():
    """Example: Basic repository CRUD operations"""
    print("=== Example 1: Basic Repository CRUD ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database (simplified for example)
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE project_repos (
            repo_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            remote_url TEXT,
            default_branch TEXT DEFAULT 'main',
            workspace_relpath TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'code',
            is_writable INTEGER NOT NULL DEFAULT 1,
            auth_profile TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, name),
            UNIQUE(project_id, workspace_relpath),
            CHECK (role IN ('code', 'docs', 'infra', 'mono-subdir'))
        );

        INSERT INTO projects (id, name, path) VALUES
            ('proj-001', 'My Awesome Project', '/workspace/my-project');
        """
    )
    conn.commit()
    conn.close()

    # Create repository manager
    repo_crud = ProjectRepository(db_path)

    # Add backend repository
    backend_repo = RepoSpec(
        repo_id="repo-backend",
        project_id="proj-001",
        name="backend",
        remote_url="https://github.com/myorg/backend.git",
        default_branch="main",
        workspace_relpath="services/backend",
        role=RepoRole.CODE,
        is_writable=True,
        auth_profile="github-pat",
        metadata={"language": "python", "framework": "fastapi"},
    )

    repo_id = repo_crud.add_repo(backend_repo)
    print(f"✓ Added backend repository: {repo_id}")

    # Add frontend repository
    frontend_repo = RepoSpec(
        repo_id="repo-frontend",
        project_id="proj-001",
        name="frontend",
        remote_url="https://github.com/myorg/frontend.git",
        default_branch="develop",
        workspace_relpath="services/frontend",
        role=RepoRole.CODE,
        is_writable=True,
        metadata={"language": "typescript", "framework": "react"},
    )

    repo_crud.add_repo(frontend_repo)
    print(f"✓ Added frontend repository: {frontend_repo.repo_id}")

    # Add documentation repository (read-only)
    docs_repo = RepoSpec(
        repo_id="repo-docs",
        project_id="proj-001",
        name="docs",
        remote_url="https://github.com/myorg/docs.git",
        default_branch="main",
        workspace_relpath="docs",
        role=RepoRole.DOCS,
        is_writable=False,
        metadata={"format": "markdown", "engine": "mkdocs"},
    )

    repo_crud.add_repo(docs_repo)
    print(f"✓ Added docs repository: {docs_repo.repo_id}\n")

    # List all repositories
    repos = repo_crud.list_repos("proj-001")
    print(f"Project has {len(repos)} repositories:")
    for repo in repos:
        print(f"  - {repo.name} ({repo.role.value}): {repo.workspace_relpath}")
        print(f"    Writable: {repo.is_writable}, Branch: {repo.default_branch}")

    # Get writable repositories only
    print("\nWritable repositories:")
    writable = repo_crud.get_writable_repos("proj-001")
    for repo in writable:
        print(f"  - {repo.name}")

    # Cleanup
    db_path.unlink()


def example_project_model():
    """Example: Using Project model with multi-repo support"""
    print("\n\n=== Example 2: Project Model with Multi-Repo ===\n")

    # Create a project with multiple repositories
    backend_repo = RepoSpec(
        repo_id="repo-backend",
        project_id="proj-002",
        name="backend",
        workspace_relpath="backend",
        role=RepoRole.CODE,
    )

    frontend_repo = RepoSpec(
        repo_id="repo-frontend",
        project_id="proj-002",
        name="frontend",
        workspace_relpath="frontend",
        role=RepoRole.CODE,
    )

    project = Project(
        id="proj-002",
        name="Multi-Repo Project",
        repos=[backend_repo, frontend_repo],
        metadata={"version": "1.0.0"},
    )

    print(f"Project: {project.name}")
    print(f"Is multi-repo: {project.is_multi_repo()}")
    print(f"Has repos: {project.has_repos()}\n")

    # Get default repository
    default = project.get_default_repo()
    print(f"Default repository: {default.name if default else 'None'}")

    # Get repository by name
    backend = project.get_repo_by_name("backend")
    if backend:
        print(f"Backend repo: {backend.workspace_relpath}")

    # List all repos
    print(f"\nAll repositories:")
    for repo in project.repos:
        print(f"  - {repo.name}: {repo.workspace_relpath}")


def example_repo_context():
    """Example: Runtime repository context"""
    print("\n\n=== Example 3: Runtime Repository Context ===\n")

    # Create a repo spec
    repo_spec = RepoSpec(
        repo_id="repo-api",
        project_id="proj-003",
        name="api",
        remote_url="https://github.com/myorg/api.git",
        default_branch="main",
        workspace_relpath="services/api",
        role=RepoRole.CODE,
        is_writable=True,
        metadata={"port": 8000},
    )

    # Convert to runtime context
    workspace_root = Path("/workspace/my-project")
    context = RepoContext.from_repo_spec(repo_spec, workspace_root)

    print(f"Repository: {context.name}")
    print(f"Absolute path: {context.path}")
    print(f"Remote URL: {context.remote_url}")
    print(f"Branch: {context.branch}")
    print(f"Writable: {context.writable}")
    print(f"Role: {context.role.value}")


def example_repo_registry():
    """Example: Using RepoRegistry for unified operations"""
    print("\n\n=== Example 4: RepoRegistry Unified Operations ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE project_repos (
            repo_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            remote_url TEXT,
            default_branch TEXT DEFAULT 'main',
            workspace_relpath TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'code',
            is_writable INTEGER NOT NULL DEFAULT 1,
            auth_profile TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, name),
            UNIQUE(project_id, workspace_relpath)
        );

        INSERT INTO projects (id, name) VALUES ('proj-004', 'Registry Example');
        """
    )
    conn.commit()
    conn.close()

    # Create registry with workspace root
    workspace_root = Path("/workspace/my-project")
    registry = RepoRegistry(db_path, workspace_root)

    # Add a default repository
    default_repo = RepoSpec(
        repo_id="repo-default",
        project_id="proj-004",
        name="default",
        workspace_relpath=".",
        role=RepoRole.CODE,
    )

    registry.add_repo(default_repo)
    print(f"✓ Added default repository")

    # Get default context
    context = registry.get_default_context("proj-004")
    if context:
        print(f"\nDefault repository context:")
        print(f"  Name: {context.name}")
        print(f"  Path: {context.path}")
        print(f"  Writable: {context.writable}")

    # Add more repos
    api_repo = RepoSpec(
        repo_id="repo-api",
        project_id="proj-004",
        name="api",
        workspace_relpath="api",
        role=RepoRole.CODE,
    )

    registry.add_repo(api_repo)

    # Get all contexts
    contexts = registry.get_all_contexts("proj-004")
    print(f"\nAll repository contexts ({len(contexts)}):")
    for ctx in contexts:
        print(f"  - {ctx.name}: {ctx.path}")

    # Cleanup
    db_path.unlink()


def example_task_repo_scope():
    """Example: Task repository scope"""
    print("\n\n=== Example 5: Task Repository Scope ===\n")

    from agentos.core.task.models import RepoScopeType, TaskRepoScope

    # Create a task repo scope with path filters
    scope = TaskRepoScope(
        task_id="task-001",
        repo_id="repo-backend",
        scope=RepoScopeType.PATHS,
        path_filters=["src/**/*.py", "tests/**/*.py"],
        metadata={"reason": "Only modify Python files in src and tests"},
    )

    print(f"Task ID: {scope.task_id}")
    print(f"Repository ID: {scope.repo_id}")
    print(f"Scope: {scope.scope.value}")
    print(f"Path filters: {scope.path_filters}")
    print(f"Reason: {scope.metadata.get('reason')}")


def example_task_dependency():
    """Example: Task dependency"""
    print("\n\n=== Example 6: Task Dependency ===\n")

    from agentos.core.task.models import DependencyType, TaskDependency

    # Create a blocking dependency
    dep = TaskDependency(
        task_id="task-frontend",
        depends_on_task_id="task-backend",
        dependency_type=DependencyType.BLOCKS,
        reason="Frontend needs backend API to be deployed first",
        created_by="system",
        metadata={"auto_detected": False},
    )

    print(f"Task: {dep.task_id}")
    print(f"Depends on: {dep.depends_on_task_id}")
    print(f"Type: {dep.dependency_type.value}")
    print(f"Reason: {dep.reason}")


def example_task_artifact():
    """Example: Task artifact reference"""
    print("\n\n=== Example 7: Task Artifact Reference ===\n")

    from agentos.core.task.models import ArtifactRefType, TaskArtifactRef

    # Create a commit artifact reference
    artifact = TaskArtifactRef(
        task_id="task-001",
        repo_id="repo-backend",
        ref_type=ArtifactRefType.COMMIT,
        ref_value="abc123def456789",
        summary="Fixed authentication bug in login endpoint",
        metadata={"lines_changed": 42, "files_modified": 3},
    )

    print(f"Task ID: {artifact.task_id}")
    print(f"Repository ID: {artifact.repo_id}")
    print(f"Reference type: {artifact.ref_type.value}")
    print(f"Commit SHA: {artifact.ref_value}")
    print(f"Summary: {artifact.summary}")
    print(f"Lines changed: {artifact.metadata.get('lines_changed')}")


if __name__ == "__main__":
    example_basic_crud()
    example_project_model()
    example_repo_context()
    example_repo_registry()
    example_task_repo_scope()
    example_task_dependency()
    example_task_artifact()

    print("\n\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
