"""
Classifier Version Management CLI

Commands for managing InfoNeedClassifier versions:
- agentos version promote --proposal BP-017 [--major]
- agentos version rollback --to v1 --reason "..."
- agentos version list
- agentos version show v2
- agentos version history
"""

import asyncio
import logging
from typing import Optional, TypeVar, Awaitable

import click
from rich.console import Console
from rich.table import Table

from agentos.core.brain.classifier_version_manager import get_version_manager
from agentos.core.brain.improvement_proposal_store import get_store

logger = logging.getLogger(__name__)
console = Console()

T = TypeVar('T')


def run_async(coro: Awaitable[T]) -> T:
    """
    Run an async coroutine in a way that works both in sync and async contexts.

    This helper handles the case where asyncio.run() is called from within
    an already-running event loop (e.g., in pytest-asyncio tests).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running, use asyncio.run()
        return asyncio.run(coro)
    else:
        # Event loop already running, need to use a different approach
        # This is typically the case in async tests
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(coro)


@click.group(name="version")
def version_group():
    """Classifier version management commands"""
    pass


@version_group.command(name="promote")
@click.option(
    "--proposal",
    required=True,
    help="ImprovementProposal ID to promote (e.g., BP-017)"
)
@click.option(
    "--major",
    is_flag=True,
    help="Major version bump (v1->v2). Default is minor (v2->v2.1)"
)
@click.option(
    "--user",
    default="admin",
    help="User performing the promotion (default: admin)"
)
def promote_version_cmd(proposal: str, major: bool, user: str):
    """
    Promote a classifier version from an approved proposal.

    This command creates a new classifier version based on an approved
    ImprovementProposal. The version number is automatically incremented.

    Examples:
        # Minor version bump (v2 -> v2.1)
        agentos version promote --proposal BP-017

        # Major version bump (v2 -> v3)
        agentos version promote --proposal BP-017 --major

        # Specify user
        agentos version promote --proposal BP-017 --user alice
    """
    try:
        manager = get_version_manager()
        store = get_store()

        # Verify proposal exists and is accepted
        proposal_obj = run_async(store.get_proposal(proposal))
        if not proposal_obj:
            console.print(f"[red]Error:[/red] Proposal {proposal} not found")
            return

        if proposal_obj.status.value != "accepted":
            console.print(
                f"[red]Error:[/red] Proposal {proposal} is not accepted "
                f"(current status: {proposal_obj.status.value})"
            )
            return

        # Get current version
        current = manager.get_active_version()
        if not current:
            console.print("[red]Error:[/red] No active version found")
            return

        console.print(f"[bold]Promoting classifier version...[/bold]")
        console.print(f"  Current version: [cyan]{current.version_id}[/cyan]")
        console.print(f"  Proposal: [cyan]{proposal}[/cyan]")
        console.print(f"  Change type: [cyan]{'Major' if major else 'Minor'}[/cyan]")
        console.print()

        # Perform promotion
        new_version = manager.promote_version(
            proposal_id=proposal,
            change_log=proposal_obj.description,
            created_by=user,
            is_major=major,
            metadata={
                "improvement_rate": proposal_obj.evidence.improvement_rate,
                "risk_level": proposal_obj.evidence.risk.value,
                "samples": proposal_obj.evidence.samples,
            }
        )

        # Mark proposal as implemented
        run_async(store.mark_implemented(proposal))

        console.print(f"[green]✓[/green] Successfully promoted to version [bold cyan]{new_version.version_id}[/bold cyan]")
        console.print()
        console.print(f"[bold]Version Details:[/bold]")
        console.print(f"  Version ID: {new_version.version_id}")
        console.print(f"  Version Number: {new_version.version_number}")
        console.print(f"  Parent Version: {new_version.parent_version_id}")
        console.print(f"  Change Log: {new_version.change_log}")
        console.print(f"  Created By: {new_version.created_by}")
        console.print(f"  Created At: {new_version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print()
        console.print(f"[yellow]Note:[/yellow] Proposal {proposal} marked as implemented")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to promote version: {str(e)}")
        logger.error(f"Version promotion failed: {e}", exc_info=True)


@version_group.command(name="rollback")
@click.option(
    "--to",
    "to_version",
    required=True,
    help="Target version to rollback to (e.g., v2)"
)
@click.option(
    "--reason",
    required=True,
    help="Reason for rollback"
)
@click.option(
    "--user",
    default="admin",
    help="User performing the rollback (default: admin)"
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt"
)
def rollback_version_cmd(to_version: str, reason: str, user: str, yes: bool):
    """
    Rollback classifier to a previous version.

    This command deactivates the current version and reactivates a previous
    version. The rollback is recorded in the audit history.

    Examples:
        # Rollback to v2
        agentos version rollback --to v2 --reason "Performance regression"

        # Skip confirmation
        agentos version rollback --to v2 --reason "Bug detected" --yes
    """
    try:
        manager = get_version_manager()

        # Get current and target versions
        current = manager.get_active_version()
        if not current:
            console.print("[red]Error:[/red] No active version found")
            return

        target = manager.get_version(to_version)
        if not target:
            console.print(f"[red]Error:[/red] Version {to_version} not found")
            return

        if target.is_active:
            console.print(f"[yellow]Warning:[/yellow] Version {to_version} is already active")
            return

        # Confirmation prompt
        if not yes:
            console.print(f"[bold yellow]⚠ Warning: Rollback Operation[/bold yellow]")
            console.print(f"  Current version: [cyan]{current.version_id}[/cyan]")
            console.print(f"  Target version: [cyan]{to_version}[/cyan]")
            console.print(f"  Reason: {reason}")
            console.print()

            confirm = click.confirm("Do you want to proceed with rollback?")
            if not confirm:
                console.print("[yellow]Rollback cancelled[/yellow]")
                return

        console.print(f"[bold]Rolling back classifier version...[/bold]")

        # Perform rollback
        restored = manager.rollback_version(
            to_version_id=to_version,
            reason=reason,
            performed_by=user,
        )

        console.print(f"[green]✓[/green] Successfully rolled back to version [bold cyan]{restored.version_id}[/bold cyan]")
        console.print()
        console.print(f"[bold]Restored Version Details:[/bold]")
        console.print(f"  Version ID: {restored.version_id}")
        console.print(f"  Version Number: {restored.version_number}")
        console.print(f"  Change Log: {restored.change_log}")
        console.print(f"  Originally Created: {restored.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print()
        console.print(f"[yellow]Note:[/yellow] Previous version {current.version_id} has been deactivated")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to rollback version: {str(e)}")
        logger.error(f"Version rollback failed: {e}", exc_info=True)


@version_group.command(name="list")
@click.option(
    "--limit",
    default=20,
    help="Maximum number of versions to display (default: 20)"
)
def list_versions_cmd(limit: int):
    """
    List all classifier versions.

    Shows all versions in reverse chronological order with status indicators.

    Example:
        agentos version list
        agentos version list --limit 50
    """
    try:
        manager = get_version_manager()
        versions = manager.list_versions(limit=limit)

        if not versions:
            console.print("[yellow]No versions found[/yellow]")
            return

        # Create table
        table = Table(title="Classifier Versions", show_header=True, header_style="bold cyan")
        table.add_column("Version ID", style="cyan")
        table.add_column("Version #", style="white")
        table.add_column("Status", style="white")
        table.add_column("Change Log", style="white", max_width=50)
        table.add_column("Source Proposal", style="white")
        table.add_column("Created By", style="white")
        table.add_column("Created At", style="white")

        for version in versions:
            status = "[green]● ACTIVE[/green]" if version.is_active else "[dim]○ Inactive[/dim]"
            proposal_id = version.source_proposal_id or "-"

            table.add_row(
                version.version_id,
                version.version_number,
                status,
                version.change_log[:47] + "..." if len(version.change_log) > 50 else version.change_log,
                proposal_id,
                version.created_by,
                version.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print(f"\nTotal: {len(versions)} versions")

    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to list versions: {str(e)}")
        logger.error(f"Version list failed: {e}", exc_info=True)


@version_group.command(name="show")
@click.argument("version_id")
def show_version_cmd(version_id: str):
    """
    Show detailed information about a specific version.

    Example:
        agentos version show v2
        agentos version show v2.1
    """
    try:
        manager = get_version_manager()
        version = manager.get_version(version_id)

        if not version:
            console.print(f"[red]Error:[/red] Version {version_id} not found")
            return

        # Display version details
        console.print(f"[bold]Classifier Version: {version.version_id}[/bold]")
        console.print()

        console.print(f"[bold]Basic Information:[/bold]")
        console.print(f"  Version ID: [cyan]{version.version_id}[/cyan]")
        console.print(f"  Version Number: {version.version_number}")
        console.print(f"  Status: {'[green]● ACTIVE[/green]' if version.is_active else '[dim]○ Inactive[/dim]'}")
        console.print(f"  Parent Version: {version.parent_version_id or 'None (root version)'}")
        console.print()

        console.print(f"[bold]Change Information:[/bold]")
        console.print(f"  Change Log: {version.change_log}")
        console.print(f"  Source Proposal: {version.source_proposal_id or 'N/A'}")
        console.print()

        console.print(f"[bold]Creation Information:[/bold]")
        console.print(f"  Created By: {version.created_by}")
        console.print(f"  Created At: {version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print()

        if version.metadata:
            console.print(f"[bold]Metadata:[/bold]")
            for key, value in version.metadata.items():
                console.print(f"  {key}: {value}")

    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to show version: {str(e)}")
        logger.error(f"Version show failed: {e}", exc_info=True)


@version_group.command(name="history")
@click.option(
    "--limit",
    default=20,
    help="Maximum number of rollback records to display (default: 20)"
)
def rollback_history_cmd(limit: int):
    """
    Show rollback history.

    Displays all version rollback operations with reasons and performers.

    Example:
        agentos version history
        agentos version history --limit 50
    """
    try:
        manager = get_version_manager()
        history = manager.get_rollback_history(limit=limit)

        if not history:
            console.print("[green]No rollback history found (no rollbacks performed)[/green]")
            return

        # Create table
        table = Table(title="Rollback History", show_header=True, header_style="bold cyan")
        table.add_column("Rollback ID", style="white")
        table.add_column("From Version", style="red")
        table.add_column("To Version", style="green")
        table.add_column("Reason", style="white", max_width=40)
        table.add_column("Performed By", style="white")
        table.add_column("Performed At", style="white")

        for record in history:
            reason_display = record.reason[:37] + "..." if len(record.reason) > 40 else record.reason

            table.add_row(
                record.rollback_id,
                record.from_version_id,
                record.to_version_id,
                reason_display,
                record.performed_by,
                record.performed_at.strftime("%Y-%m-%d %H:%M:%S"),
            )

        console.print(table)
        console.print(f"\nTotal: {len(history)} rollback operations")

    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to show rollback history: {str(e)}")
        logger.error(f"Rollback history failed: {e}", exc_info=True)


if __name__ == "__main__":
    version_group()
