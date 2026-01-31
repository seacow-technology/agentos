"""CLI command for tracing project cross-repository activities

This module provides the `agentos project trace` command to view:
- All repositories in a project
- Recent tasks by repository
- Cross-repository dependency statistics

Usage:
    agentos project trace <project_id> [--format table|json|tree]
    agentos project trace my-app
    agentos project trace my-app --format json
    agentos project trace my-app --limit 10

Created for Phase 6.1: Cross-repository trace CLI views
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from agentos.core.project.repository import ProjectRepository, RepoRegistry
from agentos.core.task.audit_service import TaskAuditService
from agentos.core.task.artifact_service import TaskArtifactService
from agentos.core.task.dependency_service import TaskDependencyService
from agentos.store import get_db, get_db_path
from agentos.core.time import utc_now


console = Console()


def _format_relative_time(iso_timestamp: Optional[str]) -> str:
    """Format timestamp as relative time (e.g., '2h ago')

    Args:
        iso_timestamp: ISO format timestamp string

    Returns:
        Relative time string (e.g., '2h ago', '1d ago')
    """
    if not iso_timestamp:
        return "never"

    try:
        # Parse ISO timestamp
        ts = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        now = utc_now()

        # Make ts timezone-aware if it's naive
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        delta = now - ts

        # Format as relative time
        seconds = delta.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}d ago"
        else:
            weeks = int(seconds / 604800)
            return f"{weeks}w ago"
    except Exception:
        return iso_timestamp


def _get_repo_recent_tasks(
    audit_service: TaskAuditService,
    artifact_service: TaskArtifactService,
    repo_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get recent tasks for a repository

    Args:
        audit_service: Audit service instance
        artifact_service: Artifact service instance
        repo_id: Repository ID
        limit: Maximum number of tasks to return

    Returns:
        List of task summaries with changes
    """
    # Get recent audits for this repo
    audits = audit_service.get_repo_audits(repo_id, limit=limit * 10)

    # Group by task_id and aggregate
    task_summaries = {}
    for audit in audits:
        task_id = audit.task_id
        if task_id not in task_summaries:
            task_summaries[task_id] = {
                "task_id": task_id,
                "status": "completed",  # Infer from audit presence
                "created_at": audit.created_at,
                "files_changed": set(),
                "lines_added": 0,
                "lines_deleted": 0,
            }

        # Aggregate changes
        if audit.files_changed:
            task_summaries[task_id]["files_changed"].update(audit.files_changed)
        task_summaries[task_id]["lines_added"] += audit.lines_added
        task_summaries[task_id]["lines_deleted"] += audit.lines_deleted

    # Convert to list and sort by created_at
    tasks = []
    for task_summary in task_summaries.values():
        task_summary["files_changed"] = len(task_summary["files_changed"])
        tasks.append(task_summary)

    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    return tasks[:limit]


def _count_cross_repo_dependencies(
    dep_service: TaskDependencyService,
    project_repos: List[str]
) -> Dict[str, int]:
    """Count cross-repository dependencies

    Args:
        dep_service: Dependency service instance
        project_repos: List of repository IDs in the project

    Returns:
        Dict with dependency counts
    """
    all_deps = dep_service.get_all_dependencies()

    total_deps = len(all_deps)
    cross_repo_deps = 0

    # For now, we can't easily detect cross-repo deps without task-repo mapping
    # This would require querying task_repo_scope table
    # Simplified: just return total count

    return {
        "total": total_deps,
        "cross_repo": cross_repo_deps,  # TODO: implement proper cross-repo detection
    }


def _format_table_output(
    project_id: str,
    repos: List[Dict[str, Any]],
    tasks_by_repo: Dict[str, List[Dict[str, Any]]],
    dep_stats: Dict[str, int]
) -> None:
    """Format and print table output

    Args:
        project_id: Project ID
        repos: List of repository data
        tasks_by_repo: Map of repo_id -> task summaries
        dep_stats: Dependency statistics
    """
    # Print header
    console.print(f"\n[bold cyan]Project:[/bold cyan] {project_id}\n")

    # Repositories table
    console.print(f"[bold]📦 Repositories ({len(repos)})[/bold]")

    if repos:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("URL", style="blue")
        table.add_column("Role", style="green")
        table.add_column("Writable", style="yellow")
        table.add_column("Last Active", style="white")

        for repo in repos:
            writable = "Yes" if repo["is_writable"] else "No"
            last_active = _format_relative_time(repo.get("last_active"))

            table.add_row(
                repo["name"],
                repo.get("remote_url", "N/A"),
                repo["role"],
                writable,
                last_active
            )

        console.print(table)
    else:
        console.print("  [yellow]No repositories found[/yellow]")

    # Recent tasks by repository
    console.print(f"\n[bold]📋 Recent Tasks by Repository[/bold]\n")

    for repo_id, tasks in tasks_by_repo.items():
        # Find repo name
        repo_name = next((r["name"] for r in repos if r["repo_id"] == repo_id), repo_id)

        if tasks:
            console.print(f"[cyan]{repo_name}[/cyan] ({len(tasks)} tasks):")
            for task in tasks:
                status = task["status"]
                status_color = "green" if status == "completed" else "yellow"

                files = task["files_changed"]
                lines_added = task["lines_added"]
                lines_deleted = task["lines_deleted"]

                console.print(
                    f"  • {task['task_id']} [{status_color}]{status}[/{status_color}] - "
                    f"{files} files, +{lines_added}/-{lines_deleted} lines"
                )
            console.print()

    # Cross-repository dependencies
    console.print(f"[bold]🔗 Cross-Repository Dependencies[/bold]")
    console.print(f"  Total: {dep_stats['total']}")
    if dep_stats['cross_repo'] > 0:
        console.print(f"  Cross-repo: {dep_stats['cross_repo']}")
    console.print()


