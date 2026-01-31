"""Memory management CLI commands."""

import json
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agentos.core.memory import MemoryService
from agentos.core.memory.decay import DecayEngine
from agentos.core.verify.schema_validator import validate_memory_item
from agentos.core.time import utc_now

# MemoryGCJob imported lazily in gc command to avoid jobs/ dependency

console = Console()


@click.group()
def memory_group():
    """Manage external memory storage."""
    pass


@memory_group.command("add")
@click.option("--type", "mem_type", required=True, type=click.Choice(
    ["decision", "convention", "constraint", "known_issue", "playbook", "glossary"]
), help="Memory type")
@click.option("--scope", required=True, type=click.Choice(
    ["global", "project", "repo", "task", "agent"]
), help="Memory scope")
@click.option("--summary", required=True, help="Brief summary")
@click.option("--details", help="Detailed information")
@click.option("--tags", help="Comma-separated tags")
@click.option("--sources", help="Comma-separated sources (e.g., ev001,file:path/file.ts:123)")
@click.option("--project-id", help="Project ID (required for project/repo/task/agent scopes)")
@click.option("--confidence", type=float, default=0.8, help="Confidence score (0.0-1.0)")
def add_memory(mem_type: str, scope: str, summary: str, details: Optional[str], tags: Optional[str], sources: Optional[str], project_id: Optional[str], confidence: float):
    """Add a new memory item."""
    
    # Validate scope requirements
    if scope in ["project", "repo", "task", "agent"] and not project_id:
        console.print(f"[red]Error: --project-id is required for scope '{scope}'[/red]")
        raise click.Abort()
    
    # Build memory item
    memory_item = {
        "schema_version": "1.0.0",
        "scope": scope,
        "type": mem_type,
        "content": {
            "summary": summary,
        },
        "confidence": confidence,
    }
    
    if details:
        memory_item["content"]["details"] = details
    
    if tags:
        memory_item["tags"] = [t.strip() for t in tags.split(",")]
    
    if sources:
        memory_item["sources"] = [s.strip() for s in sources.split(",")]
    
    if project_id:
        memory_item["project_id"] = project_id
    
    # Validate
    is_valid, errors = validate_memory_item(memory_item)
    if not is_valid:
        console.print("[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise click.Abort()
    
    # Store
    service = MemoryService()
    memory_id = service.upsert(memory_item)
    
    console.print(f"[green]✓ Memory added:[/green] {memory_id}")


@memory_group.command("list")
@click.option("--scope", help="Filter by scope")
@click.option("--type", "mem_type", help="Filter by type")
@click.option("--project-id", help="Filter by project ID")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--limit", type=int, default=50, help="Maximum results")
def list_memories(scope: Optional[str], mem_type: Optional[str], project_id: Optional[str], tags: Optional[str], limit: int):
    """List memory items."""
    service = MemoryService()
    
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    
    memories = service.list(
        scope=scope,
        project_id=project_id,
        tags=tag_list,
        mem_type=mem_type,
        limit=limit
    )
    
    if not memories:
        console.print("[yellow]No memories found[/yellow]")
        return
    
    table = Table(title=f"Memory Items ({len(memories)} found)")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Scope", style="blue")
    table.add_column("Summary", style="white")
    table.add_column("Confidence", style="green")
    
    for mem in memories:
        table.add_row(
            mem["id"],
            mem["type"],
            mem["scope"],
            mem["content"]["summary"][:60] + "..." if len(mem["content"]["summary"]) > 60 else mem["content"]["summary"],
            f"{mem['confidence']:.2f}"
        )
    
    console.print(table)


@memory_group.command("search")
@click.argument("query")
@click.option("--scope", help="Filter by scope")
@click.option("--limit", type=int, default=20, help="Maximum results")
def search_memories(query: str, scope: Optional[str], limit: int):
    """Search memories using full-text search."""
    service = MemoryService()
    
    memories = service.search(query=query, scope=scope, limit=limit)
    
    if not memories:
        console.print(f"[yellow]No memories found for query: {query}[/yellow]")
        return
    
    console.print(f"[cyan]Found {len(memories)} memories matching '{query}':[/cyan]\n")
    
    for mem in memories:
        console.print(f"[bold cyan]{mem['id']}[/bold cyan] ({mem['type']}, {mem['scope']})")
        console.print(f"  {mem['content']['summary']}")
        if mem.get("tags"):
            console.print(f"  [dim]Tags: {', '.join(mem['tags'])}[/dim]")
        console.print()


@memory_group.command("get")
@click.argument("memory_id")
def get_memory(memory_id: str):
    """Get detailed information about a memory item."""
    service = MemoryService()
    
    mem = service.get(memory_id)
    
    if not mem:
        console.print(f"[red]Memory not found: {memory_id}[/red]")
        raise click.Abort()
    
    console.print(json.dumps(mem, indent=2))


@memory_group.command("delete")
@click.argument("memory_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def delete_memory(memory_id: str, yes: bool):
    """Delete a memory item."""
    service = MemoryService()
    
    # Check if exists
    mem = service.get(memory_id)
    if not mem:
        console.print(f"[red]Memory not found: {memory_id}[/red]")
        raise click.Abort()
    
    # Confirm
    if not yes:
        console.print(f"[yellow]About to delete:[/yellow]")
        console.print(f"  ID: {mem['id']}")
        console.print(f"  Type: {mem['type']}")
        console.print(f"  Summary: {mem['content']['summary']}")
        
        if not click.confirm("Are you sure?"):
            console.print("[yellow]Cancelled[/yellow]")
            return
    
    # Delete
    service.delete(memory_id)
    console.print(f"[green]✓ Memory deleted:[/green] {memory_id}")


@memory_group.command("build-context")
@click.option("--project-id", required=True, help="Project ID")
@click.option("--agent-type", required=True, help="Agent type")
@click.option("--task-id", help="Task ID (optional)")
@click.option("--confidence", type=float, default=0.3, help="Minimum confidence threshold")
@click.option("--output", type=click.Path(), help="Output file path (optional, prints to stdout if not provided)")
def build_context(project_id: str, agent_type: str, task_id: Optional[str], confidence: float, output: Optional[str]):
    """Build MemoryPack context for agent execution."""
    service = MemoryService()
    
    memory_pack = service.build_context(
        project_id=project_id,
        agent_type=agent_type,
        task_id=task_id,
        confidence_threshold=confidence
    )
    
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(memory_pack, f, indent=2)
        console.print(f"[green]✓ MemoryPack saved to:[/green] {output}")
    else:
        console.print(json.dumps(memory_pack, indent=2))


@memory_group.command("decay")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--decay-rate", type=float, default=0.95, help="Daily decay multiplier (default: 0.95)")
@click.option("--min-confidence", type=float, default=0.2, help="Minimum confidence threshold for cleanup (default: 0.2)")
@click.option("--cleanup/--no-cleanup", default=True, help="Also cleanup eligible memories (default: cleanup)")
def decay_memories(dry_run: bool, decay_rate: float, min_confidence: float, cleanup: bool):
    """
    Apply confidence decay and cleanup expired memories.
    
    This command:
    1. Decays confidence for all memories based on time since last use
    2. Identifies memories eligible for cleanup (expired, low confidence, etc.)
    3. Optionally removes eligible memories (unless --dry-run)
    """
    service = MemoryService()
    engine = DecayEngine(
        decay_rate=decay_rate,
        min_confidence_threshold=min_confidence
    )
    
    # Get all memories
    all_memories = service.list(limit=10000)  # Get all
    
    if not all_memories:
        console.print("[yellow]No memories found[/yellow]")
        return
    
    console.print(f"[cyan]Processing {len(all_memories)} memories...[/cyan]\n")
    
    # Calculate decay
    decay_results = engine.calculate_decay_batch(all_memories)
    
    if decay_results:
        console.print(f"[bold]Confidence Decay:[/bold]")
        table = Table()
        table.add_column("Memory ID", style="cyan")
        table.add_column("Old", style="yellow")
        table.add_column("New", style="green")
        table.add_column("Change", style="red")
        
        for memory_id, old_conf, new_conf in decay_results[:20]:  # Show first 20
            change = new_conf - old_conf
            table.add_row(
                memory_id,
                f"{old_conf:.3f}",
                f"{new_conf:.3f}",
                f"{change:+.3f}"
            )
        
        if len(decay_results) > 20:
            console.print(f"[dim]... and {len(decay_results) - 20} more[/dim]")
        
        console.print(table)
        console.print(f"\n[green]Total decayed: {len(decay_results)}[/green]\n")
        
        # Apply decay if not dry-run
        if not dry_run:
            conn = service._get_connection()
            cursor = conn.cursor()
            for memory_id, _, new_conf in decay_results:
                cursor.execute(
                    "UPDATE memory_items SET confidence = ? WHERE id = ?",
                    (new_conf, memory_id)
                )
            conn.commit()
            conn.close()
            console.print("[green]✓ Confidence values updated[/green]\n")
    else:
        console.print("[yellow]No memories needed decay[/yellow]\n")
    
    # Get cleanup candidates
    if cleanup:
        cleanup_candidates = engine.get_cleanup_candidates(all_memories)
        
        if cleanup_candidates:
            console.print(f"[bold]Cleanup Candidates:[/bold]")
            table = Table()
            table.add_column("Memory ID", style="cyan")
            table.add_column("Reason", style="yellow")
            
            for memory_id, reason in cleanup_candidates:
                table.add_row(memory_id, reason)
            
            console.print(table)
            console.print(f"\n[yellow]Total eligible for cleanup: {len(cleanup_candidates)}[/yellow]\n")
            
            # Cleanup if not dry-run
            if not dry_run:
                for memory_id, reason in cleanup_candidates:
                    service.delete(memory_id)
                console.print(f"[green]✓ Cleaned up {len(cleanup_candidates)} memories[/green]")
            else:
                console.print("[dim]Run without --dry-run to actually delete these memories[/dim]")
        else:
            console.print("[green]No memories eligible for cleanup[/green]\n")
    
    if dry_run:
        console.print("\n[bold cyan]This was a dry run. No changes were made.[/bold cyan]")
        console.print("Run without --dry-run to apply changes.")


@memory_group.command("gc")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--decay-rate", type=float, default=0.95, help="Daily decay multiplier (default: 0.95)")
@click.option("--min-confidence", type=float, default=0.2, help="Minimum confidence threshold (default: 0.2)")
@click.option("--similarity", type=float, default=0.85, help="Similarity threshold for deduplication (default: 0.85)")
def gc_memories(dry_run: bool, decay_rate: float, min_confidence: float, similarity: float):
    """
    Run full garbage collection (decay + cleanup + dedupe + promotion).

    This comprehensive command:
    1. Decays confidence for all memories
    2. Cleans up expired/low-quality memories
    3. Deduplicates similar memories
    4. Promotes eligible memories to higher scopes
    """
    try:
        from agentos.jobs.memory_gc import MemoryGCJob
    except ImportError:
        console.print("[red]Error:[/red] Memory GC job module not available in this installation")
        console.print("[dim]This is an optional feature requiring the full AgentOS installation[/dim]")
        raise click.Abort()

    job = MemoryGCJob(
        decay_rate=decay_rate,
        min_confidence=min_confidence,
        similarity_threshold=similarity,
        dry_run=dry_run
    )
    
    stats = job.run()
    
    if stats["status"] == "failed":
        console.print(f"\n[red]GC failed: {stats['error']}[/red]")
        raise click.Abort()


@memory_group.command("health")
@click.option("--project-id", help="Filter by project ID")
def memory_health(project_id: Optional[str]):
    """
    Display memory health metrics and statistics.
    
    Shows:
    - Total memories by scope
    - Average confidence
    - Context budget utilization
    - GC statistics
    - Warnings and recommendations
    """
    service = MemoryService()
    
    # Get all memories (or filter by project)
    if project_id:
        memories = service.list(project_id=project_id, limit=10000)
    else:
        memories = service.list(limit=10000)
    
    if not memories:
        console.print("[yellow]No memories found[/yellow]")
        return
    
    # Calculate statistics
    total = len(memories)
    by_scope = {}
    by_type = {}
    by_retention = {}
    confidences = []
    expired_count = 0
    low_confidence_count = 0
    
    for mem in memories:
        # Scope
        scope = mem.get("scope", "unknown")
        by_scope[scope] = by_scope.get(scope, 0) + 1
        
        # Type
        mem_type = mem.get("type", "unknown")
        by_type[mem_type] = by_type.get(mem_type, 0) + 1
        
        # Retention (if available)
        retention = mem.get("retention_policy", {}).get("type", "project")
        by_retention[retention] = by_retention.get(retention, 0) + 1
        
        # Confidence
        conf = mem.get("confidence", 0.5)
        confidences.append(conf)
        if conf < 0.3:
            low_confidence_count += 1
        
        # Check expiry
        expires_at = mem.get("retention_policy", {}).get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_dt < utc_now():
                    expired_count += 1
            except:
                pass
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Estimate context size
    from agentos.core.memory.budgeter import ContextBudgeter
    budgeter = ContextBudgeter()
    breakdown = budgeter.get_budget_breakdown(memories)
    total_tokens = breakdown["total"]["tokens"]
    budget_pct = (total_tokens / 4000) * 100  # 4000 default budget
    
    # Display report
    console.print("\n[bold cyan]Memory Health Report[/bold cyan]")
    console.print("=" * 60)
    
    # Total
    console.print(f"\n[bold]Total Memories:[/bold] {total}")
    
    # By Scope
    console.print("\n[bold]By Scope:[/bold]")
    for scope in ["task", "agent", "project", "repo", "global"]:
        count = by_scope.get(scope, 0)
        pct = (count / total * 100) if total > 0 else 0
        console.print(f"  {scope:10} {count:5} ({pct:5.1f}%)")
    
    # By Retention Type
    if by_retention:
        console.print("\n[bold]By Retention:[/bold]")
        for ret_type, count in by_retention.items():
            pct = (count / total * 100) if total > 0 else 0
            console.print(f"  {ret_type:10} {count:5} ({pct:5.1f}%)")
    
    # Confidence
    console.print(f"\n[bold]Avg Confidence:[/bold] {avg_confidence:.3f}")
    console.print(f"  Low confidence (<0.3): {low_confidence_count} memories")
    
    # Context Budget
    console.print(f"\n[bold]Context Budget:[/bold]")
    console.print(f"  Estimated tokens: {total_tokens:,} ({budget_pct:.1f}% of 4000 default)")
    for scope in ["task", "agent", "project", "repo", "global"]:
        if scope in breakdown and breakdown[scope]["count"] > 0:
            console.print(f"    {scope:10} {breakdown[scope]['tokens']:6,} tokens ({breakdown[scope]['percentage']:.1f}%)")
    
    # Last GC run
    conn = service._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT started_at, memories_decayed, memories_deleted, memories_promoted
        FROM memory_gc_runs
        ORDER BY started_at DESC
        LIMIT 1
    """)
    last_gc = cursor.fetchone()
    conn.close()
    
    if last_gc:
        gc_time = datetime.fromisoformat(last_gc[0].replace('Z', '+00:00'))
        days_ago = (utc_now() - gc_time).total_seconds() / 86400
        console.print(f"\n[bold]Last GC Run:[/bold] {int(days_ago)} days ago")
        console.print(f"  Decayed: {last_gc[1]}, Deleted: {last_gc[2]}, Promoted: {last_gc[3]}")
    else:
        console.print("\n[bold]Last GC Run:[/bold] Never")
    
    # Warnings
    warnings = []
    if expired_count > 0:
        warnings.append(f"{expired_count} memories expired but not cleaned (run 'agentos memory gc')")
    if budget_pct > 90:
        warnings.append(f"Context budget high ({budget_pct:.0f}%), consider cleanup")
    if low_confidence_count > total * 0.3:
        warnings.append(f"{low_confidence_count} low-confidence memories ({low_confidence_count/total*100:.0f}%), consider decay")
    if last_gc is None or days_ago > 7:
        warnings.append("GC hasn't run in >7 days, consider running 'agentos memory gc'")
    
    if warnings:
        console.print("\n[bold yellow]⚠️  Warnings:[/bold yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")
    else:
        console.print("\n[bold green]✓ All health checks passed![/bold green]")


@memory_group.command("compact")
@click.option("--scope", type=click.Choice(["global", "project", "repo", "task", "agent"]), help="Memory scope to compact")
@click.option("--project-id", help="Project ID (required for non-global scopes)")
@click.option("--dry-run", is_flag=True, help="Show what would be compacted without doing it")
def compact_memories(scope, project_id, dry_run):
    """Compact similar memories into summaries.
    
    This command merges similar memories in a scope to reduce clutter.
    """
    try:
        from agentos.core.command import get_registry, CommandContext
        
        if scope and scope != "global" and not project_id:
            console.print("[red]Error:[/red] --project-id required for non-global scopes")
            raise click.Abort()
        
        registry = get_registry()
        context = CommandContext(project_id=project_id, scope=scope)
        
        with console.status("[cyan]Analyzing memories...[/cyan]" if not dry_run else "[cyan]Analyzing (dry run)...[/cyan]"):
            result = registry.execute(
                "memory:compact",
                context,
                scope=scope,
                project_id=project_id,
                dry_run=dry_run
            )
        
        if not result.is_success():
            console.print(f"[red]Error:[/red] {result.error}")
            return
        
        data = result.data
        
        if dry_run:
            console.print("\n[bold yellow]Dry Run Results:[/bold yellow]")
            console.print(f"Total memories: {data['total_memories']}")
            console.print(f"Clusters found: {data['clusters_found']}")
            if data.get('memories_per_cluster'):
                console.print(f"Memories per cluster: {data['memories_per_cluster']}")
        else:
            console.print("\n[bold green]✓ Compaction complete![/bold green]")
            console.print(f"Merged {data['memories_merged']} memories into {data['summaries_created']} summaries")
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@memory_group.command("scope")
@click.argument("action", type=click.Choice(["get", "set"]))
@click.argument("scope_name", required=False, type=click.Choice(["global", "project", "repo", "task", "agent"]))
def memory_scope(action, scope_name):
    """Get or set the current memory scope.
    
    Examples:
        agentos memory scope get
        agentos memory scope set task
        agentos memory scope set global
    """
    try:
        from agentos.core.command import get_registry, CommandContext
        
        if action == "set" and not scope_name:
            console.print("[red]Error:[/red] scope_name required for 'set' action")
            raise click.Abort()
        
        registry = get_registry()
        context = CommandContext()
        
        result = registry.execute(
            "memory:scope",
            context,
            action=action,
            scope=scope_name
        )
        
        if not result.is_success():
            console.print(f"[red]Error:[/red] {result.error}")
            return
        
        data = result.data
        
        if action == "get":
            console.print(f"Current memory scope: [cyan]{data['scope']}[/cyan]")
        else:
            console.print(f"[green]✓[/green] Memory scope set to: [cyan]{data['scope']}[/cyan]")
            console.print("\n[dim]Note: This setting is only for the current session.[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
