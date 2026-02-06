"""CLI command for querying and visualizing task dependencies

Usage:
    agentos task dependencies <task_id>                # Show dependencies
    agentos task dependencies <task_id> --reverse      # Show reverse dependencies
    agentos task dependencies --graph                  # Export full DAG
    agentos task dependencies --graph --output file.dot # Export to file
    agentos task dependencies --check-cycles           # Check for circular dependencies
"""

import sys
import json
import click
from pathlib import Path

from agentos.core.task.dependency_service import TaskDependencyService, CircularDependencyError
from agentos.core.task.models import DependencyType
from agentos.store import get_db


@click.group(name="dependencies")
def dependencies_group():
    """Task dependency management and visualization"""
    pass


@dependencies_group.command(name="show")
@click.argument("task_id", required=True)
@click.option("--reverse", is_flag=True, help="Show reverse dependencies (who depends on this task)")
@click.option("--format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def show_dependencies(task_id: str, reverse: bool, format: str):
    """Show dependencies for a task

    Examples:
        agentos task dependencies show task-123
        agentos task dependencies show task-123 --reverse
        agentos task dependencies show task-123 --format json
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        if reverse:
            deps = service.get_reverse_dependencies(task_id)
            title = f"Tasks that depend on {task_id}"
        else:
            deps = service.get_dependencies(task_id)
            title = f"Dependencies of {task_id}"

        if not deps:
            click.echo(f"No dependencies found for task {task_id}")
            return

        if format == "json":
            # JSON output
            output = [dep.to_dict() for dep in deps]
            click.echo(json.dumps(output, indent=2))
        else:
            # Table output
            click.echo(f"\n{title}:\n")
            click.echo(f"{'Task ID':<20} {'Type':<10} {'Reason':<50} {'Created By':<15}")
            click.echo("-" * 95)

            for dep in deps:
                if reverse:
                    # Show who depends on this task
                    task_col = dep.task_id
                else:
                    # Show what this task depends on
                    task_col = dep.depends_on_task_id

                type_col = dep.dependency_type.value if hasattr(dep.dependency_type, 'value') else dep.dependency_type
                reason_col = (dep.reason or "")[:47] + "..." if dep.reason and len(dep.reason) > 50 else (dep.reason or "")
                created_by_col = dep.created_by or "unknown"

                click.echo(f"{task_col:<20} {type_col:<10} {reason_col:<50} {created_by_col:<15}")

            click.echo(f"\nTotal: {len(deps)} dependencies\n")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="graph")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--format", type=click.Choice(["dot", "json"]), default="dot", help="Output format")
@click.option("--tasks", multiple=True, help="Filter to specific task IDs")
def export_graph(output: str, format: str, tasks: tuple):
    """Export dependency graph

    Examples:
        agentos task dependencies graph
        agentos task dependencies graph -o deps.dot
        agentos task dependencies graph --format json -o deps.json
        agentos task dependencies graph --tasks task-001 --tasks task-002
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        # Build graph
        task_ids = list(tasks) if tasks else None
        graph = service.build_dependency_graph(task_ids=task_ids)

        # Generate output
        if format == "dot":
            content = graph.to_dot()
        else:  # json
            deps = service.get_all_dependencies()
            if task_ids:
                deps = [d for d in deps if d.task_id in task_ids or d.depends_on_task_id in task_ids]
            content = json.dumps([d.to_dict() for d in deps], indent=2)

        # Write output
        if output:
            Path(output).write_text(content)
            click.echo(f"Exported dependency graph to {output}")

            # If DOT format, suggest rendering
            if format == "dot":
                click.echo(f"\nTo render as PNG:")
                click.echo(f"  dot -Tpng {output} -o {Path(output).stem}.png")
        else:
            click.echo(content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="check-cycles")
def check_cycles():
    """Check for circular dependencies

    Examples:
        agentos task dependencies check-cycles
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        cycles = service.detect_cycles()

        if not cycles:
            click.echo("✓ No circular dependencies detected")
            return

        click.echo(f"✗ Found {len(cycles)} circular dependencies:\n")

        for i, cycle in enumerate(cycles, 1):
            click.echo(f"Cycle {i}: {' -> '.join(cycle)}")

        sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="ancestors")
@click.argument("task_id", required=True)
@click.option("--format", type=click.Choice(["list", "json"]), default="list", help="Output format")
def show_ancestors(task_id: str, format: str):
    """Show all ancestor tasks (transitive dependencies)

    Examples:
        agentos task dependencies ancestors task-123
        agentos task dependencies ancestors task-123 --format json
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        graph = service.build_dependency_graph()
        ancestors = graph.get_ancestors(task_id)

        if not ancestors:
            click.echo(f"No ancestors found for task {task_id}")
            return

        if format == "json":
            click.echo(json.dumps(list(ancestors), indent=2))
        else:
            click.echo(f"\nAncestors of {task_id}:")
            for ancestor in sorted(ancestors):
                click.echo(f"  - {ancestor}")
            click.echo(f"\nTotal: {len(ancestors)} ancestors\n")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="descendants")
