"""Task Manager: CRUD and aggregation for tasks"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

try:
    from ulid import ULID
except ImportError:
    # Fallback to UUID if ULID not available
    import uuid
    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.core.task.models import Task, TaskLineageEntry, TaskTrace
from agentos.core.task.trace_builder import TraceBuilder
from agentos.store import get_db

logger = logging.getLogger(__name__)


class TaskManager:
    """Task Manager: CRUD + aggregation queries"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Task Manager
        
        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path
        self.trace_builder = TraceBuilder()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        if self.db_path:
            conn = sqlite3.connect(str(self.db_path))
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_task(
        self,
        title: str,
        session_id: Optional[str] = None,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        route_plan_json: Optional[str] = None,
        requirements_json: Optional[str] = None,
        selected_instance_id: Optional[str] = None,
        router_version: Optional[str] = None,
    ) -> Task:
        """
        Create a new task

        ℹ️ NOTE: This method is maintained for backward compatibility.
        New code should use TaskService.create_draft_task() which enforces
        state machine rules and creates tasks in DRAFT state.

        For now, this creates tasks with status="created" (legacy behavior).
        In a future version, this will be updated to create DRAFT tasks.

        Args:
            title: Task title
            session_id: Optional session ID (auto-generated if None)
            created_by: Optional creator identifier
            metadata: Optional metadata

        Returns:
            Task object
        """
        task_id = str(ULID.from_datetime(datetime.now(timezone.utc)))
        now = datetime.now(timezone.utc).isoformat()

        # Auto-generate session_id if not provided
        auto_created_session = False
        if not session_id:
            timestamp = int(datetime.now(timezone.utc).timestamp())
            session_id = f"auto_{task_id[:8]}_{timestamp}"
            auto_created_session = True

        # Enhance metadata with execution context
        if metadata is None:
            metadata = {}

        if "execution_context" not in metadata:
            metadata["execution_context"] = {
                "created_method": "task_manager",
                "created_at": now,
            }

        # ⚠️ Legacy: Creates with status="created"
        # TODO: Migrate to DRAFT state in next version
        task = Task(
            task_id=task_id,
            title=title,
            status="created",  # Legacy status
            session_id=session_id,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata=metadata,
            route_plan_json=route_plan_json,
            requirements_json=requirements_json,
            selected_instance_id=selected_instance_id,
            router_version=router_version,
        )

        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # If we auto-created session_id, create the session record first
            if auto_created_session:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO task_sessions (session_id, channel, metadata, created_at, last_activity)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        "auto",
                        json.dumps({"auto_created": True, "task_id": task_id}),
                        now,
                        now,
                    ),
                )

            cursor.execute(
                """
                INSERT INTO tasks (
                    task_id, title, status, session_id, created_at, updated_at, created_by, metadata,
                    route_plan_json, requirements_json, selected_instance_id, router_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.title,
                    task.status,
                    task.session_id,
                    task.created_at,
                    task.updated_at,
                    task.created_by,
                    json.dumps(task.metadata) if task.metadata else None,
                    task.route_plan_json,
                    task.requirements_json,
                    task.selected_instance_id,
                    task.router_version,
                ),
            )
            conn.commit()
            logger.info(f"Created task: {task_id} (session: {session_id})")

            # 🔵 AUTO ROUTE TASK AFTER CREATION
            try:
                from agentos.core.task.routing_service import TaskRoutingService
                import asyncio
                routing_service = TaskRoutingService()
                # Build task_spec for routing
                task_spec = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "metadata": task.metadata or {},
                }
                # Run async route_new_task in sync context
                asyncio.run(routing_service.route_new_task(task.task_id, task_spec))
            except Exception as e:
                logger.exception(f"Task routing failed for task {task.task_id}: {e}")

            return task
        finally:
            conn.close()
    
    def create_orphan_task(
        self,
        ref_id: str,
        created_by: Optional[str] = None,
    ) -> Task:
        """
        Create an orphan task (execution without task_id)
        
        Args:
            ref_id: Reference ID that triggered orphan creation
            created_by: Optional creator
            
        Returns:
            Orphan task
        """
        task = self.create_task(
            title=f"Orphan: {ref_id[:20]}",
            created_by=created_by or "system",
            metadata={"orphan": True, "trigger_ref": ref_id},
        )
        
        # Update status to orphan
        self.update_task_status(task.task_id, "orphan")
        
        logger.warning(f"Created orphan task {task.task_id} for ref {ref_id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID
        
        Args:
            task_id: Task ID
            
        Returns:
            Task object or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            ).fetchone()
            
            if not row:
                return None
            
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            # Safe access for optional router fields
            try:
                route_plan_json = row["route_plan_json"]
            except (KeyError, IndexError):
                route_plan_json = None

            try:
                requirements_json = row["requirements_json"]
            except (KeyError, IndexError):
                requirements_json = None

            try:
                selected_instance_id = row["selected_instance_id"]
            except (KeyError, IndexError):
                selected_instance_id = None

            try:
                router_version = row["router_version"]
            except (KeyError, IndexError):
                router_version = None

            try:
                project_id = row["project_id"]
            except (KeyError, IndexError):
                project_id = None

            try:
                exit_reason = row["exit_reason"]
            except (KeyError, IndexError):
                exit_reason = None

            # Task #4: Safe access for v0.4 fields (spec_frozen, repo_id, workdir)
            try:
                spec_frozen = row["spec_frozen"]
            except (KeyError, IndexError):
                spec_frozen = 0  # Default to unfrozen

            try:
                repo_id = row["repo_id"]
            except (KeyError, IndexError):
                repo_id = None

            try:
                workdir = row["workdir"]
            except (KeyError, IndexError):
                workdir = None

            return Task(
                task_id=row["task_id"],
                title=row["title"],
                status=row["status"],
                session_id=row["session_id"],
                project_id=project_id,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
                metadata=metadata,
                exit_reason=exit_reason,
                route_plan_json=route_plan_json,
                requirements_json=requirements_json,
                selected_instance_id=selected_instance_id,
                router_version=router_version,
                spec_frozen=spec_frozen,  # Task #4
                repo_id=repo_id,  # v0.4
                workdir=workdir,  # v0.4
            )
        finally:
            conn.close()
    
    def list_tasks(
        self,
        limit: int = 100,
        offset: int = 0,
        status_filter: Optional[str] = None,
        orphan_only: bool = False,
    ) -> List[Task]:
        """
        List tasks
        
        Args:
            limit: Maximum number of tasks
            offset: Offset for pagination
            status_filter: Filter by status
            orphan_only: Show only orphan tasks
            
        Returns:
            List of tasks
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            query = "SELECT * FROM tasks WHERE 1=1"
            params = []
            
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            
            if orphan_only:
                query += " AND (status = 'orphan' OR json_extract(metadata, '$.orphan') = 1)"
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            rows = cursor.execute(query, params).fetchall()
            
            tasks = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}

                # Safe access for optional router fields
                try:
                    route_plan_json = row["route_plan_json"]
                except (KeyError, IndexError):
                    route_plan_json = None

                try:
                    requirements_json = row["requirements_json"]
                except (KeyError, IndexError):
                    requirements_json = None

                try:
                    selected_instance_id = row["selected_instance_id"]
                except (KeyError, IndexError):
                    selected_instance_id = None

                try:
                    router_version = row["router_version"]
                except (KeyError, IndexError):
                    router_version = None

                # Task #4: Safe access for v0.4 fields
                try:
                    project_id = row["project_id"]
                except (KeyError, IndexError):
                    project_id = None

                try:
                    exit_reason = row["exit_reason"]
                except (KeyError, IndexError):
                    exit_reason = None

                try:
                    spec_frozen = row["spec_frozen"]
                except (KeyError, IndexError):
                    spec_frozen = 0

                try:
                    repo_id = row["repo_id"]
                except (KeyError, IndexError):
                    repo_id = None

                try:
                    workdir = row["workdir"]
                except (KeyError, IndexError):
                    workdir = None

                tasks.append(Task(
                    task_id=row["task_id"],
                    title=row["title"],
                    status=row["status"],
                    session_id=row["session_id"],
                    project_id=project_id,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    created_by=row["created_by"],
                    metadata=metadata,
                    exit_reason=exit_reason,
                    route_plan_json=route_plan_json,
                    requirements_json=requirements_json,
                    selected_instance_id=selected_instance_id,
                    router_version=router_version,
                    spec_frozen=spec_frozen,  # Task #4
                    repo_id=repo_id,  # v0.4
                    workdir=workdir,  # v0.4
                ))

            return tasks
        finally:
            conn.close()
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Update task status

        ⚠️ DEPRECATED: Use TaskService methods for state transitions.
        This method bypasses state machine validation and audit logging.

        Migration path:
            from agentos.core.task.service import TaskService
            service = TaskService()
            service.approve_task(task_id, actor="user", reason="...")

        Args:
            task_id: Task ID
            status: New status
        """
        import warnings
        warnings.warn(
            "TaskManager.update_task_status() is deprecated and bypasses state machine validation. "
            "Use TaskService methods (approve_task, queue_task, start_task, etc.) instead. "
            "See agentos/core/task/MIGRATION_GUIDE.md for details.",
            DeprecationWarning,
            stacklevel=2
        )

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, now, task_id)
            )
            conn.commit()
            logger.warning(f"⚠️ Direct status update (deprecated): task {task_id} -> {status}")
        finally:
            conn.close()

    def update_task(self, task: Task) -> None:
        """
        Update entire task (status + metadata)

        Args:
            task: Task object with updated fields
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE tasks
                SET status = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    task.status,
                    json.dumps(task.metadata) if task.metadata else None,
                    now,
                    task.task_id
                )
            )
            conn.commit()
            logger.info(f"Updated task {task.task_id}: status={task.status}, metadata keys={list(task.metadata.keys()) if task.metadata else []}")
        finally:
            conn.close()

    def update_task_exit_reason(self, task_id: str, exit_reason: str, status: Optional[str] = None) -> None:
        """
        Update task exit_reason (and optionally status)

        This method is used by the task runner to record why execution stopped.

        Args:
            task_id: Task ID
            exit_reason: Exit reason (done, max_iterations, blocked, fatal_error, user_cancelled, unknown)
            status: Optional new status (if provided, will be updated together with exit_reason)
        """
        # Validate exit_reason
        valid_reasons = ['done', 'max_iterations', 'blocked', 'fatal_error', 'user_cancelled', 'timeout', 'unknown']
        if exit_reason not in valid_reasons:
            logger.warning(f"Invalid exit_reason '{exit_reason}', setting to 'unknown'")
            exit_reason = 'unknown'

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            if status:
                cursor.execute(
                    "UPDATE tasks SET exit_reason = ?, status = ?, updated_at = ? WHERE task_id = ?",
                    (exit_reason, status, now, task_id)
                )
                logger.info(f"Updated task {task_id}: exit_reason={exit_reason}, status={status}")
            else:
                cursor.execute(
                    "UPDATE tasks SET exit_reason = ?, updated_at = ? WHERE task_id = ?",
                    (exit_reason, now, task_id)
                )
                logger.info(f"Updated task {task_id}: exit_reason={exit_reason}")

            conn.commit()
        finally:
            conn.close()

    def add_lineage(
        self,
        task_id: str,
        kind: str,
        ref_id: str,
        phase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add lineage entry to task
        
        Args:
            task_id: Task ID
            kind: Lineage kind (nl_request|intent|coordinator_run|...)
            ref_id: Reference ID
            phase: Optional phase
            metadata: Optional metadata
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute(
                """
                INSERT OR IGNORE INTO task_lineage (task_id, kind, ref_id, phase, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    kind,
                    ref_id,
                    phase,
                    now,
                    json.dumps(metadata) if metadata else None,
                )
            )
            conn.commit()
            logger.debug(f"Added lineage: task={task_id}, kind={kind}, ref={ref_id}")
        finally:
            conn.close()
    
    def get_lineage(self, task_id: str) -> List[TaskLineageEntry]:
        """
        Get all lineage entries for a task
        
        Args:
            task_id: Task ID
            
        Returns:
            List of lineage entries (sorted by created_at)
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT * FROM task_lineage WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,)
            ).fetchall()
            
            entries = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                entries.append(TaskLineageEntry(
                    task_id=row["task_id"],
                    kind=row["kind"],
                    ref_id=row["ref_id"],
                    phase=row["phase"],
                    timestamp=row["created_at"],  # Map DB created_at to model timestamp
                    metadata=metadata,
                ))
            
            return entries
        finally:
            conn.close()
    
    def get_trace(self, task_id: str) -> Optional[TaskTrace]:
        """
        Get task trace (shallow by default)
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskTrace object or None
        """
        task = self.get_task(task_id)
        if not task:
            return None
        
        lineage = self.get_lineage(task_id)
        
        # Get agents
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            agent_rows = cursor.execute(
                "SELECT * FROM task_agents WHERE task_id = ? ORDER BY started_at ASC",
                (task_id,)
            ).fetchall()
            
            agents = [dict(row) for row in agent_rows]
            
            # Get audits
            audit_rows = cursor.execute(
                "SELECT * FROM task_audits WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,)
            ).fetchall()
            
            audits = [dict(row) for row in audit_rows]
        finally:
            conn.close()
        
        return TaskTrace(
            task=task,
            timeline=lineage,
            agents=agents,
            audits=audits,
        )
    
    def add_audit(
        self,
        task_id: str,
        event_type: str,
        level: str = "info",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add audit event
        
        Args:
            task_id: Task ID
            event_type: Event type
            level: Log level (info|warn|error)
            payload: Optional event payload
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute(
                """
                INSERT INTO task_audits (task_id, level, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    level,
                    event_type,
                    json.dumps(payload) if payload else None,
                    now,
                )
            )
            conn.commit()
        finally:
            conn.close()

    def update_task_routing(
        self,
        task_id: str,
        route_plan_json: str,
        requirements_json: str,
        selected_instance_id: str,
        router_version: str = "v1",
    ) -> None:
        """
        Update task routing information

        Args:
            task_id: Task ID
            route_plan_json: JSON serialized RoutePlan
            requirements_json: JSON serialized TaskRequirements
            selected_instance_id: Selected provider instance ID
            router_version: Router version
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE tasks
                SET route_plan_json = ?,
                    requirements_json = ?,
                    selected_instance_id = ?,
                    router_version = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (route_plan_json, requirements_json, selected_instance_id, router_version, now, task_id)
            )
            conn.commit()
            logger.info(f"Updated routing for task {task_id}: instance={selected_instance_id}")
        finally:
            conn.close()
