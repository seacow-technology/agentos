"""CLI orchestrate command"""

import click

from agentos.core.orchestrator import Orchestrator


@click.command()
@click.option("--once", is_flag=True, help="Run once and exit (default: loop every 30s)")
def orchestrate_cmd(once: bool):
    """Run orchestrator to process tasks from queue"""
    orchestrator = Orchestrator(once=once)
    orchestrator.run()
