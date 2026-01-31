"""
CLI Inspection Commands - Read-only observability

Provides CLI commands for task inspection and governance trace viewing.
Enables headless/CI/SSH environment diagnostics without WebUI dependency.

PR-0131-2026-4: CLI Read-only Parity (v0.7 → Web+CLI 等价观测)
"""

import click
import sqlite3
import json
from pathlib import Path
from typing import Optional
import sys


@click.group(name="task")
def task_group():
    """Task inspection commands"""
    pass


@click.group(name="governance")
def governance_group():
    """Governance and decision trace commands"""
    pass


@task_group.command(name="inspect")
@click.argument("task_id")
@click.option("--db", help="Database path (default: use settings)")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def task_inspect(task_id: str, db: Optional[str], format: str):
    """
    Inspect task status, risk, and execution details

    Pure read-only operation, no admin token required.

    Example:
        agentos task inspect task_abc123
        agentos task inspect task_abc123 --format json
    """
    db_path = _resolve_db_path(db)
    if not db_path.exists():
        click.echo(f"❌ Database not found: {db_path}", err=True)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get task info
        cursor.execute(
            "SELECT task_id, title, status, risk_level, created_at, updated_at FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        task_row = cursor.fetchone()

        if not task_row:
            click.echo(f"❌ Task not found: {task_id}", err=True)
            sys.exit(1)

        task = dict(task_row)

        # Get latest decision
        cursor.execute(
            """
            SELECT event_type, payload, created_at
            FROM task_audits
            WHERE task_id = ? AND event_type LIKE 'SUPERVISOR_%'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,)
        )
        decision_row = cursor.fetchone()
        latest_decision = dict(decision_row) if decision_row else None

        # Get token usage summary (if available)
        cursor.execute(
            """
            SELECT payload
            FROM task_audits
            WHERE task_id = ? AND event_type = 'TOKEN_USAGE'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,)
        )
        token_row = cursor.fetchone()
        token_summary = None
        if token_row:
            try:
                token_summary = json.loads(token_row["payload"]).get("cumulative_usage")
            except (json.JSONDecodeError, KeyError):
                pass

        # Format output
        if format == "json":
            output = {
                "task": task,
                "latest_decision": latest_decision,
                "token_summary": token_summary
            }
            click.echo(json.dumps(output, indent=2))
        else:
            # Text format
            click.echo(f"\n📋 Task Inspection: {task_id}")
            click.echo(f"{'='*60}")
            click.echo(f"Title:        {task['title']}")
            click.echo(f"Status:       {task['status']}")
            click.echo(f"Risk Level:   {task.get('risk_level', 'N/A')}")
            click.echo(f"Created:      {task['created_at']}")
            click.echo(f"Updated:      {task['updated_at']}")

            if latest_decision:
                click.echo(f"\n🎯 Latest Decision:")
                click.echo(f"  Type:       {latest_decision['event_type']}")
                click.echo(f"  Timestamp:  {latest_decision['created_at']}")

            if token_summary:
                click.echo(f"\n💰 Token Usage:")
                click.echo(f"  Total:      {token_summary.get('total_tokens', 0)}")
                click.echo(f"  Prompt:     {token_summary.get('prompt_tokens', 0)}")
                click.echo(f"  Completion: {token_summary.get('completion_tokens', 0)}")

            click.echo(f"{'='*60}\n")

    finally:
        conn.close()


@governance_group.command(name="trace")
@click.argument("task_id")
@click.option("--db", help="Database path (default: use settings)")
@click.option("--limit", default=20, help="Number of events to show")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def governance_trace(task_id: str, db: Optional[str], limit: int, format: str):
    """
    Show governance decision trace for a task

    Pure read-only operation, no admin token required.

    Example:
        agentos governance trace task_abc123
        agentos governance trace task_abc123 --limit 50 --format json
    """
    db_path = _resolve_db_path(db)
    if not db_path.exists():
        click.echo(f"❌ Database not found: {db_path}", err=True)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get decision trace
        cursor.execute(
            """
            SELECT audit_id, event_type, level, payload, created_at
            FROM task_audits
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (task_id, limit)
        )
        trace_rows = cursor.fetchall()

        if not trace_rows:
            click.echo(f"⚠️  No trace events found for task: {task_id}", err=True)
            sys.exit(0)

        trace_items = [dict(row) for row in trace_rows]

        # Format output
        if format == "json":
            click.echo(json.dumps({"task_id": task_id, "trace": trace_items}, indent=2))
        else:
            # Text format
            click.echo(f"\n🔍 Governance Trace: {task_id}")
            click.echo(f"{'='*60}")
            click.echo(f"Showing {len(trace_items)} most recent events\n")

            for item in reversed(trace_items):
                timestamp = item['created_at'][:19] if item['created_at'] else "N/A"
                level = item['level'].upper()
                event_type = item['event_type']

                # Color coding
                if level == "ERROR":
                    level_display = click.style(level, fg="red")
                elif level == "WARN":
                    level_display = click.style(level, fg="yellow")
                else:
                    level_display = click.style(level, fg="green")

                click.echo(f"[{timestamp}] {level_display} {event_type}")

                # Show payload summary if present
                if item['payload']:
                    try:
                        payload = json.loads(item['payload']) if isinstance(item['payload'], str) else item['payload']
                        if 'reason' in payload:
                            click.echo(f"  └─ Reason: {payload['reason']}")
                        if 'decision_type' in payload:
                            click.echo(f"  └─ Decision: {payload['decision_type']}")
                    except (json.JSONDecodeError, TypeError):
                        pass

                click.echo()

            click.echo(f"{'='*60}\n")

    finally:
        conn.close()


def _resolve_db_path(db_arg: Optional[str]) -> Path:
    """
    Resolve database path from argument or settings

    Args:
        db_arg: Optional explicit database path

    Returns:
        Path to database file
    """
    if db_arg:
        return Path(db_arg)

    # Try to load from settings
    try:
        from agentos.config import load_settings
        settings = load_settings()
        if hasattr(settings, 'db_path'):
            return Path(settings.db_path)
    except Exception:
        pass

    # Default fallback: use component_db_path
    from agentos.core.storage.paths import component_db_path
    return component_db_path("agentos")
