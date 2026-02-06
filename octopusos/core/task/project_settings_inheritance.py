"""Project Settings Inheritance Module

This module handles inheriting project configuration settings when creating and executing tasks.
Implements Task #13: Task inherits Project Settings at creation time.

Configuration Priority:
    Task explicit settings > Project settings > Global defaults

Key Features:
1. Default Runner inheritance (Task.runner > Project.default_runner > Global)
2. Environment Variables injection (Project.env_overrides)
3. Risk Profile enforcement (allow_shell_write, writable_paths, require_admin_token)
4. Working Directory configuration (Task.workdir > Project.default_workdir > Global)
5. Audit logging of settings inheritance

Created: 2025-01-29
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from agentos.schemas.project import Project, ProjectSettings, RiskProfile
from agentos.core.task.models import Task
from agentos.store import get_db
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class ProjectSettingsInheritance:
    """Handles project settings inheritance for task execution

    This service loads project settings and applies them to tasks,
    enforcing the configuration priority hierarchy.
    """

    # Environment variable whitelist - only these vars can be overridden
    ENV_WHITELIST = {
        'PYTHONPATH', 'PATH', 'DEBUG', 'LOG_LEVEL', 'ENVIRONMENT',
        'API_BASE_URL', 'DATABASE_URL', 'REDIS_URL', 'NODE_ENV',
        'JAVA_HOME', 'MAVEN_OPTS', 'GRADLE_OPTS',
        'NPM_CONFIG_PREFIX', 'CARGO_HOME', 'RUSTUP_HOME',
    }

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize settings inheritance service

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path

    def get_project(self, project_id: str) -> Optional[Project]:
        """Load project from database

        Args:
            project_id: Project ID

        Returns:
            Project object or None if not found
        """
        try:
            if self.db_path:
                import sqlite3
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
            else:
                conn = get_db()

            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id, name, description, status, tags,
                    default_repo_id, default_workdir, settings,
                    created_at, updated_at, created_by, path, metadata
                FROM projects
                WHERE id = ?
            """, (project_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Convert row to dict
            project_data = dict(row)

            # Create Project object (repos can be empty for this use case)
            project = Project.from_db_row(project_data, repos=[])

            # Do NOT close: get_db() returns shared thread-local connection
            # conn.close()  # REMOVED

            return project

        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}", exc_info=True)
            return None

    def get_effective_runner(self, task: Task, project: Optional[Project] = None) -> Optional[str]:
        """Determine effective runner for task execution

        Priority: Task.runner > Project.default_runner > Global default

        Args:
            task: Task object
            project: Optional project object (loaded if None and task.project_id exists)

        Returns:
            Runner name or None for global default
        """
        # Task explicit runner takes highest priority
        if task.metadata.get('runner'):
            return task.metadata['runner']

        # Load project if needed
        if not project and task.project_id:
            project = self.get_project(task.project_id)

        # Project default runner
        if project and project.settings and project.settings.default_runner:
            return project.settings.default_runner

        # Fall back to global default (None means use system default)
        return None

    def get_effective_env(self, task: Task, project: Optional[Project] = None) -> Dict[str, str]:
        """Build effective environment variables for task execution

        Merges system env, project overrides (whitelist only), and task-specific env.

        Priority: Task.env > Project.env_overrides > System env

        Args:
            task: Task object
            project: Optional project object

        Returns:
            Dictionary of environment variables
        """
        # Start with system environment
        env = os.environ.copy()

        # Load project if needed
        if not project and task.project_id:
            project = self.get_project(task.project_id)

        # Apply project environment overrides (whitelist only)
        if project and project.settings and project.settings.env_overrides:
            for key, value in project.settings.env_overrides.items():
                if self._is_env_whitelisted(key):
                    env[key] = value
                    logger.debug(f"Applied project env override: {key}={value}")
                else:
                    logger.warning(f"Ignoring non-whitelisted env var: {key}")

        # Apply task-specific environment (if stored in metadata)
        task_env = task.metadata.get('env', {})
        if task_env:
            env.update(task_env)

        return env

    def get_effective_workdir(self, task: Task, project: Optional[Project] = None) -> str:
        """Determine effective working directory for task execution

        Priority: Task.workdir > Project.default_workdir > Current directory

        Args:
            task: Task object
            project: Optional project object

        Returns:
            Working directory path
        """
        # Task explicit workdir
        task_workdir = task.metadata.get('workdir')
        if task_workdir:
            return task_workdir

        # Load project if needed
        if not project and task.project_id:
            project = self.get_project(task.project_id)

        # Project default workdir
        if project and project.default_workdir:
            return project.default_workdir

        # Fall back to current directory
        return str(Path.cwd())

    def check_operation_allowed(
        self,
        task: Task,
        operation_type: str,
        target_path: Optional[str] = None,
        project: Optional[Project] = None
    ) -> bool:
        """Check if an operation is allowed based on project risk profile

        Args:
            task: Task object
            operation_type: Operation type ('shell_write', 'admin_operation', etc.)
            target_path: Optional target path for write operations
            project: Optional project object

        Returns:
            True if operation is allowed, False otherwise
        """
        # Load project if needed
        if not project and task.project_id:
            project = self.get_project(task.project_id)

        # No project or no risk profile - use permissive defaults
        if not project or not project.settings or not project.settings.risk_profile:
            return self._get_default_policy(operation_type)

        risk_profile = project.settings.risk_profile

        if operation_type == 'shell_write':
            # Check if shell write operations are allowed
            if not risk_profile.allow_shell_write:
                logger.warning(f"Shell write operation denied by project {project.id} risk profile")
                return False

            # If allowed, check if path is in whitelist
            if target_path and risk_profile.writable_paths:
                target_path_obj = Path(target_path).resolve()
                for allowed_path in risk_profile.writable_paths:
                    allowed_path_obj = Path(allowed_path).resolve()
                    try:
                        # Check if target is under allowed path
                        target_path_obj.relative_to(allowed_path_obj)
                        return True
                    except ValueError:
                        continue

                logger.warning(
                    f"Path {target_path} not in writable_paths whitelist "
                    f"for project {project.id}"
                )
                return False

            return True

        elif operation_type == 'admin_operation':
            # Check if admin token is required
            if risk_profile.require_admin_token:
                # Check if admin token exists (would be in environment or metadata)
                has_token = self._has_valid_admin_token(task)
                if not has_token:
                    logger.warning(
                        f"Admin operation denied - no valid token for project {project.id}"
                    )
                return has_token
            return True

        # Unknown operation type - default to deny
        logger.warning(f"Unknown operation type: {operation_type}")
        return False

    def log_settings_inheritance(self, task_id: str, project: Project) -> None:
        """Log task settings inheritance to audit trail

        Records which project settings were inherited by the task,
        including a hash of the settings for tracking changes.

        Args:
            task_id: Task ID
            project: Project object
        """
        try:
            if not project.settings:
                return

            # Calculate settings hash for tracking
            settings_json = json.dumps(
                project.settings.model_dump(),
                sort_keys=True
            )
            settings_hash = hashlib.sha256(settings_json.encode()).hexdigest()[:16]

            # Prepare audit metadata
            metadata = {
                'project_id': project.id,
                'project_name': project.name,
                'settings_hash': settings_hash,
            }

            # Add inherited settings details
            if project.settings.default_runner:
                metadata['inherited_runner'] = project.settings.default_runner

            if project.settings.env_overrides:
                metadata['inherited_env_count'] = len(project.settings.env_overrides)
                metadata['inherited_env_keys'] = list(project.settings.env_overrides.keys())

            if project.settings.risk_profile:
                metadata['risk_profile_applied'] = True
                metadata['allow_shell_write'] = project.settings.risk_profile.allow_shell_write
                metadata['require_admin_token'] = project.settings.risk_profile.require_admin_token
                if project.settings.risk_profile.writable_paths:
                    metadata['writable_paths_count'] = len(project.settings.risk_profile.writable_paths)

            # Insert audit log
            if self.db_path:
                import sqlite3
                conn = sqlite3.connect(str(self.db_path))
            else:
                conn = get_db()

            cursor = conn.cursor()
            now = utc_now_iso()

            cursor.execute("""
                INSERT INTO task_audits (task_id, level, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                task_id,
                'info',
                'PROJECT_SETTINGS_INHERITED',
                json.dumps(metadata),
                now
            ))

            conn.commit()

            # Do NOT close: get_db() returns shared thread-local connection
            # Only close if we created a new connection (self.db_path is set)
            if self.db_path:
                conn.close()

            logger.info(
                f"Logged settings inheritance for task {task_id}: "
                f"project={project.name}, hash={settings_hash}"
            )

        except Exception as e:
            logger.error(f"Failed to log settings inheritance: {e}", exc_info=True)

    def apply_project_settings(self, task: Task) -> Dict[str, Any]:
        """Apply project settings to a task and return effective configuration

        This is the main entry point for applying project settings inheritance.
        Called during task creation or before task execution.

        Args:
            task: Task object

        Returns:
            Dictionary with effective configuration:
            - runner: Effective runner name
            - env: Effective environment variables
            - workdir: Effective working directory
            - risk_profile: Effective risk profile settings
        """
        # Load project if task has project_id
        project = None
        if task.project_id:
            project = self.get_project(task.project_id)
            if project:
                logger.info(f"Applying settings from project {project.name} to task {task.task_id}")
                # Log the inheritance
                self.log_settings_inheritance(task.task_id, project)
            else:
                logger.warning(f"Project {task.project_id} not found for task {task.task_id}")

        # Build effective configuration
        effective_config = {
            'runner': self.get_effective_runner(task, project),
            'env': self.get_effective_env(task, project),
            'workdir': self.get_effective_workdir(task, project),
            'risk_profile': None,
        }

        # Add risk profile if exists
        if project and project.settings and project.settings.risk_profile:
            effective_config['risk_profile'] = {
                'allow_shell_write': project.settings.risk_profile.allow_shell_write,
                'require_admin_token': project.settings.risk_profile.require_admin_token,
                'writable_paths': project.settings.risk_profile.writable_paths,
            }

        return effective_config

    # Private helper methods

    def _is_env_whitelisted(self, key: str) -> bool:
        """Check if environment variable is whitelisted

        Args:
            key: Environment variable name

        Returns:
            True if whitelisted
        """
        return key in self.ENV_WHITELIST

    def _get_default_policy(self, operation_type: str) -> bool:
        """Get default policy for operation type when no risk profile exists

        Args:
            operation_type: Operation type

        Returns:
            True if operation is allowed by default
        """
        # Default policies (permissive for backward compatibility)
        defaults = {
            'shell_write': True,
            'admin_operation': True,
        }
        return defaults.get(operation_type, False)

    def _has_valid_admin_token(self, task: Task) -> bool:
        """Check if task has valid admin token

        Args:
            task: Task object

        Returns:
            True if valid admin token exists
        """
        # Check in task metadata
        if task.metadata.get('admin_token'):
            return True

        # Check in environment
        if os.environ.get('ADMIN_TOKEN'):
            return True

        return False


# Convenience functions for easy import

def apply_project_settings(task: Task, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Convenience function to apply project settings to a task

    Args:
        task: Task object
        db_path: Optional database path

    Returns:
        Effective configuration dictionary
    """
    service = ProjectSettingsInheritance(db_path)
    return service.apply_project_settings(task)


def check_operation_allowed(
    task: Task,
    operation_type: str,
    target_path: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Convenience function to check if operation is allowed

    Args:
        task: Task object
        operation_type: Operation type
        target_path: Optional target path
        db_path: Optional database path

    Returns:
        True if operation is allowed
    """
    service = ProjectSettingsInheritance(db_path)
    return service.check_operation_allowed(task, operation_type, target_path)
