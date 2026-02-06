"""CLI command for tracing task cross-repository activities

This module provides the `agentos task trace` command to view:
- Task basic information
- Repositories involved with change summaries
- Artifact references (commits, PRs, etc.)
- Task dependencies (upstream and downstream)

Usage:
    agentos task trace <task_id> [--format table|json|tree] [--detailed]
    agentos task trace task-123
    agentos task trace task-123 --format json
    agentos task trace task-123 --detailed

Created for Phase 6.1: Cross-repository trace CLI views
"""

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text

from agentos.core.task.audit_service import TaskAuditService
from agentos.core.task.artifact_service import TaskArtifactService, ArtifactRefType
from agentos.core.task.dependency_service import TaskDependencyService
from agentos.core.project.repository import ProjectRepository
from agentos.store import get_db, get_db_path
from agentos.core.time import utc_now


console = Console()


def _format_relative_time(iso_timestamp: Optional[str]) -> str:
    """Format timestamp as relative time (e.g., '2h ago')"""
    if not iso_timestamp:
        return "unknown"

    try:
        ts = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        now = utc_now()

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        delta = now - ts
        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        elif seconds < 604800:
            return f"{int(seconds / 86400)}d ago"
        else:
            return f"{int(seconds / 604800)}w ago"
    except Exception:
        return iso_timestamp


