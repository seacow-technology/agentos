"""CLI main entry point"""

import sys
import click

from agentos import __version__
from agentos.config import load_settings
from agentos.i18n import set_language


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="agentos")
@click.option("--web", is_flag=True, help="Start WebUI and open in browser")
@click.pass_context
def cli(ctx, web):
    """AgentOS - System-level AI Agent orchestration system

    Run without arguments to enter interactive mode.
    """
    # Handle --web flag
    if web:
        from agentos.webui.daemon import WebUIDaemon
        from agentos.config import load_settings
        try:
            settings = load_settings()
            host = settings.webui_host
            port = settings.webui_port
        except Exception:
            host = "127.0.0.1"
            port = 8080

        daemon = WebUIDaemon(host=host, port=port)
        running, pid = daemon.is_running()

        if running:
            click.echo(f"⚠️  WebUI already running (PID: {pid}), restarting...")
            if not daemon.stop():
                click.echo("❌ Failed to stop existing WebUI")
                ctx.exit(1)
            # Wait a moment for port to be released
            import time
            time.sleep(1)

        click.echo("🚀 Starting WebUI...")
        if daemon.start(background=True):
            click.echo(f"✅ WebUI started at http://{host}:{port}")
        else:
            click.echo("❌ Failed to start WebUI")
            ctx.exit(1)

        # Open browser
        import webbrowser
        url = f"http://{host}:{port}"
        click.echo(f"🌐 Opening browser: {url}")
        webbrowser.open(url)
        ctx.exit(0)
    # Initialize language from settings (before any output)
    try:
        settings = load_settings()
        set_language(settings.language)
    except Exception:
        # If settings loading fails, use default English
        set_language("en")
    
    # Perform health check on CLI startup (non-blocking)
    # Skip for init/migrate commands to avoid circular issues
    if ctx.invoked_subcommand not in ("init", "migrate", None):
        from agentos.cli.health import check_schema_version, print_schema_warning
        is_ok, message = check_schema_version()
        if not is_ok and message:
            print_schema_warning(message)

    # Auto-start WebUI if enabled (skip for web and webui commands)
    if ctx.invoked_subcommand not in ("init", "migrate", "web", "webui", None):
        try:
            settings = load_settings()
            if settings.webui_auto_start:
                from agentos.webui.daemon import auto_start_webui
                auto_start_webui(host=settings.webui_host, port=settings.webui_port)
        except Exception:
            # Silently fail - WebUI is optional
            pass
    
    # If no subcommand provided, enter interactive mode
    if ctx.invoked_subcommand is None:
        from agentos.cli.interactive import interactive_main
        interactive_main()


# Import subcommands
from agentos.cli.init import init_cmd
from agentos.cli.doctor import doctor
from agentos.cli.project import project_group
from agentos.cli.scan import scan_cmd
from agentos.cli.generate import generate_group
from agentos.cli.verify import verify_cmd
from agentos.cli.orchestrate import orchestrate_cmd
from agentos.cli.migrate import migrate
from agentos.cli.memory import memory_group
from agentos.cli.content import content_group
from agentos.cli.evaluator import evaluator
from agentos.cli.intent_builder import builder
from agentos.cli.dry_executor import dry_run_group
from agentos.cli.answers import answers_group
from agentos.cli.pipeline import pipeline_group
from agentos.cli.executor import exec_group
from agentos.cli.tools import tool_group
from agentos.cli.run import run_cmd
from agentos.cli.task import task_group
from agentos.cli.kb import kb
from agentos.cli.interactive import interactive_main
from agentos.cli.web import web_cmd
from agentos.cli.webui_control import webui_group
from agentos.cli.auth import auth_group

# Import v0.4 Project-Aware Task OS commands
from agentos.cli.commands.project_v31 import project_v31_group
from agentos.cli.commands.repo_v31 import repo_v31_group
from agentos.cli.commands.task_v31 import task_v31_group

# Import v3 Classifier Version Management
from agentos.cli.classifier_version import version_group

# Import v1.3 Inspection Commands (PR-0131-2026-4: CLI Read-only Parity)
from agentos.cli.inspect import task_group as inspect_task_group, governance_group

# Import Skill Management Commands (PR-0201-2026-3: GitHub Importer)
from agentos.cli.commands.skill import skill as skill_group

# Import NetworkOS Commands (Cloudflare Tunnel Management)
from agentos.cli.commands.networkos import networkos as networkos_group

cli.add_command(init_cmd, name="init")
cli.add_command(doctor, name="doctor")
cli.add_command(project_group, name="project")
cli.add_command(scan_cmd, name="scan")
cli.add_command(generate_group, name="generate")
cli.add_command(verify_cmd, name="verify")
cli.add_command(orchestrate_cmd, name="orchestrate")
cli.add_command(migrate, name="migrate")
cli.add_command(memory_group, name="memory")
cli.add_command(content_group, name="content")
cli.add_command(evaluator, name="evaluator")
cli.add_command(builder, name="builder")
cli.add_command(dry_run_group, name="dry-run")
cli.add_command(answers_group, name="answers")
cli.add_command(pipeline_group, name="pipeline")
cli.add_command(exec_group, name="exec")
cli.add_command(tool_group, name="tool")
cli.add_command(run_cmd, name="run")
cli.add_command(task_group, name="task")
cli.add_command(kb, name="kb")
cli.add_command(web_cmd, name="web")
cli.add_command(webui_group, name="webui")
cli.add_command(auth_group, name="auth")

# Register v0.4 Project-Aware Task OS commands
cli.add_command(project_v31_group, name="project-v31")
cli.add_command(repo_v31_group, name="repo-v31")
cli.add_command(task_v31_group, name="task-v31")

# Register v3 Classifier Version Management
cli.add_command(version_group, name="version")

# Register v1.3 Inspection Commands (PR-0131-2026-4: CLI Read-only Parity)
cli.add_command(governance_group, name="governance")

# Register Skill Management Commands (PR-0201-2026-3: GitHub Importer)
cli.add_command(skill_group, name="skill")

# Register NetworkOS Commands (Cloudflare Tunnel Management)
cli.add_command(networkos_group, name="networkos")

# Add inspect commands to existing task_group
from agentos.cli.inspect import task_inspect, governance_trace
task_group.add_command(task_inspect, name="inspect")
governance_group.add_command(governance_trace, name="trace")


@cli.command(name="interactive")
def interactive_cmd():
    """Enter interactive mode (Task Control Plane)"""
    interactive_main()


if __name__ == "__main__":
    cli()
