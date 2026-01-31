"""Database maintenance CLI commands.

Commands:
- cleanup-orphans: Remove orphan task records
- cleanup-sessions: Remove stale chat sessions
- db-stats: Show database statistics
- vacuum: Optimize database file
"""

import click
import logging
from tabulate import tabulate

from agentos.core.maintenance import DatabaseCleaner

logger = logging.getLogger(__name__)


@click.group()
def maintenance():
    """Database maintenance and cleanup commands."""
    pass


@maintenance.command("cleanup-orphans")
@click.option(
    "--days",
    default=30,
    type=int,
    help="Delete orphan tasks older than N days (default: 30)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
def cleanup_orphans(days: int, dry_run: bool):
    """Clean up orphan task records (tasks with NULL session_id).

    Orphan tasks are tasks that are not associated with any chat session.
    This command removes old orphan tasks in terminal states (completed,
    cancelled, failed) to keep the database clean.

    Examples:
        # Dry run to see what would be deleted
        agentos maintenance cleanup-orphans --dry-run

        # Delete orphan tasks older than 30 days
        agentos maintenance cleanup-orphans

        # Delete orphan tasks older than 60 days
        agentos maintenance cleanup-orphans --days 60
    """
    cleaner = DatabaseCleaner()

    click.echo(f"Cleaning up orphan tasks older than {days} days...")

    try:
        result = cleaner.cleanup_orphan_tasks(days_old=days, dry_run=dry_run)

        if dry_run:
            click.echo(f"\n[DRY RUN] Would delete: {result['candidate_count']} tasks")
        else:
            click.echo(f"\n✓ Deleted: {result['deleted_count']} orphan tasks")

        click.echo(f"Cutoff date: {result['cutoff_date']}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@maintenance.command("cleanup-sessions")
@click.option(
    "--days",
    default=90,
    type=int,
    help="Delete sessions inactive for N days (default: 90)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
def cleanup_sessions(days: int, dry_run: bool):
    """Clean up stale chat sessions.

    This command removes chat sessions that have had no activity for
    a specified number of days.

    Examples:
        # Dry run
        agentos maintenance cleanup-sessions --dry-run

        # Delete sessions inactive for 90+ days
        agentos maintenance cleanup-sessions

        # Delete sessions inactive for 180+ days
        agentos maintenance cleanup-sessions --days 180
    """
    cleaner = DatabaseCleaner()

    click.echo(f"Cleaning up sessions inactive for {days}+ days...")

    try:
        result = cleaner.cleanup_stale_sessions(days_inactive=days, dry_run=dry_run)

        if dry_run:
            click.echo(f"\n[DRY RUN] Would delete: {result['candidate_count']} sessions")
        else:
            click.echo(f"\n✓ Deleted: {result['deleted_count']} sessions")

        click.echo(f"Cutoff date: {result['cutoff_date']}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@maintenance.command("stats")
def db_stats():
    """Show database statistics and health information.

    Displays:
    - Row counts for main tables
    - Orphan task counts
    - Stale session counts
    - Database file size
    """
    cleaner = DatabaseCleaner()

    click.echo("Database Statistics:\n")

    try:
        stats = cleaner.get_database_stats()

        # Table counts
        click.echo("Table Row Counts:")
        table_data = []
        for table, count in stats['table_counts'].items():
            count_str = str(count) if count is not None else "N/A"
            table_data.append([table, count_str])

        click.echo(tabulate(table_data, headers=["Table", "Rows"], tablefmt="simple"))

        # Orphan statistics
        click.echo(f"\nOrphan Tasks:")
        click.echo(f"  Total with NULL session_id: {stats['orphan_tasks']}")
        click.echo(f"  Old orphans (>30 days, terminal): {stats['old_orphans']}")

        # Session statistics
        click.echo(f"\nStale Sessions:")
        click.echo(f"  Inactive >90 days: {stats['stale_sessions']}")

        # Database size
        if stats['database_size_mb'] is not None:
            click.echo(f"\nDatabase Size: {stats['database_size_mb']} MB")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@maintenance.command("vacuum")
def vacuum():
    """Optimize database and reclaim disk space.

    Runs VACUUM command to rebuild the database file, repacking it
    into minimal disk space. This is useful after large deletions.

    Warning: This requires exclusive database access and may take
    time on large databases.
    """
    cleaner = DatabaseCleaner()

    click.echo("Running VACUUM to optimize database...")
    click.echo("This may take a few moments...\n")

    try:
        result = cleaner.vacuum_database()

        click.echo("✓ VACUUM completed")
        click.echo(f"\nSize before:  {result['size_before_mb']} MB")
        click.echo(f"Size after:   {result['size_after_mb']} MB")
        click.echo(f"Space freed:  {result['space_reclaimed_mb']} MB")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@maintenance.command("full-cleanup")
@click.option(
    "--orphan-days",
    default=30,
    type=int,
    help="Orphan task age threshold (default: 30)",
)
@click.option(
    "--session-days",
    default=90,
    type=int,
    help="Session inactivity threshold (default: 90)",
)
@click.option(
    "--vacuum",
    is_flag=True,
    help="Run VACUUM after cleanup",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
def full_cleanup(orphan_days: int, session_days: int, vacuum: bool, dry_run: bool):
    """Run full database cleanup and maintenance.

    This command performs:
    1. Orphan task cleanup
    2. Stale session cleanup
    3. VACUUM (optional)

    Examples:
        # Dry run
        agentos maintenance full-cleanup --dry-run

        # Full cleanup with vacuum
        agentos maintenance full-cleanup --vacuum

        # Custom thresholds
        agentos maintenance full-cleanup --orphan-days 60 --session-days 180
    """
    cleaner = DatabaseCleaner()

    click.echo("=== Full Database Cleanup ===\n")

    # Step 1: Cleanup orphans
    click.echo(f"1. Cleaning up orphan tasks (>{orphan_days} days)...")
    try:
        orphan_result = cleaner.cleanup_orphan_tasks(days_old=orphan_days, dry_run=dry_run)
        if dry_run:
            click.echo(f"   [DRY RUN] Would delete: {orphan_result['candidate_count']} tasks")
        else:
            click.echo(f"   ✓ Deleted: {orphan_result['deleted_count']} tasks")
    except Exception as e:
        click.echo(f"   ✗ Error: {e}", err=True)

    # Step 2: Cleanup sessions
    click.echo(f"\n2. Cleaning up stale sessions (>{session_days} days)...")
    try:
        session_result = cleaner.cleanup_stale_sessions(days_inactive=session_days, dry_run=dry_run)
        if dry_run:
            click.echo(f"   [DRY RUN] Would delete: {session_result['candidate_count']} sessions")
        else:
            click.echo(f"   ✓ Deleted: {session_result['deleted_count']} sessions")
    except Exception as e:
        click.echo(f"   ✗ Error: {e}", err=True)

    # Step 3: VACUUM (if requested and not dry run)
    if vacuum and not dry_run:
        click.echo("\n3. Running VACUUM...")
        try:
            vacuum_result = cleaner.vacuum_database()
            click.echo(f"   ✓ Reclaimed: {vacuum_result['space_reclaimed_mb']} MB")
        except Exception as e:
            click.echo(f"   ✗ Error: {e}", err=True)
    elif vacuum and dry_run:
        click.echo("\n3. VACUUM (skipped in dry run)")

    click.echo("\n=== Cleanup Complete ===")


if __name__ == "__main__":
    maintenance()