def _get_task_basic_info(db, task_id: str) -> Optional[Dict[str, Any]]:
    """Get basic task information

    Args:
        db: Database connection
        task_id: Task ID

    Returns:
        Task info dict or None if not found
    """
    cursor = db.execute(
        """
        SELECT task_id, status, created_at, updated_at
        FROM tasks
        WHERE task_id = ?
        """,
        (task_id,)
    )

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "task_id": row["task_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_task_repo_scopes(db, task_id: str) -> List[Dict[str, Any]]:
    """Get repository scopes for a task

    Args:
        db: Database connection
        task_id: Task ID

    Returns:
        List of repo scope dicts
    """
    cursor = db.execute(
        """
        SELECT repo_id, access_scope
        FROM task_repo_scope
        WHERE task_id = ?
        """,
        (task_id,)
    )

    rows = cursor.fetchall()
    return [{"repo_id": row["repo_id"], "scope": row["access_scope"]} for row in rows]


def _aggregate_repo_changes(
    audit_service: TaskAuditService,
    task_id: str,
    repo_id: str
) -> Dict[str, Any]:
    """Aggregate changes for a repository

    Args:
        audit_service: Audit service instance
        task_id: Task ID
        repo_id: Repository ID

    Returns:
        Aggregated change summary
    """
    audits = audit_service.get_task_audits(task_id, repo_id=repo_id, limit=1000)

    # Aggregate changes
    files_changed = set()
    lines_added = 0
    lines_deleted = 0
    commit_hash = None

    for audit in audits:
        if audit.files_changed:
            files_changed.update(audit.files_changed)
        lines_added += audit.lines_added
        lines_deleted += audit.lines_deleted

        # Get first commit hash
        if audit.commit_hash and not commit_hash:
            commit_hash = audit.commit_hash

    return {
        "files": list(files_changed),
        "file_count": len(files_changed),
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "commit_hash": commit_hash,
    }


def _format_table_output(
    task_info: Dict[str, Any],
    repos_data: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    dependencies: Dict[str, List[Dict[str, Any]]],
    detailed: bool
) -> None:
    """Format and print table output

    Args:
        task_info: Task basic information
        repos_data: List of repository data with changes
        artifacts: List of artifact references
        dependencies: Dict with 'depends_on' and 'depended_by' lists
        detailed: Whether to show detailed information
    """
    # Task header
    console.print(f"\n[bold cyan]Task:[/bold cyan] {task_info['task_id']}")
    console.print(f"[bold]Status:[/bold] [{_status_color(task_info['status'])}]{task_info['status']}[/{_status_color(task_info['status'])}]")
    console.print(f"[bold]Created:[/bold] {_format_relative_time(task_info['created_at'])}")
    console.print()

    # Repositories section
    console.print(f"[bold]📦 Repositories ({len(repos_data)})[/bold]\n")

    for repo in repos_data:
        scope_color = "green" if repo["scope"] == "FULL" else "yellow"
        console.print(f"[cyan]{repo['name']}[/cyan] ([{scope_color}]{repo['scope']}[/{scope_color}] access):")

        changes = repo["changes"]
        if changes["file_count"] > 0:
            console.print("  Changes:")

            if detailed and changes["files"]:
                # Show individual files
                for file_path in changes["files"][:20]:  # Limit to 20 files
                    console.print(f"    M  {file_path}")

                if len(changes["files"]) > 20:
                    console.print(f"    ... and {len(changes['files']) - 20} more files")
            else:
                console.print(f"    {changes['file_count']} files modified")

            console.print(
                f"    Total: {changes['file_count']} files, "
                f"+{changes['lines_added']}/-{changes['lines_deleted']} lines"
            )

            if changes["commit_hash"]:
                console.print(f"    Commit: {changes['commit_hash'][:8]}")
        else:
            console.print("  [dim]No changes[/dim]")

        console.print()

    # Artifacts section
    if artifacts:
        console.print(f"[bold]🎯 Artifacts ({len(artifacts)})[/bold]")
        for artifact in artifacts:
            ref_type = artifact["ref_type"]
            ref_value = artifact["ref_value"]
            summary = artifact.get("summary", "")

            console.print(f"  • {ref_type}:{ref_value}")
            if summary:
                console.print(f"    {summary}")
        console.print()

    # Dependencies section
    console.print(f"[bold]🔗 Dependencies[/bold]")

    depends_on = dependencies.get("depends_on", [])
    depended_by = dependencies.get("depended_by", [])

    if depends_on:
        console.print(f"\n  [bold]Depends on:[/bold]")
        for dep in depends_on:
            dep_type = dep["dependency_type"]
            reason = dep.get("reason", "")
            console.print(f"    • {dep['depends_on_task_id']} ({dep_type})")
            if reason and detailed:
                console.print(f"      {reason}")

    if depended_by:
        console.print(f"\n  [bold]Depended by:[/bold]")
        for dep in depended_by:
            dep_type = dep["dependency_type"]
            reason = dep.get("reason", "")
            console.print(f"    • {dep['task_id']} ({dep_type})")
            if reason and detailed:
                console.print(f"      {reason}")

    if not depends_on and not depended_by:
        console.print("  [dim]No dependencies[/dim]")

    console.print()


def _format_json_output(
    task_info: Dict[str, Any],
    repos_data: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    dependencies: Dict[str, List[Dict[str, Any]]]
) -> None:
    """Format and print JSON output"""
    output = {
        "task": task_info,
        "repositories": repos_data,
        "artifacts": artifacts,
        "dependencies": dependencies,
    }

    console.print(json.dumps(output, indent=2))


def _format_tree_output(
    task_info: Dict[str, Any],
    repos_data: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    dependencies: Dict[str, List[Dict[str, Any]]]
) -> None:
    """Format and print tree output (dependency tree)"""
    task_id = task_info["task_id"]
    status = task_info["status"]

    # Create main tree
    tree = Tree(f"[bold cyan]{task_id}[/bold cyan] ([{_status_color(status)}]{status}[/{_status_color(status)}])")

    # Add dependencies branch
    depends_on = dependencies.get("depends_on", [])
    if depends_on:
        deps_branch = tree.add("[bold]depends on:[/bold]")
        for dep in depends_on:
            dep_node = deps_branch.add(
                f"{dep['depends_on_task_id']} ({dep['dependency_type']})"
            )
            # Recursively show nested dependencies (simplified - just show direct)
            if dep.get("reason"):
                dep_node.add(f"[dim]{dep['reason']}[/dim]")

    # Add dependents branch
    depended_by = dependencies.get("depended_by", [])
    if depended_by:
        dependents_branch = tree.add("[bold]depended by:[/bold]")
        for dep in depended_by:
            dependent_node = dependents_branch.add(
                f"{dep['task_id']} ({dep['dependency_type']})"
            )
            if dep.get("reason"):
                dependent_node.add(f"[dim]{dep['reason']}[/dim]")

    # Add repositories branch
    repos_branch = tree.add(f"[bold]repositories ({len(repos_data)})[/bold]")
    for repo in repos_data:
        repo_node = repos_branch.add(f"[cyan]{repo['name']}[/cyan] ({repo['scope']})")
        changes = repo["changes"]
        if changes["file_count"] > 0:
            repo_node.add(
                f"{changes['file_count']} files, "
                f"+{changes['lines_added']}/-{changes['lines_deleted']} lines"
            )

    console.print(tree)


def _status_color(status: str) -> str:
    """Get color for task status"""
    status_colors = {
        "pending": "yellow",
        "in_progress": "blue",
        "completed": "green",
        "failed": "red",
        "cancelled": "dim",
    }
    return status_colors.get(status, "white")


@click.command(name="trace")
@click.argument("task_id", required=True)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "tree"]),
    default="table",
    help="Output format"
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed information (file lists, full reasons)"
)
def task_trace(task_id: str, output_format: str, detailed: bool):
    """Trace task cross-repository activities

    Shows task info, repository changes, artifacts, and dependencies.

    Examples:
        agentos task trace task-123
        agentos task trace task-123 --format json
        agentos task trace task-123 --detailed
        agentos task trace task-123 --format tree
    """
    try:
        db = get_db()
        db_path = get_db_path()

        # Initialize services
        repo_crud = ProjectRepository(db_path)
        audit_service = TaskAuditService(db)
        artifact_service = TaskArtifactService(db)
        dep_service = TaskDependencyService(db)

        # Get task basic info
        task_info = _get_task_basic_info(db, task_id)
        if not task_info:
            console.print(f"[red]✗[/red] Task not found: {task_id}", err=True)
            sys.exit(1)

        # Get repository scopes
        repo_scopes = _get_task_repo_scopes(db, task_id)

        # Get detailed repo information with changes
        repos_data = []
        for scope_data in repo_scopes:
            repo_id = scope_data["repo_id"]

            # Get repo spec for name
            cursor = db.execute(
                "SELECT name, remote_url FROM project_repos WHERE repo_id = ?",
                (repo_id,)
            )
            repo_row = cursor.fetchone()
            repo_name = repo_row["name"] if repo_row else repo_id

            # Get change summary
            changes = _aggregate_repo_changes(audit_service, task_id, repo_id)

            repos_data.append({
                "repo_id": repo_id,
                "name": repo_name,
                "scope": scope_data["scope"],
                "changes": changes,
            })

        # Get artifacts
        artifact_refs = artifact_service.get_task_artifacts(task_id)
        artifacts = [
            {
                "ref_type": art.ref_type.value if hasattr(art.ref_type, 'value') else art.ref_type,
                "ref_value": art.ref_value,
                "summary": art.summary,
                "repo_id": art.repo_id,
            }
            for art in artifact_refs
        ]

        # Get dependencies
        depends_on = dep_service.get_dependencies(task_id)
        depended_by = dep_service.get_reverse_dependencies(task_id)

        dependencies = {
            "depends_on": [
                {
                    "depends_on_task_id": dep.depends_on_task_id,
                    "dependency_type": dep.dependency_type.value if hasattr(dep.dependency_type, 'value') else dep.dependency_type,
                    "reason": dep.reason,
                }
                for dep in depends_on
            ],
            "depended_by": [
                {
                    "task_id": dep.task_id,
                    "dependency_type": dep.dependency_type.value if hasattr(dep.dependency_type, 'value') else dep.dependency_type,
                    "reason": dep.reason,
                }
                for dep in depended_by
            ],
        }

        # Format output
        if output_format == "json":
            _format_json_output(task_info, repos_data, artifacts, dependencies)
        elif output_format == "tree":
            _format_tree_output(task_info, repos_data, artifacts, dependencies)
        else:  # table
            _format_table_output(task_info, repos_data, artifacts, dependencies, detailed)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    task_trace()
