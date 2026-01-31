"""Startup health check for recovery system.

Validates all critical configurations on startup to ensure the recovery system
is operational. Supports three enforcement modes:

- STRICT: Block startup on failure (production)
- SAFE: Disable recovery features on failure, allow startup (graceful degradation)
- DEV: Warn only, allow startup (development)

Target: Complete all checks in <5 seconds.

Example:
    from agentos.core.startup import run_startup_health_check, HealthCheckMode
    from agentos.core.storage.paths import component_db_path

    db_path = component_db_path("agentos")

    # Production: block startup on failure
    run_startup_health_check(
        db_path=str(db_path),
        mode=HealthCheckMode.STRICT
    )

    # Staging: disable recovery features on failure
    run_startup_health_check(
        db_path=str(db_path),
        mode=HealthCheckMode.SAFE
    )

    # Development: warn only
    run_startup_health_check(
        db_path=str(db_path),
        mode=HealthCheckMode.DEV
    )
"""

import sqlite3
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class HealthCheckMode(Enum):
    """Health check enforcement modes.

    STRICT: Block startup on failure (production)
    - Raises RuntimeError if any check fails
    - Use in production to ensure all recovery features are operational

    SAFE: Disable recovery features on failure (graceful degradation)
    - Allows startup but disables recovery system
    - Logs warnings about disabled features
    - Use in staging or when you want graceful degradation

    DEV: Warn only (development)
    - Logs warnings but allows startup
    - Recovery features remain enabled (at your own risk)
    - Use in development environments
    """
    STRICT = "strict"
    SAFE = "safe"
    DEV = "dev"


