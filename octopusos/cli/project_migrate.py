"""CLI commands for project migration to multi-repo

Provides tools to help users migrate legacy single-repo projects
to the new multi-repo architecture.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentos.core.project.compat import (
    check_compatibility_warnings,
    migrate_project_to_multi_repo,
)
from agentos.core.project.repository import ProjectRepository
from agentos.schemas.project import Project, RepoSpec
from agentos.store import get_db
from agentos.core.db import registry_db

console = Console()


@click.group(name="migrate")
def migrate_group():
    """Project migration tools"""
    pass


@migrate_group.command(name="check")
@click.argument("project_id", required=False)
@click.option("--all", "check_all", is_flag=True, help="Check all projects")
def check_compatibility(project_id: str, check_all: bool):
    """Check project compatibility with multi-repo model

    Examples:
        agentos project migrate check my-project
        agentos project migrate check --all
    """
    try:
        db = get_db()
        cursor = db.cursor()

        # Determine which projects to check
        if check_all:
            projects = cursor.execute(
                "SELECT id, name, path FROM projects ORDER BY id"
            ).fetchall()
            project_ids = [p["id"] for p in projects]
        elif project_id:
            project = cursor.execute(
                "SELECT id, name, path FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                console.print(f"[red]✗ Project '{project_id}' not found[/red]")
                db.close()
                raise click.Abort()
            project_ids = [project_id]
        else:
            console.print("[red]✗ Specify --all or provide project_id[/red]")
            db.close()
            raise click.Abort()

        # Check each project
        # Use registry_db connection instead of hardcoded path
        repo_crud = ProjectRepository(registry_db.get_db())

        results = []
        for pid in project_ids:
            # Load project data
            project_row = cursor.execute(
                "SELECT * FROM projects WHERE id = ?", (pid,)
            ).fetchone()

            # Load repos
            repos = repo_crud.list_repos(pid)

            # Create Project instance
            project = Project(
                id=project_row["id"],
                name=project_row.get("name", pid),
                path=project_row.get("path"),
                repos=repos,
            )

            # Check compatibility
            warnings = check_compatibility_warnings(project)

            results.append({
                "project_id": pid,
                "has_repos": len(repos) > 0,
                "repo_count": len(repos),
                "has_path": bool(project.path),
                "warnings": warnings,
            })

        db.close()

        # Display results
        console.print()
        table = Table(title="Project Compatibility Check", show_header=True)
        table.add_column("Project ID", style="cyan")
        table.add_column("Repos", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Issues", style="red")

        for result in results:
            pid = result["project_id"]
            repo_count = result["repo_count"]
            has_path = result["has_path"]
            warnings = result["warnings"]

            if repo_count == 0 and not has_path:
                status = "❌ BROKEN"
                issues = "No repos, no path"
            elif repo_count == 0 and has_path:
                status = "⚠️  LEGACY"
                issues = "Needs migration"
            elif repo_count == 1:
                status = "✓ SINGLE-REPO"
                issues = "OK" if not warnings else f"{len(warnings)} warnings"
            else:
                status = "✓ MULTI-REPO"
                issues = "OK" if not warnings else f"{len(warnings)} warnings"

            table.add_row(
                pid,
                str(repo_count),
                status,
                issues
            )

        console.print(table)

        # Show detailed warnings
        for result in results:
            if result["warnings"]:
                console.print()
                console.print(Panel(
                    "\n".join(f"• {w}" for w in result["warnings"]),
                    title=f"[yellow]Warnings: {result['project_id']}[/yellow]",
                    border_style="yellow"
                ))

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]✗ Check failed: {e}[/red]")
        raise click.Abort()


@migrate_group.command(name="to-multi-repo")
@click.argument("project_id")
@click.option(
    "--workspace-root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Workspace root path (default: current directory)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes"
)
def migrate_to_multi_repo(project_id: str, workspace_root: str, dry_run: bool):
    """Migrate a legacy project to multi-repo model

    This command converts a legacy single-repo project (with only a 'path' field)
    to the new multi-repo model by creating a default repository binding.

    Examples:
        agentos project migrate to-multi-repo my-project
        agentos project migrate to-multi-repo my-project --dry-run
        agentos project migrate to-multi-repo my-project --workspace-root /workspace
    """
    try:
        db = get_db()
        cursor = db.cursor()

        # Load project
        project_row = cursor.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not project_row:
            console.print(f"[red]✗ Project '{project_id}' not found[/red]")
            db.close()
            raise click.Abort()

        # Load existing repos
        # Use registry_db connection instead of hardcoded path
        repo_crud = ProjectRepository(registry_db.get_db())
        repos = repo_crud.list_repos(project_id)

        # Create Project instance
        project = Project(
            id=project_row["id"],
            name=project_row.get("name", project_id),
            path=project_row.get("path"),
            repos=repos,
        )

        db.close()

        # Show current state
        console.print()
        console.print(Panel(
            f"Project ID: [cyan]{project.id}[/cyan]\n"
            f"Name: {project.name}\n"
            f"Legacy Path: {project.path or 'None'}\n"
            f"Current Repos: {len(project.repos)}",
            title="[yellow]Current State[/yellow]",
            border_style="yellow"
        ))

        # Check if migration needed
        if project.has_repos():
            console.print("[green]✓ Project already has repositories. No migration needed.[/green]")
            return

        if not project.path:
            console.print("[red]✗ Project has no path field. Cannot migrate automatically.[/red]")
            console.print("[yellow]Add a repository manually or set the path field first.[/yellow]")
            raise click.Abort()

        # Dry run mode
        if dry_run:
            console.print()
            console.print(Panel(
                f"Would create default repository:\n"
                f"  • name: default\n"
                f"  • workspace_relpath: .\n"
                f"  • is_writable: True\n"
                f"\n"
                f"This would bind the repository to project '{project_id}'",
                title="[cyan]Dry Run[/cyan]",
                border_style="cyan"
            ))
            console.print("[yellow]Run without --dry-run to perform migration[/yellow]")
            return

        # Perform migration
        console.print()
        console.print("[yellow]Migrating project to multi-repo model...[/yellow]")

        workspace_path = Path(workspace_root).resolve()
        success, messages = migrate_project_to_multi_repo(
            project, repo_crud, workspace_path
        )

        # Display results
        console.print()
        for message in messages:
            if "ERROR" in message:
                console.print(f"[red]✗ {message}[/red]")
            elif "✓" in message:
                console.print(f"[green]{message}[/green]")
            else:
                console.print(f"[yellow]• {message}[/yellow]")

        if success:
            console.print()
            console.print(Panel(
                f"[green]✓ Migration completed successfully[/green]\n\n"
                f"The project now has a default repository binding.\n"
                f"All existing code will continue to work.\n\n"
                f"Next steps:\n"
                f"  1. Run: agentos project migrate check {project_id}\n"
                f"  2. Test your workflows\n"
                f"  3. Consider updating code to use new multi-repo APIs",
                title="[green]Success[/green]",
                border_style="green"
            ))
        else:
            console.print()
            console.print("[red]✗ Migration failed[/red]")
            raise click.Abort()

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]✗ Migration failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise click.Abort()


@migrate_group.command(name="list-repos")
@click.argument("project_id")
def list_repos(project_id: str):
    """List all repositories bound to a project

    Examples:
        agentos project migrate list-repos my-project
    """
    try:
        db = get_db()
        cursor = db.cursor()

        # Check project exists
        project = cursor.execute(
            "SELECT id, name FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not project:
            console.print(f"[red]✗ Project '{project_id}' not found[/red]")
            db.close()
            raise click.Abort()

        db.close()

        # Load repos
        # Use registry_db connection instead of hardcoded path
        repo_crud = ProjectRepository(registry_db.get_db())
        repos = repo_crud.list_repos(project_id)

        if not repos:
            console.print(f"[yellow]ℹ  Project '{project_id}' has no repositories bound[/yellow]")
            return

        # Display repos
        console.print()
        table = Table(title=f"Repositories for '{project_id}'", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Role", style="yellow")
        table.add_column("Writable", style="blue")
        table.add_column("Remote", style="magenta")

        for repo in repos:
            table.add_row(
                repo.name,
                repo.workspace_relpath,
                repo.role.value,
                "✓" if repo.is_writable else "✗",
                repo.remote_url or "-"
            )

        console.print(table)

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]✗ Failed to list repos: {e}[/red]")
        raise click.Abort()


# Register commands with main project group
# This would be done in agentos/cli/project.py:
# from agentos.cli.project_migrate import migrate_group
# project_group.add_command(migrate_group)
