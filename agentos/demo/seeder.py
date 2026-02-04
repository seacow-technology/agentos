"""
Demo Data Seeder

Loads seed data from YAML files and provides access to demo data.

Design:
- Load seed data from agentos/demo/seeds/ directory
- Parse YAML files into structured data
- Provide methods to query demo data
- Thread-safe singleton pattern for data cache

Usage:
    from agentos.demo.seeder import DemoDataSeeder

    seeder = DemoDataSeeder()
    projects = seeder.load_projects()
    tasks = seeder.load_tasks(project_id="demo-project-001")
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

logger = logging.getLogger(__name__)


class DemoDataSeeder:
    """
    Demo data seeder that loads and provides access to seed data.

    Singleton pattern ensures only one instance loads the data.
    """

    _instance = None
    _data_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.seeds_dir = Path(__file__).parent / "seeds" / "core"

        # Validate seeds directory exists
        if not self.seeds_dir.exists():
            logger.warning(f"Demo seeds directory not found: {self.seeds_dir}")
            self.seeds_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"DemoDataSeeder initialized with seeds_dir: {self.seeds_dir}")

    def _load_yaml_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Load and parse a YAML seed file.

        Args:
            filename: Name of the YAML file (e.g., "projects.yaml")

        Returns:
            Parsed YAML data or None if file not found
        """
        file_path = self.seeds_dir / filename

        # Check cache first
        cache_key = str(file_path)
        if cache_key in self._data_cache:
            logger.debug(f"Returning cached data for {filename}")
            return self._data_cache[cache_key]

        # Load from file
        if not file_path.exists():
            logger.warning(f"Seed file not found: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Cache the data
            self._data_cache[cache_key] = data
            logger.info(f"Loaded seed data from {filename}")

            return data

        except Exception as e:
            logger.error(f"Failed to load seed file {filename}: {e}", exc_info=True)
            return None

    def load_projects(self) -> List[Dict[str, Any]]:
        """
        Load demo projects.

        Returns:
            List of project dictionaries
        """
        data = self._load_yaml_file("projects.yaml")
        if not data or "projects" not in data:
            logger.warning("No projects found in seed data")
            return []

        projects = data["projects"]
        logger.info(f"Loaded {len(projects)} demo projects")
        return projects

    def load_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load demo tasks, optionally filtered by project.

        Args:
            project_id: Optional project ID to filter tasks

        Returns:
            List of task dictionaries
        """
        data = self._load_yaml_file("tasks.yaml")
        if not data or "tasks" not in data:
            logger.warning("No tasks found in seed data")
            return []

        tasks = data["tasks"]

        # Filter by project if specified
        if project_id:
            tasks = [t for t in tasks if t.get("project_id") == project_id]
            logger.info(f"Loaded {len(tasks)} demo tasks for project {project_id}")
        else:
            logger.info(f"Loaded {len(tasks)} demo tasks")

        return tasks

    def load_chat_sessions(self) -> List[Dict[str, Any]]:
        """
        Load demo chat sessions.

        Returns:
            List of session dictionaries with messages
        """
        data = self._load_yaml_file("chat_sessions.yaml")
        if not data or "sessions" not in data:
            logger.warning("No chat sessions found in seed data")
            return []

        sessions = data["sessions"]
        logger.info(f"Loaded {len(sessions)} demo chat sessions")
        return sessions

    def load_memory(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load demo memory items, optionally filtered by scope.

        Args:
            scope: Optional scope to filter memory ("user", "project", "system")

        Returns:
            List of memory item dictionaries
        """
        data = self._load_yaml_file("memory.yaml")
        if not data or "memory" not in data:
            logger.warning("No memory items found in seed data")
            return []

        memory = data["memory"]

        # Filter by scope if specified
        if scope:
            memory = [m for m in memory if m.get("scope") == scope]
            logger.info(f"Loaded {len(memory)} demo memory items for scope {scope}")
        else:
            logger.info(f"Loaded {len(memory)} demo memory items")

        return memory

    def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific demo project by ID.

        Args:
            project_id: Project ID to find

        Returns:
            Project dictionary or None if not found
        """
        projects = self.load_projects()
        for project in projects:
            if project.get("id") == project_id:
                return project
        return None

    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific demo task by ID.

        Args:
            task_id: Task ID to find

        Returns:
            Task dictionary or None if not found
        """
        tasks = self.load_tasks()
        for task in tasks:
            if task.get("id") == task_id:
                return task
        return None

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific demo session by ID.

        Args:
            session_id: Session ID to find

        Returns:
            Session dictionary or None if not found
        """
        sessions = self.load_chat_sessions()
        for session in sessions:
            if session.get("id") == session_id:
                return session
        return None

    def clear_cache(self):
        """
        Clear the data cache, forcing reload on next access.
        """
        self._data_cache.clear()
        logger.info("Demo data cache cleared")

    def get_available_modules(self) -> List[str]:
        """
        Get list of available seed modules.

        Returns:
            List of module names (e.g., ["projects", "tasks", "chat_sessions", "memory"])
        """
        modules = []

        for yaml_file in self.seeds_dir.glob("*.yaml"):
            module_name = yaml_file.stem
            modules.append(module_name)

        logger.debug(f"Available seed modules: {modules}")
        return modules

    def persist_projects(self, projects: List[Dict[str, Any]]) -> int:
        """
        Persist projects to database.

        Args:
            projects: List of project dictionaries

        Returns:
            Number of projects inserted
        """
        from agentos.core.db import SQLiteWriter
        from agentos.core.storage.paths import component_db_path
        import json

        if not projects:
            return 0

        try:
            db_path = str(component_db_path("agentos"))
            writer = SQLiteWriter(db_path)

            def insert_projects(conn):
                cursor = conn.cursor()
                count = 0

                for proj in projects:
                    # Map YAML fields to DB schema
                    cursor.execute("""
                        INSERT OR REPLACE INTO projects
                        (project_id, name, description, path, added_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        proj.get("id"),
                        proj.get("name"),
                        proj.get("description"),
                        proj.get("path", ""),
                        proj.get("created_at"),
                        json.dumps(proj.get("metadata", {}))
                    ))
                    count += 1

                conn.commit()
                return count

            inserted = writer.submit(insert_projects, timeout=10.0)
            logger.info(f"Persisted {inserted} projects to database")
            return inserted

        except Exception as e:
            logger.error(f"Failed to persist projects: {e}", exc_info=True)
            return 0

    def persist_tasks(self, tasks: List[Dict[str, Any]]) -> int:
        """
        Persist tasks to database.

        Args:
            tasks: List of task dictionaries

        Returns:
            Number of tasks inserted
        """
        from agentos.core.db import SQLiteWriter
        from agentos.core.storage.paths import component_db_path
        import json

        if not tasks:
            return 0

        try:
            db_path = str(component_db_path("agentos"))
            writer = SQLiteWriter(db_path)

            def insert_tasks(conn):
                cursor = conn.cursor()
                count = 0

                for task in tasks:
                    # Ensure demo scope in metadata
                    metadata = task.get("metadata", {})
                    metadata["scope"] = "demo"

                    cursor.execute("""
                        INSERT OR REPLACE INTO tasks
                        (task_id, title, status, created_at, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        task.get("id"),
                        task.get("title"),
                        task.get("status", "pending"),
                        task.get("created_at"),
                        json.dumps(metadata)
                    ))
                    count += 1

                conn.commit()
                return count

            inserted = writer.submit(insert_tasks, timeout=10.0)
            logger.info(f"Persisted {inserted} tasks to database")
            return inserted

        except Exception as e:
            logger.error(f"Failed to persist tasks: {e}", exc_info=True)
            return 0

    def persist_chat_sessions(self, sessions: List[Dict[str, Any]]) -> int:
        """
        Persist chat sessions and messages to database.

        Args:
            sessions: List of session dictionaries with messages

        Returns:
            Number of sessions inserted
        """
        from agentos.core.db import SQLiteWriter
        from agentos.core.storage.paths import component_db_path
        import json

        if not sessions:
            return 0

        try:
            db_path = str(component_db_path("agentos"))
            writer = SQLiteWriter(db_path)

            def insert_sessions(conn):
                cursor = conn.cursor()
                count = 0

                for session in sessions:
                    session_id = session.get("id")

                    # Insert session
                    cursor.execute("""
                        INSERT OR REPLACE INTO chat_sessions
                        (session_id, title, created_at, updated_at, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        session.get("title"),
                        session.get("created_at"),
                        session.get("updated_at"),
                        json.dumps(session.get("metadata", {}))
                    ))

                    # Insert messages
                    messages = session.get("messages", [])
                    for msg in messages:
                        cursor.execute("""
                            INSERT OR REPLACE INTO chat_messages
                            (message_id, session_id, role, content, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            msg.get("id"),
                            session_id,
                            msg.get("role"),
                            msg.get("content"),
                            msg.get("created_at")
                        ))

                    count += 1

                conn.commit()
                return count

            inserted = writer.submit(insert_sessions, timeout=10.0)
            logger.info(f"Persisted {inserted} chat sessions to database")
            return inserted

        except Exception as e:
            logger.error(f"Failed to persist chat sessions: {e}", exc_info=True)
            return 0

    def persist_memories(self, memories: List[Dict[str, Any]]) -> int:
        """
        Persist memory items to database.

        Args:
            memories: List of memory dictionaries

        Returns:
            Number of memories inserted
        """
        from agentos.core.db import SQLiteWriter
        from agentos.core.storage.paths import component_db_path
        import json

        if not memories:
            return 0

        try:
            db_path = str(component_db_path("agentos"))
            writer = SQLiteWriter(db_path)

            def insert_memories(conn):
                cursor = conn.cursor()
                count = 0

                for memory in memories:
                    # Ensure demo scope in metadata
                    metadata = memory.get("metadata", {})
                    metadata["scope"] = "demo"

                    cursor.execute("""
                        INSERT OR REPLACE INTO memory_items
                        (id, scope, type, content, tags, created_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        memory.get("id"),
                        memory.get("scope", "demo"),
                        memory.get("type", "fact"),
                        memory.get("content"),
                        memory.get("tags", ""),
                        memory.get("created_at"),
                        json.dumps(metadata)
                    ))
                    count += 1

                conn.commit()
                return count

            inserted = writer.submit(insert_memories, timeout=10.0)
            logger.info(f"Persisted {inserted} memory items to database")
            return inserted

        except Exception as e:
            logger.error(f"Failed to persist memories: {e}", exc_info=True)
            return 0


# Convenience function to get seeder instance
def get_demo_seeder() -> DemoDataSeeder:
    """
    Get the singleton DemoDataSeeder instance.

    Returns:
        DemoDataSeeder instance
    """
    return DemoDataSeeder()
