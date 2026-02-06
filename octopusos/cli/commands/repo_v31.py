"""CLI commands for v0.4 Project-Aware Task OS (Repositories)

Implements v0.4 CLI commands for repository management.
Created for Task #6 Phase 5: CLI Implementation
"""

import json
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentos.core.project.service import ProjectService
from agentos.core.project.repo_service import RepoService
from agentos.core.project.errors import (
    ProjectNotFoundError,
    RepoNotFoundError,
    RepoNameConflictError,
    InvalidPathError,
    PathNotFoundError,
    RepoNotInProjectError,
)

console = Console()


@click.group(name="repo-v31")
def repo_v31_group():
    """v0.4 Repository management (Project-Aware Task OS)"""
    pass


@repo_v31_group.command("add")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--name", required=True, help="Repository name")
@click.option("--path", required=True, help="Local path to repository")
@click.option("--vcs", default="git", help="VCS type (default: git)")
@click.option("--remote", help="Remote URL")
@click.option("--branch", default="main", help="Default branch (default: main)")
@click.option("--quiet", is_flag=True, help="Only output repo ID")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def add_repo(
    project_id: str,
    name: str,
    path: str,
    vcs: str,
    remote: Optional[str],
    branch: str,
    quiet: bool,
    output_json: bool,
):
    """Add a repository to a project"""
    try:
        project_service = ProjectService()
        repo_service = RepoService()

        # Verify project exists
        project = project_service.get_project(project_id)
        if not project:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise click.Abort()

        # Add repository
        repo = repo_service.add_repo(
            project_id=project_id,
            name=name,
            local_path=path,
            vcs_type=vcs,
            remote_url=remote,
            default_branch=branch,
        )

        if quiet:
            # Only output repo ID
            console.print(repo.repo_id)
            return

        if output_json:
            # JSON output
            output = {
                "repo_id": repo.repo_id,
                "project_id": repo.project_id,
                "name": repo.name,
                "local_path": repo.local_path,
                "vcs_type": repo.vcs_type,
                "remote_url": repo.remote_url,
                "default_branch": repo.default_branch,
                "created_at": repo.created_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Repository added successfully[/green]")
        console.print(f"  [cyan]ID:[/cyan] {repo.repo_id}")
        console.print(f"  [cyan]Name:[/cyan] {repo.name}")
        console.print(f"  [cyan]Path:[/cyan] {repo.local_path}")
        console.print(f"  [cyan]Project:[/cyan] {project.name} ({project_id[:15]})")

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except RepoNameConflictError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print(f"[yellow]Hint: Repository name '{name}' already exists in project[/yellow]")
        raise click.Abort()
    except InvalidPathError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Path must be absolute and safe[/yellow]")
        raise click.Abort()
    except PathNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Path doesn't exist on filesystem[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@repo_v31_group.command("list")
@click.option("--project", "project_id", help="Filter by project ID")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_repos(project_id: Optional[str], output_json: bool):
    """List all repositories"""
    try:
        project_service = ProjectService()
        repo_service = RepoService()

        if project_id:
            # List repos for specific project
            project = project_service.get_project(project_id)
            if not project:
                console.print(f"[red]✗ Project not found: {project_id}[/red]")
                raise click.Abort()
            repos = project_service.get_project_repos(project_id)
        else:
            # List all repos (across all projects)
            repos = repo_service.list_repos()

        if output_json:
            # JSON output
            output = [
                {
                    "repo_id": r.repo_id,
                    "project_id": r.project_id,
                    "name": r.name,
                    "local_path": r.local_path,
                    "vcs_type": r.vcs_type,
                    "remote_url": r.remote_url,
                }
                for r in repos
            ]
            console.print_json(data=output)
            return

        if not repos:
            console.print("[yellow]No repositories found[/yellow]")
            return

        # Rich table output
        table = Table(title=f"Repositories (showing {len(repos)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Project", style="magenta")
        table.add_column("Path", style="yellow")
        table.add_column("VCS", style="blue")

        for r in repos:
            # Get project name
            project = project_service.get_project(r.project_id)
            project_name = project.name if project else "Unknown"

            table.add_row(
                r.repo_id[:15],
                r.name[:30],
                project_name[:20],
                r.local_path[:40],
                r.vcs_type,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(repos)} repositories[/dim]")

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@repo_v31_group.command("show")
@click.argument("repo_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show_repo(repo_id: str, output_json: bool):
    """Show repository details"""
    try:
        project_service = ProjectService()
        repo_service = RepoService()
        repo = repo_service.get_repo(repo_id)

        if not repo:
            console.print(f"[red]✗ Repository not found: {repo_id}[/red]")
            raise click.Abort()

        # Get project
        project = project_service.get_project(repo.project_id)

        if output_json:
            # JSON output
            output = {
                "repo_id": repo.repo_id,
                "project_id": repo.project_id,
                "project_name": project.name if project else None,
                "name": repo.name,
                "local_path": repo.local_path,
                "vcs_type": repo.vcs_type,
                "remote_url": repo.remote_url,
                "default_branch": repo.default_branch,
                "created_at": repo.created_at,
                "updated_at": repo.updated_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        details = f"""[cyan]Repository ID:[/cyan] {repo.repo_id}
[cyan]Name:[/cyan] {repo.name}
[cyan]Project:[/cyan] {project.name if project else 'N/A'} ({repo.project_id[:15]})
[cyan]Local Path:[/cyan] {repo.local_path}
[cyan]VCS Type:[/cyan] {repo.vcs_type}
[cyan]Remote URL:[/cyan] {repo.remote_url or 'N/A'}
[cyan]Default Branch:[/cyan] {repo.default_branch}
[cyan]Created:[/cyan] {repo.created_at}
[cyan]Updated:[/cyan] {repo.updated_at}
"""

        panel = Panel(details, title="Repository Details", border_style="cyan")
        console.print(panel)

    except RepoNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@repo_v31_group.command("scan")
@click.argument("repo_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def scan_repo(repo_id: str, output_json: bool):
    """Scan Git repository for current state"""
    try:
        repo_service = RepoService()
        repo = repo_service.get_repo(repo_id)

        if not repo:
            console.print(f"[red]✗ Repository not found: {repo_id}[/red]")
            raise click.Abort()

        # Scan repository
        info = repo_service.scan_repo(repo_id)

        if output_json:
            # JSON output
            console.print_json(data=info)
            return

        # Rich output
        details = f"""[cyan]Repository:[/cyan] {repo.name} ({repo_id[:15]})
[cyan]Path:[/cyan] {repo.local_path}
[cyan]VCS Type:[/cyan] {info.get('vcs_type', 'N/A')}
[cyan]Current Branch:[/cyan] {info.get('current_branch', 'N/A')}
[cyan]Remote URL:[/cyan] {info.get('remote_url', 'N/A')}
[cyan]Last Commit:[/cyan] {info.get('last_commit', 'N/A')}
[cyan]Status:[/cyan] {'[red]Dirty[/red]' if info.get('is_dirty') else '[green]Clean[/green]'}
"""

        panel = Panel(details, title="Repository Scan", border_style="cyan")
        console.print(panel)

    except RepoNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    repo_v31_group()
