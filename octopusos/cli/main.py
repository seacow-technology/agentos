"""CLI main entry point"""

import sys
import click

from octopusos import __version__
from octopusos.config import load_settings
from octopusos.i18n import set_language


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="octopusos")
@click.option("--web", is_flag=True, help="Deprecated: show WebUI v2 migration guidance")
@click.pass_context
def cli(ctx, web):
    """OctopusOS - System-level AI Agent orchestration system

    Run without arguments to enter interactive mode.
    """
    # Handle --web flag
    if web:
        click.echo("⚠️  WebUI v1 has been removed.")
        click.echo("   Please use WebUI v2 (standalone frontend).")
        click.echo("")
        click.echo("Quick start (dev server):")
        click.echo("  cd apps/webui")
        click.echo("  npm install")
        click.echo("  npm run dev")
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
        from octopusos.cli.health import check_schema_version, print_schema_warning
        is_ok, message = check_schema_version()
        if not is_ok and message:
            print_schema_warning(message)

    # Auto-start WebUI if enabled (skip for web and webui commands)
    if ctx.invoked_subcommand not in ("init", "migrate", "web", "webui", None):
        try:
            settings = load_settings()
            if settings.webui_auto_start:
                from octopusos.daemon.service import start_webui

                start_webui(host=settings.webui_host, preferred_port=settings.webui_port)
        except Exception:
            # Silently fail - WebUI is optional
            pass
    
    # If no subcommand provided, enter interactive mode
    if ctx.invoked_subcommand is None:
        from octopusos.cli.interactive import interactive_main
        interactive_main()


# Import subcommands
from octopusos.cli.init import init_cmd
from octopusos.cli.doctor import doctor
from octopusos.cli.project import project_group
from octopusos.cli.scan import scan_cmd
from octopusos.cli.generate import generate_group
from octopusos.cli.verify import verify_cmd
from octopusos.cli.orchestrate import orchestrate_cmd
from octopusos.cli.migrate import migrate
from octopusos.cli.memory import memory_group
from octopusos.cli.content import content_group
from octopusos.cli.evaluator import evaluator
from octopusos.cli.intent_builder import builder
from octopusos.cli.dry_executor import dry_run_group
from octopusos.cli.answers import answers_group
from octopusos.cli.pipeline import pipeline_group
from octopusos.cli.executor import exec_group
from octopusos.cli.tools import tool_group
from octopusos.cli.run import run_cmd
from octopusos.cli.task import task_group
from octopusos.cli.kb import kb
from octopusos.cli.interactive import interactive_main
from octopusos.cli.web import web_cmd
from octopusos.cli.webui_control import webui_group
from octopusos.cli.logs import logs_cmd
from octopusos.cli.auth import auth_group
from octopusos.cli.imessage_bridge import imessage_bridge_group

# Import v0.4 Project-Aware Task OS commands
from octopusos.cli.commands.project_v31 import project_v31_group
from octopusos.cli.commands.repo_v31 import repo_v31_group
from octopusos.cli.commands.task_v31 import task_v31_group

# Import v3 Classifier Version Management
from octopusos.cli.classifier_version import version_group

# Import v1.3 Inspection Commands (PR-0131-2026-4: CLI Read-only Parity)
from octopusos.cli.inspect import task_group as inspect_task_group, governance_group

# Import Skill Management Commands (PR-0201-2026-3: GitHub Importer)
from octopusos.cli.commands.skill import skill as skill_group

# Import NetworkOS Commands (Cloudflare Tunnel Management)
from octopusos.cli.commands.networkos import networkos as networkos_group

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
cli.add_command(logs_cmd, name="logs")
cli.add_command(auth_group, name="auth")
cli.add_command(imessage_bridge_group, name="imessage-bridge")

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
from octopusos.cli.inspect import task_inspect, governance_trace
task_group.add_command(task_inspect, name="inspect")
governance_group.add_command(governance_trace, name="trace")


@cli.command(name="interactive")
def interactive_cmd():
    """Enter interactive mode (Task Control Plane)"""
    interactive_main()


if __name__ == "__main__":
    cli()
