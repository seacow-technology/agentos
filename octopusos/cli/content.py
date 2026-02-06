"""Content management CLI commands."""

import json
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agentos.core.content import (
    ContentActivationGate,
    ContentLineageTracker,
    ContentRegistry,
    ContentTypeRegistry,
    LineageRequiredError,
)

console = Console()


@click.group()
def content_group():
    """Manage content registry (agents, workflows, commands, rules, policies, memories)."""
    pass


@content_group.command("register")
@click.option("--type", "content_type", required=True, help="Content type (agent, workflow, command, rule, policy, memory, fact)")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Path to content JSON file")
def register_content(content_type: str, file_path: str):
    """Register new content (metadata only, does not execute)."""
    try:
        # Load content from file
        with open(file_path, encoding="utf-8") as f:
            content = json.load(f)

        # Ensure type matches
        if "type" not in content:
            content["type"] = content_type
        elif content["type"] != content_type:
            console.print(
                f"[red]Error: Content type mismatch (file has '{content['type']}', --type specified '{content_type}')[/red]"
            )
            raise click.Abort()

        # Register
        registry = ContentRegistry()
        content_id = registry.register(content)

        console.print(f"[green]✓ Content registered:[/green] {content_id} v{content['version']}")
        console.print(f"[dim]Status: {content.get('status', 'draft')}[/dim]")

        # Show lineage info
        metadata = content.get("metadata", {})
        if metadata.get("is_root"):
            console.print("[cyan]  (Root version)[/cyan]")
        elif metadata.get("parent_version"):
            console.print(f"[cyan]  (Evolved from v{metadata['parent_version']})[/cyan]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("list")
@click.option("--type", "content_type", help="Filter by content type")
@click.option("--status", help="Filter by status (draft, active, deprecated, frozen)")
@click.option("--limit", type=int, default=50, help="Maximum results")
def list_content(content_type: Optional[str], status: Optional[str], limit: int):
    """List registered content."""
    try:
        registry = ContentRegistry()
        contents = registry.list(type_=content_type, status=status, limit=limit)

        if not contents:
            console.print("[yellow]No content found[/yellow]")
            return

        table = Table(title=f"Content Registry ({len(contents)} items)")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Version", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Lineage", style="dim")

        for content in contents:
            metadata = content.get("metadata", {})
            if metadata.get("is_root"):
                lineage = "ROOT"
            elif metadata.get("parent_version"):
                lineage = f"← v{metadata['parent_version']}"
            else:
                lineage = "?"

            status_style = {
                "active": "bold green",
                "draft": "yellow",
                "deprecated": "dim",
                "frozen": "cyan",
            }.get(content.get("status", "draft"), "white")

            table.add_row(
                content["id"],
                content["type"],
                content["version"],
                f"[{status_style}]{content.get('status', 'draft')}[/{status_style}]",
                lineage,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@content_group.command("activate")
@click.argument("content_id")
@click.option("--version", help="Content version (defaults to latest draft)")
def activate_content(content_id: str, version: Optional[str]):
    """Activate content (enforces lineage validation)."""
    try:
        registry = ContentRegistry()
        gate = ContentActivationGate(registry)

        # Get content
        if not version:
            content = registry.get(content_id)
            if not content:
                console.print(f"[red]Content not found: {content_id}[/red]")
                raise click.Abort()
            version = content["version"]

        # Activate
        gate.activate(content_id, version)

        console.print(f"[green]✓ Content activated:[/green] {content_id} v{version}")

    except LineageRequiredError as e:
        console.print(f"[red bold]🚨 RED LINE VIOLATION:[/red bold]")
        console.print(f"[red]{e}[/red]")
        raise click.Abort()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("deprecate")
@click.argument("content_id")
@click.option("--version", required=True, help="Content version to deprecate")
def deprecate_content(content_id: str, version: str):
    """Deprecate content (mark as deprecated)."""
    try:
        gate = ContentActivationGate()
        gate.deactivate(content_id, version)

        console.print(f"[yellow]✓ Content deprecated:[/yellow] {content_id} v{version}")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("freeze")
@click.argument("content_id")
@click.option("--version", required=True, help="Content version to freeze")
def freeze_content(content_id: str, version: str):
    """Freeze content (make immutable)."""
    try:
        gate = ContentActivationGate()
        gate.freeze(content_id, version)

        console.print(f"[cyan]✓ Content frozen:[/cyan] {content_id} v{version}")
        console.print("[dim]  (Content is now immutable - cannot be modified)[/dim]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("unfreeze")
@click.argument("content_id")
@click.option("--version", required=True, help="Content version to unfreeze")
def unfreeze_content(content_id: str, version: str):
    """Unfreeze content (allow modifications)."""
    try:
        gate = ContentActivationGate()
        gate.unfreeze(content_id, version)

        console.print(f"[green]✓ Content unfrozen:[/green] {content_id} v{version}")
        console.print("[dim]  (Content reverted to draft status)[/dim]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("explain")
@click.argument("content_id")
@click.option("--version", help="Content version (defaults to active/latest)")
def explain_content(content_id: str, version: Optional[str]):
    """Explain content (lineage + detailed spec for workflows)."""
    try:
        registry = ContentRegistry()
        tracker = ContentLineageTracker(registry)

        # Get content
        if not version:
            content = registry.get(content_id)
            if not content:
                console.print(f"[red]Content not found: {content_id}[/red]")
                raise click.Abort()
            version = content["version"]
        else:
            content = registry.get(content_id, version)
            if not content:
                console.print(f"[red]Content not found: {content_id} v{version}[/red]")
                raise click.Abort()

        # Show lineage
        explanation = tracker.explain_version(content_id, version)
        console.print(f"\n[bold cyan]Lineage: {content_id} v{version}[/bold cyan]")
        console.print(explanation)

        # For workflows, show detailed explanation
        if content["type"] == "workflow":
            _explain_workflow(content)
        
        # For agents, show detailed explanation
        if content["type"] == "agent":
            _explain_agent(content)
        
        # For commands, show detailed explanation
        if content["type"] == "command":
            _explain_command(content)

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


def _explain_workflow(content: dict):
    """Provide detailed workflow explanation."""
    spec = content["spec"]
    
    console.print(f"\n[bold cyan]Workflow Details[/bold cyan]")
    console.print(f"[bold]Category:[/bold] {spec.get('category', 'unknown')}")
    console.print(f"\n[bold]Purpose:[/bold]")
    console.print(f"  {spec.get('description', 'No description')}")
    
    # Phases
    phases = spec.get("phases", [])
    if phases:
        console.print(f"\n[bold]Phases ({len(phases)}):[/bold]")
        for i, phase in enumerate(phases, 1):
            phase_id = phase.get("id", "unknown")
            phase_desc = phase.get("description", "No description")
            allows_q = "✓" if phase.get("allows_questions", False) else "✗"
            risk = phase.get("risk_level", "unknown")
            
            console.print(f"  {i}. [cyan]{phase_id}[/cyan] (risk: {risk}, questions: {allows_q})")
            console.print(f"     {phase_desc}")
            
            requires = phase.get("requires", [])
            if requires:
                console.print(f"     Requires: {', '.join(requires)}")
            
            produces = phase.get("produces", [])
            if produces:
                console.print(f"     Produces: {', '.join(produces)}")
    
    # Interaction policy
    interaction = spec.get("interaction", {})
    console.print(f"\n[bold]Interaction Policy:[/bold]")
    console.print(f"  Mode: {interaction.get('default_mode', 'unknown')}")
    
    question_policy = interaction.get("question_policy", {})
    triggers = question_policy.get("trigger_when", [])
    if triggers:
        console.print(f"  Questions triggered when:")
        for trigger in triggers:
            console.print(f"    - {trigger}")
    
    # Use cases
    metadata = spec.get("metadata", {})
    use_cases = metadata.get("use_cases", [])
    if use_cases:
        console.print(f"\n[bold green]When to use:[/bold green]")
        for use_case in use_cases:
            console.print(f"  ✓ {use_case}")
    
    anti_use_cases = metadata.get("anti_use_cases", [])
    if anti_use_cases:
        console.print(f"\n[bold red]When NOT to use:[/bold red]")
        for anti_use_case in anti_use_cases:
            console.print(f"  ✗ {anti_use_case}")
    
    # Related workflows
    related = metadata.get("related_workflows", [])
    if related:
        console.print(f"\n[bold]Related Workflows:[/bold]")
        console.print(f"  {', '.join(related)}")


def _explain_agent(content: dict):
    """Provide detailed agent explanation."""
    spec = content["spec"]
    
    console.print(f"\n[bold cyan]Agent Details[/bold cyan]")
    console.print(f"[bold]Category:[/bold] {spec.get('category', 'unknown')}")
    console.print(f"\n[bold]Purpose:[/bold]")
    console.print(f"  {spec.get('description', 'No description')}")
    
    # Responsibilities
    responsibilities = spec.get("responsibilities", [])
    if responsibilities:
        console.print(f"\n[bold]Responsibilities ({len(responsibilities)}):[/bold]")
        for i, resp in enumerate(responsibilities, 1):
            console.print(f"  {i}. {resp}")
    
    # Allowed interactions
    interactions = spec.get("allowed_interactions", [])
    console.print(f"\n[bold]Allowed Interactions:[/bold]")
    console.print(f"  {', '.join(interactions) if interactions else 'None defined'}")
    
    # Constraints
    constraints = spec.get("constraints", {})
    if constraints:
        console.print(f"\n[bold red]Constraints (Red Lines):[/bold red]")
        for key, value in constraints.items():
            if value == "forbidden":
                console.print(f"  🚨 {key}: {value}")
            elif value == "allowed":
                console.print(f"  ✓ {key}: {value}")
            else:
                console.print(f"  • {key}: {value}")
    
    # Real-world roles
    metadata = spec.get("metadata", {})
    real_world_roles = metadata.get("real_world_roles", [])
    if real_world_roles:
        console.print(f"\n[bold]Real-world Job Titles:[/bold]")
        for role in real_world_roles:
            console.print(f"  • {role}")
    
    # Typical workflows
    typical_workflows = metadata.get("typical_workflows", [])
    if typical_workflows:
        console.print(f"\n[bold]Typically Participates In:[/bold]")
        console.print(f"  {', '.join(typical_workflows)}")


def _explain_command(content: dict):
    """Provide detailed command explanation."""
    spec = content["spec"]
    
    console.print(f"\n[bold cyan]Command Details[/bold cyan]")
    console.print(f"[bold]Title:[/bold] {spec.get('title', 'Unknown')}")
    console.print(f"[bold]Category:[/bold] {spec.get('category', 'unknown')}")
    console.print(f"\n[bold]Description:[/bold]")
    console.print(f"  {spec.get('description', 'No description')}")
    
    # Recommended roles
    recommended_roles = spec.get("recommended_roles", [])
    if recommended_roles:
        console.print(f"\n[bold]Recommended for Roles:[/bold]")
        console.print(f"  {', '.join(recommended_roles)}")
    
    # Workflow links
    workflow_links = spec.get("workflow_links", [])
    if workflow_links:
        console.print(f"\n[bold]Used in Workflows:[/bold]")
        for link in workflow_links:
            workflow = link.get("workflow", "unknown")
            phases = link.get("phases", [])
            console.print(f"  • {workflow}: {', '.join(phases)}")
    
    # Inputs
    inputs = spec.get("inputs", [])
    if inputs:
        console.print(f"\n[bold]Inputs:[/bold]")
        for inp in inputs:
            required = "required" if inp.get("required", False) else "optional"
            inp_type = inp.get("type", "unknown")
            desc = inp.get("description", "")
            console.print(f"  • {inp.get('name', 'unknown')} ({inp_type}, {required})")
            if desc:
                console.print(f"    {desc}")
    
    # Outputs
    outputs = spec.get("outputs", [])
    if outputs:
        console.print(f"\n[bold]Outputs:[/bold]")
        for out in outputs:
            out_type = out.get("type", "unknown")
            desc = out.get("description", "")
            console.print(f"  • {out.get('name', 'unknown')} ({out_type})")
            if desc:
                console.print(f"    {desc}")
    
    # Preconditions
    preconditions = spec.get("preconditions", [])
    if preconditions:
        console.print(f"\n[bold]Preconditions:[/bold]")
        for precond in preconditions:
            console.print(f"  ✓ {precond}")
    
    # Effects
    effects = spec.get("effects", [])
    if effects:
        console.print(f"\n[bold yellow]Side Effects:[/bold yellow]")
        for effect in effects:
            scope = effect.get("scope", "unknown")
            kind = effect.get("kind", "unknown")
            desc = effect.get("description", "")
            console.print(f"  • Scope: {scope}, Kind: {kind}")
            if desc:
                console.print(f"    {desc}")
    
    # Risk level
    risk_level = spec.get("risk_level", "unknown")
    risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(risk_level, "white")
    console.print(f"\n[bold]Risk Level:[/bold] [{risk_color}]{risk_level.upper()}[/{risk_color}]")
    
    # Evidence required
    evidence_required = spec.get("evidence_required", False)
    console.print(f"[bold]Evidence Required:[/bold] {'Yes' if evidence_required else 'No'}")
    
    # Constraints (Red Lines)
    constraints = spec.get("constraints", {})
    if constraints:
        console.print(f"\n[bold red]Constraints (Red Lines):[/bold red]")
        for key, value in constraints.items():
            console.print(f"  🚨 {key}: {value}")
    
    # Lineage
    lineage = spec.get("lineage", {})
    console.print(f"\n[bold]Lineage:[/bold]")
    console.print(f"  Introduced in: {lineage.get('introduced_in', 'unknown')}")
    derived_from = lineage.get("derived_from")
    if derived_from:
        console.print(f"  Derived from: {derived_from}")
    supersedes = lineage.get("supersedes", [])
    if supersedes:
        console.print(f"  Supersedes: {', '.join(supersedes)}")



@content_group.command("history")
@click.argument("content_id")
def show_history(content_id: str):
    """Show evolution history for content."""
    try:
        registry = ContentRegistry()
        tracker = ContentLineageTracker(registry)

        # Get all versions
        all_contents = registry.list(limit=1000)
        versions = [c for c in all_contents if c["id"] == content_id]

        if not versions:
            console.print(f"[red]Content not found: {content_id}[/red]")
            raise click.Abort()

        console.print(f"\n[bold cyan]Version History: {content_id}[/bold cyan]")
        console.print(f"Total versions: {len(versions)}\n")

        # Sort by creation time
        versions.sort(key=lambda c: c["metadata"].get("created_at", ""))

        table = Table()
        table.add_column("Version", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Parent", style="dim")
        table.add_column("Reason", style="white")
        table.add_column("Created", style="dim")

        for content in versions:
            metadata = content["metadata"]
            status_style = {
                "active": "bold green",
                "draft": "yellow",
                "deprecated": "dim",
                "frozen": "cyan",
            }.get(content.get("status", "draft"), "white")

            parent = metadata.get("parent_version", "ROOT" if metadata.get("is_root") else "?")
            reason = metadata.get("change_reason", "Initial version" if metadata.get("is_root") else "")
            created_at = metadata.get("created_at", "")[:19] if metadata.get("created_at") else ""

            table.add_row(
                content["version"],
                f"[{status_style}]{content.get('status', 'draft')}[/{status_style}]",
                parent,
                reason[:40] + "..." if len(reason) > 40 else reason,
                created_at,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@content_group.command("diff")
@click.argument("content_id")
@click.option("--from", "version_a", required=True, help="Source version")
@click.option("--to", "version_b", required=True, help="Target version")
def diff_versions(content_id: str, version_a: str, version_b: str):
    """Show diff between two versions."""
    try:
        registry = ContentRegistry()
        tracker = ContentLineageTracker(registry)

        # Get diff
        diff = tracker.diff_versions(content_id, version_a, version_b)

        console.print(f"\n[bold cyan]Diff: {content_id} v{version_a} → v{version_b}[/bold cyan]\n")

        if diff["added"]:
            console.print("[green]Added fields:[/green]")
            for key, value in diff["added"].items():
                console.print(f"  + {key}: {value}")

        if diff["removed"]:
            console.print("\n[red]Removed fields:[/red]")
            for key, value in diff["removed"].items():
                console.print(f"  - {key}: {value}")

        if diff["changed"]:
            console.print("\n[yellow]Changed fields:[/yellow]")
            for key, changes in diff["changed"].items():
                console.print(f"  ~ {key}:")
                console.print(f"      [red]- {changes['from']}[/red]")
                console.print(f"      [green]+ {changes['to']}[/green]")

        if not (diff["added"] or diff["removed"] or diff["changed"]):
            console.print("[dim]No changes detected[/dim]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.Abort()


@content_group.command("types")
@click.option("--all", "show_all", is_flag=True, help="Show all types including placeholders")
def list_types(show_all: bool):
    """List registered content types."""
    try:
        type_registry = ContentTypeRegistry()
        types = type_registry.list_types(include_placeholders=show_all)

        console.print(f"\n[bold cyan]Registered Content Types ({len(types)})[/bold cyan]\n")

        table = Table()
        table.add_column("Type ID", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Schema", style="dim")
        table.add_column("Status", style="green")

        for type_desc in types:
            is_placeholder = type_desc.metadata and type_desc.metadata.get("placeholder")
            available_in = type_desc.metadata.get("available_in", "") if type_desc.metadata else ""

            status = f"[yellow]Placeholder (v{available_in})[/yellow]" if is_placeholder else "[green]Available[/green]"

            table.add_row(
                type_desc.type_id,
                type_desc.description[:60] + "..." if len(type_desc.description) > 60 else type_desc.description,
                type_desc.schema_ref,
                status,
            )

        console.print(table)

        if not show_all:
            placeholder_count = sum(
                1 for t in type_registry.list_types(include_placeholders=True)
                if t.metadata and t.metadata.get("placeholder")
            )
            if placeholder_count > 0:
                console.print(f"\n[dim]({placeholder_count} placeholder types hidden. Use --all to show them)[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