def _format_json_output(
    project_id: str,
    repos: List[Dict[str, Any]],
    tasks_by_repo: Dict[str, List[Dict[str, Any]]],
    dep_stats: Dict[str, int]
) -> None:
    """Format and print JSON output

    Args:
        project_id: Project ID
        repos: List of repository data
        tasks_by_repo: Map of repo_id -> task summaries
        dep_stats: Dependency statistics
    """
    output = {
        "project_id": project_id,
        "repositories": repos,
        "tasks_by_repo": tasks_by_repo,
        "dependency_stats": dep_stats,
    }

    console.print(json.dumps(output, indent=2))


def _format_tree_output(
    project_id: str,
    repos: List[Dict[str, Any]],
    tasks_by_repo: Dict[str, List[Dict[str, Any]]],
    dep_stats: Dict[str, int]
) -> None:
    """Format and print tree output

    Args:
        project_id: Project ID
        repos: List of repository data
        tasks_by_repo: Map of repo_id -> task summaries
        dep_stats: Dependency statistics
    """
    tree = Tree(f"[bold cyan]{project_id}[/bold cyan]")

    # Add repositories
    repos_branch = tree.add("[bold]📦 Repositories[/bold]")
    for repo in repos:
        repo_node = repos_branch.add(
            f"[cyan]{repo['name']}[/cyan] ({repo['role']})"
        )
        repo_node.add(f"URL: {repo.get('remote_url', 'N/A')}")
        repo_node.add(f"Writable: {'Yes' if repo['is_writable'] else 'No'}")

        # Add tasks for this repo
        tasks = tasks_by_repo.get(repo["repo_id"], [])
        if tasks:
            tasks_node = repo_node.add(f"Recent tasks ({len(tasks)})")
            for task in tasks:
                status_color = "green" if task["status"] == "completed" else "yellow"
                tasks_node.add(
                    f"[{status_color}]{task['task_id']}[/{status_color}] - "
                    f"{task['files_changed']} files"
                )

    # Add dependencies
    deps_branch = tree.add("[bold]🔗 Dependencies[/bold]")
    deps_branch.add(f"Total: {dep_stats['total']}")
    if dep_stats['cross_repo'] > 0:
        deps_branch.add(f"Cross-repo: {dep_stats['cross_repo']}")

    console.print(tree)


@click.command(name="trace")
@click.argument("project_id", required=True)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "tree"]),
    default="table",
    help="Output format"
)
@click.option(
    "--limit",
    type=int,
    default=5,
    help="Maximum number of tasks per repository"
)
def project_trace(project_id: str, output_format: str, limit: int):
    """Trace project cross-repository activities

    Shows all repositories, recent tasks, and cross-repo dependencies.

    Examples:
        agentos project trace my-app
        agentos project trace my-app --format json
        agentos project trace my-app --limit 10
    """
    try:
        db = get_db()
        db_path = get_db_path()

        # Initialize services
        repo_crud = ProjectRepository(db_path)
        audit_service = TaskAuditService(db)
        artifact_service = TaskArtifactService(db)
        dep_service = TaskDependencyService(db)

        # Check if project exists
        cursor = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()

        if not project:
            console.print(f"[red]✗[/red] Project not found: {project_id}", err=True)
            sys.exit(1)

        # Get all repositories for the project
        repo_specs = repo_crud.list_repos(project_id)

        if not repo_specs:
            console.print(f"[yellow]⚠[/yellow] No repositories found for project: {project_id}")
            sys.exit(0)

        # Convert to dict for output
        repos = []
        repo_ids = []
        for spec in repo_specs:
            repo_dict = {
                "repo_id": spec.repo_id,
                "name": spec.name,
                "remote_url": spec.remote_url,
                "role": spec.role.value if hasattr(spec.role, 'value') else spec.role,
                "is_writable": spec.is_writable,
                "last_active": spec.updated_at,  # Use updated_at as proxy for activity
            }
            repos.append(repo_dict)
            repo_ids.append(spec.repo_id)

        # Get recent tasks for each repository
        tasks_by_repo = {}
        for repo_id in repo_ids:
            tasks = _get_repo_recent_tasks(
                audit_service,
                artifact_service,
                repo_id,
                limit=limit
            )
            if tasks:
                tasks_by_repo[repo_id] = tasks

        # Get cross-repo dependency stats
        dep_stats = _count_cross_repo_dependencies(dep_service, repo_ids)

        # Format output
        if output_format == "json":
            _format_json_output(project_id, repos, tasks_by_repo, dep_stats)
        elif output_format == "tree":
            _format_tree_output(project_id, repos, tasks_by_repo, dep_stats)
        else:  # table
            _format_table_output(project_id, repos, tasks_by_repo, dep_stats)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    project_trace()
