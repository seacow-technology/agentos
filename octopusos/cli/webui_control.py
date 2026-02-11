"""WebUI control commands backed by a single daemon runtime source."""

from __future__ import annotations

import os
import socket
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import click
import requests
from rich import print as rprint
from rich.table import Table

from octopusos.config import load_settings, save_settings
from octopusos.daemon.service import (
    ensure_runtime_dirs,
    get_or_create_control_token,
    read_status,
    start_webui,
    stop_webui,
    tail_logs,
)
from octopusos.networkos.config_store import NetworkConfigStore
from octopusos.networkos.service import NetworkOSService


def _control_base_url() -> str:
    status = read_status()
    return f"http://{status.host}:{status.port}/api/daemon"


def _control_headers() -> dict[str, str]:
    return {"X-OctopusOS-Token": get_or_create_control_token()}


def _control_get(path: str, *, timeout: float = 1.5, **params):
    url = f"{_control_base_url()}{path}"
    return requests.get(url, headers=_control_headers(), timeout=timeout, params=params)


def _control_post(path: str, *, timeout: float = 1.5):
    url = f"{_control_base_url()}{path}"
    return requests.post(url, headers=_control_headers(), timeout=timeout)


def _configured_admin_token_source() -> str | None:
    if os.getenv("OCTOPUSOS_ADMIN_TOKEN_SECRET", "").strip():
        return "OCTOPUSOS_ADMIN_TOKEN_SECRET"
    if os.getenv("OCTOPUSOS_ADMIN_TOKEN", "").strip():
        return "OCTOPUSOS_ADMIN_TOKEN"
    return None


def _print_admin_token_guidance() -> None:
    source = _configured_admin_token_source()
    if source:
        rprint(f"[green]admin token configured via {source}[/green]")
        return

    rprint("[yellow]admin token is not configured[/yellow]")
    rprint(
        "[dim]protected write operations may fail (for example: build index, approve/reject actions).[/dim]"
    )
    click.echo("Set one of the following before starting WebUI:")
    click.echo("  export OCTOPUSOS_ADMIN_TOKEN='your-token'")
    click.echo("  export OCTOPUSOS_ADMIN_TOKEN_SECRET='your-token'  # optional alternative")
    click.echo("Optional helper to generate a token:")
    click.echo("  uv run python scripts/generate_admin_token.py --name \"WebUI Admin\" --permissions \"*\"")


def _find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _write_runtime_config(public_origin: str) -> None:
    runtime_file = Path("apps/webui/public/runtime/runtime-config.json")
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text(f'{{"public_origin":"{public_origin}"}}', encoding="utf-8")


def _start_frontend_dev_server(*, host: str, frontend_port: int, backend_host: str, backend_port: int) -> tuple[bool, str]:
    backend_origin = f"http://{backend_host}:{backend_port}"
    public_origin = f"http://{host}:{frontend_port}"
    _write_runtime_config(public_origin)

    paths = ensure_runtime_dirs()
    frontend_log = paths.log_dir / "webui-frontend.log"
    frontend_pid_file = paths.runtime_dir / "webui-frontend.pid"

    existing_pid = None
    if frontend_pid_file.exists():
        try:
            existing_pid = int(frontend_pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            existing_pid = None
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
            os.kill(existing_pid, 15)
        except OSError:
            pass
        frontend_pid_file.unlink(missing_ok=True)

    env = os.environ.copy()
    env["OCTOPUS_BACKEND_ORIGIN"] = backend_origin
    env["OCTOPUS_PUBLIC_ORIGIN"] = public_origin

    log_handle = frontend_log.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", host, "--port", str(frontend_port)],
        cwd="apps/webui",
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
    )
    frontend_pid_file.write_text(str(proc.pid), encoding="utf-8")
    return True, public_origin


