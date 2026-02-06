"""CLI commands for task management and tracing"""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from datetime import datetime

from agentos.core.task import TaskManager, TraceBuilder
from agentos.core.time import utc_now_iso


console = Console()


@click.group(name="task")
def task_group():
    """Task management and tracing commands"""
    pass


# Import cross-repository trace command
from agentos.cli.commands.task_trace import task_trace as task_repo_trace

# Add as subcommand with different name to avoid conflict with existing trace
task_group.add_command(task_repo_trace, name="repo-trace")


@task_group.command("list")
@click.option("--limit", default=20, help="Maximum number of tasks to show")
@click.option("--orphan", is_flag=True, help="Show only orphan tasks")
@click.option("--status", help="Filter by status")
def list_tasks(limit: int, orphan: bool, status: str):
    """List all tasks"""
    try:
        task_manager = TaskManager()
        tasks = task_manager.list_tasks(
            limit=limit,
            orphan_only=orphan,
            status_filter=status
        )
        
        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Tasks (showing {len(tasks)})")
        table.add_column("Task ID", style="cyan", no_wrap=True)
        table.add_column("Title")
        table.add_column("Status", style="green")
        table.add_column("Created", style="dim")
        table.add_column("Session", style="magenta")
        
        for task in tasks:
            created = task.created_at[:19] if task.created_at else "N/A"
            session = task.session_id[:8] if task.session_id else "-"
            
            # Color status
            status_style = {
                "created": "yellow",
                "planning": "cyan",
                "executing": "blue",
                "succeeded": "green",
                "failed": "red",
                "orphan": "red bold"
            }.get(task.status, "white")
            
            table.add_row(
                task.task_id[:12],
                task.title[:50],
                f"[{status_style}]{task.status}[/{status_style}]",
                created,
                session
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@task_group.command("show")
@click.argument("task_id")
def show_task(task_id: str):
    """Show task details"""
    try:
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            raise click.Abort()
        
        # Create panel with task details
        details = f"""
[cyan]Task ID:[/cyan] {task.task_id}
[cyan]Title:[/cyan] {task.title}
[cyan]Status:[/cyan] {task.status}
[cyan]Session:[/cyan] {task.session_id or 'N/A'}
[cyan]Created By:[/cyan] {task.created_by or 'system'}
[cyan]Created At:[/cyan] {task.created_at}
[cyan]Updated At:[/cyan] {task.updated_at}
"""
        
        if task.metadata:
            details += f"\n[cyan]Metadata:[/cyan]\n{json.dumps(task.metadata, indent=2)}"
        
        panel = Panel(details, title="Task Details", border_style="cyan")
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@task_group.command("trace")
@click.argument("task_id")
@click.option("--expand", multiple=True, help="Expand specific kinds (e.g., --expand intent --expand plan)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def trace_task(task_id: str, expand: tuple, output_json: bool):
    """Show trace of a task (shallow by default)"""
    try:
        task_manager = TaskManager()
        trace = task_manager.get_trace(task_id)
        
        if not trace:
            console.print(f"[red]Task not found: {task_id}[/red]")
            raise click.Abort()
        
        if output_json:
            # JSON output
            output = trace.to_dict()
            console.print_json(data=output)
            return
        
        # Rich output - shallow by default
        console.print(Panel(f"[bold]Task Trace[/bold]: {task_id}", style="cyan"))
        console.print()
        
        # Task info
        console.print(f"[cyan]Title:[/cyan] {trace.task.title}")
        console.print(f"[cyan]Status:[/cyan] {trace.task.status}")
        console.print(f"[cyan]Created:[/cyan] {trace.task.created_at}")
        console.print()
        
        # Timeline (shallow - just refs)
        if trace.timeline:
            console.print("[bold]Timeline:[/bold]")
            tree = Tree("📅 Execution Timeline")
            
            for entry in trace.timeline:
                timestamp = entry.timestamp[:19] if entry.timestamp else "N/A"
                phase_label = f" ({entry.phase})" if entry.phase else ""
                node = tree.add(f"[dim]{timestamp}[/dim] {entry.kind}: [yellow]{entry.ref_id[:16]}[/yellow]{phase_label}")
                
                # If this kind should be expanded
                if entry.kind in expand:
                    trace_builder = TraceBuilder()
                    content = trace_builder.expand_content(trace, entry.kind, entry.ref_id)
                    if content:
                        # Show abbreviated content
                        content_str = json.dumps(content, indent=2)
                        if len(content_str) > 500:
                            content_str = content_str[:500] + "..."
                        node.add(f"[dim]{content_str}[/dim]")
            
            console.print(tree)
            console.print()
        
        # Agents
        if trace.agents:
            console.print(f"[bold]Agents:[/bold] {len(trace.agents)} invocations")
            for agent in trace.agents[:5]:  # Show first 5
                console.print(f"  - {agent.get('agent_key', 'N/A')} ({agent.get('model', 'N/A')})")
            if len(trace.agents) > 5:
                console.print(f"  ... and {len(trace.agents) - 5} more")
            console.print()
        
        # Audits
        if trace.audits:
            console.print(f"[bold]Audits:[/bold] {len(trace.audits)} events")
            for audit in trace.audits[:5]:  # Show first 5
                level_color = {"info": "blue", "warn": "yellow", "error": "red"}.get(audit.get("level"), "white")
                console.print(f"  [{level_color}]{audit.get('level', 'info')}[/{level_color}]: {audit.get('event_type', 'N/A')}")
            if len(trace.audits) > 5:
                console.print(f"  ... and {len(trace.audits) - 5} more")
            console.print()
        
        # Hints
        if not expand:
            console.print("[dim]Tip: Use --expand <kind> to see detailed content (e.g., --expand intent)[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@task_group.command("resume")
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Force resume even without approval lineage (危险)")
def resume_task(task_id: str, force: bool):
    """Resume a paused task
    
    P2-3: Resume mechanism with strict validation
    
    RED LINE:
    - Task must be in 'awaiting_approval' status
    - Task must have approval lineage (unless --force)
    - Only open_plan checkpoint is valid
    """
    try:
        task_manager = TaskManager()
        
        # 1. Get task
        task = task_manager.get_task(task_id)
        
        if not task:
            console.print(f"[red]Error: Task {task_id} not found[/red]")
            raise click.Abort()
        
        # 2. Check status
        if task.status != "awaiting_approval":
            console.print(f"[yellow]Warning: Task status is '{task.status}', not 'awaiting_approval'[/yellow]")
            
            if task.status in ["succeeded", "failed", "canceled"]:
                console.print(f"[red]Error: Cannot resume task in terminal state '{task.status}'[/red]")
                raise click.Abort()
            
            if not force:
                console.print(f"[red]Use --force to resume task not in 'awaiting_approval' state[/red]")
                raise click.Abort()
        
        # 3. Check for approval lineage (P2 RED LINE)
        trace = task_manager.get_trace(task_id)
        approval_entries = [
            entry for entry in trace.timeline
            if entry.kind == "approval"
        ]
        
        if not approval_entries and not force:
            console.print(f"[red]Error: No approval lineage found for task {task_id}[/red]")
            console.print(f"[yellow]RED LINE: Task must be approved before resume[/yellow]")
            console.print(f"[dim]Use --force to bypass this check (NOT recommended)[/dim]")
            raise click.Abort()
        
        if approval_entries:
            latest_approval = approval_entries[-1]
            console.print(f"[green]✅ Approval found:[/green] {latest_approval.ref_id}")
            console.print(f"[dim]   Approved at: {latest_approval.timestamp}[/dim]")
        
        # 4. Check pause checkpoint (must be open_plan)
        pause_checkpoints = [
            entry for entry in trace.timeline
            if entry.kind == "pause_checkpoint"
        ]
        
        if pause_checkpoints:
            latest_pause = pause_checkpoints[-1]
            console.print(f"[blue]Pause checkpoint:[/blue] {latest_pause.ref_id}")
            
            if latest_pause.ref_id != "open_plan":
                console.print(f"[red]Error: Invalid pause checkpoint '{latest_pause.ref_id}'[/red]")
                console.print(f"[yellow]RED LINE: Only 'open_plan' checkpoint is valid in v1[/yellow]")
                raise click.Abort()
        
        # 5. P2-C2: Record resume event in lineage and audit
        from datetime import datetime, timezone
        
        task_manager.add_lineage(
            task_id=task_id,
            kind="resume",
            ref_id="requested",
            phase="execution",
            metadata={
                "resumed_at": utc_now_iso(),
                "resumed_by": "cli_user",
                "resumed_from_status": task.status
            }
        )
        
        task_manager.add_audit(
            task_id=task_id,
            event_type="task_resume_requested",
            level="info",
            payload={
                "action": "resume",
                "resumed_by": "cli_user",
                "previous_status": task.status
            }
        )
        
        console.print(f"[green]✅ Resume event recorded in lineage and audit[/green]")
        
        # 6. Update status to executing
        task_manager.update_task_status(task_id, "executing")
        console.print(f"[green]✅ Task {task_id} status updated to 'executing'[/green]")
        
        # 7. Restart runner
        console.print(f"[blue]Starting task runner...[/blue]")
        
        import subprocess
        import sys
        from pathlib import Path
        
        # Get project root
        project_root = Path(__file__).parent.parent.parent
        
        # Start runner as subprocess
        cmd = [sys.executable, "-m", "agentos.core.runner.task_runner", task_id]
        
        # Check if task should use real pipeline (from metadata)
        if task.metadata.get("use_real_pipeline"):
            cmd.append("--real-pipeline")
        
        subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        console.print(f"[green]✅ Task runner started in background[/green]")
        console.print(f"\n[dim]Monitor progress with:[/dim]")
        console.print(f"  agentos task show {task_id}")
        console.print(f"  agentos task trace {task_id}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    task_group()
