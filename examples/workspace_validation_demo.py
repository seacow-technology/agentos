"""Workspace Validation Demo

Demonstrates workspace layout and validation features.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.workspace import WorkspaceLayout, WorkspaceValidator
from agentos.schemas.project import RepoSpec, RepoRole


def demo_workspace_layout():
    """Demonstrate workspace layout management"""
    print("=" * 60)
    print("Demo 1: Workspace Layout Management")
    print("=" * 60)

    with TemporaryDirectory() as tmpdir:
        # Initialize workspace
        layout = WorkspaceLayout(Path(tmpdir))

        print(f"\n📂 Workspace root: {layout.workspace_root.root_path}")
        print(f"📍 Projects dir: {layout.workspace_root.get_projects_dir()}")

        # Define repositories
        repos = [
            RepoSpec(
                repo_id="repo1",
                project_id="my-app",
                name="backend",
                remote_url="git@github.com:org/backend",
                workspace_relpath="./be",
                role=RepoRole.CODE,
                is_writable=True,
            ),
            RepoSpec(
                repo_id="repo2",
                project_id="my-app",
                name="frontend",
                remote_url="git@github.com:org/frontend",
                workspace_relpath="./fe",
                role=RepoRole.CODE,
                is_writable=True,
            ),
            RepoSpec(
                repo_id="repo3",
                project_id="my-app",
                name="docs",
                remote_url="git@github.com:org/docs",
                workspace_relpath="./docs",
                role=RepoRole.DOCS,
                is_writable=False,
            ),
        ]

        # Get repository paths
        print("\n📚 Repository paths:")
        for repo in repos:
            repo_path = layout.get_repo_path("my-app", repo)
            print(f"  • {repo.name}: {repo_path}")

        # Ensure project structure
        project_root = layout.ensure_project_root("my-app")
        metadata_dir = layout.ensure_metadata_dir("my-app")

        print(f"\n✅ Project root created: {project_root}")
        print(f"✅ Metadata dir created: {metadata_dir}")

        # Save workspace manifest
        layout.save_workspace_manifest("my-app", repos)
        print(f"✅ Workspace manifest saved")

        # Load and display manifest
        manifest = layout.load_workspace_manifest("my-app")
        print(f"\n📄 Manifest loaded:")
        print(f"  • Project: {manifest['project_id']}")
        print(f"  • Version: {manifest['workspace_version']}")
        print(f"  • Repositories: {len(manifest['repositories'])}")


def demo_validation_success():
    """Demonstrate successful validation"""
    print("\n" + "=" * 60)
    print("Demo 2: Validation - Success Case")
    print("=" * 60)

    layout = WorkspaceLayout(Path("/tmp/workspace"))
    validator = WorkspaceValidator()

    repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="demo-app",
            name="backend",
            workspace_relpath="./be",
            role=RepoRole.CODE,
        ),
        RepoSpec(
            repo_id="repo2",
            project_id="demo-app",
            name="frontend",
            workspace_relpath="./fe",
            role=RepoRole.CODE,
        ),
    ]

    # Validate layout (path conflicts only, no filesystem checks)
    result = layout.validate_layout("demo-app", repos)

    print(f"\n🔍 Validation result: {'✅ PASSED' if result.is_valid else '❌ FAILED'}")
    print(f"   • Conflicts: {len(result.conflicts)}")

    if result.is_valid:
        print("\n✨ No conflicts detected!")
        print("   • Unique repository names: ✓")
        print("   • No path overlaps: ✓")
        print("   • All paths within project root: ✓")


def demo_validation_conflicts():
    """Demonstrate conflict detection"""
    print("\n" + "=" * 60)
    print("Demo 3: Validation - Conflict Detection")
    print("=" * 60)

    layout = WorkspaceLayout(Path("/tmp/workspace"))

    # Test 1: Duplicate names
    print("\n📋 Test 1: Duplicate repository names")
    repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="demo-app",
            name="backend",
            workspace_relpath="./be1",
            role=RepoRole.CODE,
        ),
        RepoSpec(
            repo_id="repo2",
            project_id="demo-app",
            name="backend",  # Duplicate!
            workspace_relpath="./be2",
            role=RepoRole.CODE,
        ),
    ]

    result = layout.validate_layout("demo-app", repos)
    if not result.is_valid:
        print("❌ Conflict detected:")
        for conflict in result.conflicts:
            print(f"   • {conflict.message}")

    # Test 2: Path overlap
    print("\n📋 Test 2: Overlapping paths")
    repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="demo-app",
            name="lib",
            workspace_relpath="./lib",
            role=RepoRole.CODE,
        ),
        RepoSpec(
            repo_id="repo2",
            project_id="demo-app",
            name="lib-sub",
            workspace_relpath="./lib/sub",  # Nested!
            role=RepoRole.CODE,
        ),
    ]

    result = layout.validate_layout("demo-app", repos)
    if not result.is_valid:
        print("❌ Conflict detected:")
        for conflict in result.conflicts:
            print(f"   • {conflict.message}")

    # Test 3: Path outside root
    print("\n📋 Test 3: Path outside project root")
    repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="demo-app",
            name="external",
            workspace_relpath="../../external",  # Outside!
            role=RepoRole.CODE,
        ),
    ]

    result = layout.validate_layout("demo-app", repos)
    if not result.is_valid:
        print("❌ Conflict detected:")
        for conflict in result.conflicts:
            print(f"   • {conflict.message}")


def demo_idempotency():
    """Demonstrate idempotency checks"""
    print("\n" + "=" * 60)
    print("Demo 4: Idempotency Checks")
    print("=" * 60)

    validator = WorkspaceValidator()

    # Test 1: Same configuration (idempotent)
    print("\n📋 Test 1: Importing same configuration")
    existing_repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="my-app",
            name="backend",
            remote_url="git@github.com:org/backend",
            workspace_relpath="./be",
            role=RepoRole.CODE,
        ),
    ]

    new_repos = [
        RepoSpec(
            repo_id="repo2",
            project_id="my-app",
            name="backend",
            remote_url="git@github.com:org/backend",
            workspace_relpath="./be",
            role=RepoRole.CODE,
        ),
    ]

    result = validator.check_idempotency("my-app", new_repos, existing_repos)
    print(f"   Result: {'✅ Idempotent' if result.is_valid else '❌ Not idempotent'}")

    # Test 2: Adding new repository
    print("\n📋 Test 2: Adding new repository")
    new_repos = [
        RepoSpec(
            repo_id="repo1",
            project_id="my-app",
            name="backend",
            remote_url="git@github.com:org/backend",
            workspace_relpath="./be",
            role=RepoRole.CODE,
        ),
        RepoSpec(
            repo_id="repo3",
            project_id="my-app",
            name="frontend",
            workspace_relpath="./fe",
            role=RepoRole.CODE,
        ),
    ]

    result = validator.check_idempotency("my-app", new_repos, existing_repos)
    print(f"   Result: {'✅ Valid (with warnings)' if result.is_valid else '❌ Invalid'}")
    if result.warnings:
        for warning in result.warnings:
            print(f"   ⚠️  {warning}")

    # Test 3: Removing repository (not allowed)
    print("\n📋 Test 3: Removing existing repository")
    new_repos = []  # Empty - removes backend

    result = validator.check_idempotency("my-app", new_repos, existing_repos)
    print(f"   Result: {'✅ Valid' if result.is_valid else '❌ Invalid (protected)'}")
    if result.conflicts:
        for conflict in result.conflicts:
            print(f"   ❌ {conflict.message}")

    # Test 4: Modifying configuration (not allowed)
    print("\n📋 Test 4: Modifying repository configuration")
    new_repos = [
        RepoSpec(
            repo_id="repo2",
            project_id="my-app",
            name="backend",
            remote_url="git@github.com:other/backend",  # Different URL!
            workspace_relpath="./be",
            role=RepoRole.CODE,
        ),
    ]

    result = validator.check_idempotency("my-app", new_repos, existing_repos)
    print(f"   Result: {'✅ Valid' if result.is_valid else '❌ Invalid (protected)'}")
    if result.conflicts:
        for conflict in result.conflicts:
            print(f"   ❌ {conflict.message}")


def demo_error_formatting():
    """Demonstrate error message formatting"""
    print("\n" + "=" * 60)
    print("Demo 5: Error Message Formatting")
    print("=" * 60)

    from agentos.core.workspace.validation import Conflict, ConflictType

    # Example 1: Path exists
    print("\n📋 Example 1: Directory already exists")
    conflict = Conflict(
        type=ConflictType.PATH_EXISTS,
        message="Directory already exists and is not empty",
        repo_name="backend",
        path="/workspace/projects/my-app/be",
        suggestions=[
            "Remove the directory: rm -rf /workspace/projects/my-app/be",
            "Or use --force to overwrite (WARNING: will delete local changes)",
            "Or choose a different workspace path",
        ],
    )
    print(conflict.format_error())

    # Example 2: Remote mismatch
    print("\n📋 Example 2: Remote URL mismatch")
    conflict = Conflict(
        type=ConflictType.REMOTE_MISMATCH,
        message="Existing git remote URL differs from expected",
        repo_name="backend",
        path="/workspace/projects/my-app/be",
        expected_value="git@github.com:new/backend",
        actual_value="git@github.com:old/backend",
        suggestions=[
            "Remove the directory: rm -rf /workspace/projects/my-app/be",
            "Or use --force to overwrite",
            "Or update the project config to use existing remote",
        ],
    )
    print(conflict.format_error())

    # Example 3: Path overlap
    print("\n📋 Example 3: Nested repository path")
    conflict = Conflict(
        type=ConflictType.PATH_OVERLAP,
        message="Repository 'lib-sub' is nested within 'lib'",
        repo_name="lib-sub",
        path="/workspace/projects/my-app/lib/sub",
        details={
            "parent_repo": "lib",
            "parent_path": "/workspace/projects/my-app/lib",
        },
        suggestions=[
            "Choose non-overlapping workspace paths",
            "Nested repositories are not supported",
        ],
    )
    print(conflict.format_error())


if __name__ == "__main__":
    print("\n🚀 Workspace Validation Demo")
    print("=" * 60)

    try:
        demo_workspace_layout()
        demo_validation_success()
        demo_validation_conflicts()
        demo_idempotency()
        demo_error_formatting()

        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
