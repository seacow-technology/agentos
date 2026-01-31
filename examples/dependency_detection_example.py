"""Example: Automatic Dependency Detection with TaskRunner

This example demonstrates how to integrate Phase 5.3 dependency detection
into the task execution pipeline.

Scenario:
1. Task A creates a commit in backend repo
2. Task B references Task A's commit and modifies frontend
3. Task C reads files from both repos
4. Dependency detection auto-creates: C -> B, C -> A, B -> A
5. DAG visualization shows execution order

Usage:
    python examples/dependency_detection_example.py
"""

import sqlite3
from pathlib import Path
from datetime import datetime

from agentos.core.task.dependency_service import TaskDependencyService, CircularDependencyError
from agentos.core.task.artifact_service import TaskArtifactService
from agentos.core.task.audit_service import TaskAuditService
from agentos.core.task.models import Task, DependencyType
from agentos.core.task.repo_context import ExecutionEnv, TaskRepoContext, RepoScopeType


def create_test_database(db_path: Path):
    """Create test database with schema"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'created',
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS task_dependency (
            dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            depends_on_task_id TEXT NOT NULL,
            dependency_type TEXT NOT NULL DEFAULT 'blocks',
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            metadata TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
            UNIQUE(task_id, depends_on_task_id, dependency_type),
            CHECK (task_id != depends_on_task_id),
            CHECK (dependency_type IN ('blocks', 'requires', 'suggests'))
        );

        CREATE TABLE IF NOT EXISTS task_artifact_ref (
            artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            ref_type TEXT NOT NULL,
            ref_value TEXT NOT NULL,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            UNIQUE(task_id, repo_id, ref_type, ref_value),
            CHECK (ref_type IN ('commit', 'branch', 'pr', 'patch', 'file', 'tag'))
        );

        CREATE TABLE IF NOT EXISTS task_audits (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            repo_id TEXT,
            level TEXT DEFAULT 'info',
            event_type TEXT NOT NULL,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_type_value
        ON task_artifact_ref(ref_type, ref_value);
    """)

    conn.commit()
    return conn


def execute_task_with_dependency_detection(
    task: Task,
    exec_env: ExecutionEnv,
    dep_service: TaskDependencyService,
    artifact_service: TaskArtifactService,
    audit_service: TaskAuditService
):
    """Execute task and auto-detect dependencies

    This is what would be integrated into TaskRunner._execute_stage()
    """
    print(f"\n{'='*60}")
    print(f"Executing: {task.title} ({task.task_id})")
    print(f"{'='*60}")

    # Step 1: Execute task logic (simulated here)
    # In real TaskRunner, this would be the actual task execution
    print("  [1] Running task logic...")

    # Step 2: Record artifacts created by task
    # (This would happen during actual execution)
    print("  [2] Recording artifacts...")

    # Step 3: Record audit trail
    # (This would happen during file operations)
    print("  [3] Recording audit trail...")

    # Step 4: Auto-detect dependencies
    print("  [4] Detecting dependencies...")
    dependencies = dep_service.detect_dependencies(task, exec_env)

    if dependencies:
        print(f"      Found {len(dependencies)} potential dependencies:")
        for dep in dependencies:
            print(f"        - {dep.task_id} -> {dep.depends_on_task_id} ({dep.dependency_type.value})")
            print(f"          Reason: {dep.reason}")
    else:
        print("      No dependencies detected")

    # Step 5: Save dependencies (with cycle check)
    print("  [5] Saving dependencies...")
    saved_count = 0
    for dep in dependencies:
        try:
            dep_service.create_dependency_safe(
                task_id=dep.task_id,
                depends_on_task_id=dep.depends_on_task_id,
                dependency_type=dep.dependency_type,
                reason=dep.reason,
                created_by="auto_detect"
            )
            saved_count += 1
        except CircularDependencyError as e:
            print(f"      ✗ Skipped circular dependency: {e}")
        except Exception as e:
            print(f"      ✗ Error saving dependency: {e}")

    print(f"      Saved {saved_count}/{len(dependencies)} dependencies")
    print("  [✓] Task execution complete")


