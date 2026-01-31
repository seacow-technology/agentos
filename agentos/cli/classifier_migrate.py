"""
Classifier Migration CLI - Shadow → Active Promotion

Commands for migrating validated shadow classifiers to active status:
- agentos classifier migrate --shadow v2-shadow-a --to-active
- agentos classifier migrate --dry-run --shadow v2-shadow-a
- agentos classifier migrate --verify --shadow v2-shadow-a
- agentos classifier migrate --rollback

This is the final step in the Shadow Evaluation + Controlled Adaptation system,
enabling safe promotion of proven shadow classifiers to production.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, TypeVar, Awaitable

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentos.config.loader import load_shadow_config, save_shadow_config
from agentos.core.brain.classifier_version_manager import get_version_manager
from agentos.core.brain.improvement_proposal_store import get_store
from agentos.core.chat.shadow_registry import get_shadow_registry
from agentos.core.chat.decision_comparator import DecisionComparator
from agentos.core.db import registry_db
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)
console = Console()

T = TypeVar('T')


def run_async(coro: Awaitable[T]) -> T:
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(coro)


class MigrationPrerequisites:
    """Validation results for migration prerequisites."""

    def __init__(
        self,
        shadow_version: str,
        proposal_id: Optional[str] = None,
        samples: int = 0,
        improvement_rate: float = 0.0,
        risk_level: str = "HIGH",
        proposal_status: Optional[str] = None,
    ):
        self.shadow_version = shadow_version
        self.proposal_id = proposal_id
        self.samples = samples
        self.improvement_rate = improvement_rate
        self.risk_level = risk_level
        self.proposal_status = proposal_status

        # Validation thresholds
        self.MIN_SAMPLES = 100
        self.MIN_IMPROVEMENT_RATE = 0.15  # 15%
        self.REQUIRED_RISK_LEVEL = "LOW"
        self.REQUIRED_PROPOSAL_STATUS = "accepted"

    def is_valid(self) -> bool:
        """Check if all prerequisites are met."""
        return (
            self.has_sufficient_samples() and
            self.has_sufficient_improvement() and
            self.has_low_risk() and
            self.has_approved_proposal()
        )

    def has_sufficient_samples(self) -> bool:
        """Check if sample count meets threshold."""
        return self.samples >= self.MIN_SAMPLES

    def has_sufficient_improvement(self) -> bool:
        """Check if improvement rate meets threshold."""
        return self.improvement_rate >= self.MIN_IMPROVEMENT_RATE

    def has_low_risk(self) -> bool:
        """Check if risk level is acceptable."""
        return self.risk_level == self.REQUIRED_RISK_LEVEL

    def has_approved_proposal(self) -> bool:
        """Check if proposal is accepted."""
        return (
            self.proposal_id is not None and
            self.proposal_status == self.REQUIRED_PROPOSAL_STATUS
        )

    def get_validation_report(self) -> Dict[str, Any]:
        """Get detailed validation report."""
        return {
            "shadow_version": self.shadow_version,
            "prerequisites": {
                "samples": {
                    "current": self.samples,
                    "required": self.MIN_SAMPLES,
                    "passed": self.has_sufficient_samples(),
                },
                "improvement_rate": {
                    "current": f"{self.improvement_rate:.1%}",
                    "required": f"{self.MIN_IMPROVEMENT_RATE:.1%}",
                    "passed": self.has_sufficient_improvement(),
                },
                "risk_level": {
                    "current": self.risk_level,
                    "required": self.REQUIRED_RISK_LEVEL,
                    "passed": self.has_low_risk(),
                },
                "proposal": {
                    "proposal_id": self.proposal_id,
                    "status": self.proposal_status,
                    "required_status": self.REQUIRED_PROPOSAL_STATUS,
                    "passed": self.has_approved_proposal(),
                },
            },
            "overall_status": "PASSED" if self.is_valid() else "FAILED",
        }


class MigrationState:
    """State snapshot for migration rollback."""

    def __init__(
        self,
        active_version: str,
        shadow_version: str,
        config_backup: Dict[str, Any],
        timestamp: datetime,
    ):
        self.active_version = active_version
        self.shadow_version = shadow_version
        self.config_backup = config_backup
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "active_version": self.active_version,
            "shadow_version": self.shadow_version,
            "config_backup": self.config_backup,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationState":
        """Deserialize from dictionary."""
        return cls(
            active_version=data["active_version"],
            shadow_version=data["shadow_version"],
            config_backup=data["config_backup"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class ClassifierMigrationManager:
    """Manages safe migration of shadow classifiers to active status."""

    def __init__(self):
        self.version_manager = get_version_manager()
        self.proposal_store = get_store()
        self.shadow_registry = get_shadow_registry()
        self.comparator = DecisionComparator()

    async def verify_prerequisites(
        self, shadow_version: str
    ) -> MigrationPrerequisites:
        """
        Verify migration prerequisites for a shadow classifier.

        Args:
            shadow_version: Shadow classifier version ID (e.g., "v2-shadow-a")

        Returns:
            MigrationPrerequisites with validation results
        """
        # Get active version
        active_version_info = self.version_manager.get_active_version()
        if not active_version_info:
            raise ValueError("No active classifier version found")

        active_version = active_version_info.version_id

        # Get comparison metrics
        comparison = self.comparator.compare_versions(
            active_version=active_version,
            shadow_version=shadow_version,
        )

        samples = comparison["comparison"]["sample_count"]
        improvement_rate = comparison["comparison"].get("improvement_rate", 0.0)

        # Find associated proposal
        proposals = await self.proposal_store.list_proposals(
            shadow_version_id=shadow_version,
            status="accepted",
            limit=10,
        )

        proposal_id = None
        proposal_status = None
        risk_level = "HIGH"

        if proposals:
            # Use the most recent accepted proposal
            proposal = proposals[0]
            proposal_id = proposal.proposal_id
            proposal_status = proposal.status.value
            risk_level = proposal.evidence.risk.value

            # Use proposal evidence if available
            if proposal.evidence.samples > samples:
                samples = proposal.evidence.samples
            if proposal.evidence.improvement_rate > improvement_rate:
                improvement_rate = proposal.evidence.improvement_rate

        return MigrationPrerequisites(
            shadow_version=shadow_version,
            proposal_id=proposal_id,
            samples=samples,
            improvement_rate=improvement_rate,
            risk_level=risk_level,
            proposal_status=proposal_status,
        )

    async def migrate_to_active(
        self,
        shadow_version: str,
        user: str = "admin",
        skip_verification: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Migrate shadow classifier to active status.

        This performs the following steps:
        1. Verify prerequisites (unless skip_verification=True)
        2. Create migration state backup
        3. Create new version from approved proposal
        4. Update shadow registry configuration
        5. Rotate roles: active → shadow, shadow → active
        6. Create new shadow for ongoing validation

        Args:
            shadow_version: Shadow version to promote (e.g., "v2-shadow-a")
            user: User performing migration
            skip_verification: Skip prerequisite verification
            dry_run: Simulate migration without making changes

        Returns:
            Migration result dictionary

        Raises:
            ValueError: If prerequisites not met or validation fails
        """
        # Step 1: Verify prerequisites
        if not skip_verification:
            prereqs = await self.verify_prerequisites(shadow_version)
            if not prereqs.is_valid():
                raise ValueError(
                    f"Migration prerequisites not met for {shadow_version}. "
                    f"Run 'agentos classifier migrate --verify --shadow {shadow_version}' "
                    f"for details."
                )
        else:
            # Still need to get proposal for version creation
            proposals = await self.proposal_store.list_proposals(
                shadow_version_id=shadow_version,
                status="accepted",
                limit=1,
            )
            if not proposals:
                raise ValueError(
                    f"No accepted proposal found for {shadow_version}. "
                    f"A proposal is required for migration."
                )
            prereqs = await self.verify_prerequisites(shadow_version)

        proposal_id = prereqs.proposal_id
        if not proposal_id:
            raise ValueError(f"No proposal ID found for {shadow_version}")

        proposal = await self.proposal_store.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # Get current active version
        current_active = self.version_manager.get_active_version()
        if not current_active:
            raise ValueError("No active version found")

        # Step 2: Create migration state backup
        config_backup = load_shadow_config()
        migration_state = MigrationState(
            active_version=current_active.version_id,
            shadow_version=shadow_version,
            config_backup=config_backup,
            timestamp=utc_now(),
        )

        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
            return {
                "status": "dry_run",
                "migration_state": migration_state.to_dict(),
                "new_version": f"{current_active.version_id} → (simulated promotion)",
                "changes": [
                    f"Would promote version using proposal {proposal_id}",
                    f"Would update shadow registry configuration",
                    f"Would rotate: {current_active.version_id} → shadow, {shadow_version} → active",
                    f"Would create new shadow for validation",
                ],
            }

        # Step 3: Save migration state for rollback
        self._save_migration_state(migration_state)

        # Step 4: Create new version from proposal
        new_version = self.version_manager.promote_version(
            proposal_id=proposal_id,
            change_log=proposal.description,
            created_by=user,
            is_major=False,  # Shadow promotions are typically minor versions
            metadata={
                "promoted_from_shadow": shadow_version,
                "migration_user": user,
                "improvement_rate": proposal.evidence.improvement_rate,
                "risk_level": proposal.evidence.risk.value,
                "samples": proposal.evidence.samples,
            }
        )

        # Mark proposal as implemented
        await self.proposal_store.mark_implemented(proposal_id)

        # Step 5: Update shadow registry configuration
        config = load_shadow_config()

        # Remove promoted shadow from active_versions
        active_versions = config["shadow_classifiers"]["active_versions"]
        if shadow_version in active_versions:
            active_versions.remove(shadow_version)

        # Add former active as shadow for comparison (optional)
        # This allows validating that the new active is still performing well
        new_shadow_id = f"{current_active.version_id}-shadow-validation"
        if new_shadow_id not in active_versions:
            active_versions.append(new_shadow_id)

        # Add version configuration for validation shadow
        if new_shadow_id not in config["shadow_classifiers"]["versions"]:
            config["shadow_classifiers"]["versions"][new_shadow_id] = {
                "enabled": True,
                "priority": 10,  # High priority for validation
                "description": f"Validation shadow from previous active {current_active.version_id}",
                "risk_level": "low",
            }

        # Update promoted shadow's config to mark it as promoted
        if shadow_version in config["shadow_classifiers"]["versions"]:
            config["shadow_classifiers"]["versions"][shadow_version]["enabled"] = False
            config["shadow_classifiers"]["versions"][shadow_version]["promoted_at"] = utc_now_iso()
            config["shadow_classifiers"]["versions"][shadow_version]["promoted_to"] = new_version.version_id

        save_shadow_config(config)

        # Step 6: Update shadow registry (deactivate promoted shadow)
        if self.shadow_registry.is_active(shadow_version):
            self.shadow_registry.deactivate(shadow_version)

        logger.info(
            f"Migration completed: {shadow_version} → {new_version.version_id} "
            f"(proposal: {proposal_id}, user: {user})"
        )

        return {
            "status": "success",
            "migration_state": migration_state.to_dict(),
            "old_active_version": current_active.version_id,
            "new_active_version": new_version.version_id,
            "promoted_shadow": shadow_version,
            "proposal_id": proposal_id,
            "new_validation_shadow": new_shadow_id,
            "timestamp": utc_now_iso(),
        }

    def _save_migration_state(self, state: MigrationState) -> None:
        """Save migration state for rollback."""
        sql = """
        INSERT INTO classifier_migration_history (
            migration_id, active_version, shadow_version,
            config_backup, timestamp
        ) VALUES (?, ?, ?, ?, ?)
        """

        migration_id = f"migration-{state.timestamp.strftime('%Y%m%d-%H%M%S')}"

        with registry_db.transaction() as conn:
            # Ensure table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classifier_migration_history (
                    migration_id TEXT PRIMARY KEY,
                    active_version TEXT NOT NULL,
                    shadow_version TEXT NOT NULL,
                    config_backup TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            conn.execute(
                sql,
                (
                    migration_id,
                    state.active_version,
                    state.shadow_version,
                    json.dumps(state.config_backup),
                    state.timestamp.isoformat(),
                )
            )

        logger.info(f"Saved migration state: {migration_id}")

    def get_latest_migration_state(self) -> Optional[MigrationState]:
        """Get the most recent migration state for rollback."""
        sql = """
        SELECT active_version, shadow_version, config_backup, timestamp
        FROM classifier_migration_history
        ORDER BY timestamp DESC
        LIMIT 1
        """

        row = registry_db.query_one(sql)
        if not row:
            return None

        return MigrationState(
            active_version=row["active_version"],
            shadow_version=row["shadow_version"],
            config_backup=json.loads(row["config_backup"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    async def rollback_migration(
        self, user: str = "admin", reason: str = "Manual rollback"
    ) -> Dict[str, Any]:
        """
        Rollback the most recent migration.

        Args:
            user: User performing rollback
            reason: Reason for rollback

        Returns:
            Rollback result dictionary

        Raises:
            ValueError: If no migration history found
        """
        # Get latest migration state
        migration_state = self.get_latest_migration_state()
        if not migration_state:
            raise ValueError("No migration history found. Nothing to rollback.")

        # Rollback version
        restored = self.version_manager.rollback_version(
            to_version_id=migration_state.active_version,
            reason=reason,
            performed_by=user,
        )

        # Restore shadow registry configuration
        save_shadow_config(migration_state.config_backup)

        logger.warning(
            f"Migration rolled back: {restored.version_id} "
            f"(reason: {reason}, user: {user})"
        )

        return {
            "status": "rollback_complete",
            "restored_version": restored.version_id,
            "migration_timestamp": migration_state.timestamp.isoformat(),
            "rollback_timestamp": utc_now_iso(),
            "user": user,
            "reason": reason,
        }


# ============================================================================
# CLI Commands
# ============================================================================

@click.group(name="classifier")
def classifier_group():
    """Classifier management commands"""
    pass


@classifier_group.group(name="migrate")
def migrate_group():
    """Shadow classifier migration commands"""
    pass


@migrate_group.command(name="to-active")
@click.option(
    "--shadow",
    required=True,
    help="Shadow classifier version to promote (e.g., v2-shadow-a)"
)
@click.option(
    "--user",
    default="admin",
    help="User performing migration (default: admin)"
)
@click.option(
    "--skip-verification",
    is_flag=True,
    help="Skip prerequisite verification (dangerous!)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate migration without making changes"
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt"
)
def migrate_to_active_cmd(
    shadow: str, user: str, skip_verification: bool, dry_run: bool, yes: bool
):
    """
    Migrate a shadow classifier to active status.

    This command promotes a validated shadow classifier to production.
    The migration includes:
    - Version promotion (creates new active version)
    - Shadow registry configuration update
    - Role rotation (active → shadow, shadow → active)
    - Creation of new validation shadow

    Examples:
        # Standard migration with verification
        agentos classifier migrate to-active --shadow v2-shadow-a

        # Dry run to preview changes
        agentos classifier migrate to-active --shadow v2-shadow-a --dry-run

        # Skip verification (not recommended)
        agentos classifier migrate to-active --shadow v2-shadow-a --skip-verification
    """
    try:
        manager = ClassifierMigrationManager()

        # Verify prerequisites first (even in dry-run)
        console.print(f"[bold]Verifying prerequisites for {shadow}...[/bold]")
        prereqs = run_async(manager.verify_prerequisites(shadow))

        # Display validation report
        report = prereqs.get_validation_report()
        _display_prerequisite_report(report)

        if not prereqs.is_valid() and not skip_verification:
            console.print("\n[red]✗ Prerequisites not met. Migration aborted.[/red]")
            console.print("\nUse --skip-verification to bypass checks (not recommended)")
            return

        # Confirmation prompt
        if not yes and not dry_run:
            console.print("\n[bold yellow]⚠ Confirm Migration[/bold yellow]")
            console.print(f"  Shadow version: [cyan]{shadow}[/cyan]")
            console.print(f"  Proposal: [cyan]{prereqs.proposal_id}[/cyan]")
            console.print(f"  Improvement: [cyan]{prereqs.improvement_rate:+.1%}[/cyan]")
            console.print(f"  Samples: [cyan]{prereqs.samples}[/cyan]")
            console.print()

            confirm = click.confirm("Do you want to proceed with migration?")
            if not confirm:
                console.print("[yellow]Migration cancelled[/yellow]")
                return

        # Perform migration
        console.print(f"\n[bold]{'Simulating' if dry_run else 'Performing'} migration...[/bold]")

        result = run_async(manager.migrate_to_active(
            shadow_version=shadow,
            user=user,
            skip_verification=skip_verification,
            dry_run=dry_run,
        ))

        # Display result
        if dry_run:
            console.print(Panel(
                "\n".join(result["changes"]),
                title="[bold]Dry Run - Planned Changes[/bold]",
                border_style="yellow"
            ))
        else:
            console.print(f"\n[green]✓ Migration completed successfully[/green]")
            console.print()
            console.print(f"[bold]Migration Summary:[/bold]")
            console.print(f"  Previous active: [cyan]{result['old_active_version']}[/cyan]")
            console.print(f"  New active: [bold cyan]{result['new_active_version']}[/bold cyan]")
            console.print(f"  Promoted shadow: [cyan]{result['promoted_shadow']}[/cyan]")
            console.print(f"  Proposal: [cyan]{result['proposal_id']}[/cyan]")
            console.print(f"  New validation shadow: [cyan]{result['new_validation_shadow']}[/cyan]")
            console.print()
            console.print("[yellow]Note:[/yellow] Use 'agentos classifier migrate rollback' if issues arise")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Migration failed: {str(e)}")
        logger.error(f"Migration failed: {e}", exc_info=True)


@migrate_group.command(name="verify")
@click.option(
    "--shadow",
    required=True,
    help="Shadow classifier version to verify"
)
def verify_prerequisites_cmd(shadow: str):
    """
    Verify migration prerequisites for a shadow classifier.

    Checks:
    - Sample count >= 100
    - Improvement rate >= 15%
    - Risk level = LOW
    - Approved ImprovementProposal exists

    Example:
        agentos classifier migrate verify --shadow v2-shadow-a
    """
    try:
        manager = ClassifierMigrationManager()

        console.print(f"[bold]Verifying migration prerequisites for {shadow}...[/bold]\n")

        prereqs = run_async(manager.verify_prerequisites(shadow))
        report = prereqs.get_validation_report()

        _display_prerequisite_report(report)

        if prereqs.is_valid():
            console.print("\n[green]✓ All prerequisites met. Ready for migration.[/green]")
        else:
            console.print("\n[red]✗ Some prerequisites not met.[/red]")
            console.print("Address the issues above before attempting migration.")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        logger.error(f"Verification failed: {e}", exc_info=True)


@migrate_group.command(name="rollback")
@click.option(
    "--reason",
    default="Manual rollback",
    help="Reason for rollback"
)
@click.option(
    "--user",
    default="admin",
    help="User performing rollback"
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt"
)
def rollback_migration_cmd(reason: str, user: str, yes: bool):
    """
    Rollback the most recent classifier migration.

    This command:
    - Restores the previous active version
    - Restores shadow registry configuration
    - Records rollback in audit history

    Example:
        agentos classifier migrate rollback --reason "Performance regression detected"
    """
    try:
        manager = ClassifierMigrationManager()

        # Get latest migration state
        migration_state = manager.get_latest_migration_state()
        if not migration_state:
            console.print("[yellow]No migration history found. Nothing to rollback.[/yellow]")
            return

        # Confirmation prompt
        if not yes:
            console.print("[bold yellow]⚠ Confirm Rollback[/bold yellow]")
            console.print(f"  Will restore version: [cyan]{migration_state.active_version}[/cyan]")
            console.print(f"  Migration date: [cyan]{migration_state.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/cyan]")
            console.print(f"  Reason: {reason}")
            console.print()

            confirm = click.confirm("Do you want to proceed with rollback?")
            if not confirm:
                console.print("[yellow]Rollback cancelled[/yellow]")
                return

        console.print("[bold]Performing rollback...[/bold]")

        result = run_async(manager.rollback_migration(
            user=user,
            reason=reason,
        ))

        console.print(f"\n[green]✓ Rollback completed successfully[/green]")
        console.print()
        console.print(f"[bold]Rollback Summary:[/bold]")
        console.print(f"  Restored version: [cyan]{result['restored_version']}[/cyan]")
        console.print(f"  Original migration: [cyan]{result['migration_timestamp']}[/cyan]")
        console.print(f"  Rollback time: [cyan]{result['rollback_timestamp']}[/cyan]")
        console.print(f"  Reason: {result['reason']}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Rollback failed: {str(e)}")
        logger.error(f"Rollback failed: {e}", exc_info=True)


def _display_prerequisite_report(report: Dict[str, Any]) -> None:
    """Display prerequisite validation report as a rich table."""
    table = Table(title="Migration Prerequisites", show_header=True, header_style="bold cyan")
    table.add_column("Prerequisite", style="white")
    table.add_column("Current", style="white")
    table.add_column("Required", style="white")
    table.add_column("Status", style="white")

    prereqs = report["prerequisites"]

    # Samples
    samples = prereqs["samples"]
    table.add_row(
        "Sample Count",
        str(samples["current"]),
        f">= {samples['required']}",
        "[green]✓ PASS[/green]" if samples["passed"] else "[red]✗ FAIL[/red]"
    )

    # Improvement rate
    improvement = prereqs["improvement_rate"]
    table.add_row(
        "Improvement Rate",
        improvement["current"],
        f">= {improvement['required']}",
        "[green]✓ PASS[/green]" if improvement["passed"] else "[red]✗ FAIL[/red]"
    )

    # Risk level
    risk = prereqs["risk_level"]
    table.add_row(
        "Risk Level",
        risk["current"],
        risk["required"],
        "[green]✓ PASS[/green]" if risk["passed"] else "[red]✗ FAIL[/red]"
    )

    # Proposal
    proposal = prereqs["proposal"]
    proposal_status = f"{proposal['proposal_id']} ({proposal['status']})" if proposal['proposal_id'] else "None"
    table.add_row(
        "Approved Proposal",
        proposal_status,
        f"Status = {proposal['required_status']}",
        "[green]✓ PASS[/green]" if proposal["passed"] else "[red]✗ FAIL[/red]"
    )

    console.print(table)

    # Overall status
    overall_status = report["overall_status"]
    if overall_status == "PASSED":
        console.print(f"\n[bold green]Overall Status: {overall_status}[/bold green]")
    else:
        console.print(f"\n[bold red]Overall Status: {overall_status}[/bold red]")


if __name__ == "__main__":
    classifier_group()
