"""Task dependency graph management."""

from __future__ import annotations

from typing import Optional

try:
    import networkx as nx
except ImportError:
    nx = None

from rich.console import Console

from agentos.core.scheduler.audit import TaskNode

console = Console()


class TaskGraph:
    """Manages task dependency graph for scheduling."""

    def __init__(self):
        """Initialize task graph."""
        if nx is None:
            raise ImportError(
                "networkx is required for task scheduling. "
                "Install it with: pip install networkx"
            )
        self.graph = nx.DiGraph()
        self._nodes: dict[str, TaskNode] = {}

    def add_task(self, task_id: str = None, depends_on: list[str] = None, node: TaskNode = None) -> None:
        """
        Add task to graph (v0.3 interface).

        Args:
            task_id: Task ID (used if node not provided)
            depends_on: Dependencies (used if node not provided)
            node: TaskNode instance (preferred)
        """
        if node is not None:
            # Use TaskNode
            task_id = node.task_id
            self._nodes[task_id] = node
            self.graph.add_node(
                task_id,
                task_type=node.task_type,
                policy_mode=node.policy_mode,
                parallelism_group=node.parallelism_group,
                priority=node.priority,
            )
            
            # Add dependencies
            for dep_id in node.depends_on:
                self.graph.add_edge(dep_id, task_id)
        else:
            # Compatibility mode: use task_id and depends_on
            if task_id is None:
                raise ValueError("Either node or task_id must be provided")
            
            depends_on = depends_on or []
            self.graph.add_node(task_id)
            
            for dep_id in depends_on:
                self.graph.add_edge(dep_id, task_id)

    def add_dependency(self, before_task_id: str, after_task_id: str) -> None:
        """
        Add dependency between tasks (v0.3 interface).

        Args:
            before_task_id: Task that must run before
            after_task_id: Task that depends on before_task_id
        """
        self.graph.add_edge(before_task_id, after_task_id)

    def toposort(self) -> list[str]:
        """
        Get topological sort order (v0.3 interface).

        Returns:
            Flat list of task IDs in dependency order
        """
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError as e:
            # Cycle detected
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"Task dependency graph has cycles: {cycles}") from e

    def ready_tasks(self, completed: set[str]) -> list[str]:
        """
        Get tasks that are ready to execute (v0.3 interface).

        Args:
            completed: Set of completed task IDs

        Returns:
            List of task IDs ready to execute
        """
        return self.get_ready_tasks(completed)

    def build(self, tasks: list[dict]) -> nx.DiGraph:
        """
        Build dependency graph from task definitions.

        Args:
            tasks: List of task definition dicts

        Returns:
            Directed graph with task dependencies
        """
        graph = nx.DiGraph()

        # Add nodes
        for task in tasks:
            task_id = task["task_id"]
            graph.add_node(task_id, **task)

            # Add dependency edges
            for dep_id in task.get("depends_on", []):
                graph.add_edge(dep_id, task_id)

        # Check for cycles
        if not nx.is_directed_acyclic_graph(graph):
            cycles = list(nx.simple_cycles(graph))
            raise ValueError(f"Task dependency graph has cycles: {cycles}")

        self.graph = graph
        return graph

    def get_execution_order(self, graph: Optional[nx.DiGraph] = None) -> list[list[str]]:
        """
        Get topological execution order (by layers).

        Args:
            graph: Optional graph (uses self.graph if not provided)

        Returns:
            List of layers, where each layer is a list of task IDs
            that can be executed in parallel
        """
        if graph is None:
            graph = self.graph

        # Use topological generations to get layers
        return list(nx.topological_generations(graph))

    def get_parallelizable_tasks(
        self, layer: list[str], graph: Optional[nx.DiGraph] = None
    ) -> dict[str, list[str]]:
        """
        Group tasks in a layer by parallelism group.

        Args:
            layer: List of task IDs in a layer
            graph: Optional graph (uses self.graph if not provided)

        Returns:
            Dict mapping parallelism group to list of task IDs
        """
        if graph is None:
            graph = self.graph

        groups = {}

        for task_id in layer:
            task = graph.nodes[task_id]
            group = task.get("parallelism_group", "default")

            if group not in groups:
                groups[group] = []

            groups[group].append(task_id)

        return groups

    def get_ready_tasks(self, completed: set[str]) -> list[str]:
        """
        Get tasks that are ready to execute.

        Args:
            completed: Set of completed task IDs

        Returns:
            List of task IDs ready to execute
        """
        ready = []

        for task_id in self.graph.nodes():
            if task_id in completed:
                continue

            # Check if all dependencies are completed
            dependencies = list(self.graph.predecessors(task_id))
            if all(dep in completed for dep in dependencies):
                ready.append(task_id)

        return ready

    def get_task_priority(self, task_id: str) -> int:
        """Get task priority (from node attributes)."""
        return self.graph.nodes[task_id].get("priority", 0)

    def sort_by_priority(self, task_ids: list[str]) -> list[str]:
        """Sort task IDs by priority (descending)."""
        return sorted(task_ids, key=lambda tid: self.get_task_priority(tid), reverse=True)

    def visualize(self, output_path: Optional[str] = None):
        """
        Visualize task graph.

        Args:
            output_path: Optional path to save visualization
        """
        try:
            import matplotlib.pyplot as plt

            pos = nx.spring_layout(self.graph)
            nx.draw(
                self.graph,
                pos,
                with_labels=True,
                node_color="lightblue",
                node_size=2000,
                font_size=10,
                font_weight="bold",
                arrows=True,
            )

            if output_path:
                plt.savefig(output_path)
                console.print(f"[green]✓ Graph visualization saved:[/green] {output_path}")
            else:
                plt.show()

        except ImportError:
            console.print("[yellow]matplotlib not installed, cannot visualize[/yellow]")

    def check_conflicts(self, task_id: str, running: set[str]) -> bool:
        """
        Check if task conflicts with any running tasks.

        Args:
            task_id: Task to check
            running: Set of currently running task IDs

        Returns:
            True if there's a conflict, False otherwise
        """
        task = self.graph.nodes[task_id]
        conflicts_with = set(task.get("conflicts_with", []))

        return bool(conflicts_with & running)
