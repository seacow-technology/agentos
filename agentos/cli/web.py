"""
Web UI Command - v1 deprecated (WebUI v2 is standalone)

agentos web [--host HOST] [--port PORT]
"""

import click


@click.command(name="web")
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
    show_default=True,
)
@click.option(
    "--port",
    default=8080,
    type=int,
    help="Port to bind to (default: 8080)",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload (development mode)",
)
@click.option(
    "--log-level",
    default="info",
    type=click.Choice(["debug", "info", "warning", "error"]),
    help="Log level",
    show_default=True,
)
def web_cmd(host: str, port: int, reload: bool, log_level: str):
    """
    WebUI v1 has been removed. Use webui-v2 instead.
    """
    click.secho("\n⚠️  AgentOS WebUI v1 has been removed.", fg="yellow", bold=True)
    click.secho("   Please use WebUI v2 (standalone frontend).\n", fg="yellow")
    click.secho("Quick start (dev server):", fg="cyan")
    click.secho("  cd webui-v2", fg="cyan")
    click.secho("  npm install", fg="cyan")
    click.secho("  npm run dev", fg="cyan")
    click.secho("\nPreview build:", fg="cyan")
    click.secho("  cd webui-v2", fg="cyan")
    click.secho("  npm install", fg="cyan")
    click.secho("  npm run build", fg="cyan")
    click.secho("  npm run preview", fg="cyan")
    return 0
