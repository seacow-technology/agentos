"""CLI commands for v0.4 Project-Aware Task OS (Tasks)

Implements v0.4 CLI commands for task management extensions.
Created for Task #6 Phase 5: CLI Implementation
"""

import json
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentos.core.task.service import TaskService
from agentos.core.task.spec_service import TaskSpecService
from agentos.core.task.binding_service import BindingService
from agentos.core.project.service import ProjectService
from agentos.core.project.repo_service import RepoService
from agentos.core.task.errors import (
    TaskNotFoundError,
    InvalidTransitionError,
    TaskStateError,
)
from agentos.core.project.errors import (
    ProjectNotFoundError,
    RepoNotFoundError,
    SpecNotFoundError,
    SpecAlreadyFrozenError,
    SpecIncompleteError,
    BindingNotFoundError,
    BindingValidationError,
)

console = Console()


@click.group(name="task-v31")
def task_v31_group():
    """v0.4 Task management extensions (Project-Aware Task OS)"""
    pass


@task_v31_group.command("create")
@click.option("--project", "project_id", required=True, help="Project ID (required)")
@click.option("--title", required=True, help="Task title")
@click.option("--intent", help="Task intent/description")
@click.option("--ac", "--acceptance-criteria", "acceptance_criteria", multiple=True, help="Acceptance criteria (can specify multiple)")
@click.option("--repo", "repo_id", help="Repository ID to bind")
@click.option("--workdir", help="Working directory within repo")
@click.option("--quiet", is_flag=True, help="Only output task ID")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def create_task(
    project_id: str,
    title: str,
    intent: Optional[str],
    acceptance_criteria: tuple,
    repo_id: Optional[str],
    workdir: Optional[str],
    quiet: bool,
    output_json: bool,
):
    """Create a new task (must specify project)"""
    try:
        task_service = TaskService()
        project_service = ProjectService()

        # Verify project exists
        project = project_service.get_project(project_id)
        if not project:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise click.Abort()

        # Create task in DRAFT state with project_id
        task = task_service.create_draft_task(
            title=title,
            project_id=project_id,
            metadata={
                "intent": intent,
                "acceptance_criteria": list(acceptance_criteria) if acceptance_criteria else [],
            },
        )

        # If repo_id specified, bind immediately
        if repo_id:
            task_service.bind_task(
                task_id=task.task_id,
                project_id=project_id,
                repo_id=repo_id,
                workdir=workdir,
            )

        if quiet:
            # Only output task ID
            console.print(task.task_id)
            return

        if output_json:
            # JSON output
            output = {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status,
                "project_id": project_id,
                "created_at": task.created_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Task created successfully[/green]")
        console.print(f"  [cyan]ID:[/cyan] {task.task_id}")
        console.print(f"  [cyan]Title:[/cyan] {task.title}")
        console.print(f"  [cyan]Project:[/cyan] {project.name} ({project_id[:15]})")
        console.print(f"  [cyan]Status:[/cyan] {task.status}")

        console.print("\n[dim]Next steps:[/dim]")
        console.print(f"  1. Review spec: [cyan]agentos task-v31 show {task.task_id}[/cyan]")
        console.print(f"  2. Freeze spec: [cyan]agentos task-v31 freeze {task.task_id}[/cyan]")
        if not repo_id:
            console.print(f"  3. Bind to repo: [cyan]agentos task-v31 bind {task.task_id} --project {project_id} --repo <repo_id>[/cyan]")
        console.print(f"  4. Mark ready: [cyan]agentos task-v31 ready {task.task_id}[/cyan]")

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@task_v31_group.command("freeze")
@click.argument("task_id")
@click.option("--ac", "--acceptance-criteria", "acceptance_criteria", multiple=True, help="Add acceptance criteria before freezing")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def freeze_task_spec(task_id: str, acceptance_criteria: tuple, output_json: bool):
    """Freeze task specification (DRAFT → PLANNED)"""
    try:
        spec_service = TaskSpecService()
        task_service = TaskService()

        # Get task
        task = task_service.get_task(task_id)
        if not task:
            console.print(f"[red]✗ Task not found: {task_id}[/red]")
            raise click.Abort()

        # Add acceptance criteria if provided
        if acceptance_criteria:
            # TODO: Add method to append acceptance criteria before freezing
            pass

        # Freeze spec
        spec = spec_service.freeze_spec(task_id)
        frozen_task = task_service.get_task(task_id)

        if output_json:
            # JSON output
            output = {
                "task_id": frozen_task.task_id,
                "title": frozen_task.title,
                "status": frozen_task.status,
                "spec_frozen": frozen_task.spec_frozen,
                "updated_at": frozen_task.updated_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Task spec frozen[/green]")
        console.print(f"  [cyan]Task:[/cyan] {task_id}")
        console.print(f"  [cyan]Status:[/cyan] draft → planned")

        console.print("\n[dim]Next step:[/dim]")
        console.print(f"  Mark as ready: [cyan]agentos task-v31 ready {task_id}[/cyan]")

    except (TaskNotFoundError, SpecNotFoundError) as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except SpecAlreadyFrozenError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Task spec is already frozen[/yellow]")
        raise click.Abort()
    except SpecIncompleteError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Ensure task has title and acceptance criteria[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@task_v31_group.command("bind")
@click.argument("task_id")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--repo", "repo_id", help="Repository ID")
@click.option("--workdir", help="Working directory within repo")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def bind_task(
    task_id: str,
    project_id: str,
    repo_id: Optional[str],
    workdir: Optional[str],
    output_json: bool,
):
    """Bind task to project/repository"""
    try:
        binding_service = BindingService()
        project_service = ProjectService()
        repo_service = RepoService()

        # Verify project exists
        project = project_service.get_project(project_id)
        if not project:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise click.Abort()

        # Verify repo exists if specified
        if repo_id:
            repo = repo_service.get_repo(repo_id)
            if not repo:
                console.print(f"[red]✗ Repository not found: {repo_id}[/red]")
                raise click.Abort()

            # Verify repo belongs to project
            if repo.project_id != project_id:
                console.print(f"[red]✗ Repository {repo_id} does not belong to project {project_id}[/red]")
                raise click.Abort()

        # Bind task
        binding = binding_service.create_binding(
            task_id=task_id,
            project_id=project_id,
            repo_id=repo_id,
            workdir=workdir,
        )

        if output_json:
            # JSON output
            output = {
                "task_id": task_id,
                "project_id": project_id,
                "repo_id": repo_id,
                "workdir": workdir,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Task bound successfully[/green]")
        console.print(f"  [cyan]Task:[/cyan] {task_id}")
        console.print(f"  [cyan]Project:[/cyan] {project.name}")
        if repo_id:
            repo = repo_service.get_repo(repo_id)
            console.print(f"  [cyan]Repository:[/cyan] {repo.name}")
        if workdir:
            console.print(f"  [cyan]Working Directory:[/cyan] {workdir}")

    except TaskNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except RepoNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@task_v31_group.command("ready")
@click.argument("task_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def mark_task_ready(task_id: str, output_json: bool):
    """Mark task as ready (PLANNED → READY)"""
    try:
        from agentos.core.task.state_machine import TaskStateMachine
        from agentos.core.task.states import TaskState

        binding_service = BindingService()
        task_service = TaskService()

        # Validate binding
        binding_service.validate_binding(task_id)

        # Transition to READY state
        state_machine = TaskStateMachine()
        task = state_machine.transition(
            task_id,
            to=TaskState.READY.value,
            actor="cli_user",
            reason="Manual transition to READY via CLI"
        )

        if output_json:
            # JSON output
            output = {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status,
                "spec_frozen": task.spec_frozen,
                "updated_at": task.updated_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        console.print(f"[green]✓ Task marked as ready[/green]")
        console.print(f"  [cyan]Task:[/cyan] {task_id}")
        console.print(f"  [cyan]Status:[/cyan] planned → ready")

        console.print("\n[dim]Task is now ready for execution.[/dim]")

    except (TaskNotFoundError, BindingNotFoundError) as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except BindingValidationError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Ensure spec is frozen and task is bound to a project[/yellow]")
        raise click.Abort()
    except InvalidTransitionError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print("[yellow]Hint: Task must be in PLANNED state to mark as ready[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@task_v31_group.command("list")
@click.option("--project", "project_id", help="Filter by project ID")
@click.option("--status", help="Filter by status")
@click.option("--limit", default=50, help="Max results (default: 50)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_tasks(project_id: Optional[str], status: Optional[str], limit: int, output_json: bool):
    """List tasks with project filtering"""
    try:
        project_service = ProjectService()

        if project_id:
            # List tasks for specific project
            project = project_service.get_project(project_id)
            if not project:
                console.print(f"[red]✗ Project not found: {project_id}[/red]")
                raise click.Abort()

            tasks = project_service.get_project_tasks(project_id)
            # Apply status filter if provided
            if status:
                tasks = [t for t in tasks if t.status == status]
        else:
            # List all tasks (use TaskManager)
            task_service = TaskService()
            tasks = task_service.task_manager.list_tasks(limit=limit, status_filter=status)

        if output_json:
            # JSON output
            output = [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "status": t.status,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in tasks[:limit]
            ]
            console.print_json(data=output)
            return

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return

        # Rich table output
        table = Table(title=f"Tasks (showing {min(len(tasks), limit)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="green")
        table.add_column("Project", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Updated", style="dim")

        for t in tasks[:limit]:
            # Get project name if available
            project_name = "-"
            if hasattr(t, 'project_id') and t.project_id:
                project = project_service.get_project(t.project_id)
                if project:
                    project_name = project.name[:20]

            # Color status
            status_style = {
                "draft": "yellow",
                "planned": "cyan",
                "ready": "green",
                "executing": "blue",
                "succeeded": "green bold",
                "failed": "red bold",
            }.get(t.status, "white")

            updated = t.updated_at[:19] if t.updated_at else "N/A"

            table.add_row(
                t.task_id[:12],
                t.title[:40],
                project_name,
                f"[{status_style}]{t.status}[/{status_style}]",
                updated,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(tasks)} tasks[/dim]")

    except ProjectNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


@task_v31_group.command("show")
@click.argument("task_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show_task(task_id: str, output_json: bool):
    """Show task details with project/repo info"""
    try:
        task_service = TaskService()
        project_service = ProjectService()
        repo_service = RepoService()
        binding_service = BindingService()

        task = task_service.get_task(task_id)
        if not task:
            console.print(f"[red]✗ Task not found: {task_id}[/red]")
            raise click.Abort()

        # Get project info if bound
        project = None
        repo = None
        binding = None

        try:
            # Try to get binding
            binding = binding_service.get_binding(task_id)
            if binding:
                project = project_service.get_project(binding.project_id)
                if binding.repo_id:
                    repo = repo_service.get_repo(binding.repo_id)
        except (BindingNotFoundError, ProjectNotFoundError, RepoNotFoundError):
            # Task not bound yet, that's okay
            pass

        if output_json:
            # JSON output
            output = {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status,
                "spec_frozen": getattr(task, 'spec_frozen', 0),
                "project_id": getattr(task, 'project_id', None),
                "project_name": project.name if project else None,
                "repo_id": binding.repo_id if binding else None,
                "repo_name": repo.name if repo else None,
                "workdir": binding.workdir if binding else None,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
            console.print_json(data=output)
            return

        # Rich output
        details = f"""[cyan]Task ID:[/cyan] {task.task_id}
[cyan]Title:[/cyan] {task.title}
[cyan]Status:[/cyan] {task.status}
[cyan]Spec Frozen:[/cyan] {'Yes' if getattr(task, 'spec_frozen', 0) else 'No'}"""

        if project:
            details += f"\n[cyan]Project:[/cyan] {project.name} ({project.project_id[:15]})"
        else:
            details += "\n[cyan]Project:[/cyan] [yellow]Not bound[/yellow]"

        if repo:
            details += f"\n[cyan]Repository:[/cyan] {repo.name} ({repo.repo_id[:15]})"
            details += f"\n[cyan]Working Directory:[/cyan] {binding.workdir or 'N/A'}"

        details += f"\n\n[cyan]Created:[/cyan] {task.created_at}"
        details += f"\n[cyan]Updated:[/cyan] {task.updated_at}"

        # Show intent and acceptance criteria if available
        if task.metadata:
            meta = task.metadata
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)

            if meta.get('intent'):
                details += f"\n\n[bold]Intent:[/bold]\n  {meta['intent']}"

            if meta.get('acceptance_criteria'):
                details += f"\n\n[bold]Acceptance Criteria:[/bold]"
                for i, ac in enumerate(meta['acceptance_criteria'], 1):
                    details += f"\n  {i}. {ac}"

        panel = Panel(details, title="Task Details", border_style="cyan")
        console.print(panel)

    except TaskNotFoundError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    task_v31_group()