@click.argument("task_id", required=True)
@click.option("--format", type=click.Choice(["list", "json"]), default="list", help="Output format")
def show_descendants(task_id: str, format: str):
    """Show all descendant tasks (who depends on this recursively)

    Examples:
        agentos task dependencies descendants task-123
        agentos task dependencies descendants task-123 --format json
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        graph = service.build_dependency_graph()
        descendants = graph.get_descendants(task_id)

        if not descendants:
            click.echo(f"No descendants found for task {task_id}")
            return

        if format == "json":
            click.echo(json.dumps(list(descendants), indent=2))
        else:
            click.echo(f"\nDescendants of {task_id} (tasks that depend on it):")
            for descendant in sorted(descendants):
                click.echo(f"  - {descendant}")
            click.echo(f"\nTotal: {len(descendants)} descendants\n")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="topological-sort")
@click.option("--format", type=click.Choice(["list", "json"]), default="list", help="Output format")
def topological_sort(format: str):
    """Show tasks in topological order (execution order)

    Examples:
        agentos task dependencies topological-sort
        agentos task dependencies topological-sort --format json
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        graph = service.build_dependency_graph()
        order = graph.topological_sort()

        if format == "json":
            click.echo(json.dumps(order, indent=2))
        else:
            click.echo("\nTopological order (dependencies first):")
            for i, task_id in enumerate(order, 1):
                click.echo(f"  {i}. {task_id}")
            click.echo(f"\nTotal: {len(order)} tasks\n")

    except CircularDependencyError as e:
        click.echo(f"Error: Cannot compute topological sort due to circular dependencies", err=True)
        click.echo(f"{e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="create")
@click.argument("task_id", required=True)
@click.argument("depends_on_task_id", required=True)
@click.option("--type", "dep_type", type=click.Choice(["blocks", "requires", "suggests"]), default="requires", help="Dependency type")
@click.option("--reason", required=True, help="Reason for dependency")
@click.option("--safe", is_flag=True, help="Check for cycles before creating")
def create_dependency(task_id: str, depends_on_task_id: str, dep_type: str, reason: str, safe: bool):
    """Create a manual dependency

    Examples:
        agentos task dependencies create task-002 task-001 --type requires --reason "Needs output"
        agentos task dependencies create task-003 task-002 --type blocks --reason "Must wait" --safe
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        # Convert string to enum
        dependency_type = DependencyType(dep_type)

        if safe:
            dep = service.create_dependency_safe(
                task_id=task_id,
                depends_on_task_id=depends_on_task_id,
                dependency_type=dependency_type,
                reason=reason,
                created_by="manual_cli"
            )
        else:
            dep = service.create_dependency(
                task_id=task_id,
                depends_on_task_id=depends_on_task_id,
                dependency_type=dependency_type,
                reason=reason,
                created_by="manual_cli"
            )

        click.echo(f"✓ Created dependency: {task_id} -> {depends_on_task_id} ({dep_type})")
        click.echo(f"  Reason: {reason}")

    except CircularDependencyError as e:
        click.echo(f"✗ Error: {e}", err=True)
        click.echo(f"  Cannot create dependency as it would introduce a cycle", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dependencies_group.command(name="delete")
@click.argument("task_id", required=True)
@click.argument("depends_on_task_id", required=True)
@click.option("--type", "dep_type", type=click.Choice(["blocks", "requires", "suggests"]), help="Dependency type to delete (optional)")
def delete_dependency(task_id: str, depends_on_task_id: str, dep_type: str):
    """Delete a dependency

    Examples:
        agentos task dependencies delete task-002 task-001
        agentos task dependencies delete task-002 task-001 --type requires
    """
    try:
        db = get_db()
        service = TaskDependencyService(db)

        dependency_type = DependencyType(dep_type) if dep_type else None

        deleted = service.delete_dependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            dependency_type=dependency_type
        )

        if deleted:
            type_str = f" ({dep_type})" if dep_type else ""
            click.echo(f"✓ Deleted dependency: {task_id} -> {depends_on_task_id}{type_str}")
        else:
            click.echo(f"✗ Dependency not found: {task_id} -> {depends_on_task_id}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Import cross-repository trace command
from agentos.cli.commands.task_trace import task_trace

# Add trace command to dependencies group as well
dependencies_group.add_command(task_trace, name="trace")


if __name__ == "__main__":
    dependencies_group()
