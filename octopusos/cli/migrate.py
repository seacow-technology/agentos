"""Database migration CLI commands."""

import click
from typing import Optional
from pathlib import Path

from rich.console import Console

from agentos.store.migrations import (
    migrate as run_migrate, 
    get_current_version,
    get_latest_version,
)
from agentos.store import get_db_path

console = Console()


@click.command()
@click.option(
    "--to",
    default=None,
    help="Target version to migrate to (defaults to latest available)",
)
@click.option(
    "--db-path",
    type=click.Path(),
    default=None,
    help="Database path (defaults to AgentOS store path)",
)
def migrate(to: Optional[str], db_path: Optional[str]):
    """Migrate database schema to target version.
    
    Examples:
        agentos migrate              # Migrate to latest version
        agentos migrate --to 0.8.0   # Migrate to specific version
    """
    if db_path is None:
        db_path = get_db_path()
    else:
        db_path = Path(db_path)

    # Get latest version from filesystem if not specified
    if to is None:
        migrations_dir = Path(__file__).parent.parent / "store" / "migrations"
        to = get_latest_version(migrations_dir)
        if to is None:
            console.print("[red]✗ 无法确定最新版本：未找到迁移文件[/red]")
            raise click.Abort()

    # Get current version
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    current = get_current_version(conn)
    conn.close()

    # Print migration info
    console.print(f"""
╔══════════════════════════════════════════════════════════════════
║ 数据库迁移
╠══════════════════════════════════════════════════════════════════
║ 数据库: {db_path.name}
║ 当前版本: v{current}
║ 目标版本: v{to}
╚══════════════════════════════════════════════════════════════════
""")

    if current == to:
        console.print("[green]✅ 已经是目标版本，无需迁移[/green]")
        return

    try:
        run_migrate(db_path, target_version=to)
        console.print(f"[green]✅ 迁移到 v{to} 成功完成[/green]")
    except Exception as e:
        console.print(f"[red]✗ 迁移失败: {e}[/red]")
        raise click.Abort()
