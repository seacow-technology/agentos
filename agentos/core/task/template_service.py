"""
Task Template Service

Provides template management operations for saving and reusing task configurations.
Created for Task #11: Implement task template functionality
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from agentos.core.time import utc_now, utc_now_iso


try:
    from ulid import ULID
except ImportError:
    import uuid

    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.core.task.models import TaskTemplate, Task
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing task templates"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Template Service

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path

    def create_template(
        self,
        name: str,
        title_template: str,
        description: Optional[str] = None,
        created_by_default: Optional[str] = None,
        metadata_template: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> TaskTemplate:
        """
        Create a new task template

        Args:
            name: Template name (1-100 characters)
            title_template: Task title template
            description: Optional template description
            created_by_default: Default creator for tasks created from this template
            metadata_template: Optional metadata template
            created_by: Template creator

        Returns:
            TaskTemplate object

        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        if not name or len(name.strip()) < 1 or len(name) > 100:
            raise ValueError("Template name must be 1-100 characters")

        if not title_template or len(title_template.strip()) < 1:
            raise ValueError("Title template cannot be empty")

        # Generate template_id
        template_id = str(ULID.from_datetime(utc_now()))
        now = utc_now_iso()

        if metadata_template is None:
            metadata_template = {}

        # Create template object
        template = TaskTemplate(
            template_id=template_id,
            name=name.strip(),
            title_template=title_template.strip(),
            description=description,
            created_by_default=created_by_default,
            metadata_template=metadata_template,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            use_count=0,
        )

        # Define write function
        def _write_template_to_db(conn):
            """Write template to database"""
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_templates (
                    template_id, name, description, title_template,
                    created_by_default, metadata_template_json,
                    created_at, updated_at, created_by, use_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.template_id,
                    template.name,
                    template.description,
                    template.title_template,
                    template.created_by_default,
                    json.dumps(template.metadata_template) if template.metadata_template else None,
                    template.created_at,
                    template.updated_at,
                    template.created_by,
                    template.use_count,
                ),
            )
            return template_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_template_to_db, timeout=10.0)
            logger.info(f"Created task template: {result_id} (name: {name})")
        except Exception as e:
            logger.error(f"Failed to create template: {e}", exc_info=True)
            raise

        return template

    def list_templates(
        self,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
    ) -> List[TaskTemplate]:
        """
        List all templates

        Args:
            limit: Maximum number of results (default 50)
            offset: Offset for pagination (default 0)
            order_by: Order by field (created_at, name, use_count)

        Returns:
            List of TaskTemplate objects
        """
        # Validate order_by to prevent SQL injection
        valid_order_fields = {
            "created_at": "created_at DESC",
            "name": "name ASC",
            "use_count": "use_count DESC",
            "updated_at": "updated_at DESC",
        }

        if order_by not in valid_order_fields:
            order_by = "created_at"

        order_clause = valid_order_fields[order_by]

        conn = get_db()
        cursor = conn.execute(
            f"""
            SELECT
                template_id, name, description, title_template,
                created_by_default, metadata_template_json,
                created_at, updated_at, created_by, use_count
            FROM task_templates
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

        templates = []
        for row in cursor.fetchall():
            template = TaskTemplate.from_db_row(dict(row))
            templates.append(template)

        # Do NOT close: get_db() returns shared thread-local connection
        return templates

    def get_template(self, template_id: str) -> Optional[TaskTemplate]:
        """
        Get template by ID

        Args:
            template_id: Template ID

        Returns:
            TaskTemplate object or None if not found
        """
        conn = get_db()
        cursor = conn.execute(
            """
            SELECT
                template_id, name, description, title_template,
                created_by_default, metadata_template_json,
                created_at, updated_at, created_by, use_count
            FROM task_templates
            WHERE template_id = ?
            """,
            (template_id,),
        )

        row = cursor.fetchone()
        if row:
            return TaskTemplate.from_db_row(dict(row))
        return None
        # Do NOT close: get_db() returns shared thread-local connection

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        title_template: Optional[str] = None,
        description: Optional[str] = None,
        created_by_default: Optional[str] = None,
        metadata_template: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskTemplate]:
        """
        Update a template

        Args:
            template_id: Template ID
            name: Optional new name
            title_template: Optional new title template
            description: Optional new description
            created_by_default: Optional new default creator
            metadata_template: Optional new metadata template

        Returns:
            Updated TaskTemplate object or None if not found

        Raises:
            ValueError: If validation fails
        """
        # Get existing template
        existing = self.get_template(template_id)
        if not existing:
            return None

        # Validate updates
        if name is not None:
            if len(name.strip()) < 1 or len(name) > 100:
                raise ValueError("Template name must be 1-100 characters")

        if title_template is not None:
            if len(title_template.strip()) < 1:
                raise ValueError("Title template cannot be empty")

        # Build update query dynamically
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())

        if title_template is not None:
            updates.append("title_template = ?")
            params.append(title_template.strip())

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if created_by_default is not None:
            updates.append("created_by_default = ?")
            params.append(created_by_default)

        if metadata_template is not None:
            updates.append("metadata_template_json = ?")
            params.append(json.dumps(metadata_template))

        if not updates:
            # No updates provided
            return existing

        # Add updated_at
        updates.append("updated_at = ?")
        params.append(utc_now_iso())

        # Add template_id to params
        params.append(template_id)

        # Define write function
        def _update_template_in_db(conn):
            """Update template in database"""
            cursor = conn.cursor()
            query = f"""
                UPDATE task_templates
                SET {', '.join(updates)}
                WHERE template_id = ?
            """
            cursor.execute(query, params)
            return template_id

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_update_template_in_db, timeout=10.0)
            logger.info(f"Updated task template: {template_id}")
        except Exception as e:
            logger.error(f"Failed to update template: {e}", exc_info=True)
            raise

        # Return updated template
        return self.get_template(template_id)

    def delete_template(self, template_id: str) -> bool:
        """
        Delete a template

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        # Check if template exists
        existing = self.get_template(template_id)
        if not existing:
            return False

        # Define write function
        def _delete_template_from_db(conn):
            """Delete template from database"""
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM task_templates WHERE template_id = ?",
                (template_id,),
            )
            return True

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_delete_template_from_db, timeout=10.0)
            logger.info(f"Deleted task template: {template_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete template: {e}", exc_info=True)
            raise

    def create_task_from_template(
        self,
        template_id: str,
        title_override: Optional[str] = None,
        created_by_override: Optional[str] = None,
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Create a task from a template

        Args:
            template_id: Template ID
            title_override: Optional title to override template
            created_by_override: Optional creator to override template default
            metadata_override: Optional metadata to merge with template

        Returns:
            Created Task object

        Raises:
            ValueError: If template not found
        """
        # Get template
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Merge metadata
        metadata = dict(template.metadata_template) if template.metadata_template else {}
        if metadata_override:
            metadata.update(metadata_override)

        # Add template reference to metadata
        metadata["created_from_template"] = {
            "template_id": template_id,
            "template_name": template.name,
        }

        # Determine title and creator
        title = title_override if title_override else template.title_template
        created_by = created_by_override if created_by_override else template.created_by_default

        # Create task using TaskService
        from agentos.core.task.service import TaskService

        task_service = TaskService(db_path=self.db_path)
        task = task_service.create_draft_task(
            title=title,
            created_by=created_by,
            metadata=metadata,
        )

        # Increment template use_count
        self._increment_use_count(template_id)

        logger.info(f"Created task {task.task_id} from template {template_id}")
        return task

    def _increment_use_count(self, template_id: str) -> None:
        """
        Increment the use_count for a template

        Args:
            template_id: Template ID
        """

        def _increment_count_in_db(conn):
            """Increment use count"""
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE task_templates
                SET use_count = use_count + 1
                WHERE template_id = ?
                """,
                (template_id,),
            )

        writer = get_writer()
        try:
            writer.submit(_increment_count_in_db, timeout=5.0)
        except Exception as e:
            # Don't fail task creation if use_count increment fails
            logger.warning(f"Failed to increment use_count for template {template_id}: {e}")
