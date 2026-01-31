"""
Router Persistence - Database operations for routing data

Handles saving and loading routing plans from the tasks table.

PR-1: Router Core - Database integration
"""

import json
import logging
import sqlite3
from typing import Optional
from pathlib import Path

from agentos.router.models import RoutePlan, TaskRequirements
from agentos.core.db.registry_db import get_db, transaction

logger = logging.getLogger(__name__)


class RouterPersistence:
    """
    Persist and retrieve routing plans from database

    Uses the routing fields added to tasks table in migration v12.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize persistence layer

        Args:
            db_path: Optional path to database (defaults to store default)
                     Note: Custom paths are deprecated, use registry DB instead.
        """
        if db_path:
            import warnings
            warnings.warn(
                "Custom db_path is deprecated. Use default registry DB.",
                DeprecationWarning
            )
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection.

        Note: DO NOT close the returned connection if using default DB.
        """
        if self.db_path:
            # Custom path: caller must close
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn
        else:
            # Default registry: DO NOT close
            return get_db()

    def save_route_plan(self, route_plan: RoutePlan) -> None:
        """
        Save route plan to database

        Updates the routing fields in tasks table.

        Args:
            route_plan: RoutePlan to save
        """
        try:
            # Serialize route plan and requirements
            route_plan_json = json.dumps(route_plan.to_dict())
            requirements_json = None
            if route_plan.requirements:
                requirements_json = json.dumps(route_plan.requirements.to_dict())

            if self.db_path:
                # Custom DB: manage connection lifecycle
                conn = self._get_conn()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET route_plan_json = ?,
                            requirements_json = ?,
                            selected_instance_id = ?,
                            router_version = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                        """,
                        (
                            route_plan_json,
                            requirements_json,
                            route_plan.selected,
                            route_plan.router_version,
                            route_plan.task_id,
                        ),
                    )
                    conn.commit()
                finally:
                    conn.close()
            else:
                # Registry DB: use transaction context
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET route_plan_json = ?,
                            requirements_json = ?,
                            selected_instance_id = ?,
                            router_version = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                        """,
                        (
                            route_plan_json,
                            requirements_json,
                            route_plan.selected,
                            route_plan.router_version,
                            route_plan.task_id,
                        ),
                    )
                    # Auto-commit on success

            logger.info(f"Saved route plan for task {route_plan.task_id}")
        except Exception as e:
            logger.error(f"Failed to save route plan: {e}", exc_info=True)
            raise

    def load_route_plan(self, task_id: str) -> Optional[RoutePlan]:
        """
        Load route plan from database

        Args:
            task_id: Task identifier

        Returns:
            RoutePlan or None if not found
        """
        try:
            if self.db_path:
                # Custom DB: manage connection lifecycle
                conn = self._get_conn()
                try:
                    cursor = conn.cursor()
                    row = cursor.execute(
                        """
                        SELECT route_plan_json, requirements_json, selected_instance_id, router_version
                        FROM tasks
                        WHERE task_id = ?
                        """,
                        (task_id,),
                    ).fetchone()
                finally:
                    conn.close()
            else:
                # Registry DB: do not close shared connection
                conn = self._get_conn()
                cursor = conn.cursor()
                row = cursor.execute(
                    """
                    SELECT route_plan_json, requirements_json, selected_instance_id, router_version
                    FROM tasks
                    WHERE task_id = ?
                    """,
                    (task_id,),
                ).fetchone()

            if not row or not row["route_plan_json"]:
                logger.debug(f"No route plan found for task {task_id}")
                return None

            # Deserialize route plan
            route_plan_data = json.loads(row["route_plan_json"])
            route_plan = RoutePlan.from_dict(route_plan_data)

            logger.debug(f"Loaded route plan for task {task_id}")
            return route_plan

        except Exception as e:
            logger.error(f"Failed to load route plan: {e}", exc_info=True)
            return None

    def delete_route_plan(self, task_id: str) -> None:
        """
        Delete route plan from database

        Clears routing fields for a task.

        Args:
            task_id: Task identifier
        """
        try:
            if self.db_path:
                # Custom DB: manage connection lifecycle
                conn = self._get_conn()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET route_plan_json = NULL,
                            requirements_json = NULL,
                            selected_instance_id = NULL,
                            router_version = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                        """,
                        (task_id,),
                    )
                    conn.commit()
                finally:
                    conn.close()
            else:
                # Registry DB: use transaction context
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET route_plan_json = NULL,
                            requirements_json = NULL,
                            selected_instance_id = NULL,
                            router_version = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                        """,
                        (task_id,),
                    )
                    # Auto-commit on success

            logger.info(f"Deleted route plan for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete route plan: {e}", exc_info=True)
            raise

    def get_tasks_by_instance(self, instance_id: str, limit: int = 100) -> list:
        """
        Get tasks routed to a specific instance

        Args:
            instance_id: Instance identifier
            limit: Maximum number of tasks to return

        Returns:
            List of task_id strings
        """
        try:
            if self.db_path:
                # Custom DB: manage connection lifecycle
                conn = self._get_conn()
                try:
                    cursor = conn.cursor()
                    rows = cursor.execute(
                        """
                        SELECT task_id
                        FROM tasks
                        WHERE selected_instance_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (instance_id, limit),
                    ).fetchall()
                finally:
                    conn.close()
            else:
                # Registry DB: do not close shared connection
                conn = self._get_conn()
                cursor = conn.cursor()
                rows = cursor.execute(
                    """
                    SELECT task_id
                    FROM tasks
                    WHERE selected_instance_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (instance_id, limit),
                ).fetchall()

            task_ids = [row["task_id"] for row in rows]
            logger.debug(f"Found {len(task_ids)} tasks for instance {instance_id}")

            return task_ids

        except Exception as e:
            logger.error(f"Failed to query tasks by instance: {e}", exc_info=True)
            return []

    def get_routing_stats(self) -> dict:
        """
        Get routing statistics

        Returns:
            Dictionary with routing statistics
        """
        try:
            if self.db_path:
                # Custom DB: manage connection lifecycle
                conn = self._get_conn()
                try:
                    cursor = conn.cursor()

                    # Count tasks by selected instance
                    instance_counts = cursor.execute(
                        """
                        SELECT selected_instance_id, COUNT(*) as count
                        FROM tasks
                        WHERE selected_instance_id IS NOT NULL
                        GROUP BY selected_instance_id
                        ORDER BY count DESC
                        """
                    ).fetchall()

                    # Total routed tasks
                    total_routed = cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM tasks
                        WHERE selected_instance_id IS NOT NULL
                        """
                    ).fetchone()["count"]
                finally:
                    conn.close()
            else:
                # Registry DB: do not close shared connection
                conn = self._get_conn()
                cursor = conn.cursor()

                # Count tasks by selected instance
                instance_counts = cursor.execute(
                    """
                    SELECT selected_instance_id, COUNT(*) as count
                    FROM tasks
                    WHERE selected_instance_id IS NOT NULL
                    GROUP BY selected_instance_id
                    ORDER BY count DESC
                    """
                ).fetchall()

                # Total routed tasks
                total_routed = cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM tasks
                    WHERE selected_instance_id IS NOT NULL
                    """
                ).fetchone()["count"]

            stats = {
                "total_routed": total_routed,
                "by_instance": {
                    row["selected_instance_id"]: row["count"]
                    for row in instance_counts
                },
            }

            logger.debug(f"Retrieved routing stats: {total_routed} total routed tasks")
            return stats

        except Exception as e:
            logger.error(f"Failed to get routing stats: {e}", exc_info=True)
            return {"total_routed": 0, "by_instance": {}}
