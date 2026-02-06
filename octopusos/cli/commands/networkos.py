"""NetworkOS CLI Commands"""

import click
import json
from agentos.networkos.service import NetworkOSService


def _format_table(headers, rows):
    """Simple table formatter (fallback if tabulate not available)"""
    try:
        from tabulate import tabulate
        return tabulate(rows, headers=headers, tablefmt="simple")
    except ImportError:
        # Fallback to simple formatting
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Header
        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        separator = "-+-".join("-" * w for w in col_widths)

        # Rows
        lines = [header_line, separator]
        for row in rows:
            line = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            lines.append(line)

        return "\n".join(lines)


@click.group()
def networkos():
    """NetworkOS tunnel management"""
    pass


@networkos.command()
@click.option('--provider', default='cloudflare', help='Tunnel provider (cloudflare, ngrok, etc.)')
@click.option('--name', required=True, help='Tunnel name')
@click.option('--hostname', required=True, help='Public hostname')
@click.option('--target', default='http://127.0.0.1:8000', help='Local target (e.g., http://127.0.0.1:8000)')
@click.option('--token', required=True, help='Provider token')
@click.option('--mode', default='http', help='Tunnel mode (http, tcp, https)')
def create(provider, name, hostname, target, token, mode):
    """Create a new tunnel"""
    try:
        service = NetworkOSService()
        tunnel_id = service.create_tunnel(
            provider=provider,
            name=name,
            public_hostname=hostname,
            local_target=target,
            token=token,
            mode=mode
        )
        click.echo(f"✓ Created tunnel: {tunnel_id}")
        click.echo(f"  Name: {name}")
        click.echo(f"  Public: {hostname}")
        click.echo(f"  Local: {target}")
        click.echo(f"\nStart with: agentos networkos start {tunnel_id}")
    except Exception as e:
        click.echo(f"✗ Failed to create tunnel: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id')
def start(tunnel_id):
    """Start a tunnel"""
    try:
        service = NetworkOSService()
        if service.start_tunnel(tunnel_id):
            tunnel = service.store.get_tunnel(tunnel_id)
            if tunnel:
                click.echo(f"✓ Started tunnel: {tunnel.name}")
                click.echo(f"  Public URL: https://{tunnel.public_hostname}")
                click.echo(f"  Local target: {tunnel.local_target}")
        else:
            click.echo(f"✗ Failed to start tunnel: {tunnel_id}", err=True)
            raise click.Abort()
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id')
def stop(tunnel_id):
    """Stop a tunnel"""
    try:
        service = NetworkOSService()
        service.stop_tunnel(tunnel_id)
        click.echo(f"✓ Stopped tunnel: {tunnel_id}")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command(name='list')
def list_tunnels():
    """List all tunnels"""
    try:
        service = NetworkOSService()
        tunnels = service.list_tunnels()

        if not tunnels:
            click.echo("No tunnels configured.")
            return

        # Prepare table data
        headers = ["Status", "Name", "Provider", "Health", "Public Hostname", "Tunnel ID"]
        rows = []

        for t in tunnels:
            status_icon = "●" if t.is_enabled else "○"
            health_icon = {
                "up": "✓",
                "down": "✗",
                "unknown": "?"
            }.get(t.health_status, "?")

            rows.append([
                status_icon,
                t.name,
                t.provider,
                f"{health_icon} {t.health_status}",
                t.public_hostname,
                t.tunnel_id[:8] + "..."
            ])

        click.echo(_format_table(headers, rows))
        click.echo(f"\nTotal: {len(tunnels)} tunnel(s)")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id')
def status(tunnel_id):
    """Show tunnel status and recent events"""
    try:
        service = NetworkOSService()
        status = service.get_tunnel_status(tunnel_id)

        if not status:
            click.echo(f"✗ Tunnel not found: {tunnel_id}", err=True)
            raise click.Abort()

        tunnel = status['tunnel']
        is_running = status['is_running']
        events = status['recent_events']

        # Show tunnel info
        click.echo("=" * 60)
        click.echo(f"Tunnel: {tunnel.name}")
        click.echo("=" * 60)
        click.echo(f"ID:              {tunnel.tunnel_id}")
        click.echo(f"Provider:        {tunnel.provider}")
        click.echo(f"Status:          {'Running ●' if is_running else 'Stopped ○'}")
        click.echo(f"Health:          {tunnel.health_status}")
        click.echo(f"Public URL:      https://{tunnel.public_hostname}")
        click.echo(f"Local Target:    {tunnel.local_target}")
        click.echo(f"Mode:            {tunnel.mode}")

        if tunnel.last_error_code:
            click.echo(f"Last Error:      {tunnel.last_error_code}")
            if tunnel.last_error_message:
                click.echo(f"  {tunnel.last_error_message[:200]}")

        # Show recent events
        if events:
            click.echo("\n" + "=" * 60)
            click.echo("Recent Events (latest 10)")
            click.echo("=" * 60)

            for event in events:
                level_icon = {
                    "info": "ℹ",
                    "warn": "⚠",
                    "error": "✗"
                }.get(event.level, "•")

                from agentos.core.time import from_epoch_ms
                timestamp = from_epoch_ms(event.created_at).strftime("%Y-%m-%d %H:%M:%S")

                click.echo(f"{level_icon} [{timestamp}] {event.event_type}: {event.message}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id')
@click.confirmation_option(prompt="Are you sure you want to delete this tunnel?")
def delete(tunnel_id):
    """Delete a tunnel"""
    try:
        service = NetworkOSService()
        if service.delete_tunnel(tunnel_id):
            click.echo(f"✓ Deleted tunnel: {tunnel_id}")
        else:
            click.echo(f"✗ Failed to delete tunnel: {tunnel_id}", err=True)
            raise click.Abort()
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id')
@click.option('--limit', default=50, help='Number of events to show')
def logs(tunnel_id, limit):
    """Show tunnel event logs"""
    try:
        service = NetworkOSService()
        events = service.store.get_recent_events(tunnel_id, limit=limit)

        if not events:
            click.echo("No events found.")
            return

        click.echo(f"Showing {len(events)} recent events for tunnel {tunnel_id}:\n")

        for event in events:
            level_icon = {
                "info": "ℹ",
                "warn": "⚠",
                "error": "✗"
            }.get(event.level, "•")

            from agentos.core.time import from_epoch_ms
            timestamp = from_epoch_ms(event.created_at).strftime("%Y-%m-%d %H:%M:%S")

            click.echo(f"{level_icon} [{timestamp}] {event.level.upper()}: {event.event_type}")
            click.echo(f"  {event.message}")

            if event.data_json:
                try:
                    data = json.loads(event.data_json)
                    for key, value in data.items():
                        click.echo(f"    {key}: {value}")
                except:
                    pass

            click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()


@networkos.command()
@click.argument('tunnel_id', required=False)
@click.option('--check', is_flag=True, help='Only check migration status without migrating')
def migrate_secrets(tunnel_id, check):
    """Migrate tunnel secrets to secure storage (secret_ref pattern)

    This command migrates tunnel tokens from plaintext database storage
    to encrypted secure storage, following the secret_ref pattern.

    Security Benefits:
    - Tokens stored encrypted in ~/.agentos/secrets.json (0600 permissions)
    - Database only stores references, not plaintext tokens
    - Diagnostic exports won't leak tokens
    - Aligns with "zero secrets in DB" security posture

    Examples:
        # Check migration status
        agentos networkos migrate-secrets --check

        # Migrate all tunnels
        agentos networkos migrate-secrets

        # Migrate specific tunnel
        agentos networkos migrate-secrets TUNNEL_ID
    """
    try:
        service = NetworkOSService()

        # Check mode: show status without migrating
        if check:
            status = service.get_migration_status()
            click.echo("=" * 60)
            click.echo("Tunnel Secret Migration Status")
            click.echo("=" * 60)
            click.echo(f"Total tunnels:     {status['total_tunnels']}")
            click.echo(f"Migrated:          {status['migrated_count']} ✓")
            click.echo(f"Needs migration:   {status['unmigrated_count']}")

            if status['unmigrated_tunnel_ids']:
                click.echo("\nUnmigrated tunnels:")
                for tid in status['unmigrated_tunnel_ids']:
                    tunnel = service.store.get_tunnel(tid)
                    if tunnel:
                        click.echo(f"  - {tunnel.name} ({tid[:8]}...)")

            if status['migration_complete']:
                click.echo("\n✓ All tunnels migrated to secure storage")
            else:
                click.echo("\n⚠  Run without --check to migrate")
            return

        # Migration mode
        count = service.migrate_tunnel_secrets(tunnel_id)

        if count > 0:
            click.echo(f"✓ Successfully migrated {count} tunnel(s) to secure storage")
            click.echo(f"\nSecurity improvements:")
            click.echo(f"  • Tokens now encrypted in ~/.agentos/secrets.json")
            click.echo(f"  • Database only stores references (not plaintext)")
            click.echo(f"  • Diagnostic exports safe from token leakage")
        else:
            if tunnel_id:
                click.echo(f"⚠  Tunnel {tunnel_id} already migrated or not found")
            else:
                click.echo("⚠  No tunnels to migrate (all already using secret_ref)")

    except NotImplementedError as e:
        click.echo(f"✗ {e}", err=True)
        click.echo("\nNext steps:", err=True)
        click.echo("1. Ensure secure storage module is available", err=True)
        click.echo("2. Check ~/.agentos/secrets.json permissions (should be 0600)", err=True)
        click.echo("3. Re-run migration command", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"✗ Migration failed: {e}", err=True)
        raise click.Abort()
