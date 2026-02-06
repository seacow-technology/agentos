"""CLI verify command"""

import click
from rich.console import Console

from agentos.core.verify import validate_file

console = Console()


@click.command()
@click.argument("artifact_path", type=click.Path(exists=True))
def verify_cmd(artifact_path: str):
    """Verify artifact (FactPack, AgentSpec, or Markdown)"""
    console.print(f"ℹ️  Verifying: [cyan]{artifact_path}[/cyan]")
    
    try:
        is_valid, errors, detected_type = validate_file(artifact_path)
        
        if detected_type:
            console.print(f"ℹ️  Detected schema type: [blue]{detected_type}[/blue]")
        
        if is_valid:
            console.print("✅ [green]Verification passed[/green]")
        else:
            console.print("❌ [red]Verification failed[/red]")
            for error in errors:
                console.print(f"  • {error}")
            raise click.Abort()
    except click.Abort:
        raise
    except Exception as e:
        console.print(f"❌ [red]Error during verification: {e}[/red]")
        raise click.Abort()