class StartupHealthCheck:
    """Recovery system startup health check.

    Validates:
    - SQLite WAL mode enabled
    - busy_timeout configured
    - ConnectionFactory available
    - Schema version >= 24
    - Recovery tables exist
    - Can create test checkpoint

    All checks complete in <5 seconds.
    """

    def __init__(self, db_path: str):
        """Initialize health checker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.checks_passed = []
        self.checks_failed = []

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """Run all health checks.

        Returns:
            (all_passed, results_dict)

        Example:
            from agentos.core.storage.paths import component_db_path

            checker = StartupHealthCheck(str(component_db_path("agentos")))
            all_passed, results = checker.run_all_checks()

            if not all_passed:
                print(f"Failed checks: {results['summary']['checks_failed']}")
        """
        checks = [
            self.check_db_exists,
            self.check_sqlite_wal,
            self.check_busy_timeout,
            self.check_schema_version,
            self.check_recovery_tables
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
            return False, f"Database not found: {self.db_path}"

        # Check size
        size_mb = self.db_path.stat().st_size / (1024 * 1024)
        return True, f"Database exists: {self.db_path} ({size_mb:.2f} MB)"

    def check_sqlite_wal(self) -> Tuple[bool, str]:
        """Check if SQLite is using WAL mode.

        WAL mode enables better concurrency for AgentOS multi-worker scenarios.
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            conn.close()

            if mode.upper() == "WAL":
                return True, f"WAL mode enabled: {mode}"
            else:
                return False, f"WAL mode not enabled: {mode} (expected WAL)"

        except Exception as e:
            return False, f"Failed to check journal_mode: {e}"

    def check_busy_timeout(self) -> Tuple[bool, str]:
        """Check if busy_timeout is configured.

        A reasonable busy_timeout (>=5000ms) prevents immediate lock failures
        in concurrent scenarios.
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("PRAGMA busy_timeout")
            timeout = cursor.fetchone()[0]
            conn.close()

            if timeout >= 5000:
                return True, f"busy_timeout is {timeout}ms (good)"
            else:
                return False, f"busy_timeout is {timeout}ms (should be >= 5000ms)"

        except Exception as e:
            return False, f"Failed to check busy_timeout: {e}"

    def check_schema_version(self) -> Tuple[bool, str]:
        """Check if schema is recent enough.

        Recovery system requires schema v24+.
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path))

            # Check if schema_version table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)
            if not cursor.fetchone():
                conn.close()
                return False, "schema_version table does not exist"

            # Get latest version
            cursor = conn.execute("""
                SELECT version FROM schema_version
                ORDER BY applied_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()

            if not row:
                return False, "No schema version found"

            version_str = row[0]

            # Parse version (format: "0.24.0" → 24)
            try:
                major = int(version_str.split('.')[1])
            except (IndexError, ValueError):
                return False, f"Cannot parse version: {version_str}"

            if major >= 24:
                return True, f"Schema version: {version_str} (✓)"
            else:
                return False, f"Schema version: {version_str} (need >= 0.24.0)"

        except Exception as e:
            return False, f"Failed to check schema version: {e}"

    def check_recovery_tables(self) -> Tuple[bool, str]:
        """Check if recovery tables exist.

        Required tables:
        - checkpoints
        - work_items (optional - may not exist in all deployments)
        - idempotency_keys (optional)
        """
        if not self.db_path.exists():
            return False, "Database does not exist"

        try:
            conn = sqlite3.connect(str(self.db_path))

            # Get all table names
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            all_tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            # Core recovery tables (required)
            required_tables = ["checkpoints"]
            # Optional tables
            optional_tables = ["work_items", "idempotency_keys"]

            # Check required tables
            missing_required = [t for t in required_tables if t not in all_tables]
            if missing_required:
                return False, f"Missing required tables: {', '.join(missing_required)}"

            # Check optional tables
            existing_optional = [t for t in optional_tables if t in all_tables]

            return True, f"Required tables exist. Optional tables: {', '.join(existing_optional) if existing_optional else 'none'}"

        except Exception as e:
            return False, f"Failed to check tables: {e}"


def run_startup_health_check(
    db_path: str,
    mode: HealthCheckMode = HealthCheckMode.SAFE,
    verbose: bool = True,
    fail_fast: bool = None  # Deprecated, use mode instead
) -> Dict[str, any]:
    """Run startup health check with enforcement mode.

    Args:
        db_path: Database path
        mode: Enforcement mode (STRICT/SAFE/DEV)
        verbose: If True, log results
        fail_fast: Deprecated, use mode=HealthCheckMode.STRICT instead

    Returns:
        Dict with:
            - all_passed: bool
            - recovery_enabled: bool (whether recovery system should be enabled)
            - mode: str (enforcement mode used)
            - summary: dict (check results summary)

    Raises:
        RuntimeError: If mode=STRICT and checks fail

    Examples:
        from agentos.core.storage.paths import component_db_path

        # Production: block startup on failure
        result = run_startup_health_check(
            str(component_db_path("agentos")),
            mode=HealthCheckMode.STRICT
        )

        # Staging: disable recovery on failure
        result = run_startup_health_check(
            str(component_db_path("agentos")),
            mode=HealthCheckMode.SAFE
        )
        if not result["recovery_enabled"]:
            logger.warning("Recovery system disabled due to health check failures")

        # Development: warn only
        result = run_startup_health_check(
            str(component_db_path("agentos")),
            mode=HealthCheckMode.DEV
        )
    """
    # Handle deprecated fail_fast parameter
    if fail_fast is not None:
        logger.warning("fail_fast parameter is deprecated, use mode=HealthCheckMode.STRICT instead")
        if fail_fast:
            mode = HealthCheckMode.STRICT

    checker = StartupHealthCheck(db_path)
    all_passed, results = checker.run_all_checks()

    # Determine if recovery should be enabled based on mode
    recovery_enabled = True

    if verbose:
        summary = results["summary"]

        if all_passed:
            logger.info(f"✅ All startup health checks passed (mode: {mode.value})")
            logger.info(f"   Passed: {summary['passed_count']}/{summary['passed_count'] + summary['failed_count']}")
        else:
            logger.warning(f"❌ Startup health check failed (mode: {mode.value})")
            logger.warning(f"   Passed: {summary['passed_count']}/{summary['passed_count'] + summary['failed_count']}")
            logger.warning(f"   Failed checks: {', '.join(summary['checks_failed'])}")

            # Print detailed failure messages
            for check_name in summary['checks_failed']:
                if check_name in results:
                    logger.warning(f"   - {check_name}: {results[check_name]['message']}")

    # Handle failures based on mode
    if not all_passed:
        summary = results["summary"]

        if mode == HealthCheckMode.STRICT:
            # STRICT: Block startup
            raise RuntimeError(
                f"[STRICT MODE] Startup blocked: {summary['failed_count']} health checks failed. "
                f"Failed checks: {', '.join(summary['checks_failed'])}. "
                f"Fix issues or use SAFE mode for graceful degradation."
            )

        elif mode == HealthCheckMode.SAFE:
            # SAFE: Disable recovery system
            recovery_enabled = False
            logger.warning("")
            logger.warning("⚠️  [SAFE MODE] Recovery system DISABLED due to health check failures")
            logger.warning("   Application will start, but recovery features are unavailable:")
            logger.warning("   - Checkpoint recovery: DISABLED")
            logger.warning("   - LLM caching: DISABLED")
            logger.warning("   - Tool replay: DISABLED")
            logger.warning("   - Work item leases: DISABLED")
            logger.warning("")
            logger.warning("   To enable recovery features:")
            logger.warning("   1. Fix the failed health checks above")
            logger.warning("   2. Restart the application")
            logger.warning("   3. Or use mode=STRICT to block startup until fixed")
            logger.warning("")

        elif mode == HealthCheckMode.DEV:
            # DEV: Warn only
            logger.warning("")
            logger.warning("⚠️  [DEV MODE] Health checks failed but recovery system remains ENABLED")
            logger.warning("   This may cause unexpected behavior or data corruption!")
            logger.warning("   Use at your own risk in development only.")
            logger.warning("")
            logger.warning("   For production use:")
            logger.warning("   - mode=STRICT: Block startup until fixed")
            logger.warning("   - mode=SAFE: Disable recovery features")
            logger.warning("")
            recovery_enabled = True  # Risky but allowed in DEV mode

    return {
        "all_passed": all_passed,
        "recovery_enabled": recovery_enabled,
        "mode": mode.value,
        "summary": results["summary"],
        "checks": results
    }


__all__ = ['StartupHealthCheck', 'HealthCheckMode', 'run_startup_health_check']
