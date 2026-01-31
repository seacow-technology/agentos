"""
Replay Engine for AgentOS v3

Replay historical action executions for debugging and audit.

Capabilities:
1. Dry-run replay (no side effects)
2. Actual replay (requires ADMIN)
3. Compare replay vs original
4. Detect behavioral changes

Use Cases:
- Debugging: Reproduce issues
- Audit: Verify execution correctness
- Testing: Compare behavior across versions
- Security: Detect tampering

Safety:
- Dry-run mode: Read-only, no mutations
- Actual mode: Requires ADMIN capability
- Comparison: Detect differences
- Replay logs: Immutable audit trail
"""

import logging
import json
from typing import Dict, List, Optional, Any
from ulid import ULID

from agentos.core.capability.domains.action.models import (
    ActionExecution,
    ActionExecutionStatus,
    ReplayMode,
    ReplayResult,
    SideEffectType,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class ReplayError(Exception):
    """Base exception for replay errors"""
    pass


class ExecutionNotFoundError(ReplayError):
    """Raised when execution to replay not found"""
    pass


class InsufficientPermissionsError(ReplayError):
    """Raised when agent lacks ADMIN permission for actual replay"""
    pass


class ReplayComparisonError(ReplayError):
    """Raised when replay result differs from original"""
    pass


# ===================================================================
# Replay Engine
# ===================================================================

class ReplayEngine:
    """
    Replay engine for action executions.

    Modes:
    1. DRY_RUN: Simulate without side effects (read-only)
    2. ACTUAL: Re-execute with side effects (requires ADMIN)
    3. COMPARE: Compare replay with original

    Example:
        engine = ReplayEngine()

        # Dry-run replay
        result = engine.replay(
            execution_id="exec-123",
            mode=ReplayMode.DRY_RUN,
            replayed_by="debugger_agent"
        )

        print(f"Replay successful: {result.results_match}")

        # Actual replay (requires ADMIN)
        result = engine.replay(
            execution_id="exec-123",
            mode=ReplayMode.ACTUAL,
            replayed_by="admin_agent"
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize replay engine.

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path
        self._db_conn = None
        self._ensure_tables()
        logger.debug("ReplayEngine initialized")

    def _get_db(self):
        """Get database connection"""
        if self.db_path:
            import sqlite3
            if not self._db_conn:
                self._db_conn = sqlite3.connect(self.db_path)
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
        """Ensure required tables exist"""
        try:
            self._execute_sql("SELECT 1 FROM action_replay_log LIMIT 1")
        except Exception as e:
            logger.warning(f"action_replay_log table may not exist: {e}")

    # ===================================================================
    # Replay Execution
    # ===================================================================

    def replay(
        self,
        execution_id: str,
        mode: ReplayMode,
        replayed_by: str,
        override_params: Optional[Dict[str, Any]] = None,
    ) -> ReplayResult:
        """
        Replay an action execution.

        Args:
            execution_id: Original execution ID
            mode: Replay mode (DRY_RUN or ACTUAL)
            replayed_by: Agent initiating replay
            override_params: Optional parameter overrides

        Returns:
            ReplayResult with comparison

        Raises:
            ExecutionNotFoundError: If execution not found
            InsufficientPermissionsError: If ACTUAL mode without ADMIN
            ReplayError: If replay fails
        """
        replay_id = str(ULID())

        logger.info(
            f"Starting replay {replay_id} for execution {execution_id} "
            f"(mode: {mode.value})"
        )

        # Get original execution
        original = self._get_execution(execution_id)
        if not original:
            raise ExecutionNotFoundError(
                f"Execution {execution_id} not found"
            )

        # Check permissions for ACTUAL mode
        if mode == ReplayMode.ACTUAL:
            self._check_admin_permission(replayed_by)

        # Create replay result
        result = ReplayResult(
            replay_id=replay_id,
            original_execution_id=execution_id,
            replay_mode=mode,
            original_result=original.result,
            original_side_effects=original.actual_side_effects,
            replayed_by=replayed_by,
            replayed_at_ms=utc_now_ms(),
            results_match=False,
        )

        start_ms = utc_now_ms()

        try:
            if mode == ReplayMode.DRY_RUN:
                # Simulate without side effects
                replay_result = self._simulate_execution(original, override_params)
                result.replay_result = replay_result
                result.replay_side_effects = []  # No side effects in dry-run

            elif mode == ReplayMode.ACTUAL:
                # Actually re-execute
                replay_execution = self._execute_actual(
                    original, replayed_by, override_params
                )
                result.replay_result = replay_execution.result
                result.replay_side_effects = replay_execution.actual_side_effects

            elif mode == ReplayMode.COMPARE:
                # Execute and compare
                replay_execution = self._execute_actual(
                    original, replayed_by, override_params
                )
                result.replay_result = replay_execution.result
                result.replay_side_effects = replay_execution.actual_side_effects

            # Compare results
            comparison = self._compare_results(original, result)
            result.results_match = comparison["match"]
            result.differences = comparison["differences"]

            result.duration_ms = utc_now_ms() - start_ms

        except Exception as e:
            logger.error(f"Replay {replay_id} failed: {e}")
            result.differences = {"error": str(e)}
            raise ReplayError(f"Replay failed: {e}") from e

        finally:
            # Always save replay log
            self._save_replay(result)

        logger.info(
            f"Replay {replay_id} completed: "
            f"match={result.results_match}, duration={result.duration_ms}ms"
        )

        return result

    def _simulate_execution(
        self, original: ActionExecution, override_params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Simulate execution without side effects.

        This is a read-only operation that predicts what would happen.
        """
        params = override_params or original.params

        # Simulate based on action type
        simulation = {
            "action_id": original.action_id,
            "params": params,
            "simulated": True,
            "would_produce_side_effects": [e.value for e in original.declared_side_effects],
        }

        if original.action_id == "action.execute.local":
            command = params.get("command", "")
            simulation["command_preview"] = command
            simulation["warning"] = "This is a simulation - no command executed"

        elif original.action_id == "action.file.write":
            path = params.get("path")
            simulation["would_write_to"] = path
            simulation["warning"] = "This is a simulation - no file written"

        elif original.action_id == "action.database.write":
            simulation["would_modify_table"] = params.get("table")
            simulation["warning"] = "This is a simulation - no database modified"

        return simulation

    def _execute_actual(
        self,
        original: ActionExecution,
        replayed_by: str,
        override_params: Optional[Dict[str, Any]],
    ) -> ActionExecution:
        """
        Actually re-execute the action.

        This creates a new execution with side effects.
        """
        from agentos.core.capability.domains.action.action_executor import (
            get_action_executor,
        )

        executor = get_action_executor()

        params = override_params or original.params

        # Execute with original decision_id
        replay_execution = executor.execute(
            action_id=original.action_id,
            params=params,
            decision_id=original.decision_id,
            agent_id=replayed_by,
            skip_governance=False,  # Replay must pass governance
        )

        return replay_execution

    # ===================================================================
    # Comparison
    # ===================================================================

    def _compare_results(
        self, original: ActionExecution, replay: ReplayResult
    ) -> Dict[str, Any]:
        """
        Compare original and replay results.

        Returns:
            Comparison dict with match status and differences
        """
        comparison = {
            "match": True,
            "differences": {},
        }

        # Compare status
        if replay.replay_mode == ReplayMode.DRY_RUN:
            # Can't compare status in dry-run
            pass
        else:
            # Compare actual results
            if original.result != replay.replay_result:
                comparison["match"] = False
                comparison["differences"]["result"] = {
                    "original": original.result,
                    "replay": replay.replay_result,
                }

        # Compare side effects
        if set(original.actual_side_effects) != set(replay.replay_side_effects):
            comparison["match"] = False
            comparison["differences"]["side_effects"] = {
                "original": [e.value for e in original.actual_side_effects],
                "replay": [e.value for e in replay.replay_side_effects],
            }

        return comparison

    def compare_executions(
        self, execution_id1: str, execution_id2: str
    ) -> Dict[str, Any]:
        """
        Compare two executions.

        Useful for comparing different runs of the same action.

        Args:
            execution_id1: First execution ID
            execution_id2: Second execution ID

        Returns:
            Detailed comparison
        """
        exec1 = self._get_execution(execution_id1)
        exec2 = self._get_execution(execution_id2)

        if not exec1 or not exec2:
            raise ExecutionNotFoundError("One or both executions not found")

        comparison = {
            "execution_ids": [execution_id1, execution_id2],
            "same_action": exec1.action_id == exec2.action_id,
            "same_params": exec1.params == exec2.params,
            "same_status": exec1.status == exec2.status,
            "same_result": exec1.result == exec2.result,
            "same_side_effects": set(exec1.actual_side_effects) == set(exec2.actual_side_effects),
            "duration_diff_ms": (exec1.duration_ms or 0) - (exec2.duration_ms or 0),
            "differences": {},
        }

        # Collect differences
        if exec1.action_id != exec2.action_id:
            comparison["differences"]["action_id"] = {
                "exec1": exec1.action_id,
                "exec2": exec2.action_id,
            }

        if exec1.params != exec2.params:
            comparison["differences"]["params"] = {
                "exec1": exec1.params,
                "exec2": exec2.params,
            }

        if exec1.result != exec2.result:
            comparison["differences"]["result"] = {
                "exec1": exec1.result,
                "exec2": exec2.result,
            }

        return comparison

    # ===================================================================
    # Queries
    # ===================================================================

    def get_replay(self, replay_id: str) -> Optional[ReplayResult]:
        """Get replay result by ID"""
        row = self._execute_sql(
            """
            SELECT replay_id, original_execution_id, replay_mode,
                   original_result_json, replay_result_json, differences_json,
                   replayed_by, replayed_at_ms
            FROM action_replay_log
            WHERE replay_id = ?
            """,
            (replay_id,),
        ).fetchone()

        if not row:
            return None

        return ReplayResult(
            replay_id=row[0],
            original_execution_id=row[1],
            replay_mode=ReplayMode(row[2]),
            original_result=json.loads(row[3]) if row[3] else None,
            replay_result=json.loads(row[4]) if row[4] else None,
            differences=json.loads(row[5]) if row[5] else None,
            replayed_by=row[6],
            replayed_at_ms=row[7],
            results_match=False,  # Computed from differences
        )

    def get_replay_history(self, execution_id: str) -> List[ReplayResult]:
        """Get all replays for an execution"""
        rows = self._execute_sql(
            """
            SELECT replay_id, original_execution_id, replay_mode,
                   original_result_json, replay_result_json, differences_json,
                   replayed_by, replayed_at_ms
            FROM action_replay_log
            WHERE original_execution_id = ?
            ORDER BY replayed_at_ms DESC
            """,
            (execution_id,),
        ).fetchall()

        replays = []
        for row in rows:
            replay = ReplayResult(
                replay_id=row[0],
                original_execution_id=row[1],
                replay_mode=ReplayMode(row[2]),
                original_result=json.loads(row[3]) if row[3] else None,
                replay_result=json.loads(row[4]) if row[4] else None,
                differences=json.loads(row[5]) if row[5] else None,
                replayed_by=row[6],
                replayed_at_ms=row[7],
                results_match=False,
            )
            replays.append(replay)

        return replays

    # ===================================================================
    # Helpers
    # ===================================================================

    def _get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        """Get execution from database"""
        from agentos.core.capability.domains.action.action_executor import (
            get_action_executor,
        )

        executor = get_action_executor()
        return executor.get_execution(execution_id)

    def _check_admin_permission(self, agent_id: str):
        """
        Check if agent has ADMIN permission for actual replay.

        Args:
            agent_id: Agent ID

        Raises:
            InsufficientPermissionsError: If not ADMIN
        """
        # Check if agent has ADMIN capability grant
        row = self._execute_sql(
            """
            SELECT grant_id FROM capability_grants
            WHERE agent_id = ?
            AND capability_id LIKE '%admin%'
            AND (expires_at_ms IS NULL OR expires_at_ms > ?)
            """,
            (agent_id, utc_now_ms()),
        ).fetchone()

        if not row:
            raise InsufficientPermissionsError(
                f"Agent {agent_id} requires ADMIN capability for actual replay"
            )

    def _save_replay(self, result: ReplayResult):
        """Save replay result to database"""
        self._execute_sql(
            """
            INSERT OR REPLACE INTO action_replay_log (
                replay_id,
                original_execution_id,
                replay_mode,
                original_result_json,
                replay_result_json,
                differences_json,
                replayed_by,
                replayed_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.replay_id,
                result.original_execution_id,
                result.replay_mode.value,
                json.dumps(result.original_result) if result.original_result else None,
                json.dumps(result.replay_result) if result.replay_result else None,
                json.dumps(result.differences) if result.differences else None,
                result.replayed_by,
                result.replayed_at_ms,
            ),
        )

    # ===================================================================
    # Batch Replay
    # ===================================================================

    def replay_batch(
        self,
        execution_ids: List[str],
        mode: ReplayMode,
        replayed_by: str,
    ) -> List[ReplayResult]:
        """
        Replay multiple executions.

        Args:
            execution_ids: List of execution IDs
            mode: Replay mode
            replayed_by: Agent initiating replays

        Returns:
            List of replay results
        """
        results = []

        for execution_id in execution_ids:
            try:
                result = self.replay(execution_id, mode, replayed_by)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to replay {execution_id}: {e}")
                # Continue with other replays

        logger.info(
            f"Batch replay completed: {len(results)}/{len(execution_ids)} succeeded"
        )

        return results


# ===================================================================
# Global Singleton
# ===================================================================

_replay_engine_instance: Optional[ReplayEngine] = None


def get_replay_engine(db_path: Optional[str] = None) -> ReplayEngine:
    """Get global ReplayEngine singleton"""
    global _replay_engine_instance
    if _replay_engine_instance is None:
        _replay_engine_instance = ReplayEngine(db_path=db_path)
    return _replay_engine_instance
