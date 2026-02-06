"""CLI init command"""

import click
from rich.console import Console

from agentos.store import init_db

console = Console()


@click.command()
def init_cmd():
    """Initialize AgentOS store"""
    try:
        db_path = init_db()
        console.print(f"✅ AgentOS initialized at [green]{db_path}[/green]")
    except Exception as e:
        console.print(f"❌ [red]Initialization failed: {e}[/red]")
        raise click.Abort()
