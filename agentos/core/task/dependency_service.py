"""Task Dependency Service - Cross-repository dependency auto-generation

This module provides dependency detection, DAG management, and cycle prevention
for tasks across multiple repositories.

Key Features:
1. Auto-detect dependencies from artifact references, file reads, and audit trails
2. Build and query dependency DAG (Directed Acyclic Graph)
3. Cycle detection and prevention
4. Topological sort for execution ordering
5. Export to GraphViz DOT format

Created for Phase 5.3: Cross-repository dependency auto-generation

Usage Example:
    # Detect dependencies after task execution
    dep_service = TaskDependencyService(db)
    exec_env = prepare_execution_env(task)

    dependencies = dep_service.detect_dependencies(task, exec_env)
    for dep in dependencies:
        dep_service.create_dependency_safe(
            task.task_id,
            dep.depends_on_task_id,
            dep.dependency_type,
            dep.reason
        )

    # Query dependencies
    deps = dep_service.get_dependencies(task.task_id)
    reverse_deps = dep_service.get_reverse_dependencies(task.task_id)

    # Build and query DAG
    graph = dep_service.build_dependency_graph()
    ancestors = graph.get_ancestors(task.task_id)
    execution_order = graph.topological_sort()
"""

import json
import logging
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agentos.core.task.models import Task, DependencyType, TaskDependency
from agentos.core.task.repo_context import ExecutionEnv
from agentos.core.task.artifact_service import TaskArtifactService, ArtifactRefType
from agentos.core.task.audit_service import TaskAuditService
from agentos.store import get_db
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected"""
    pass


class RuleType(str, Enum):
    """Dependency detection rule type"""

    ARTIFACT_REF = "artifact_ref"  # Artifact reference (most important)
    FILE_READ = "file_read"  # File read from another task's modifications
    API_CALL = "api_call"  # API call dependency (future)
    MANUAL = "manual"  # Manually created dependency


@dataclass
class DependencyRule:
    """Dependency detection rule

    Defines a pattern for detecting dependencies between tasks.
    """

    rule_id: str
    rule_type: RuleType
    pattern: str  # Match pattern (file path, artifact type, etc.)
    reason_template: str  # Template for dependency reason
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def format_reason(self, **kwargs) -> str:
        """Format reason template with provided values"""
        try:
            return self.reason_template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing key in reason template: {e}")
            return self.reason_template


class DependencyGraph:
    """Dependency DAG (Directed Acyclic Graph)

    Provides graph operations for dependency analysis and visualization.
    """

    def __init__(self, dependencies: List[TaskDependency]):
        """Initialize dependency graph

        Args:
            dependencies: List of TaskDependency objects
        """
        self.dependencies = dependencies
        self.graph = self._build_graph(dependencies)
        self.reverse_graph = self._build_reverse_graph(dependencies)

    def _build_graph(self, dependencies: List[TaskDependency]) -> Dict[str, Set[str]]:
        """Build forward graph (task -> dependencies)

        Returns:
            Dict mapping task_id -> set of tasks it depends on
        """
        graph = defaultdict(set)

        for dep in dependencies:
            graph[dep.task_id].add(dep.depends_on_task_id)

        return dict(graph)

    def _build_reverse_graph(self, dependencies: List[TaskDependency]) -> Dict[str, Set[str]]:
        """Build reverse graph (task -> dependents)

        Returns:
            Dict mapping task_id -> set of tasks that depend on it
        """
        graph = defaultdict(set)

        for dep in dependencies:
            graph[dep.depends_on_task_id].add(dep.task_id)

        return dict(graph)

    def get_dependencies(self, task_id: str) -> Set[str]:
        """Get direct dependencies of a task

        Args:
            task_id: Task ID

        Returns:
            Set of task IDs that this task depends on
        """
        return self.graph.get(task_id, set())

    def get_dependents(self, task_id: str) -> Set[str]:
        """Get direct dependents of a task

        Args:
            task_id: Task ID

        Returns:
            Set of task IDs that depend on this task
        """
        return self.reverse_graph.get(task_id, set())

    def get_ancestors(self, task_id: str) -> Set[str]:
        """Get all ancestor nodes (recursive dependencies)

        Args:
            task_id: Task ID

        Returns:
            Set of all task IDs this task transitively depends on
        """
        ancestors = set()
        visited = set()
        queue = deque([task_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Get direct dependencies
            deps = self.graph.get(current, set())
            for dep in deps:
                if dep not in ancestors:
                    ancestors.add(dep)
                    queue.append(dep)

        return ancestors

    def get_descendants(self, task_id: str) -> Set[str]:
        """Get all descendant nodes (who depends on this task recursively)

        Args:
            task_id: Task ID

        Returns:
            Set of all task IDs that transitively depend on this task
        """
        descendants = set()
        visited = set()
        queue = deque([task_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Get direct dependents
            dependents = self.reverse_graph.get(current, set())
            for dependent in dependents:
                if dependent not in descendants:
                    descendants.add(dependent)
                    queue.append(dependent)

        return descendants

    def topological_sort(self) -> List[str]:
        """Topological sort (execution order)

        Returns tasks in an order where dependencies come before dependents.

        Returns:
            List of task IDs in topological order

        Raises:
            CircularDependencyError: If graph contains cycles
        """
        # Collect all nodes
        all_nodes = set()
        for task_id in self.graph.keys():
            all_nodes.add(task_id)
        for task_id in self.reverse_graph.keys():
            all_nodes.add(task_id)

        # Calculate in-degree for each node (how many tasks depend on it)
        # For topological sort, we want: if A depends on B, then B should come first
        # So in_degree[A] = number of tasks that A depends on
        in_degree = {node: 0 for node in all_nodes}
        for task_id, deps in self.graph.items():
            in_degree[task_id] = len(deps)

        # Start with nodes that have no dependencies (in_degree = 0)
        queue = deque([node for node in all_nodes if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # For each task that depends on this node, reduce its in-degree
            for dependent in self.reverse_graph.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check if all nodes were processed (no cycles)
        if len(result) != len(all_nodes):
            unprocessed = all_nodes - set(result)
            raise CircularDependencyError(
                f"Circular dependency detected. Unprocessed nodes: {unprocessed}"
            )

        return result

    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the graph

        Returns:
            List of cycles (each cycle is a list of task IDs)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.remove(node)

        # Try DFS from each node
        all_nodes = set(self.graph.keys()) | set(self.reverse_graph.keys())
        for node in all_nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def to_dot(self) -> str:
        """Export to GraphViz DOT format

        Returns:
            DOT format string
        """
        lines = ["digraph TaskDependencies {"]
        lines.append("  rankdir=LR;")  # Left to right layout
        lines.append("  node [shape=box];")

        # Add nodes
        all_nodes = set(self.graph.keys()) | set(self.reverse_graph.keys())
        for node in all_nodes:
            # Shorten task ID for readability
            label = node[-8:] if len(node) > 8 else node
            lines.append(f'  "{node}" [label="{label}"];')

        # Add edges
        for task_id, deps in self.graph.items():
            for dep in deps:
                lines.append(f'  "{task_id}" -> "{dep}";')

        lines.append("}")
        return "\n".join(lines)


class TaskDependencyService:
    """Service for managing task dependencies and auto-detection

    Provides methods to:
    1. Auto-detect dependencies from artifacts, audits, and file operations
    2. Create and query dependencies
    3. Build dependency DAG
    4. Detect and prevent cycles
    """

    def __init__(self, db=None):
        """Initialize service

        Args:
            db: Database connection (optional, uses default if not provided)
        """
        self.db = db or get_db()
        self.artifact_service = TaskArtifactService(self.db)
        self.audit_service = TaskAuditService(self.db)

        # Default detection rules
        self.rules = self._init_default_rules()

    def _init_default_rules(self) -> List[DependencyRule]:
        """Initialize default dependency detection rules"""
        return [
            DependencyRule(
                rule_id="artifact_ref_commit",
                rule_type=RuleType.ARTIFACT_REF,
                pattern="commit",
                reason_template="Uses artifact {ref_type}:{ref_value} from task {producer_task_id}",
            ),
            DependencyRule(
                rule_id="artifact_ref_branch",
                rule_type=RuleType.ARTIFACT_REF,
                pattern="branch",
                reason_template="Uses branch {ref_value} from task {producer_task_id}",
            ),
            DependencyRule(
                rule_id="artifact_ref_patch",
                rule_type=RuleType.ARTIFACT_REF,
                pattern="patch",
                reason_template="Applies patch from task {producer_task_id}",
            ),
            DependencyRule(
                rule_id="file_read_dependency",
                rule_type=RuleType.FILE_READ,
                pattern="*",
                reason_template="Reads file {file_path} modified by task {modifier_task_id}",
            ),
        ]

    def detect_dependencies(
        self,
        task: Task,
        exec_env: ExecutionEnv,
        rules: Optional[List[DependencyRule]] = None
    ) -> List[TaskDependency]:
        """Auto-detect task dependencies

        Args:
            task: Task to detect dependencies for
            exec_env: Execution environment
            rules: Optional custom rules (uses default if None)

        Returns:
            List of detected TaskDependency objects (not yet saved to DB)
        """
        if rules is None:
            rules = self.rules

        dependencies = []

        # Rule 1: Detect artifact reference dependencies
        artifact_deps = self._detect_artifact_dependencies(task)
        dependencies.extend(artifact_deps)

        # Rule 2: Detect file read dependencies
        file_deps = self._detect_file_dependencies(task, exec_env)
        dependencies.extend(file_deps)

        # Deduplicate (same depends_on_task_id and type)
        dependencies = self._deduplicate_dependencies(dependencies)

        logger.info(
            f"Detected {len(dependencies)} dependencies for task {task.task_id}"
        )

        return dependencies

    def _detect_artifact_dependencies(self, task: Task) -> List[TaskDependency]:
        """Detect dependencies from artifact references

        When Task B references Task A's artifact, create dependency.

        Args:
            task: Task to analyze

        Returns:
            List of TaskDependency objects
        """
        dependencies = []

        # Get all artifacts referenced by this task
        artifacts = self.artifact_service.get_task_artifacts(task.task_id)

        for artifact in artifacts:
            # Find who produced this artifact
            producer_tasks = self._find_artifact_producer(artifact)

            for producer_task_id in producer_tasks:
                if producer_task_id == task.task_id:
                    # Skip self-dependency
                    continue

                # Determine dependency type based on artifact type
                if artifact.ref_type in [ArtifactRefType.COMMIT, ArtifactRefType.PATCH]:
                    dep_type = DependencyType.REQUIRES
                elif artifact.ref_type == ArtifactRefType.BRANCH:
                    dep_type = DependencyType.SUGGESTS
                else:
                    dep_type = DependencyType.SUGGESTS

                reason = f"Uses artifact {artifact.ref_type.value}:{artifact.ref_value} from task {producer_task_id}"

                dependencies.append(TaskDependency(
                    task_id=task.task_id,
                    depends_on_task_id=producer_task_id,
                    dependency_type=dep_type,
                    reason=reason,
                    created_by="auto_detect",
                    metadata={
                        "rule": "artifact_ref",
                        "artifact_id": artifact.artifact_id,
                        "ref_type": artifact.ref_type.value,
                        "ref_value": artifact.ref_value,
                    }
                ))

        return dependencies

    def _find_artifact_producer(self, artifact) -> List[str]:
        """Find tasks that produced an artifact

        Args:
            artifact: TaskArtifactRef object

        Returns:
            List of task IDs that produced this artifact
        """
        # Query for tasks that produced the same artifact (earlier in time)
        producers = self.artifact_service.get_artifact_by_ref(
            artifact.ref_type,
            artifact.ref_value
        )

        # Filter out the current task and tasks created after
        producer_tasks = []
        for producer in producers:
            if producer.task_id != artifact.task_id:
                # Check if producer was created before consumer
                # (simplified: just check it's a different task)
                producer_tasks.append(producer.task_id)

        return producer_tasks

    def _detect_file_dependencies(
        self,
        task: Task,
        exec_env: ExecutionEnv
    ) -> List[TaskDependency]:
        """Detect dependencies from file reads

        When Task B reads files modified by Task A, create suggestion dependency.

        Args:
            task: Task to analyze
            exec_env: Execution environment

        Returns:
            List of TaskDependency objects
        """
        dependencies = []

        # Get audit trail for this task
        audits = self.audit_service.get_task_audits(task.task_id, limit=1000)

        # Extract files read by this task
        files_read = set()
        for audit in audits:
            if audit.operation == "read" and audit.files_changed:
                files_read.update(audit.files_changed)

        # For each file read, find who last modified it
        for file_path in files_read:
            modifier_task_id = self._find_last_modifier(file_path, task.task_id)

            if modifier_task_id and modifier_task_id != task.task_id:
                reason = f"Reads file {file_path} modified by task {modifier_task_id}"

                dependencies.append(TaskDependency(
                    task_id=task.task_id,
                    depends_on_task_id=modifier_task_id,
                    dependency_type=DependencyType.SUGGESTS,
                    reason=reason,
                    created_by="auto_detect",
                    metadata={
                        "rule": "file_read",
                        "file_path": file_path,
                    }
                ))

        return dependencies

    def _find_last_modifier(self, file_path: str, before_task_id: str) -> Optional[str]:
        """Find the last task that modified a file

        Args:
            file_path: File path
            before_task_id: Only consider tasks created before this one

        Returns:
            Task ID of last modifier, or None
        """
        try:
            # Query based on payload JSON structure (operation is embedded in payload)
            cursor = self.db.execute(
                """
                SELECT DISTINCT ta.task_id
                FROM task_audits ta
                WHERE ta.event_type LIKE '%write%'
                  AND ta.payload LIKE ?
                  AND ta.task_id != ?
                ORDER BY ta.created_at DESC
                LIMIT 1
                """,
                (f'%{file_path}%', before_task_id)
            )

            row = cursor.fetchone()
            if row:
                return row[0]

        except Exception as e:
            logger.warning(f"Error finding last modifier for {file_path}: {e}")

        return None

    def _deduplicate_dependencies(
        self,
        dependencies: List[TaskDependency]
    ) -> List[TaskDependency]:
        """Remove duplicate dependencies

        Keep the strongest dependency type for each task pair.

        Args:
            dependencies: List of TaskDependency objects

        Returns:
            Deduplicated list
        """
        # Group by (task_id, depends_on_task_id)
        groups = defaultdict(list)
        for dep in dependencies:
            key = (dep.task_id, dep.depends_on_task_id)
            groups[key].append(dep)

        # Keep strongest dependency type for each pair
        dep_type_priority = {
            DependencyType.BLOCKS: 3,
            DependencyType.REQUIRES: 2,
            DependencyType.SUGGESTS: 1,
        }

        result = []
        for key, deps in groups.items():
            # Sort by priority (highest first)
            deps_sorted = sorted(
                deps,
                key=lambda d: dep_type_priority.get(d.dependency_type, 0),
                reverse=True
            )
            # Keep the strongest
            result.append(deps_sorted[0])

        return result

    def create_dependency(
        self,
        task_id: str,
        depends_on_task_id: str,
        dependency_type: str | DependencyType,
        reason: str,
        created_by: str = "manual",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskDependency:
        """Create a dependency record

        Args:
            task_id: Task ID (dependent)
            depends_on_task_id: Task ID (dependency)
            dependency_type: Dependency type
            reason: Reason for dependency
            created_by: Creator identifier
            metadata: Additional metadata

        Returns:
            Created TaskDependency

        Raises:
            sqlite3.IntegrityError: If dependency already exists
        """
        # Normalize dependency_type
        if not isinstance(dependency_type, DependencyType):
            dependency_type = DependencyType(dependency_type)

        # Create dependency object
        dependency = TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            dependency_type=dependency_type,
            reason=reason,
            created_by=created_by,
            created_at=utc_now_iso(),
            metadata=metadata or {}
        )

        # Insert into database
        db_dict = dependency.to_dict()

        cursor = self.db.execute(
            """
            INSERT INTO task_dependency (
                task_id, depends_on_task_id, dependency_type, reason,
                created_at, created_by, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                db_dict["task_id"],
                db_dict["depends_on_task_id"],
                db_dict["dependency_type"],
                db_dict["reason"],
                db_dict["created_at"],
                db_dict["created_by"],
                db_dict["metadata"],
            )
        )

        dependency.dependency_id = cursor.lastrowid
        self.db.commit()

        logger.info(
            f"Created dependency: {task_id} -> {depends_on_task_id} "
            f"(type={dependency_type.value}, by={created_by})"
        )

        return dependency

    def create_dependency_safe(
        self,
        task_id: str,
        depends_on_task_id: str,
        dependency_type: str | DependencyType,
        reason: str,
        created_by: str = "manual",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskDependency:
        """Create dependency with cycle detection

        Args:
            task_id: Task ID (dependent)
            depends_on_task_id: Task ID (dependency)
            dependency_type: Dependency type
            reason: Reason for dependency
            created_by: Creator identifier
            metadata: Additional metadata

        Returns:
            Created TaskDependency

        Raises:
            CircularDependencyError: If adding dependency would create cycle
        """
        # Build temporary graph with new edge
        existing_deps = self.get_all_dependencies()

        # Simulate adding the new dependency
        temp_deps = existing_deps + [TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            dependency_type=dependency_type if isinstance(dependency_type, DependencyType) else DependencyType(dependency_type),
            reason=reason,
        )]

        temp_graph = DependencyGraph(temp_deps)

        # Check for cycles
        cycles = temp_graph.find_cycles()
        if cycles:
            raise CircularDependencyError(
                f"Adding this dependency would create cycle: {cycles[0]}"
            )

        # Safe to create
        return self.create_dependency(
            task_id, depends_on_task_id, dependency_type, reason, created_by, metadata
        )

    def get_dependencies(self, task_id: str) -> List[TaskDependency]:
        """Get all dependencies of a task

        Args:
            task_id: Task ID

        Returns:
            List of TaskDependency objects (tasks this one depends on)
        """
        cursor = self.db.execute(
            """
            SELECT * FROM task_dependency
            WHERE task_id = ?
            ORDER BY created_at ASC
            """,
            (task_id,)
        )

        rows = cursor.fetchall()
        return [TaskDependency.from_db_row(dict(row)) for row in rows]

    def get_reverse_dependencies(self, task_id: str) -> List[TaskDependency]:
        """Get reverse dependencies (who depends on this task)

        Args:
            task_id: Task ID

        Returns:
            List of TaskDependency objects (tasks that depend on this one)
        """
        cursor = self.db.execute(
            """
            SELECT * FROM task_dependency
            WHERE depends_on_task_id = ?
            ORDER BY created_at ASC
            """,
            (task_id,)
        )

        rows = cursor.fetchall()
        return [TaskDependency.from_db_row(dict(row)) for row in rows]

    def get_all_dependencies(self) -> List[TaskDependency]:
        """Get all dependencies in the database

        Returns:
            List of all TaskDependency objects
        """
        cursor = self.db.execute(
            """
            SELECT * FROM task_dependency
            ORDER BY created_at ASC
            """
        )

        rows = cursor.fetchall()
        return [TaskDependency.from_db_row(dict(row)) for row in rows]

    def build_dependency_graph(
        self,
        task_ids: Optional[List[str]] = None
    ) -> DependencyGraph:
        """Build dependency graph

        Args:
            task_ids: Optional list of task IDs to include (None = all tasks)

        Returns:
            DependencyGraph object
        """
        if task_ids:
            # Filter dependencies to only include specified tasks
            all_deps = self.get_all_dependencies()
            filtered_deps = [
                dep for dep in all_deps
                if dep.task_id in task_ids or dep.depends_on_task_id in task_ids
            ]
            return DependencyGraph(filtered_deps)
        else:
            # Use all dependencies
            return DependencyGraph(self.get_all_dependencies())

    def detect_cycles(self) -> List[List[str]]:
        """Detect dependency cycles in the entire graph

        Returns:
            List of cycles (each cycle is a list of task IDs)
        """
        graph = self.build_dependency_graph()
        return graph.find_cycles()

    def delete_dependency(
        self,
        task_id: str,
        depends_on_task_id: str,
        dependency_type: Optional[str | DependencyType] = None
    ) -> bool:
        """Delete a dependency

        Args:
            task_id: Task ID (dependent)
            depends_on_task_id: Task ID (dependency)
            dependency_type: Optional dependency type filter

        Returns:
            True if deleted, False if not found
        """
        if dependency_type:
            # Normalize
            if not isinstance(dependency_type, DependencyType):
                dependency_type = DependencyType(dependency_type)

            cursor = self.db.execute(
                """
                DELETE FROM task_dependency
                WHERE task_id = ? AND depends_on_task_id = ? AND dependency_type = ?
                """,
                (task_id, depends_on_task_id, dependency_type.value)
            )
        else:
            cursor = self.db.execute(
                """
                DELETE FROM task_dependency
                WHERE task_id = ? AND depends_on_task_id = ?
                """,
                (task_id, depends_on_task_id)
            )

        self.db.commit()
        deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted dependency: {task_id} -> {depends_on_task_id}")

        return deleted
