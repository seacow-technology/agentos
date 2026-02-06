"""Task Specification Service

Provides high-level task spec operations for v0.4 Project-Aware Task OS.

Created for Task #3 Phase 2: Core Service Implementation
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from agentos.core.time import utc_now, utc_now_iso


try:
    from ulid import ULID
except ImportError:
    import uuid

    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.schemas.v31_models import TaskSpec
from agentos.core.project.errors import (
    SpecNotFoundError,
    SpecAlreadyFrozenError,
    SpecIncompleteError,
    SpecValidationError,
)
from agentos.core.task.errors import TaskNotFoundError
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class TaskSpecService:
    """Task specification management service

    Provides business-level operations for task spec management.
    All database writes go through SQLiteWriter for concurrency safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize TaskSpecService

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection (read-only)"""
        if self.db_path:
            conn = sqlite3.connect(str(self.db_path))
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # TASK SPEC CRUD
    # =========================================================================

    def create_spec(
        self,
        task_id: str,
        title: str,
        intent: str = None,
        constraints: Dict = None,
        acceptance_criteria: List[str] = None,
        inputs: Dict = None,
    ) -> TaskSpec:
        """Create initial task spec (version 0)

        Args:
            task_id: Task ID
            title: Task title
            intent: Optional task intent
            constraints: Optional constraints dict
            acceptance_criteria: Optional acceptance criteria list
            inputs: Optional inputs dict

        Returns:
            TaskSpec with spec_version = 0

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        # Generate spec ID
        spec_id = str(ULID.from_datetime(utc_now()))
        now = utc_now_iso()

        if acceptance_criteria is None:
            acceptance_criteria = []

        # Define write function
        def _write_spec(conn):
            cursor = conn.cursor()

            # Check task exists
            cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
            if not cursor.fetchone():
                raise TaskNotFoundError(task_id)

            # Insert spec (version 0)
            cursor.execute(
                """
                INSERT INTO task_specs (spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spec_id,
                    task_id,
                    0,  # Initial version
                    title,
                    intent,
                    json.dumps(constraints) if constraints else None,
                    json.dumps(acceptance_criteria),
                    json.dumps(inputs) if inputs else None,
                    now,
                ),
            )

            logger.info(f"Created spec for task {task_id}: version 0")
            return spec_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_spec, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to create spec: {e}", exc_info=True)
            raise

        # Return spec object
        return TaskSpec(
            spec_id=spec_id,
            task_id=task_id,
            spec_version=0,
            title=title,
            intent=intent,
            constraints=constraints,
            acceptance_criteria=acceptance_criteria,
            inputs=inputs,
            created_at=now,
        )

    def freeze_spec(self, task_id: str) -> TaskSpec:
        """Freeze spec: create new version, set task.spec_frozen = 1

        Process:
            1. Get latest spec for task_id
            2. Create new spec with spec_version = latest + 1
            3. Update task.spec_frozen = 1
            4. Write audit event: TASK_SPEC_FROZEN

        Args:
            task_id: Task ID

        Returns:
            Frozen TaskSpec

        Raises:
            TaskNotFoundError: If task doesn't exist
            SpecAlreadyFrozenError: If spec already frozen
            SpecIncompleteError: If spec missing required fields
        """
        now = utc_now_iso()

        # Define write function
        def _write_freeze(conn):
            cursor = conn.cursor()

            # Check task exists
            cursor.execute(
                "SELECT task_id, spec_frozen FROM tasks WHERE task_id = ?",
                (task_id,),
            )
            task_row = cursor.fetchone()
            if not task_row:
                raise TaskNotFoundError(task_id)

            # Check if already frozen
            if task_row["spec_frozen"] == 1:
                raise SpecAlreadyFrozenError(task_id)

            # Get latest spec
            cursor.execute(
                """
                SELECT spec_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, metadata
                FROM task_specs
                WHERE task_id = ?
                ORDER BY spec_version DESC
                LIMIT 1
                """,
                (task_id,),
            )
            spec_row = cursor.fetchone()

            if not spec_row:
                raise SpecNotFoundError(task_id)

            # Validate spec before freezing
            spec_dict = dict(spec_row)
            is_valid, errors = self._validate_spec_dict(spec_dict)
            if not is_valid:
                missing_fields = [
                    field for field, error in zip(["title", "acceptance_criteria"], errors) if error
                ]
                raise SpecIncompleteError(task_id, missing_fields)

            # Create new spec version (frozen)
            new_version = spec_row["spec_version"] + 1
            new_spec_id = str(ULID.from_datetime(utc_now()))

            cursor.execute(
                """
                INSERT INTO task_specs (spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_spec_id,
                    task_id,
                    new_version,
                    spec_row["title"],
                    spec_row["intent"],
                    spec_row["constraints"],
                    spec_row["acceptance_criteria"],
                    spec_row["inputs"],
                    now,
                    spec_row["metadata"],
                ),
            )

            # Update task.spec_frozen = 1
            cursor.execute(
                "UPDATE tasks SET spec_frozen = 1, updated_at = ? WHERE task_id = ?",
                (now, task_id),
            )

            # Write audit event
            cursor.execute(
                """
                INSERT INTO task_audits (task_id, level, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    "info",
                    "TASK_SPEC_FROZEN",
                    json.dumps({
                        "spec_version": new_version,
                        "frozen_at": now,
                    }),
                    now,
                ),
            )

            logger.info(f"Froze spec for task {task_id}: version {new_version}")
            return new_spec_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_freeze, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to freeze spec: {e}", exc_info=True)
            raise

        # Fetch and return frozen spec
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at, metadata
                FROM task_specs
                WHERE spec_id = ?
                """,
                (result_id,),
            )
            row = cursor.fetchone()
            if row:
                return TaskSpec.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def get_spec(self, task_id: str, version: int = None) -> Optional[TaskSpec]:
        """Get spec by task_id and optional version

        Args:
            task_id: Task ID
            version: Optional spec version (if None, get latest)

        Returns:
            TaskSpec or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if version is not None:
                cursor.execute(
                    """
                    SELECT spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at, metadata
                    FROM task_specs
                    WHERE task_id = ? AND spec_version = ?
                    """,
                    (task_id, version),
                )
            else:
                cursor.execute(
                    """
                    SELECT spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at, metadata
                    FROM task_specs
                    WHERE task_id = ?
                    ORDER BY spec_version DESC
                    LIMIT 1
                    """,
                    (task_id,),
                )

            row = cursor.fetchone()

            if not row:
                return None

            return TaskSpec.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def list_spec_versions(self, task_id: str) -> List[TaskSpec]:
        """Get all spec versions for a task (history)

        Args:
            task_id: Task ID

        Returns:
            List of TaskSpec objects (sorted by version ascending)
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT spec_id, task_id, spec_version, title, intent, constraints, acceptance_criteria, inputs, created_at, metadata
                FROM task_specs
                WHERE task_id = ?
                ORDER BY spec_version ASC
                """,
                (task_id,),
            )
            rows = cursor.fetchall()
            return [TaskSpec.from_db_row(dict(row)) for row in rows]
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    # =========================================================================
    # SPEC VALIDATION
    # =========================================================================

    def validate_spec(self, spec: TaskSpec) -> Tuple[bool, List[str]]:
        """Validate spec for freezing

        Returns:
            (is_valid, list_of_errors)

        Checks:
            - title is not empty
            - acceptance_criteria has at least 1 item
            - inputs/constraints are valid JSON (already validated by Pydantic)
        """
        errors = []

        if not spec.title or not spec.title.strip():
            errors.append("Title is required and cannot be empty")

        if not spec.acceptance_criteria or len(spec.acceptance_criteria) == 0:
            errors.append("Acceptance criteria must have at least 1 item")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _validate_spec_dict(self, spec_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Internal helper to validate spec from DB row dict"""
        errors = []

        if not spec_dict.get("title") or not spec_dict["title"].strip():
            errors.append("Title is required and cannot be empty")

        # Parse acceptance_criteria from JSON
        ac_json = spec_dict.get("acceptance_criteria")
        if ac_json:
            try:
                ac_list = json.loads(ac_json) if isinstance(ac_json, str) else ac_json
                if not ac_list or len(ac_list) == 0:
                    errors.append("Acceptance criteria must have at least 1 item")
            except json.JSONDecodeError:
                errors.append("Acceptance criteria is not valid JSON")
        else:
            errors.append("Acceptance criteria must have at least 1 item")

        is_valid = len(errors) == 0
        return is_valid, errors
