"""CLI commands for v0.4 Project-Aware Task OS (Projects)

Implements v0.4 CLI commands for project management.
Created for Task #6 Phase 5: CLI Implementation
"""

import json
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentos.core.project.service import ProjectService
from agentos.core.project.errors import (
    ProjectNotFoundError,
    ProjectNameConflictError,
    ProjectHasTasksError,
)

console = Console()


@click.group(name="project-v31")
def project_v31_group():
    """v0.4 Project management (Project-Aware Task OS)"""
    pass


@project_v31_group.command("list")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--limit", default=100, help="Max results (default: 100)")
@click.option("--offset", default=0, help="Pagination offset (default: 0)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_projects(tags: Optional[str], limit: int, offset: int, output_json: bool):
    """List all projects"""
    try:
        service = ProjectService()
        tag_list = tags.split(",") if tags else None
        projects = service.list_projects(limit=limit, offset=offset, tags=tag_list)

        if output_json:
            # JSON output
            output = [
                {
                    "project_id": p.project_id,
                    "name": p.name,
                    "description": p.description,
                    "tags": p.tags,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                }
                for p in projects
            ]
            console.print_json(data=output)
            return

        if not projects:
            console.print("[yellow]No projects found[/yellow]")
            return

        # Rich table output
        table = Table(title=f"Projects (showing {len(projects)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Tags", style="yellow")
        table.add_column("Repos", style="magenta")
        table.add_column("Tasks", style="blue")
        table.add_column("Updated", style="dim")

        for p in projects:
            # Get repos and tasks count
            repos = service.get_project_repos(p.project_id)
            tasks = service.get_project_tasks(p.project_id)

            tags_str = ", ".join(p.tags) if p.tags else "-"
            updated = p.updated_at[:19] if p.updated_at else "N/A"

            table.add_row(
                p.project_id[:15],
                p.name[:30],
                tags_str[:20],
                str(len(repos)),
                str(len(tasks)),
                updated,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(projects)} projects[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@project_v31_group.command("create")
@click.argument("name")
@click.option("--desc", "--description", help="Project description")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--quiet", is_flag=True, help="Only output project ID")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def create_project(
    name: str,
    desc: Optional[str],
    tags: Optional[str],
    quiet: bool,
    output_json: bool,
):
    """Create a new project"""
    try:
        service = ProjectService()
        tag_list = tags.split(",") if tags else []

        project = service.create_project(
            name=name,
            description=desc,
            tags=tag_list,
        )

        if quiet:
            # Only output project ID
            console.print(project.project_id)
            return

        if output_json:
            # JSON output
            output = {
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "tags": project.tags,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Project created successfully[/green]")
        console.print(f"  [cyan]ID:[/cyan] {project.project_id}")
        console.print(f"  [cyan]Name:[/cyan] {project.name}")
        if project.tags:
            console.print(f"  [cyan]Tags:[/cyan] {', '.join(project.tags)}")

    except ProjectNameConflictError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print(f"[yellow]Hint: Project name '{name}' already exists[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@project_v31_group.command("show")
@click.argument("project_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show_project(project_id: str, output_json: bool):
    """Show project details"""
    try:
        service = ProjectService()
        project = service.get_project(project_id)

        if not project:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise click.Abort()

        # Get repos and tasks
        repos = service.get_project_repos(project_id)
        tasks = service.get_project_tasks(project_id)

        if output_json:
            # JSON output
            output = {
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "tags": project.tags,
                "default_repo_id": project.default_repo_id,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "repos_count": len(repos),
                "tasks_count": len(tasks),
                "repos": [
                    {
                        "repo_id": r.repo_id,
                        "name": r.name,
                        "local_path": r.local_path,
                        "vcs_type": r.vcs_type,
                    }
                    for r in repos
                ],
            }
            console.print_json(data=output)
            return

        # Rich output
        details = f"""[cyan]Project ID:[/cyan] {project.project_id}
[cyan]Name:[/cyan] {project.name}
[cyan]Description:[/cyan] {project.description or 'N/A'}
[cyan]Tags:[/cyan] {', '.join(project.tags) if project.tags else 'None'}
[cyan]Created:[/cyan] {project.created_at}
[cyan]Updated:[/cyan] {project.updated_at}

[bold]Repositories ({len(repos)}):[/bold]"""

        if repos:
            for r in repos:
                details += f"\n  - [green]{r.name}[/green] ({r.repo_id[:15]})"
                details += f"\n    Path: {r.local_path}"
                if r.remote_url:
                    details += f"\n    Remote: {r.remote_url}"
        else:
            details += "\n  [dim]No repositories yet[/dim]"

        details += f"\n\n[bold]Tasks:[/bold] {len(tasks)} total"
        if tasks:
            completed = len([t for t in tasks if t.status == "succeeded"])
            details += f" ({completed} completed, {len(tasks) - completed} pending)"

        panel = Panel(details, title="Project Details", border_style="cyan")
        console.print(panel)

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@project_v31_group.command("delete")
@click.argument("project_id")
@click.option("--force", is_flag=True, help="Force delete even if has tasks")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_project(project_id: str, force: bool, yes: bool):
    """Delete a project"""
    try:
        service = ProjectService()
        project = service.get_project(project_id)

        if not project:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise click.Abort()

        # Confirmation
        if not yes:
            console.print(
                f"[yellow]⚠ This will delete project '{project.name}' and all its data.[/yellow]"
            )
            if not force:
                tasks = service.get_project_tasks(project_id)
                if tasks:
                    console.print(
                        f"[yellow]This project has {len(tasks)} task(s). Use --force to delete anyway.[/yellow]"
                    )
                    raise click.Abort()

            confirm = click.confirm("Continue?", default=False)
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                return

        # Delete project
        service.delete_project(project_id, force=force)
        console.print(f"[green]✓ Project deleted: {project_id}[/green]")

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except ProjectHasTasksError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Use --force to delete project with tasks[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    project_v31_group()
