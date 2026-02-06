"""
Rollback Engine for AgentOS v3

Handles rollback of action executions.

Capabilities:
1. Generate rollback plans
2. Execute rollbacks
3. Track rollback history
4. Detect irreversible actions

Design Principles:
- Not all actions are reversible
- Rollback itself is an Action (requires decision_id)
- Partial rollbacks are tracked
- Rollback history is immutable

Reversibility Rules:
- File write: Reversible (delete file)
- File delete: IRREVERSIBLE
- Database write: Partially reversible
- Network call: IRREVERSIBLE
- Payment: IRREVERSIBLE
"""

import logging
import json
from typing import Dict, List, Optional, Any
from ulid import ULID

from agentos.core.capability.domains.action.models import (
    ActionExecution,
    ActionExecutionStatus,
    RollbackPlan,
    RollbackExecution,
    RollbackStatus,
    SideEffectType,
    is_side_effect_reversible,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class IrreversibleActionError(Exception):
    """Raised when attempting to rollback an irreversible action"""
    pass


class RollbackFailedError(Exception):
    """Raised when rollback execution fails"""
    pass


class RollbackPlanNotFoundError(Exception):
    """Raised when rollback plan not found for execution"""
    pass


# ===================================================================
# Rollback Engine
# ===================================================================

class RollbackEngine:
    """
    Rollback engine for action executions.

    Responsibilities:
    1. Analyze action reversibility
    2. Generate rollback plans
    3. Execute rollbacks (via ActionExecutor)
    4. Track rollback history

    Example:
        engine = RollbackEngine()

        # Check if reversible
        if engine.is_reversible(execution_id):
            # Generate plan
            plan = engine.generate_rollback_plan(execution_id)

            # Execute rollback
            rollback = engine.rollback(
                execution_id,
                reason="User requested undo",
                initiated_by="user-123"
            )

            print(f"Rollback status: {rollback.status}")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize rollback engine.

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path
        self._db_conn = None
        self._ensure_tables()
        logger.debug("RollbackEngine initialized")

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
            self._execute_sql("SELECT 1 FROM action_rollback_history LIMIT 1")
        except Exception as e:
            logger.warning(f"action_rollback_history table may not exist: {e}")

    # ===================================================================
    # Reversibility Analysis
    # ===================================================================

    def is_reversible(self, execution_id: str) -> bool:
        """
        Check if an execution can be rolled back.

        Args:
            execution_id: Execution ID

        Returns:
            True if reversible, False otherwise
        """
        execution = self._get_execution(execution_id)
        if not execution:
            return False

        # Check if has rollback plan
        if execution.rollback_plan:
            return True

        # Check side effects
        for effect in execution.actual_side_effects:
            if not is_side_effect_reversible(effect):
                return False

        return True

    def analyze_reversibility(self, execution_id: str) -> Dict[str, Any]:
        """
        Analyze execution reversibility in detail.

        Args:
            execution_id: Execution ID

        Returns:
            Analysis report with details
        """
        execution = self._get_execution(execution_id)
        if not execution:
            return {
                "reversible": False,
                "reason": "Execution not found",
            }

        analysis = {
            "execution_id": execution_id,
            "action_id": execution.action_id,
            "reversible": True,
            "has_rollback_plan": execution.rollback_plan is not None,
            "side_effects_analysis": [],
            "warnings": [],
            "blockers": [],
        }

        # Analyze each side effect
        for effect in execution.actual_side_effects:
            reversible = is_side_effect_reversible(effect)
            analysis["side_effects_analysis"].append(
                {
                    "effect": effect.value,
                    "reversible": reversible,
                }
            )

            if not reversible:
                analysis["reversible"] = False
                analysis["blockers"].append(
                    f"Side effect {effect.value} is irreversible"
                )

        # Check execution status
        if execution.status == ActionExecutionStatus.FAILURE:
            analysis["warnings"].append(
                "Execution failed - rollback may not be meaningful"
            )

        if execution.status == ActionExecutionStatus.ROLLED_BACK:
            analysis["reversible"] = False
            analysis["blockers"].append("Execution already rolled back")

        # Check if rollback plan exists
        if not execution.rollback_plan and analysis["reversible"]:
            analysis["warnings"].append(
                "No rollback plan defined - may require manual intervention"
            )

        return analysis

    # ===================================================================
    # Rollback Plan Generation
    # ===================================================================

    def generate_rollback_plan(
        self, execution_id: str, force: bool = False
    ) -> RollbackPlan:
        """
        Generate rollback plan for an execution.

        Args:
            execution_id: Execution ID
            force: Generate plan even if action is irreversible

        Returns:
            RollbackPlan

        Raises:
            IrreversibleActionError: If action is irreversible and force=False
        """
        execution = self._get_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        # Check reversibility
        if not force and not self.is_reversible(execution_id):
            raise IrreversibleActionError(
                f"Execution {execution_id} is not reversible. "
                f"Use force=True to generate plan anyway."
            )

        # Use existing rollback plan if available
        if execution.rollback_plan:
            return RollbackPlan(
                plan_id=str(ULID()),
                execution_id=execution_id,
                rollback_action_id=execution.rollback_plan["rollback_action_id"],
                rollback_params=execution.rollback_plan["params"],
                is_full_rollback=execution.rollback_plan.get("is_full_rollback", False),
                warnings=execution.rollback_plan.get("warnings", []),
                created_at_ms=utc_now_ms(),
            )

        # Generate new plan based on action type
        plan = self._generate_plan_for_action(execution)
        return plan

    def _generate_plan_for_action(self, execution: ActionExecution) -> RollbackPlan:
        """Generate rollback plan for specific action"""
        action_id = execution.action_id
        params = execution.params

        plan = RollbackPlan(
            plan_id=str(ULID()),
            execution_id=execution.execution_id,
            rollback_action_id="",
            rollback_params={},
            is_full_rollback=False,
            warnings=[],
            created_at_ms=utc_now_ms(),
        )

        if action_id == "action.execute.local":
            # Extract command
            command = params.get("command", "")

            if "mkdir" in command:
                path = command.split("mkdir")[-1].strip()
                plan.rollback_action_id = "action.execute.local"
                plan.rollback_params = {"command": f"rmdir {path}"}
                plan.is_full_rollback = True

            elif "git commit" in command:
                plan.rollback_action_id = "action.execute.local"
                plan.rollback_params = {"command": "git reset --soft HEAD~1"}
                plan.is_full_rollback = True

            else:
                plan.warnings.append("No automatic rollback strategy for this command")

        elif action_id == "action.file.write":
            path = params.get("path")
            plan.rollback_action_id = "action.file.delete"
            plan.rollback_params = {"path": path}
            plan.is_full_rollback = True
            plan.warnings.append("Original file content will be lost")

        elif action_id == "action.database.write":
            plan.rollback_action_id = "action.database.write"
            plan.rollback_params = {"rollback_data": "TODO"}
            plan.is_full_rollback = False
            plan.warnings.append("Partial rollback only - original data may be lost")

        else:
            plan.warnings.append(f"No rollback strategy for {action_id}")

        return plan

    # ===================================================================
    # Rollback Execution
    # ===================================================================

    def rollback(
        self,
        execution_id: str,
        reason: str,
        initiated_by: str,
        force: bool = False,
    ) -> RollbackExecution:
        """
        Execute rollback for an action execution.

        Args:
            execution_id: Original execution ID
            reason: Why rollback is being performed
            initiated_by: Agent/user initiating rollback
            force: Force rollback even if irreversible

        Returns:
            RollbackExecution record

        Raises:
            IrreversibleActionError: If action is irreversible
            RollbackFailedError: If rollback fails
        """
        rollback_id = str(ULID())

        logger.info(f"Starting rollback {rollback_id} for execution {execution_id}")

        # Get execution
        execution = self._get_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        # Check if already rolled back
        if execution.status == ActionExecutionStatus.ROLLED_BACK:
            raise RollbackFailedError(
                f"Execution {execution_id} is already rolled back"
            )

        # Check reversibility
        if not force and not self.is_reversible(execution_id):
            raise IrreversibleActionError(
                f"Execution {execution_id} is not reversible. "
                f"Use force=True to attempt anyway."
            )

        # Generate rollback plan
        try:
            plan = self.generate_rollback_plan(execution_id, force=force)
        except Exception as e:
            raise RollbackPlanNotFoundError(
                f"Failed to generate rollback plan: {e}"
            ) from e

        # Create rollback record
        rollback = RollbackExecution(
            rollback_id=rollback_id,
            original_execution_id=execution_id,
            rollback_execution_id=None,
            rollback_plan=plan,
            status=RollbackStatus.PENDING,
            reason=reason,
            initiated_by=initiated_by,
            initiated_at_ms=utc_now_ms(),
        )

        try:
            # Execute rollback action
            # Note: This creates a new action execution with the original decision_id
            from agentos.core.capability.domains.action.action_executor import (
                get_action_executor,
            )

            executor = get_action_executor()

            rollback_execution = executor.execute(
                action_id=plan.rollback_action_id,
                params=plan.rollback_params,
                decision_id=execution.decision_id,  # Link to original decision
                agent_id=initiated_by,
                skip_governance=True,  # Rollbacks bypass governance
            )

            rollback.rollback_execution_id = rollback_execution.execution_id

            if rollback_execution.status == ActionExecutionStatus.SUCCESS:
                rollback.status = RollbackStatus.SUCCESS
                rollback.result = rollback_execution.result

                # Update original execution status
                self._mark_execution_rolled_back(execution_id)

            else:
                rollback.status = RollbackStatus.FAILURE
                rollback.error_message = rollback_execution.error_message

        except Exception as e:
            logger.error(f"Rollback {rollback_id} failed: {e}")
            rollback.status = RollbackStatus.FAILURE
            rollback.error_message = str(e)
            raise RollbackFailedError(f"Rollback failed: {e}") from e

        finally:
            rollback.completed_at_ms = utc_now_ms()
            self._save_rollback(rollback)

        logger.info(
            f"Rollback {rollback_id} completed: {rollback.status} "
            f"(execution: {rollback.rollback_execution_id})"
        )

        return rollback

    def _mark_execution_rolled_back(self, execution_id: str):
        """Mark execution as rolled back"""
        self._execute_sql(
            """
            UPDATE action_execution_log
            SET status = ?
            WHERE execution_id = ?
            """,
            (ActionExecutionStatus.ROLLED_BACK.value, execution_id),
        )

    # ===================================================================
    # Queries
    # ===================================================================

    def get_rollback(self, rollback_id: str) -> Optional[RollbackExecution]:
        """Get rollback by ID"""
        row = self._execute_sql(
            """
            SELECT rollback_id, original_execution_id, rollback_execution_id,
                   rollback_plan_json, rollback_status, rollback_reason,
                   initiated_by, initiated_at_ms, completed_at_ms
            FROM action_rollback_history
            WHERE rollback_id = ?
            """,
            (rollback_id,),
        ).fetchone()

        if not row:
            return None

        plan_data = json.loads(row[3])
        plan = RollbackPlan(**plan_data)

        return RollbackExecution(
            rollback_id=row[0],
            original_execution_id=row[1],
            rollback_execution_id=row[2],
            rollback_plan=plan,
            status=RollbackStatus(row[4]),
            reason=row[5],
            initiated_by=row[6],
            initiated_at_ms=row[7],
            completed_at_ms=row[8],
        )

    def get_rollback_history(
        self, execution_id: str
    ) -> List[RollbackExecution]:
        """Get all rollbacks for an execution"""
        rows = self._execute_sql(
            """
            SELECT rollback_id, original_execution_id, rollback_execution_id,
                   rollback_plan_json, rollback_status, rollback_reason,
                   initiated_by, initiated_at_ms, completed_at_ms
            FROM action_rollback_history
            WHERE original_execution_id = ?
            ORDER BY initiated_at_ms DESC
            """,
            (execution_id,),
        ).fetchall()

        rollbacks = []
        for row in rows:
            plan_data = json.loads(row[3])
            plan = RollbackPlan(**plan_data)

            rollback = RollbackExecution(
                rollback_id=row[0],
                original_execution_id=row[1],
                rollback_execution_id=row[2],
                rollback_plan=plan,
                status=RollbackStatus(row[4]),
                reason=row[5],
                initiated_by=row[6],
                initiated_at_ms=row[7],
                completed_at_ms=row[8],
            )
            rollbacks.append(rollback)

        return rollbacks

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

    def _save_rollback(self, rollback: RollbackExecution):
        """Save rollback to database"""
        self._execute_sql(
            """
            INSERT OR REPLACE INTO action_rollback_history (
                rollback_id,
                original_execution_id,
                rollback_execution_id,
                rollback_plan_json,
                rollback_status,
                rollback_reason,
                initiated_by,
                initiated_at_ms,
                completed_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rollback.rollback_id,
                rollback.original_execution_id,
                rollback.rollback_execution_id,
                json.dumps(rollback.rollback_plan.dict()),
                rollback.status.value,
                rollback.reason,
                rollback.initiated_by,
                rollback.initiated_at_ms,
                rollback.completed_at_ms,
            ),
        )


# ===================================================================
# Global Singleton
# ===================================================================

_rollback_engine_instance: Optional[RollbackEngine] = None


def get_rollback_engine(db_path: Optional[str] = None) -> RollbackEngine:
    """Get global RollbackEngine singleton"""
    global _rollback_engine_instance
    if _rollback_engine_instance is None:
        _rollback_engine_instance = RollbackEngine(db_path=db_path)
    return _rollback_engine_instance