def main():
    """Run example workflow"""
    print("\n" + "="*70)
    print("Phase 5.3: Cross-Repository Dependency Auto-Detection Example")
    print("="*70)

    # Setup
    db_path = Path("example_dependencies.db")
    if db_path.exists():
        db_path.unlink()

    db = create_test_database(db_path)

    dep_service = TaskDependencyService(db)
    artifact_service = TaskArtifactService(db)
    audit_service = TaskAuditService(db)

    # Create tasks
    print("\n[Setup] Creating tasks...")
    tasks = []

    task_a = Task(task_id="task-backend-001", title="Add user authentication API")
    db.execute("INSERT INTO tasks (task_id, title) VALUES (?, ?)", (task_a.task_id, task_a.title))
    tasks.append(task_a)

    task_b = Task(task_id="task-frontend-002", title="Integrate auth API in UI")
    db.execute("INSERT INTO tasks (task_id, title) VALUES (?, ?)", (task_b.task_id, task_b.title))
    tasks.append(task_b)

    task_c = Task(task_id="task-docs-003", title="Document authentication flow")
    db.execute("INSERT INTO tasks (task_id, title) VALUES (?, ?)", (task_c.task_id, task_c.title))
    tasks.append(task_c)

    db.commit()
    print(f"  Created {len(tasks)} tasks")

    # Scenario: Execute Task A
    print("\n" + "-"*70)
    print("SCENARIO: Task A creates backend API")
    print("-"*70)

    exec_env_a = ExecutionEnv(task_id=task_a.task_id)

    # Task A creates a commit
    artifact_service.create_commit_ref(
        task_id=task_a.task_id,
        repo_id="backend-repo",
        commit_hash="abc123def456",
        summary="Added /api/auth endpoints",
        metadata={"files_changed": ["src/api/auth.py", "tests/test_auth.py"]}
    )

    # Task A writes files
    audit_service.record_operation(
        task_id=task_a.task_id,
        operation="write",
        repo_id="backend-repo",
        files_changed=["src/api/auth.py", "tests/test_auth.py"],
        lines_added=150,
    )

    execute_task_with_dependency_detection(
        task_a, exec_env_a, dep_service, artifact_service, audit_service
    )

    # Scenario: Execute Task B
    print("\n" + "-"*70)
    print("SCENARIO: Task B integrates backend API in frontend")
    print("-"*70)

    exec_env_b = ExecutionEnv(task_id=task_b.task_id)

    # Task B references Task A's commit
    artifact_service.create_commit_ref(
        task_id=task_b.task_id,
        repo_id="backend-repo",
        commit_hash="abc123def456",  # Same commit as Task A
        summary="Uses auth API from Task A",
    )

    # Task B reads backend files
    audit_service.record_operation(
        task_id=task_b.task_id,
        operation="read",
        repo_id="backend-repo",
        files_changed=["src/api/auth.py"],  # Reads what Task A wrote
    )

    # Task B writes frontend files
    artifact_service.create_commit_ref(
        task_id=task_b.task_id,
        repo_id="frontend-repo",
        commit_hash="xyz789ghi012",
        summary="Added login UI",
    )

    audit_service.record_operation(
        task_id=task_b.task_id,
        operation="write",
        repo_id="frontend-repo",
        files_changed=["src/components/Login.tsx", "src/api/auth-client.ts"],
        lines_added=200,
    )

    execute_task_with_dependency_detection(
        task_b, exec_env_b, dep_service, artifact_service, audit_service
    )

    # Scenario: Execute Task C
    print("\n" + "-"*70)
    print("SCENARIO: Task C documents both changes")
    print("-"*70)

    exec_env_c = ExecutionEnv(task_id=task_c.task_id)

    # Task C references both commits
    artifact_service.create_commit_ref(
        task_id=task_c.task_id,
        repo_id="backend-repo",
        commit_hash="abc123def456",
        summary="Documents backend auth API",
    )

    artifact_service.create_commit_ref(
        task_id=task_c.task_id,
        repo_id="frontend-repo",
        commit_hash="xyz789ghi012",
        summary="Documents frontend login UI",
    )

    # Task C reads both repos
    audit_service.record_operation(
        task_id=task_c.task_id,
        operation="read",
        repo_id="backend-repo",
        files_changed=["src/api/auth.py"],
    )

    audit_service.record_operation(
        task_id=task_c.task_id,
        operation="read",
        repo_id="frontend-repo",
        files_changed=["src/components/Login.tsx"],
    )

    # Task C writes documentation
    artifact_service.create_commit_ref(
        task_id=task_c.task_id,
        repo_id="docs-repo",
        commit_hash="doc456xyz",
        summary="Added authentication guide",
    )

    execute_task_with_dependency_detection(
        task_c, exec_env_c, dep_service, artifact_service, audit_service
    )

    # Build and analyze dependency graph
    print("\n" + "="*70)
    print("DEPENDENCY GRAPH ANALYSIS")
    print("="*70)

    graph = dep_service.build_dependency_graph()

    # Show all dependencies
    print("\n[1] All Dependencies:")
    all_deps = dep_service.get_all_dependencies()
    for dep in all_deps:
        print(f"  - {dep.task_id} -> {dep.depends_on_task_id} ({dep.dependency_type.value})")
        print(f"    Reason: {dep.reason}")

    # Topological sort
    print("\n[2] Topological Sort (Execution Order):")
    try:
        order = graph.topological_sort()
        print(f"  {' -> '.join(order)}")
    except Exception as e:
        print(f"  Error: {e}")

    # Ancestors and descendants
    print("\n[3] Dependency Queries:")
    for task in [task_a, task_b, task_c]:
        ancestors = graph.get_ancestors(task.task_id)
        descendants = graph.get_descendants(task.task_id)
        print(f"\n  {task.title} ({task.task_id}):")
        print(f"    Depends on: {ancestors or 'none'}")
        print(f"    Depended by: {descendants or 'none'}")

    # Cycle check
    print("\n[4] Cycle Detection:")
    cycles = dep_service.detect_cycles()
    if cycles:
        print(f"  ✗ Found {len(cycles)} cycles:")
        for cycle in cycles:
            print(f"    {' -> '.join(cycle)}")
    else:
        print("  ✓ No circular dependencies detected")

    # Export to DOT
    print("\n[5] GraphViz Export:")
    dot = graph.to_dot()
    dot_file = Path("dependency_graph.dot")
    dot_file.write_text(dot)
    print(f"  Saved to: {dot_file}")
    print(f"  Render with: dot -Tpng {dot_file} -o dependency_graph.png")

    print("\n" + "="*70)
    print("Example complete!")
    print("="*70)
    print(f"\nDatabase: {db_path}")
    print(f"DOT file: {dot_file}")
    print("\nNext steps:")
    print("  1. Render graph: dot -Tpng dependency_graph.dot -o dependency_graph.png")
    print("  2. Query dependencies: agentos task dependencies show <task_id>")
    print("  3. Check cycles: agentos task dependencies check-cycles")

    db.close()


if __name__ == "__main__":
    main()
