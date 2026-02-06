"""Task scheduler with multiple execution strategies."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

from agentos.core.scheduler.audit import SchedulerAuditSink, SchedulerEvent
from agentos.core.scheduler.task_graph import TaskGraph

console = Console()


class Scheduler:
    """High-level task scheduler with multiple execution modes."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        mode: str = "sequential",
        audit_sink: Optional[SchedulerAuditSink] = None,
    ):
        """
        Initialize scheduler.

        Args:
            db_path: Optional database path
            mode: Scheduler mode (sequential/parallel/cron/mixed)
            audit_sink: Optional audit sink for recording events
        """
        self.db_path = db_path
        self.mode = mode
        self.task_graph = TaskGraph()
        self.audit_sink = audit_sink or SchedulerAuditSink()

    def record_scheduling_event(self, event: SchedulerEvent) -> None:
        """
        Record scheduling event to audit log.

        Args:
            event: Scheduler event to record

        Raises:
            ValueError: If event is missing required fields
        """
        # Validate required fields
        required_fields = ["scheduler_mode", "task_id" if hasattr(event, "task_id") else "selected_tasks", 
                          "timestamp" if hasattr(event, "timestamp") else "ts", "trigger", "decision"]
        
        event_dict = event.to_dict() if hasattr(event, "to_dict") else {}
        
        # Check essential fields exist
        if not event.scheduler_mode:
            raise ValueError("Missing required field: scheduler_mode")
        if not event.trigger:
            raise ValueError("Missing required field: trigger")
        if not hasattr(event, "decision") or not event.decision:
            raise ValueError("Missing required field: decision")

        self.audit_sink.write(event)

    def get_scheduling_events(self) -> list[SchedulerEvent]:
        """
        Get all recorded scheduling events.

        Returns:
            List of scheduler events
        """
        return self.audit_sink.get_events()

    def schedule_sequential(
        self, tasks: list[dict], execute_fn: Callable[[dict], bool]
    ) -> dict:
        """
        Execute tasks sequentially in dependency order.

        Args:
            tasks: List of task definitions
            execute_fn: Function to execute a task (returns True on success)

        Returns:
            Execution summary dict
        """
        console.print("[cyan]Starting sequential execution...[/cyan]")

        graph = self.task_graph.build(tasks)
        layers = self.task_graph.get_execution_order(graph)

        results = {
            "total_tasks": len(tasks),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "task_results": {},
        }

        for layer_idx, layer in enumerate(layers):
            console.print(f"\n[bold]Layer {layer_idx + 1}:[/bold] {', '.join(layer)}")

            for task_id in layer:
                task = graph.nodes[task_id]
                console.print(f"\n[cyan]Executing:[/cyan] {task_id}")

                # Record scheduling event
                event = SchedulerEvent.create(
                    scheduler_mode="sequential",
                    trigger="dependency_satisfied",
                    selected_tasks=[task_id],
                    reason={"layer": layer_idx, "dependencies_met": True},
                    decision="schedule_now",
                )
                self.record_scheduling_event(event)

                try:
                    success = execute_fn(task)
                    if success:
                        results["completed"] += 1
                        results["task_results"][task_id] = "SUCCESS"
                        console.print(f"[green]✓ {task_id} completed[/green]")
                    else:
                        results["failed"] += 1
                        results["task_results"][task_id] = "FAILED"
                        console.print(f"[red]✗ {task_id} failed[/red]")
                except Exception as e:
                    results["failed"] += 1
                    results["task_results"][task_id] = f"ERROR: {e}"
                    console.print(f"[red]✗ {task_id} error: {e}[/red]")

        return results

    def schedule_parallel(
        self,
        tasks: list[dict],
        execute_fn: Callable[[dict], bool],
        max_workers: int = 4,
    ) -> dict:
        """
        Execute tasks in parallel (respecting dependencies and file locks).

        Args:
            tasks: List of task definitions
            execute_fn: Function to execute a task
            max_workers: Maximum parallel workers

        Returns:
            Execution summary dict
        """
        console.print(f"[cyan]Starting parallel execution (max {max_workers} workers)...[/cyan]")

        graph = self.task_graph.build(tasks)
        layers = self.task_graph.get_execution_order(graph)

        results = {
            "total_tasks": len(tasks),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "task_results": {},
        }

        for layer_idx, layer in enumerate(layers):
            console.print(f"\n[bold]Layer {layer_idx + 1}:[/bold] {', '.join(layer)}")

            # Group by parallelism group
            groups = self.task_graph.get_parallelizable_tasks(layer, graph)

            for group_name, task_ids in groups.items():
                console.print(f"[cyan]Parallel group:[/cyan] {group_name}")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}

                    for task_id in task_ids:
                        task = graph.nodes[task_id]
                        future = executor.submit(execute_fn, task)
                        futures[future] = task_id

                    # Wait for completion
                    for future in as_completed(futures):
                        task_id = futures[future]

                        try:
                            success = future.result()
                            if success:
                                results["completed"] += 1
                                results["task_results"][task_id] = "SUCCESS"
                                console.print(f"[green]✓ {task_id} completed[/green]")
                            else:
                                results["failed"] += 1
                                results["task_results"][task_id] = "FAILED"
                                console.print(f"[red]✗ {task_id} failed[/red]")
                        except Exception as e:
                            results["failed"] += 1
                            results["task_results"][task_id] = f"ERROR: {e}"
                            console.print(f"[red]✗ {task_id} error: {e}[/red]")

        return results

    def schedule_cron(
        self,
        cron_tasks: list[dict],
        execute_fn: Callable[[dict], bool],
        check_interval: int = 60,
    ):
        """
        Schedule tasks using cron expressions.

        Args:
            cron_tasks: List of task definitions with 'schedule' field
            execute_fn: Function to execute a task
            check_interval: Check interval in seconds

        Note: This runs indefinitely. Use Ctrl+C to stop.
        """
        try:
            from croniter import croniter
        except ImportError:
            console.print(
                "[red]croniter is required for cron scheduling. "
                "Install it with: pip install croniter[/red]"
            )
            return

        console.print("[cyan]Starting cron scheduler...[/cyan]")
        console.print(f"[dim]Check interval: {check_interval}s[/dim]")

        # Initialize cron iterators
        cron_iters = {}
        for task in cron_tasks:
            task_id = task["task_id"]
            schedule = task.get("schedule")

            if not schedule:
                console.print(f"[yellow]Warning: Task {task_id} has no schedule, skipping[/yellow]")
                continue

            try:
                cron_iters[task_id] = {
                    "task": task,
                    "croniter": croniter(schedule, datetime.now()),
                }
                console.print(f"[green]✓ Scheduled:[/green] {task_id} ({schedule})")
            except Exception as e:
                console.print(f"[red]✗ Invalid cron for {task_id}: {e}[/red]")

        # Main loop
        try:
            while True:
                now = datetime.now()

                for task_id, cron_data in cron_iters.items():
                    next_run = cron_data["croniter"].get_next(datetime)

                    if next_run <= now:
                        task = cron_data["task"]
                        console.print(f"\n[cyan]Cron trigger:[/cyan] {task_id}")

                        try:
                            execute_fn(task)
                        except Exception as e:
                            console.print(f"[red]✗ Cron execution error: {e}[/red]")

                        # Reset croniter
                        cron_data["croniter"] = croniter(
                            task.get("schedule"), datetime.now()
                        )

                time.sleep(check_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Cron scheduler stopped[/yellow]")

    def schedule_mixed(
        self,
        tasks: list[dict],
        execute_fn: Callable[[dict], bool],
        max_workers: int = 4,
    ) -> dict:
        """
        Mixed mode: Execute tasks with different execution modes.

        - full_auto: Execute immediately in parallel
        - semi_auto: Execute with blocker detection
        - interactive: Queue for manual review

        Args:
            tasks: List of task definitions
            execute_fn: Function to execute a task
            max_workers: Maximum parallel workers

        Returns:
            Execution summary dict
        """
        console.print("[cyan]Starting mixed-mode execution...[/cyan]")

        # Group by execution mode
        full_auto = [t for t in tasks if t.get("execution_mode") == "full_auto"]
        semi_auto = [t for t in tasks if t.get("execution_mode") == "semi_auto"]
        interactive = [t for t in tasks if t.get("execution_mode") == "interactive"]

        results = {
            "total_tasks": len(tasks),
            "completed": 0,
            "failed": 0,
            "blocked": 0,
            "queued": len(interactive),
            "task_results": {},
        }

        # 1. Execute full_auto tasks in parallel
        if full_auto:
            console.print(f"\n[bold]Full-auto tasks ({len(full_auto)}):[/bold]")
            full_auto_results = self.schedule_parallel(full_auto, execute_fn, max_workers)
            results["completed"] += full_auto_results["completed"]
            results["failed"] += full_auto_results["failed"]
            results["task_results"].update(full_auto_results["task_results"])

        # 2. Execute semi_auto tasks (stop on blocker)
        if semi_auto:
            console.print(f"\n[bold]Semi-auto tasks ({len(semi_auto)}):[/bold]")

            for task in semi_auto:
                task_id = task["task_id"]
                console.print(f"\n[cyan]Executing:[/cyan] {task_id}")

                try:
                    success = execute_fn(task)
                    if success:
                        results["completed"] += 1
                        results["task_results"][task_id] = "SUCCESS"
                    else:
                        results["blocked"] += 1
                        results["task_results"][task_id] = "BLOCKED"
                        console.print(f"[yellow]⚠ {task_id} blocked, stopping semi-auto[/yellow]")
                        break
                except Exception as e:
                    results["blocked"] += 1
                    results["task_results"][task_id] = f"BLOCKED: {e}"
                    console.print(f"[yellow]⚠ {task_id} blocked: {e}[/yellow]")
                    break

        # 3. Interactive tasks are just queued
        if interactive:
            console.print(f"\n[bold]Interactive tasks ({len(interactive)}) queued for manual review[/bold]")
            for task in interactive:
                results["task_results"][task["task_id"]] = "QUEUED"

        return results
