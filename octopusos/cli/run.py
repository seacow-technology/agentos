"""CLI command for natural language execution with Mode Pipeline

一键运行命令：agentos run "自然语言输入"
自动选择 mode 并执行多阶段 pipeline
"""

import click
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentos.core.mode import ModeSelector, ModePipelineRunner

console = Console()


def _format_duration(started_at: str, finished_at: str) -> str:
    """
    Format duration between two timestamps.

    Args:
        started_at: Start timestamp (ISO format)
        finished_at: End timestamp (ISO format)

    Returns:
        Formatted duration string (e.g., "2.5s", "1m 30s", "< 1s")
    """
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
        duration_seconds = (end - start).total_seconds()

        if duration_seconds < 1:
            return "< 1s"
        elif duration_seconds < 60:
            return f"{duration_seconds:.1f}s"
        elif duration_seconds < 3600:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except (ValueError, TypeError, AttributeError):
        return "N/A"


@click.command(name="run")
@click.argument("nl_input", type=str)
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Target repository path (default: current directory)"
)
@click.option(
    "--policy",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default="policies/sandbox_policy.json",
    help="Sandbox policy file path"
)
@click.option(
    "--output",
    type=click.Path(file_okay=False, dir_okay=True),
    default="outputs/pipeline",
    help="Output directory for pipeline results"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show mode selection without executing"
)
def run_cmd(nl_input: str, repo: str, policy: str, output: str, dry_run: bool):
    """Run AgentOS with natural language input
    
    Automatically selects the appropriate mode pipeline and executes it.
    
    Examples:
    
        # Create a landing page
        agentos run "I need a demo landing page"
        
        # Analyze code
        agentos run "analyze the authentication flow"
        
        # Fix a bug
        agentos run "fix the login bug"
    """
    console.print("\n[bold cyan]🚀 AgentOS Mode Pipeline Runner[/bold cyan]\n")
    
    # 1. Mode Selection
    console.print("[cyan]Step 1: Mode Selection[/cyan]")
    selector = ModeSelector()
    mode_selection = selector.select_mode(nl_input)
    
    # 显示选择结果
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Input", nl_input)
    table.add_row("Primary Mode", mode_selection.primary_mode)
    table.add_row("Pipeline", " → ".join(mode_selection.pipeline))
    table.add_row("Reason", mode_selection.reason)
    
    console.print(table)
    console.print()
    
    # 如果是 dry-run，到此结束
    if dry_run:
        console.print("[yellow]Dry-run mode: Stopping after mode selection[/yellow]")
        return 0
    
    # 2. Pipeline Execution
    console.print("[cyan]Step 2: Pipeline Execution[/cyan]")
    
    repo_path = Path(repo).resolve()
    policy_path = Path(policy) if Path(policy).exists() else None
    output_dir = Path(output)
    
    if not repo_path.exists():
        console.print(f"[red]Error: Repository path does not exist: {repo_path}[/red]")
        return 1
    
    if policy_path and not policy_path.exists():
        console.print(f"[yellow]Warning: Policy file not found: {policy_path}[/yellow]")
        console.print("[yellow]Continuing without policy (may be unsafe)[/yellow]")
        policy_path = None
    
    try:
        runner = ModePipelineRunner(output_dir=output_dir)
        
        console.print(f"[dim]Repository: {repo_path}[/dim]")
        console.print(f"[dim]Policy: {policy_path or 'None'}[/dim]")
        console.print(f"[dim]Output: {output_dir}[/dim]\n")
        
        # 执行 pipeline
        with console.status("[bold green]Executing pipeline..."):
            result = runner.run_pipeline(
                mode_selection=mode_selection,
                nl_input=nl_input,
                repo_path=repo_path,
                policy_path=policy_path
            )
        
        # 3. Display Results
        console.print("\n[cyan]Step 3: Results[/cyan]")
        
        # 阶段结果
        stage_table = Table(show_header=True, header_style="bold magenta")
        stage_table.add_column("Stage", style="cyan")
        stage_table.add_column("Mode", style="yellow")
        stage_table.add_column("Status", style="bold")
        stage_table.add_column("Duration", style="dim")
        
        for idx, stage in enumerate(result.stages):
            status_color = "green" if stage.status == "success" else "red"
            status_text = f"[{status_color}]{stage.status.upper()}[/{status_color}]"

            # 计算时长
            duration = _format_duration(stage.started_at, stage.finished_at)

            stage_table.add_row(
                f"Stage {idx + 1}",
                stage.mode_id,
                status_text,
                duration
            )
        
        console.print(stage_table)
        console.print()
        
        # 整体结果
        if result.overall_status == "success":
            panel_style = "green"
            emoji = "✅"
            title = "Pipeline Completed Successfully"
        else:
            panel_style = "red"
            emoji = "❌"
            title = "Pipeline Failed"
        
        # 计算总时长
        total_duration = _format_duration(result.started_at, result.finished_at)

        result_text = f"""
{emoji} {title}

Pipeline ID: {result.pipeline_id}
Total Stages: {len(result.stages)}
Success Rate: {sum(1 for s in result.stages if s.status == 'success')}/{len(result.stages)}
Total Duration: {total_duration}

Output Directory: {output_dir / result.pipeline_id}
        """
        
        console.print(Panel(
            result_text.strip(),
            title=f"[bold]{title}[/bold]",
            border_style=panel_style
        ))
        
        # 错误详情（如果有）
        failed_stages = [s for s in result.stages if s.status != "success"]
        if failed_stages:
            console.print("\n[red]Failed Stages:[/red]")
            for stage in failed_stages:
                console.print(f"  • {stage.mode_id}: {stage.error}")
        
        # 返回状态码
        return 0 if result.overall_status == "success" else 1
        
    except Exception as e:
        console.print(f"\n[red]Error during pipeline execution:[/red]")
        console.print(f"[red]{str(e)}[/red]")
        
        import traceback
        if console.is_terminal:
            console.print("\n[dim]Traceback:[/dim]")
            console.print(traceback.format_exc())
        
        return 1


if __name__ == "__main__":
    run_cmd()
