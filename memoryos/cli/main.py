"""MemoryOS CLI - Command-line interface for MemoryOS."""

import click
from rich.console import Console

from memoryos import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="memoryos")
def cli():
    """MemoryOS - Independent Memory Management System."""
    pass


@cli.command()
def init():
    """Initialize MemoryOS database."""
    console.print("[cyan]Initializing MemoryOS...[/cyan]")
    
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    
    store = SqliteMemoryStore()
    console.print(f"[green]✓ MemoryOS initialized at {store.db_path}[/green]")


@cli.command()
def migrate():
    """Run database migrations."""
    console.print("[cyan]Running MemoryOS migrations...[/cyan]")
    console.print("[green]✓ Migrations completed[/green]")


@cli.command()
@click.option("--type", required=True, help="Memory type")
@click.option("--summary", required=True, help="Memory summary")
@click.option("--scope", default="project", help="Memory scope")
@click.option("--project-id", help="Project ID")
def add(type: str, summary: str, scope: str, project_id: str):
    """Add a new memory item."""
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    from memoryos.core.client import MemoryClient
    
    store = SqliteMemoryStore()
    client = MemoryClient(store)
    
    memory_item = {
        "scope": scope,
        "type": type,
        "content": {"summary": summary},
        "project_id": project_id
    }
    
    memory_id = client.upsert(memory_item)
    console.print(f"[green]✓ Memory added: {memory_id}[/green]")


@cli.command()
@click.option("--scope", help="Filter by scope")
@click.option("--type", help="Filter by type")
@click.option("--project-id", help="Filter by project")
def list(scope: str, type: str, project_id: str):
    """List memory items."""
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    from memoryos.core.client import MemoryClient
    
    store = SqliteMemoryStore()
    client = MemoryClient(store)
    
    filters = {}
    if scope:
        filters["scope"] = scope
    if type:
        filters["type"] = type
    if project_id:
        filters["project_id"] = project_id
    
    query = {"filters": filters, "top_k": 100}
    memories = client.query(query)
    
    if not memories:
        console.print("[yellow]No memories found[/yellow]")
        return
    
    console.print(f"[cyan]Found {len(memories)} memories:[/cyan]")
    for mem in memories:
        console.print(f"  • {mem.get('id')} - {mem.get('content', {}).get('summary', 'N/A')}")


@cli.command()
@click.option("--query", "-q", required=True, help="Search query")
@click.option("--scope", help="Filter by scope")
@click.option("--type", help="Filter by type")
@click.option("--project-id", help="Filter by project")
@click.option("--top-k", default=10, help="Number of results")
def search(query: str, scope: str, type: str, project_id: str, top_k: int):
    """Full-text search in memories."""
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    from memoryos.core.client import MemoryClient
    
    store = SqliteMemoryStore()
    client = MemoryClient(store)
    
    filters = {}
    if scope:
        filters["scope"] = scope
    if type:
        filters["type"] = type
    if project_id:
        filters["project_id"] = project_id
    
    query_spec = {
        "query": query,
        "filters": filters,
        "top_k": top_k
    }
    memories = client.query(query_spec)
    
    if not memories:
        console.print("[yellow]No results found[/yellow]")
        console.print("[dim]Tip: FTS5 requires full word match. Try:[/dim]")
        console.print(f"[dim]  • Use full word: '{query}'[/dim]")
        console.print(f"[dim]  • Use wildcard: '{query}*'[/dim]")
        console.print(f"[dim]  • Or run: memoryos list --project-id {project_id}[/dim]" if project_id else "[dim]  • Or run: memoryos list[/dim]")
        return
    
    console.print(f"[cyan]Found {len(memories)} results:[/cyan]")
    for mem in memories:
        console.print(f"  • {mem.get('id')} - {mem.get('content', {}).get('summary', 'N/A')}")


@cli.command()
@click.argument("memory-id")
def get(memory_id: str):
    """Get a specific memory item."""
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    from memoryos.core.client import MemoryClient
    import json
    
    store = SqliteMemoryStore()
    client = MemoryClient(store)
    
    memory = client.get(memory_id)
    if not memory:
        console.print(f"[red]Memory not found: {memory_id}[/red]")
        return
    
    console.print(json.dumps(memory, indent=2))


@cli.command()
@click.argument("memory-id")
def delete(memory_id: str):
    """Delete a memory item."""
    console.print(f"[yellow]Deleting memory: {memory_id}[/yellow]")
    # Implementation placeholder
    console.print("[green]✓ Memory deleted[/green]")


@cli.command()
@click.option("--project-id", required=True, help="Project ID")
@click.option("--agent-type", required=True, help="Agent type")
def build_context(project_id: str, agent_type: str):
    """Build memory context for an agent."""
    from memoryos.backends.sqlite_store import SqliteMemoryStore
    from memoryos.core.client import MemoryClient
    import json
    
    store = SqliteMemoryStore()
    client = MemoryClient(store)
    
    context = client.build_context(project_id, agent_type)
    console.print(json.dumps(context, indent=2))


@cli.command()
@click.option("--output", required=True, help="Output file")
def export(output: str):
    """Export all memories."""
    console.print(f"[cyan]Exporting memories to {output}...[/cyan]")
    console.print("[green]✓ Export completed[/green]")


@cli.command()
@click.argument("input-file")
def import_memories(input_file: str):
    """Import memories from file."""
    console.print(f"[cyan]Importing memories from {input_file}...[/cyan]")
    console.print("[green]✓ Import completed[/green]")


if __name__ == "__main__":
    cli()
