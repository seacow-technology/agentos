"""
Replay Engine for AgentOS v3

Evidence replay for debugging, validation, and time-travel.

Core Responsibilities:
1. Replay evidence in read-only mode (no side effects)
2. Validate mode: re-execute and compare results
3. Time-travel debugging support
4. Diff generation for comparisons

Design Principles:
- Read-only by default (safety first)
- Validate mode requires ADMIN permission
- Never modifies state in read-only mode
- Complete diff for debugging

Safety Guarantees:
- Read-only mode: NEVER triggers side effects
- Validate mode: Requires explicit permission check
- All replays are logged for audit

Schema: v51 (evidence_replay_log)
"""

import logging
import json
import sqlite3
from typing import Dict, List, Optional, Any
from ulid import ULID

from agentos.core.capability.domains.evidence.models import (
    Evidence,
    ReplayResult,
    ReplayMode,
)
from agentos.core.capability.domains.evidence.evidence_collector import (
    get_evidence_collector,
    EvidenceNotFoundError,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class ReplayError(Exception):
    """Raised when replay fails"""
    pass


class InvalidReplayModeError(Exception):
    """Raised when invalid replay mode specified"""
    pass


class PermissionDeniedForValidateError(Exception):
    """Raised when validate mode attempted without permission"""
    pass


# ===================================================================
# Replay Engine
# ===================================================================

class ReplayEngine:
    """
    Evidence replay engine for debugging and validation.

    Supports two modes:
    1. READ_ONLY: Simulate execution without side effects (default, safe)
    2. VALIDATE: Re-execute and compare with original (requires ADMIN)

    Example:
        engine = ReplayEngine()

        # Read-only replay (safe)
        result = engine.replay(
            evidence_id="ev-123",
            mode=ReplayMode.READ_ONLY,
            replayed_by="debug_agent"
        )

        # Validate mode (requires ADMIN)
        result = engine.replay(
            evidence_id="ev-123",
            mode=ReplayMode.VALIDATE,
            replayed_by="admin_agent"
        )

        # Check if results match
        if result.matches:
            print("Replay matched original execution")
        else:
            print(f"Differences: {result.differences}")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize replay engine.

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path
        self._db_conn = None
        self._evidence_collector = get_evidence_collector(db_path)
        self._ensure_tables()
        logger.debug("ReplayEngine initialized")

    def _get_db(self):
        """Get database connection"""
        if self.db_path:
            if not self._db_conn:
                self._db_conn = sqlite3.connect(self.db_path)
                self._db_conn.row_factory = sqlite3.Row
            return self._db_conn
        else:
            return get_db()

    def _execute_sql(self, sql: str, params=None):
        """Execute SQL with parameters"""
        conn = self._get_db()
        if params:
            return conn.execute(sql, params)
        else:
            return conn.execute(sql)

    def _ensure_tables(self):
        """Ensure replay tables exist"""
        try:
            self._execute_sql("SELECT 1 FROM evidence_replay_log LIMIT 1")
        except Exception as e:
            logger.warning(f"evidence_replay_log table may not exist: {e}")
            self._create_minimal_schema()

    def _create_minimal_schema(self):
        """Create minimal replay schema for testing"""
        logger.info("Creating minimal replay schema")
        conn = self._get_db()

        # Evidence replay log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_replay_log (
                replay_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                replay_mode TEXT NOT NULL,
                original_output_hash TEXT NOT NULL,
                replayed_output_hash TEXT,
                matches INTEGER,
                replayed_by TEXT NOT NULL,
                replayed_at_ms INTEGER NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence_log(evidence_id)
            )
        """)

        # Create index
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_replay_evidence "
            "ON evidence_replay_log(evidence_id)"
        )

        conn.commit()
        logger.info("Minimal replay schema created")

    # ===================================================================
    # Core Replay API
    # ===================================================================

    def replay(
        self,
        evidence_id: str,
        mode: ReplayMode = ReplayMode.READ_ONLY,
        replayed_by: str = "system",
    ) -> ReplayResult:
        """
        Replay evidence execution.

        Args:
            evidence_id: Evidence to replay
            mode: Replay mode (READ_ONLY or VALIDATE)
            replayed_by: Agent initiating replay

        Returns:
            ReplayResult with comparison data

        Raises:
            EvidenceNotFoundError: If evidence not found
            InvalidReplayModeError: If mode is invalid
            PermissionDeniedForValidateError: If VALIDATE mode without permission
            ReplayError: If replay fails
        """
        # Validate mode
        if mode not in [ReplayMode.READ_ONLY, ReplayMode.VALIDATE]:
            raise InvalidReplayModeError(
                f"Invalid replay mode: {mode}. Only READ_ONLY and VALIDATE are supported."
            )

        # Get original evidence
        evidence = self._evidence_collector.get(evidence_id)
        if not evidence:
            raise EvidenceNotFoundError(f"Evidence {evidence_id} not found")

        logger.info(
            f"Replaying evidence {evidence_id} in {mode.value} mode by {replayed_by}"
        )

        # Check permission for VALIDATE mode
        if mode == ReplayMode.VALIDATE:
            self._check_validate_permission(replayed_by)

        # Generate replay ID
        replay_id = f"replay-{ULID()}"
        start_ms = utc_now_ms()

        try:
            # Perform replay based on mode
            if mode == ReplayMode.READ_ONLY:
                result = self._replay_read_only(evidence)
            else:  # VALIDATE
                result = self._replay_validate(evidence)

            # Calculate duration
            duration_ms = utc_now_ms() - start_ms

            # Build replay result
            replay_result = ReplayResult(
                replay_id=replay_id,
                evidence_id=evidence_id,
                replay_mode=mode,
                original_evidence=evidence,
                replayed_at_ms=start_ms,
                replayed_by=replayed_by,
                original_output=evidence.output,
                replayed_output=result.get("output"),
                matches=result.get("matches", True),
                differences=result.get("differences"),
                duration_ms=duration_ms,
                success=True,
                error_message=None,
            )

            # Log replay
            self._log_replay(replay_result)

            logger.info(
                f"Replay {replay_id} completed in {duration_ms}ms "
                f"(matches: {replay_result.matches})"
            )

            return replay_result

        except Exception as e:
            logger.error(f"Replay {replay_id} failed: {e}")

            # Log failed replay
            duration_ms = utc_now_ms() - start_ms
            replay_result = ReplayResult(
                replay_id=replay_id,
                evidence_id=evidence_id,
                replay_mode=mode,
                original_evidence=evidence,
                replayed_at_ms=start_ms,
                replayed_by=replayed_by,
                original_output=evidence.output,
                replayed_output=None,
                matches=False,
                differences={"error": str(e)},
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )

            self._log_replay(replay_result)

            raise ReplayError(f"Replay failed: {e}") from e

    def _replay_read_only(self, evidence: Evidence) -> Dict[str, Any]:
        """
        Replay in read-only mode (simulation, no side effects).

        Args:
            evidence: Evidence to replay

        Returns:
            Simulation result
        """
        logger.debug(f"Simulating evidence {evidence.evidence_id} (read-only)")

        # Simulate execution without triggering side effects
        simulated_output = {
            "evidence_id": evidence.evidence_id,
            "operation": evidence.operation,
            "context": evidence.context,
            "input": evidence.input,
            "output": evidence.output,
            "simulated": True,
            "side_effects_prevented": True,
        }

        return {
            "output": simulated_output,
            "matches": True,  # Simulation always matches (it's a copy)
            "differences": None,
        }

    def _replay_validate(self, evidence: Evidence) -> Dict[str, Any]:
        """
        Replay in validate mode (re-execute and compare).

        WARNING: This actually re-executes the operation with side effects.

        Args:
            evidence: Evidence to replay

        Returns:
            Validation result with comparison
        """
        logger.warning(
            f"Re-executing evidence {evidence.evidence_id} in VALIDATE mode "
            f"(will trigger side effects)"
        )

        # Re-execute operation
        operation_type = evidence.operation["type"]
        capability_id = evidence.operation["capability_id"]

        # Get handler for this capability
        replayed_output = self._re_execute_operation(evidence)

        # Compare outputs
        original_output = evidence.output
        matches = self._compare_outputs(original_output, replayed_output)

        # Generate diff if not matching
        differences = None
        if not matches:
            differences = self._generate_diff(original_output, replayed_output)

        return {
            "output": replayed_output,
            "matches": matches,
            "differences": differences,
        }

    def _re_execute_operation(self, evidence: Evidence) -> Dict[str, Any]:
        """
        Re-execute operation from evidence.

        This is a placeholder - actual implementation would call the
        appropriate capability handler.

        Args:
            evidence: Evidence to re-execute

        Returns:
            Execution result
        """
        # NOTE: In production, this would:
        # 1. Get capability handler from registry
        # 2. Extract params from evidence.input
        # 3. Call handler with same params
        # 4. Return new result

        # For now, return simulated result
        logger.warning(
            "Re-execution not fully implemented, returning simulated result"
        )

        return {
            "simulated_re_execution": True,
            "original_output": evidence.output,
            "note": "Full re-execution requires capability handler integration",
        }

    def _compare_outputs(
        self, original: Dict[str, Any], replayed: Dict[str, Any]
    ) -> bool:
        """
        Compare original and replayed outputs.

        Args:
            original: Original output
            replayed: Replayed output

        Returns:
            True if outputs match, False otherwise
        """
        try:
            # Normalize and compare
            original_json = json.dumps(original, sort_keys=True)
            replayed_json = json.dumps(replayed, sort_keys=True)

            return original_json == replayed_json

        except Exception as e:
            logger.error(f"Output comparison failed: {e}")
            return False

    def _generate_diff(
        self, original: Dict[str, Any], replayed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate diff between original and replayed outputs.

        Args:
            original: Original output
            replayed: Replayed output

        Returns:
            Diff dict
        """
        diff = {
            "original": original,
            "replayed": replayed,
            "added_keys": [],
            "removed_keys": [],
            "changed_values": {},
        }

        # Find added/removed keys
        original_keys = set(original.keys()) if isinstance(original, dict) else set()
        replayed_keys = set(replayed.keys()) if isinstance(replayed, dict) else set()

        diff["added_keys"] = list(replayed_keys - original_keys)
        diff["removed_keys"] = list(original_keys - replayed_keys)

        # Find changed values
        for key in original_keys & replayed_keys:
            if original[key] != replayed[key]:
                diff["changed_values"][key] = {
                    "original": original[key],
                    "replayed": replayed[key],
                }

        return diff

    def _check_validate_permission(self, agent_id: str):
        """
        Check if agent has permission for VALIDATE mode.

        VALIDATE mode requires ADMIN capability as it re-executes operations
        with side effects.

        Args:
            agent_id: Agent requesting validation

        Raises:
            PermissionDeniedForValidateError: If permission denied
        """
        # NOTE: In production, this would check:
        # 1. Agent has "evidence.replay.validate" capability
        # 2. Agent has ADMIN role
        # 3. Governance policy allows validation

        # For now, require explicit "admin" or "system" agent
        if agent_id not in ["admin", "system", "admin_agent"]:
            raise PermissionDeniedForValidateError(
                f"Agent {agent_id} does not have permission for VALIDATE mode. "
                f"This mode requires ADMIN capability as it re-executes operations "
                f"with side effects."
            )

        logger.debug(f"Validated permission for {agent_id} to use VALIDATE mode")

    # ===================================================================
    # Logging
    # ===================================================================

    def _log_replay(self, result: ReplayResult):
        """
        Log replay to database.

        Args:
            result: Replay result to log
        """
        conn = self._get_db()

        # Compute hashes
        original_hash = result.original_evidence.output.get("result_hash", "")
        replayed_hash = ""
        if result.replayed_output:
            from agentos.core.capability.domains.evidence.models import hash_content
            replayed_hash = hash_content(
                json.dumps(result.replayed_output, sort_keys=True)
            )

        # Insert replay log
        conn.execute(
            """
            INSERT INTO evidence_replay_log (
                replay_id,
                evidence_id,
                replay_mode,
                original_output_hash,
                replayed_output_hash,
                matches,
                replayed_by,
                replayed_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.replay_id,
                result.evidence_id,
                result.replay_mode.value,
                original_hash,
                replayed_hash,
                int(result.matches),
                result.replayed_by,
                result.replayed_at_ms,
            ),
        )

        conn.commit()

    # ===================================================================
    # Query API
    # ===================================================================

    def get_replay_history(self, evidence_id: str) -> List[Dict[str, Any]]:
        """
        Get replay history for evidence.

        Args:
            evidence_id: Evidence ID

        Returns:
            List of replay records
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT replay_id, replay_mode, matches, replayed_by, replayed_at_ms
            FROM evidence_replay_log
            WHERE evidence_id = ?
            ORDER BY replayed_at_ms DESC
            """,
            (evidence_id,),
        )

        replays = []
        for row in cursor.fetchall():
            replays.append(
                {
                    "replay_id": row["replay_id"],
                    "replay_mode": row["replay_mode"],
                    "matches": bool(row["matches"]),
                    "replayed_by": row["replayed_by"],
                    "replayed_at_ms": row["replayed_at_ms"],
                }
            )

        return replays

    def get_stats(self) -> Dict[str, int]:
        """
        Get replay statistics.

        Returns:
            Statistics dict
        """
        conn = self._get_db()

        stats = {}

        # Total replays
        cursor = conn.execute("SELECT COUNT(*) as count FROM evidence_replay_log")
        stats["total_replays"] = cursor.fetchone()["count"]

        # Replay modes
        cursor = conn.execute(
            "SELECT replay_mode, COUNT(*) as count FROM evidence_replay_log GROUP BY replay_mode"
        )
        for row in cursor.fetchall():
            stats[f"replays_{row['replay_mode']}"] = row["count"]

        # Match rate
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM evidence_replay_log WHERE matches = 1"
        )
        matches = cursor.fetchone()["count"]
        stats["matches"] = matches
        if stats["total_replays"] > 0:
            stats["match_rate_percent"] = (matches / stats["total_replays"]) * 100

        return stats


# ===================================================================
# Global Singleton
# ===================================================================

_replay_engine_instance: Optional[ReplayEngine] = None


def get_replay_engine(db_path: Optional[str] = None) -> ReplayEngine:
    """
    Get global ReplayEngine singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton ReplayEngine instance
    """
    global _replay_engine_instance
    if _replay_engine_instance is None:
        _replay_engine_instance = ReplayEngine(db_path=db_path)
    return _replay_engine_instance
