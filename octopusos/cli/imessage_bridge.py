from __future__ import annotations

import logging
from pathlib import Path

import click

from octopusos.bridgeos.imessage_local_bridge import BridgeConfig, run_bridge


@click.group(name="imessage-bridge")
def imessage_bridge_group() -> None:
    """Run the built-in local iMessage bridge (no third-party bridge required)."""


@imessage_bridge_group.command(name="run")
@click.option("--listen-host", default="127.0.0.1", show_default=True, help="HTTP listen host.")
@click.option("--listen-port", default=19080, show_default=True, type=int, help="HTTP listen port.")
@click.option(
    "--webhook-url",
    default="http://127.0.0.1:8080/api/channels/imessage/webhook",
    show_default=True,
    help="OctopusOS iMessage webhook URL.",
)
@click.option(
    "--bridge-token",
    default="",
    show_default=False,
    help="Optional shared token for /api/imessage/send auth and webhook auth header.",
)
@click.option("--poll-interval", default=2.0, show_default=True, type=float, help="Messages DB poll interval in seconds.")
@click.option(
    "--db-path",
    default="~/Library/Messages/chat.db",
    show_default=True,
    help="Path to macOS Messages sqlite database.",
)
@click.option(
    "--state-file",
    default="~/.octopusos/imessage_bridge/state.json",
    show_default=True,
    help="State file for last processed message row id.",
)
@click.option(
    "--bootstrap-latest/--replay-all",
    default=True,
    show_default=True,
    help="On first run, start from latest row (avoid replaying old messages).",
)
@click.option(
    "--allow-from-me/--inbound-only",
    default=False,
    show_default=True,
    help="Allow self-sent iMessage rows (single-account self-chat mode, with echo suppression).",
)
@click.option("--verbose", is_flag=True, help="Enable verbose logs.")
def run_cmd(
    listen_host: str,
    listen_port: int,
    webhook_url: str,
    bridge_token: str,
    poll_interval: float,
    db_path: str,
    state_file: str,
    bootstrap_latest: bool,
    allow_from_me: bool,
    verbose: bool,
) -> None:
    """Start local iMessage bridge service."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = BridgeConfig(
        listen_host=str(listen_host).strip(),
        listen_port=int(listen_port),
        webhook_url=str(webhook_url).strip(),
        bridge_token=str(bridge_token or "").strip(),
        poll_interval_s=max(0.5, float(poll_interval)),
        db_path=Path(db_path).expanduser(),
        state_file=Path(state_file).expanduser(),
        bootstrap_latest=bool(bootstrap_latest),
        allow_from_me=bool(allow_from_me),
    )
    click.echo(f"starting imessage bridge on http://{cfg.listen_host}:{cfg.listen_port}")
    click.echo(f"webhook -> {cfg.webhook_url}")
    if cfg.bridge_token:
        click.echo("bridge token enabled")
    else:
        click.echo("bridge token disabled")
    click.echo(f"allow_from_me={'yes' if cfg.allow_from_me else 'no'}")
    try:
        run_bridge(cfg)
    except KeyboardInterrupt:
        click.echo("stopped")
