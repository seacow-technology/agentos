"""NetworkOS Health Check - Validates DB and Schema Integrity

Validates:
- Database accessibility (component_db_path("networkos"))
- Database write capability
- Schema version correctness (>= v54)
- Critical tables existence
- WAL mode enablement

Target: Complete all checks in <2 seconds.

Example:
    from agentos.networkos.health import NetworkOSHealthCheck

    checker = NetworkOSHealthCheck()
    all_passed, results = checker.run_all_checks()

    if not all_passed:
        print(f"Failed checks: {results['summary']['checks_failed']}")
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Tuple, Optional

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class NetworkOSHealthCheck:
    """NetworkOS database health checker.

    Validates database integrity and operational status:
    - DB file exists and is readable
    - DB is writable (creates/deletes test record)
    - Schema version is correct (>= v54)
    - Critical tables exist (network_tunnels, network_events, network_routes, tunnel_secrets)
    - WAL mode is enabled

    All checks complete in <2 seconds.
    """

    # Expected schema version for NetworkOS
    EXPECTED_SCHEMA_VERSION = 54

    # Critical tables that must exist
    REQUIRED_TABLES = [
        "network_tunnels",
        "network_events",
        "network_routes",
        "tunnel_secrets"
    ]

    def __init__(self, db_path: Optional[str] = None):
        """Initialize health checker.

        Args:
            db_path: Optional database path. If None, uses component_db_path("networkos")
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(component_db_path("networkos"))

        self.checks_passed = []
        self.checks_failed = []

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """Run all health checks.

        Returns:
            (all_passed, results_dict)

        Example:
            checker = NetworkOSHealthCheck()
            all_passed, results = checker.run_all_checks()

            if not all_passed:
                for check_name in results['summary']['checks_failed']:
                    print(f"FAILED: {check_name} - {results[check_name]['message']}")
        """
        checks = [
            self.check_db_exists,
            self.check_db_accessible,
            self.check_db_writable,
            self.check_schema_version,
            self.check_required_tables,
            self.check_wal_mode
        ]

        results = {}

        for check in checks:
            check_name = check.__name__
            try:
                passed, message = check()
                results[check_name] = {"passed": passed, "message": message}

                if passed:
                    self.checks_passed.append(check_name)
                    logger.info(f"✅ {check_name}: {message}")
                else:
                    self.checks_failed.append(check_name)
                    logger.error(f"❌ {check_name}: {message}")

            except Exception as e:
                results[check_name] = {"passed": False, "message": f"Exception: {e}"}
                self.checks_failed.append(check_name)
                logger.error(f"❌ {check_name}: Exception: {e}")

        all_passed = len(self.checks_failed) == 0

        results["summary"] = {
            "all_passed": all_passed,
            "passed_count": len(self.checks_passed),
            "failed_count": len(self.checks_failed),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed
        }

        return all_passed, results

    def check_db_exists(self) -> Tuple[bool, str]:
        """Check if database file exists."""
        if not self.db_path.exists():
            return False, (
                f"Database not found: {self.db_path}\n"
                f"Fix: Run migration or initialize NetworkOS"
            )

        # Check size
        size_kb = self.db_path.stat().st_size / 1024
        return True, f"Database exists: {self.db_path} ({size_kb:.2f} KB)"

    def check_db_accessible(self) -> Tuple[bool, str]:
        """Check if database can be opened and queried."""
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            return True, "Database is accessible"
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                return False, (
                    f"Database is locked: {e}\n"
                    f"Fix: Close other connections or check for stale locks"
                )
            return False, f"Database access error: {e}"
        except Exception as e:
            return False, f"Failed to access database: {e}"

    def check_db_writable(self) -> Tuple[bool, str]:
        """Check if database is writable by inserting and deleting a test event."""
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)

            # Check if network_events table exists first
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='network_events'
            """)
            if not cursor.fetchone():
                conn.close()
                return False, (
                    "Cannot test write capability: network_events table does not exist\n"
                    "Fix: Run schema migration v54"
                )

            # Insert test event
            test_event_id = f"health_check_{utc_now_ms()}"
            conn.execute("""
                INSERT INTO network_events (
                    event_id, tunnel_id, level, event_type, message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                test_event_id,
                "health_check_tunnel",
                "info",
                "health_check",
                "Health check test event",
                utc_now_ms()
            ))
            conn.commit()

            # Delete test event
            conn.execute("DELETE FROM network_events WHERE event_id = ?", (test_event_id,))
            conn.commit()
            conn.close()

            return True, "Database is writable"

        except sqlite3.OperationalError as e:
            if "readonly" in str(e).lower():
                return False, (
                    f"Database is read-only: {e}\n"
                    f"Fix: Check file permissions (chmod 644 {self.db_path})"
                )
            return False, f"Write operation failed: {e}"
        except Exception as e:
            return False, f"Failed to test write capability: {e}"

    def check_schema_version(self) -> Tuple[bool, str]:
        """Check if schema version is correct (>= v54).

        NetworkOS requires schema v54 which introduces the network tables.
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)

            # Check if schema_version table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)
            if not cursor.fetchone():
                conn.close()
                return False, (
                    "schema_version table does not exist\n"
                    "Fix: Run database migration system"
                )

            # Get latest version
            cursor = conn.execute("""
                SELECT version FROM schema_version
                ORDER BY applied_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()

            if not row:
                return False, (
                    "No schema version found\n"
                    "Fix: Run database migration system"
                )

            version_str = row[0]

            # Parse version (format: "0.54.0" → 54 or "v54" → 54)
            try:
                if version_str.startswith('v'):
                    # Format: "v54"
                    version_num = int(version_str[1:])
                elif '.' in version_str:
                    # Format: "0.54.0"
                    parts = version_str.split('.')
                    version_num = int(parts[1]) if len(parts) > 1 else int(parts[0])
                else:
                    # Format: "54"
                    version_num = int(version_str)
            except (IndexError, ValueError):
                return False, (
                    f"Cannot parse schema version: {version_str}\n"
                    f"Expected format: v54, 0.54.0, or 54"
                )

            if version_num >= self.EXPECTED_SCHEMA_VERSION:
                return True, f"Schema version: {version_str} (>= v{self.EXPECTED_SCHEMA_VERSION}) ✓"
            else:
                return False, (
                    f"Schema version: {version_str} (current) < v{self.EXPECTED_SCHEMA_VERSION} (required)\n"
                    f"Fix: Run migration to v{self.EXPECTED_SCHEMA_VERSION}"
                )

        except Exception as e:
            return False, f"Failed to check schema version: {e}"

    def check_required_tables(self) -> Tuple[bool, str]:
        """Check if all required NetworkOS tables exist.

        Required tables:
        - network_tunnels: Tunnel configurations
        - network_events: Event logs
        - network_routes: Routing information
        - tunnel_secrets: Encrypted credentials
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)

            # Get all table names
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            # Check for missing required tables
            missing_tables = [t for t in self.REQUIRED_TABLES if t not in existing_tables]

            if missing_tables:
                return False, (
                    f"Missing required tables: {', '.join(missing_tables)}\n"
                    f"Fix: Run schema migration v54 to create NetworkOS tables"
                )

            return True, f"All required tables exist: {', '.join(self.REQUIRED_TABLES)}"

        except Exception as e:
            return False, f"Failed to check tables: {e}"

    def check_wal_mode(self) -> Tuple[bool, str]:
        """Check if SQLite WAL mode is enabled.

        WAL mode provides better concurrency for multi-process scenarios.
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            conn.close()

            if mode.upper() == "WAL":
                return True, f"WAL mode enabled: {mode}"
            else:
                return False, (
                    f"WAL mode not enabled: {mode} (expected WAL)\n"
                    f"Fix: Run: sqlite3 {self.db_path} 'PRAGMA journal_mode=WAL;'"
                )

        except Exception as e:
            return False, f"Failed to check WAL mode: {e}"


def get_health_status() -> Dict[str, any]:
    """Get NetworkOS health status (convenience function).

    Returns:
        Dict with health check results including:
        - status: "ok" | "warn" | "error"
        - all_passed: bool
        - checks: dict of individual check results
        - summary: aggregated summary

    Example:
        from agentos.networkos.health import get_health_status

        status = get_health_status()
        if status['status'] != 'ok':
            print(f"NetworkOS unhealthy: {status['summary']}")
    """
    checker = NetworkOSHealthCheck()
    all_passed, results = checker.run_all_checks()

    status = "ok" if all_passed else "error"

    return {
        "status": status,
        "all_passed": all_passed,
        "checks": results,
        "summary": results.get("summary", {}),
        "message": "NetworkOS healthy" if all_passed else "NetworkOS health check failed"
    }


__all__ = [
    'NetworkOSHealthCheck',
    'get_health_status'
]
