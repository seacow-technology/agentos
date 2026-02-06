#!/usr/bin/env python3
"""
Demo Reset Manager

Provides reliable demo data reset functionality with verification.
"""

import logging
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DemoResetManager:
    """Demo reset manager for reliable data cleanup and regeneration"""

    DEMO_SCOPE = "demo"
    DEMO_PROJECT_PREFIX = "demo-"
    DEMO_SESSION_PREFIX = "demo-session-"

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self.seeder = None  # Lazy load
        self._reset_log_path = Path.home() / ".agentos" / "demo_reset_log.json"

    def reset_all(self, verify: bool = True) -> Dict[str, Any]:
        """
        Completely reset all demo data

        Args:
            verify: Whether to verify reset state

        Returns:
            Reset result report
        """
        logger.info("Starting demo data reset...")

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "success": False,
            "verification": None
        }

        try:
            # Step 1: Delete demo data
            step1 = self._delete_demo_data()
            result["steps"].append(step1)

            # Step 2: Clean up temp files
            step2 = self._cleanup_temp_files()
            result["steps"].append(step2)

            # Step 3: Regenerate seed data
            step3 = self._regenerate_seed_data()
            result["steps"].append(step3)

            # Step 4: Verification (optional)
            if verify:
                result["verification"] = self._verify_reset()

            # Check if all steps succeeded
            all_success = all(s["success"] for s in result["steps"])
            result["success"] = all_success

            if all_success:
                logger.info("✅ Demo data reset successful")
                self._save_reset_log(result)
            else:
                logger.warning("⚠️ Demo data reset partially failed")

        except Exception as e:
            logger.error(f"❌ Demo data reset failed: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    def _delete_demo_data(self) -> Dict[str, Any]:
        """Delete all demo data from database"""
        from agentos.core.db import SQLiteWriter
        from agentos.core.storage.paths import component_db_path

        deleted = {
            "projects": 0,
            "sessions": 0,
            "tasks": 0,
            "memories": 0,
            "messages": 0
        }

        try:
            db_path = str(component_db_path("agentos"))
            writer = SQLiteWriter(db_path)

            # Delete demo projects
            def delete_projects(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM projects
                    WHERE project_id LIKE ?
                """, (f"{self.DEMO_PROJECT_PREFIX}%",))
                conn.commit()
                return cursor.rowcount

            deleted["projects"] = writer.submit(delete_projects, timeout=10.0)

            # Delete demo chat sessions
            def delete_sessions(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM chat_sessions
                    WHERE session_id LIKE ?
                """, (f"{self.DEMO_SESSION_PREFIX}%",))
                conn.commit()
                return cursor.rowcount

            deleted["sessions"] = writer.submit(delete_sessions, timeout=10.0)

            # Delete demo chat messages
            def delete_messages(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM chat_messages
                    WHERE session_id LIKE ?
                """, (f"{self.DEMO_SESSION_PREFIX}%",))
                conn.commit()
                return cursor.rowcount

            deleted["messages"] = writer.submit(delete_messages, timeout=10.0)

            # Delete demo tasks
            def delete_tasks(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM tasks
                    WHERE json_extract(metadata, '$.scope') = ?
                """, (self.DEMO_SCOPE,))
                conn.commit()
                return cursor.rowcount

            deleted["tasks"] = writer.submit(delete_tasks, timeout=10.0)

            # Delete demo memories
            def delete_memories(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM memory_items
                    WHERE json_extract(metadata, '$.scope') = ?
                """, (self.DEMO_SCOPE,))
                conn.commit()
                return cursor.rowcount

            deleted["memories"] = writer.submit(delete_memories, timeout=10.0)

            logger.info(f"Deleted demo data: {deleted}")

            return {
                "step": "delete_demo_data",
                "success": True,
                "deleted": deleted
            }

        except Exception as e:
            logger.error(f"Failed to delete demo data: {e}", exc_info=True)
            return {
                "step": "delete_demo_data",
                "success": False,
                "error": str(e)
            }

    def _cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up temporary files"""
        temp_dirs = [
            Path.home() / ".agentos" / "demo_temp",
            Path("/tmp") / "agentos_demo"
        ]

        cleaned = 0
        errors = []

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    cleaned += 1
                    logger.info(f"Cleaned temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean {temp_dir}: {e}")
                    errors.append(str(e))

        return {
            "step": "cleanup_temp_files",
            "success": len(errors) == 0,
            "cleaned": cleaned,
            "errors": errors
        }

    def _regenerate_seed_data(self) -> Dict[str, Any]:
        """Regenerate seed data from YAML files"""
        from agentos.demo.seeder import get_demo_seeder

        try:
            seeder = get_demo_seeder()

            # Load seed data from YAML
            projects = seeder.load_projects()
            tasks = seeder.load_tasks()
            sessions = seeder.load_chat_sessions()
            memories = seeder.load_memory()

            # Persist to database
            persisted = {
                "projects": seeder.persist_projects(projects),
                "tasks": seeder.persist_tasks(tasks),
                "sessions": seeder.persist_chat_sessions(sessions),
                "memories": seeder.persist_memories(memories)
            }

            logger.info(f"Regenerated seed data: {persisted}")

            return {
                "step": "regenerate_seed_data",
                "success": True,
                "generated": persisted
            }

        except Exception as e:
            logger.error(f"Failed to regenerate seed data: {e}", exc_info=True)
            return {
                "step": "regenerate_seed_data",
                "success": False,
                "error": str(e)
            }

    def _verify_reset(self) -> Dict[str, Any]:
        """Verify reset state"""
        from agentos.core.db.registry_db import get_db

        checks = {}

        try:
            conn = get_db()
            cursor = conn.cursor()

            # Count demo projects
            cursor.execute(
                "SELECT COUNT(*) FROM projects WHERE project_id LIKE ?",
                (f"{self.DEMO_PROJECT_PREFIX}%",)
            )
            checks["demo_projects"] = cursor.fetchone()[0]

            # Count demo sessions
            cursor.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE session_id LIKE ?",
                (f"{self.DEMO_SESSION_PREFIX}%",)
            )
            checks["demo_sessions"] = cursor.fetchone()[0]

            # Count demo tasks
            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE json_extract(metadata, '$.scope') = ?",
                (self.DEMO_SCOPE,)
            )
            checks["demo_tasks"] = cursor.fetchone()[0]

            # Count demo memories
            cursor.execute(
                "SELECT COUNT(*) FROM memory_items WHERE json_extract(metadata, '$.scope') = ?",
                (self.DEMO_SCOPE,)
            )
            checks["demo_memories"] = cursor.fetchone()[0]

            # Expected counts from seed files
            expected = {
                "demo_projects": 5,  # From projects.yaml
                "demo_sessions": 3,  # From chat_sessions.yaml
                "demo_tasks": 0,     # Tasks may vary
                "demo_memories": 0   # Memories may vary
            }

            # Verify
            issues = []
            for key, expected_count in expected.items():
                actual = checks.get(key, 0)
                if actual != expected_count and expected_count > 0:
                    issues.append(f"{key}: expected {expected_count}, got {actual}")

            passed = len(issues) == 0

            return {
                "passed": passed,
                "checks": checks,
                "expected": expected,
                "issues": issues
            }

        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            return {
                "passed": False,
                "error": str(e)
            }

    def get_health_status(self) -> Dict[str, Any]:
        """Get current demo health status"""
        from agentos.core.db.registry_db import get_db
        from agentos.demo.seeder import get_demo_seeder

        try:
            conn = get_db()
            cursor = conn.cursor()

            # Count demo data
            cursor.execute(
                "SELECT COUNT(*) FROM projects WHERE project_id LIKE ?",
                (f"{self.DEMO_PROJECT_PREFIX}%",)
            )
            projects_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE session_id LIKE ?",
                (f"{self.DEMO_SESSION_PREFIX}%",)
            )
            sessions_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE json_extract(metadata, '$.scope') = ?",
                (self.DEMO_SCOPE,)
            )
            tasks_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM memory_items WHERE json_extract(metadata, '$.scope') = ?",
                (self.DEMO_SCOPE,)
            )
            memories_count = cursor.fetchone()[0]

            # Get seed hash
            seeder = get_demo_seeder()
            seed_hash = self._compute_seed_hash(seeder)

            # Get last reset time
            last_reset = self._get_last_reset_time()

            # Check health
            expected_projects = 5
            expected_sessions = 3
            healthy = (projects_count == expected_projects and
                      sessions_count == expected_sessions)

            issues = []
            if projects_count != expected_projects:
                issues.append(f"Projects count mismatch: expected {expected_projects}, got {projects_count}")
            if sessions_count != expected_sessions:
                issues.append(f"Sessions count mismatch: expected {expected_sessions}, got {sessions_count}")

            return {
                "data": {
                    "projects": projects_count,
                    "sessions": sessions_count,
                    "tasks": tasks_count,
                    "memories": memories_count
                },
                "seed": {
                    "version": "1.0.0",
                    "hash": seed_hash,
                    "last_reset": last_reset
                },
                "status": {
                    "healthy": healthy,
                    "issues": issues if issues else None
                },
                "log": self._get_recent_log()
            }

        except Exception as e:
            logger.error(f"Failed to get health status: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": {
                    "healthy": False,
                    "issues": [str(e)]
                }
            }

    def _compute_seed_hash(self, seeder) -> str:
        """Compute hash of seed files for version tracking"""
        try:
            seeds_dir = seeder.seeds_dir
            hasher = hashlib.sha256()

            for yaml_file in sorted(seeds_dir.glob("*.yaml")):
                with open(yaml_file, 'rb') as f:
                    hasher.update(f.read())

            return hasher.hexdigest()[:12]
        except Exception as e:
            logger.warning(f"Failed to compute seed hash: {e}")
            return "unknown"

    def _get_last_reset_time(self) -> Optional[str]:
        """Get timestamp of last reset"""
        try:
            if self._reset_log_path.exists():
                import json
                with open(self._reset_log_path, 'r') as f:
                    log = json.load(f)
                    return log.get("timestamp")
        except Exception:
            pass
        return None

    def _save_reset_log(self, result: Dict[str, Any]) -> None:
        """Save reset log to file"""
        try:
            import json
            self._reset_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._reset_log_path, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save reset log: {e}")

    def _get_recent_log(self) -> Optional[str]:
        """Get recent reset log as string"""
        try:
            if self._reset_log_path.exists():
                import json
                with open(self._reset_log_path, 'r') as f:
                    log = json.load(f)
                    return json.dumps(log, indent=2)
        except Exception:
            pass
        return None

    def export_diagnostic(self) -> Dict[str, Any]:
        """Export diagnostic information"""
        health = self.get_health_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health,
            "system": {
                "db_path": str(Path.home() / ".agentos" / "store" / "agentos" / "db.sqlite"),
                "demo_scope": self.DEMO_SCOPE,
                "project_prefix": self.DEMO_PROJECT_PREFIX,
                "session_prefix": self.DEMO_SESSION_PREFIX
            }
        }


def get_demo_reset_manager() -> DemoResetManager:
    """Get singleton DemoResetManager instance"""
    return DemoResetManager()