def _parse_target_port(target: str) -> int | None:
    raw = str(target or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        if parsed.port:
            return int(parsed.port)
    except Exception:
        return None
    return None


def _resolve_bridge_cloudflare_proxy(*, backend_host: str, backend_port: int) -> str | None:
    # 1) Prefer configured canonical hostname from NetworkOS config.
    try:
        cfg = NetworkConfigStore().resolve_cloudflare_config()
        hostname = str((cfg.get("network.cloudflare.hostname").value if cfg.get("network.cloudflare.hostname") else "") or "").strip()  # type: ignore[union-attr]
        if hostname:
            return f"https://{hostname}"
    except Exception:
        pass

    # 2) Fallback to enabled/running Cloudflare tunnel entries targeting current backend.
    try:
        service = NetworkOSService()
        for tunnel in service.list_tunnels():
            if str(tunnel.provider).strip().lower() != "cloudflare":
                continue
            if not bool(tunnel.is_enabled):
                continue
            t_port = _parse_target_port(tunnel.local_target)
            if t_port is not None and int(t_port) != int(backend_port):
                continue
            host = str(tunnel.public_hostname or "").strip()
            if host:
                return f"https://{host}"
    except Exception:
        pass
    return None


def _print_runtime_endpoints(*, frontend_url: str | None, backend_url: str, backend_host: str, backend_port: int, log_file: str) -> None:
    if frontend_url:
        rprint(f"[green]frontend started: {frontend_url}[/green]")
    rprint(f"[green]started backend: {backend_url}[/green]")
    bridge_url = _resolve_bridge_cloudflare_proxy(backend_host=backend_host, backend_port=backend_port)
    if bridge_url:
        rprint(f"[green]bridge proxy (cloudflare): {bridge_url}[/green]")
    rprint(f"[dim]log file: {log_file}[/dim]")


@click.group(name="webui", invoke_without_command=True)
@click.pass_context
def webui_group(ctx: click.Context) -> None:
    """Manage OctopusOS WebUI daemon."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(start_cmd, host=None, port=None, foreground=False, open_browser=True, with_frontend=True, frontend_port=None)


def _start_webui_stack(
    host: str | None,
    port: int | None,
    foreground: bool,
    open_browser: bool,
    with_frontend: bool,
    frontend_port: int | None,
) -> None:
    """Start WebUI daemon."""
    _print_admin_token_guidance()

    settings = load_settings()
    actual_host = host or settings.webui_host
    preferred_port = port or settings.webui_port

    result = start_webui(
        host=actual_host,
        preferred_port=preferred_port,
        foreground=foreground,
        open_browser=False,
    )

    if not result.ok:
        rprint(f"[red]start failed: {result.message}[/red]")
        raise click.Abort()

    if result.already_running:
        rprint(f"[cyan]backend already running: {result.status.url}[/cyan]")
    elif result.port_changed:
        rprint(
            f"[yellow]preferred port {preferred_port} busy, using {result.status.port}[/yellow]"
        )

    frontend_url = None
    if with_frontend:
        selected_frontend_port = frontend_port or int(os.getenv("OCTOPUS_FRONTEND_PORT", "0") or 0) or _find_free_port(actual_host)
        ok, frontend_url = _start_frontend_dev_server(
            host=actual_host,
            frontend_port=selected_frontend_port,
            backend_host=actual_host,
            backend_port=result.status.port,
        )
        if not ok:
            rprint("[red]frontend failed to start[/red]")
            raise click.Abort()
    _print_runtime_endpoints(
        frontend_url=frontend_url,
        backend_url=result.status.url,
        backend_host=actual_host,
        backend_port=result.status.port,
        log_file=str(result.status.log_file),
    )
    if open_browser:
        webbrowser.open(frontend_url or result.status.url)


@webui_group.command(name="start")
@click.option("--host", default=None, help="WebUI host (default: from config)")
@click.option("--port", default=None, type=int, help="WebUI port (default: from config)")
@click.option("--foreground", is_flag=True, help="Run in foreground")
@click.option("--open", "open_browser", is_flag=True, help="Open browser after start")
@click.option("--with-frontend/--backend-only", default=True, help="Start frontend dev server together")
@click.option("--frontend-port", default=None, type=int, help="Frontend port (default: auto-select)")
def start_cmd(
    host: str | None,
    port: int | None,
    foreground: bool,
    open_browser: bool,
    with_frontend: bool,
    frontend_port: int | None,
) -> None:
    _start_webui_stack(
        host=host,
        port=port,
        foreground=foreground,
        open_browser=open_browser,
        with_frontend=with_frontend,
        frontend_port=frontend_port,
    )


@webui_group.command(name="stop")
def stop_cmd() -> None:
    """Stop WebUI daemon."""
    ok = False
    message = "not running"
    status = read_status()
    if status.running:
        try:
            resp = _control_post("/stop")
            if resp.ok:
                ok = True
                message = "stopping"
            else:
                ok, message = stop_webui()
        except requests.RequestException:
            ok, message = stop_webui()
    else:
        ok, message = stop_webui()

    if not ok:
        rprint(f"[red]{message}[/red]")
        raise click.Abort()
    rprint(f"[green]{message}[/green]")


@webui_group.command(name="restart")
@click.option("--host", default=None, help="WebUI host (default: from config)")
@click.option("--port", default=None, type=int, help="WebUI port (default: from config)")
@click.option("--open/--no-open", "open_browser", default=True, help="Open browser after restart")
@click.option("--with-frontend/--backend-only", default=True, help="Start frontend dev server together")
@click.option("--frontend-port", default=None, type=int, help="Frontend port (default: auto-select)")
def restart_cmd(
    host: str | None,
    port: int | None,
    open_browser: bool,
    with_frontend: bool,
    frontend_port: int | None,
) -> None:
    """Restart WebUI daemon."""
    status = read_status()
    if status.running and not with_frontend:
        try:
            resp = _control_post("/restart", timeout=2.0)
            if resp.ok:
                rprint("[green]restarting[/green]")
                _print_runtime_endpoints(
                    frontend_url=None,
                    backend_url=status.url,
                    backend_host=str(getattr(status, "host", "127.0.0.1")),
                    backend_port=int(getattr(status, "port", 8080)),
                    log_file=str(getattr(status, "log_file", "")),
                )
                if open_browser:
                    webbrowser.open(status.url)
                return
        except requests.RequestException:
            pass
    stop_webui()
    _start_webui_stack(
        host=host,
        port=port,
        foreground=False,
        open_browser=open_browser,
        with_frontend=with_frontend,
        frontend_port=frontend_port,
    )


@webui_group.command(name="status")
def status_cmd() -> None:
    """Show WebUI daemon status."""
    status = read_status()
    try:
        resp = _control_get("/status")
        if resp.ok:
            payload = resp.json()
            status.running = bool(payload.get("running"))
            status.pid = payload.get("pid")
            status.host = payload.get("host", status.host)
            status.port = int(payload.get("port", status.port))
            status.url = payload.get("url", status.url)
            status.started_at = payload.get("started_at", status.started_at)
            status.last_error = payload.get("last_error", status.last_error)
            status.port_source = payload.get("port_source", status.port_source)
    except requests.RequestException:
        pass

    table = Table(title="WebUI Daemon Status", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Running", "yes" if status.running else "no")
    table.add_row("URL", status.url)
    table.add_row("PID", str(status.pid) if status.pid else "-")
    table.add_row("Port source", status.port_source)
    table.add_row("Data dir", str(status.data_dir))
    table.add_row("Log file", str(status.log_file))
    table.add_row("Status file", str(status.status_file))
    table.add_row("Started at", status.started_at or "-")
    table.add_row("Last error", status.last_error or "-")

    rprint(table)


@webui_group.command(name="logs")
@click.option("--tail", is_flag=True, help="Show tail of daemon logs")
@click.option("--lines", default=100, type=int, help="Number of lines to show")
def logs_cmd(tail: bool, lines: int) -> None:
    """Show WebUI daemon logs."""
    if not tail:
        rprint("[yellow]use --tail to print logs[/yellow]")
        return
    content = ""
    try:
        resp = _control_get("/logs", lines=lines)
        if resp.ok:
            content = resp.json().get("content", "")
    except requests.RequestException:
        content = ""
    if not content:
        content = tail_logs(lines=lines)
    if not content:
        rprint("[yellow]no logs yet[/yellow]")
        return
    click.echo(content)


@webui_group.command(name="config")
@click.option("--auto-start/--no-auto-start", default=None, help="Enable/disable auto-start")
@click.option("--host", default=None, help="Set WebUI host")
@click.option("--port", default=None, type=int, help="Set WebUI port")
@click.option("--show", is_flag=True, help="Show current configuration")
def config_cmd(auto_start: bool | None, host: str | None, port: int | None, show: bool) -> None:
    """Configure WebUI settings."""
    settings = load_settings()

    if show:
        table = Table(title="WebUI Configuration", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Auto-start", "enabled" if settings.webui_auto_start else "disabled")
        table.add_row("Host", settings.webui_host)
        table.add_row("Port", str(settings.webui_port))
        rprint(table)
        return

    changed = False
    if auto_start is not None:
        settings.webui_auto_start = auto_start
        changed = True
    if host is not None:
        settings.webui_host = host
        changed = True
    if port is not None:
        settings.webui_port = port
        changed = True

    if changed:
        save_settings(settings)
        rprint("[green]configuration updated[/green]")
    else:
        rprint("[yellow]no changes made[/yellow]")
