"""
WebUI Control Commands - Manage WebUI background service

agentos webui start   - Start WebUI
agentos webui stop    - Stop WebUI
agentos webui restart - Restart WebUI
agentos webui status  - View status
agentos webui config  - Configuration management
"""

import click
from rich import print as rprint
from rich.table import Table

from agentos.webui.daemon import WebUIDaemon
from agentos.config import load_settings, save_settings


@click.group(name="webui")
def webui_group():
    """
    WebUI service management

    Manage the startup, shutdown and configuration of AgentOS WebUI background service.
    """
    pass


@webui_group.command(name="start")
@click.option(
    "--host",
    default=None,
    help="Bind host (default: use config)",
)
@click.option(
    "--port",
    default=None,
    type=int,
    help="Bind port (default: use config)",
)
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (not background)",
)
def start_cmd(host: str, port: int, foreground: bool):
    """Start WebUI service"""
    settings = load_settings()

    # 使用配置或命令行参数
    actual_host = host or settings.webui_host
    actual_port = port or settings.webui_port

    daemon = WebUIDaemon(host=actual_host, port=actual_port)

    # 检查是否已运行
    is_running, pid = daemon.is_running()
    if is_running:
        rprint(f"[yellow]⚠️  WebUI already running at PID {pid}[/yellow]")
        rprint(f"[cyan]URL: http://{actual_host}:{actual_port}[/cyan]")
        return

    # 启动
    rprint(f"[blue]🚀 Starting WebUI at {actual_host}:{actual_port}...[/blue]")

    if daemon.start(background=not foreground):
        if not foreground:
            rprint(f"[green]✅ WebUI started successfully[/green]")
            rprint(f"[cyan]URL: http://{actual_host}:{actual_port}[/cyan]")
            rprint(f"[dim]Logs: {daemon.log_file}[/dim]")
    else:
        rprint("[red]❌ Failed to start WebUI[/red]")


@webui_group.command(name="stop")
def stop_cmd():
    """Stop WebUI service"""
    settings = load_settings()
    daemon = WebUIDaemon(host=settings.webui_host, port=settings.webui_port)

    # 检查是否运行
    is_running, pid = daemon.is_running()
    if not is_running:
        rprint("[yellow]⚠️  WebUI is not running[/yellow]")
        return

    # 停止
    rprint(f"[blue]🛑 Stopping WebUI (PID {pid})...[/blue]")

    if daemon.stop():
        rprint("[green]✅ WebUI stopped successfully[/green]")
    else:
        rprint("[red]❌ Failed to stop WebUI[/red]")


@webui_group.command(name="restart")
def restart_cmd():
    """Restart WebUI service"""
    settings = load_settings()
    daemon = WebUIDaemon(host=settings.webui_host, port=settings.webui_port)

    rprint("[blue]🔄 Restarting WebUI...[/blue]")

    if daemon.restart():
        rprint("[green]✅ WebUI restarted successfully[/green]")
        rprint(f"[cyan]URL: http://{settings.webui_host}:{settings.webui_port}[/cyan]")
    else:
        rprint("[red]❌ Failed to restart WebUI[/red]")


@webui_group.command(name="status")
def status_cmd():
    """View WebUI status"""
    settings = load_settings()
    daemon = WebUIDaemon(host=settings.webui_host, port=settings.webui_port)

    status = daemon.status()

    # 创建状态表格
    table = Table(title="WebUI Status", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Running", "✅ Yes" if status["running"] else "❌ No")

    if status["running"]:
        table.add_row("PID", str(status["pid"]))
        table.add_row("URL", status["url"])

    table.add_row("Host", status["host"])
    table.add_row("Port", str(status["port"]))

    if status["log_file"]:
        table.add_row("Log File", status["log_file"])

    rprint(table)

    # 显示配置
    rprint(f"\n[dim]Auto-start: {'Enabled' if settings.webui_auto_start else 'Disabled'}[/dim]")


@webui_group.command(name="config")
@click.option(
    "--auto-start/--no-auto-start",
    default=None,
    help="Enable/disable auto-start",
)
@click.option(
    "--host",
    default=None,
    help="Set bind host",
)
@click.option(
    "--port",
    default=None,
    type=int,
    help="Set port",
)
@click.option(
    "--show",
    is_flag=True,
    help="Show current configuration",
)
def config_cmd(auto_start: bool, host: str, port: int, show: bool):
    """Configure WebUI settings"""
    settings = load_settings()

    if show:
        # 显示当前配置
        table = Table(title="WebUI Configuration", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Auto-start", "✅ Enabled" if settings.webui_auto_start else "❌ Disabled")
        table.add_row("Host", settings.webui_host)
        table.add_row("Port", str(settings.webui_port))

        rprint(table)
        return

    # 更新配置
    changed = False

    if auto_start is not None:
        settings.webui_auto_start = auto_start
        changed = True
        rprint(f"[green]✅ Auto-start: {'Enabled' if auto_start else 'Disabled'}[/green]")

    if host is not None:
        settings.webui_host = host
        changed = True
        rprint(f"[green]✅ Host: {host}[/green]")

    if port is not None:
        settings.webui_port = port
        changed = True
        rprint(f"[green]✅ Port: {port}[/green]")

    if changed:
        save_settings(settings)
        rprint("[blue]💾 Configuration saved[/blue]")
    else:
        rprint("[yellow]No changes made. Use --show to see current config.[/yellow]")
