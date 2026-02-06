"""Resource-aware scheduler for budget-constrained execution."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from agentos.core.scheduler.audit import SchedulerAuditSink, SchedulerEvent
from agentos.core.scheduler.scheduler import Scheduler
from agentos.core.scheduler.task_graph import TaskGraph

console = Console()


class ResourceAwareScheduler(Scheduler):
    """Scheduler with resource budget awareness (v0.3 interface)."""

    def __init__(
        self,
        budget: dict,
        db_path: Optional[Path] = None,
        audit_sink: Optional[SchedulerAuditSink] = None,
    ):
        """
        Initialize resource-aware scheduler.

        Args:
            budget: Resource budget dict
                {
                    "token_budget": 10000,
                    "cost_budget_usd": 1.0,
                    "parallelism_budget": 3
                }
            db_path: Optional database path
            audit_sink: Optional audit sink
        """
        super().__init__(db_path, mode="parallel", audit_sink=audit_sink)
        self.budget = budget
        self.used_tokens = 0
        self.used_cost = 0.0
        self.running_count = 0

    def can_schedule(self, task: dict) -> tuple[bool, str]:
        """
        Check if task can be scheduled within budget.

        Args:
            task: Task definition dict with estimated resources

        Returns:
            (can_schedule, reason) tuple
        """
        estimated_tokens = task.get("estimated_tokens", 0)
        estimated_cost = task.get("estimated_cost", 0.0)

        # Check token budget
        token_budget = self.budget.get("token_budget", float("inf"))
        if self.used_tokens + estimated_tokens > token_budget:
            return False, f"token_budget_exceeded (used={self.used_tokens}, need={estimated_tokens}, limit={token_budget})"

        # Check cost budget
        cost_budget = self.budget.get("cost_budget_usd", float("inf"))
        if self.used_cost + estimated_cost > cost_budget:
            return False, f"cost_budget_exceeded (used=${self.used_cost:.2f}, need=${estimated_cost:.2f}, limit=${cost_budget:.2f})"

        # Check parallelism budget
        parallelism_budget = self.budget.get("parallelism_budget", float("inf"))
        if self.running_count >= parallelism_budget:
            return False, f"parallelism_budget_exceeded (running={self.running_count}, limit={parallelism_budget})"

        return True, "within_budget"

    def record_usage(self, tokens: int, cost: float) -> None:
        """
        Record resource usage.

        Args:
            tokens: Tokens used
            cost: Cost in USD
        """
        self.used_tokens += tokens
        self.used_cost += cost
        self.running_count += 1

    def release_slot(self) -> None:
        """Release a running slot (decrement running count)."""
        self.running_count = max(0, self.running_count - 1)

    def tick(self, graph: TaskGraph, trigger: str = "manual") -> list[str]:
        """
        Perform scheduling tick with resource awareness.

        Args:
            graph: Task graph
            trigger: Trigger reason

        Returns:
            List of selected task IDs to schedule
        """
        # Get ready tasks
        completed: set[str] = set()  # In real implementation, query from DB
        ready = graph.ready_tasks(completed)

        # Sort by priority
        ready_sorted = graph.sort_by_priority(ready)

        # Filter by budget
        selected = []
        rejected = []

        for task_id in ready_sorted:
            task = graph.graph.nodes[task_id]
            can_schedule, reason = self.can_schedule(task)

            if can_schedule:
                selected.append(task_id)
                # Simulate recording usage
                self.record_usage(
                    task.get("estimated_tokens", 0),
                    task.get("estimated_cost", 0.0),
                )
            else:
                rejected.append((task_id, reason))

        # Record audit event
        if self.audit_sink:
            event = SchedulerEvent.create(
                scheduler_mode="parallel",
                trigger=trigger,
                selected_tasks=selected,
                reason={
                    "budget_state": {
                        "used_tokens": self.used_tokens,
                        "used_cost": self.used_cost,
                        "running_count": self.running_count,
                    },
                    "rejected": [{"task_id": tid, "reason": r} for tid, r in rejected],
                },
                decision="schedule_now",
            )
            self.audit_sink.write(event)

        return selected

    def get_budget_status(self) -> dict:
        """
        Get current budget status.

        Returns:
            Budget status dict
        """
        return {
            "token_budget": self.budget.get("token_budget"),
            "used_tokens": self.used_tokens,
            "cost_budget_usd": self.budget.get("cost_budget_usd"),
            "used_cost_usd": self.used_cost,
            "parallelism_budget": self.budget.get("parallelism_budget"),
            "running_count": self.running_count,
        }
