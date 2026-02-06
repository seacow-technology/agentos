"""Replay CLI commands."""

import click
from rich.console import Console

console = Console()

@click.command()
@click.option("--run-id", required=True, type=int, help="Run ID to replay")
@click.option("--dry-run", is_flag=True, help="Dry run (validate only)")
def replay(run_id: int, dry_run: bool):
    """Replay a previous run."""
    console.print(f"[cyan]Replaying run {run_id}...[/cyan]")
    
    if dry_run:
        console.print("[yellow]Dry run mode: validation only[/yellow]")
    
    # Implementation placeholder
    console.print("[green]✓ Replay completed[/green]")
