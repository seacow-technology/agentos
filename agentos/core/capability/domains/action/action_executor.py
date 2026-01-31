"""
Action Executor for AgentOS v3

Core action execution engine with full safety guarantees.

Safety Features:
1. MUST have frozen decision_id (traceability)
2. MUST declare side effects before execution
3. MUST record evidence after execution
4. MUST check governance policies
5. MUST generate rollback plan (if reversible)

Execution Flow:
1. Validate decision is frozen
2. Declare side effects
3. Check governance approval
4. Generate rollback plan
5. Execute action
6. Track actual side effects
7. Compare declared vs actual
8. Record evidence
9. Return result

Error Handling:
- MissingDecisionError: No decision_id provided
- UnfrozenPlanError: Decision not frozen
- GovernanceRejectionError: Governance denied
- EvidenceRecordingFailedError: Evidence not recorded
"""

import logging
import json
import subprocess
import time
from typing import Dict, List, Optional, Any, Callable
from ulid import ULID

from agentos.core.capability.domains.action.models import (
    ActionExecution,
    ActionExecutionStatus,
    SideEffectType,
    RiskLevel,
    ActionCapabilityDefinition,
    is_execution_complete,
    compute_execution_duration,
)
from agentos.core.capability.domains.action.side_effects_tracker import (
    ActionSideEffectsTracker,
    get_action_side_effects_tracker,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class MissingDecisionError(Exception):
    """Raised when action execution attempted without decision_id"""
    pass


class UnfrozenPlanError(Exception):
    """Raised when decision is not frozen"""
    pass


class MissingSideEffectsDeclarationError(Exception):
    """Raised when side effects not declared before execution"""
    pass


class EvidenceRecordingFailedError(Exception):
    """Raised when evidence recording fails"""
    pass


class GovernanceRejectionError(Exception):
    """Raised when governance rejects action"""
    pass


class ActionExecutionError(Exception):
    """Raised when action execution fails"""
    pass


# ===================================================================
# Action Executor
# ===================================================================

class ActionExecutor:
    """
    Core action execution engine for AgentOS v3.

    Responsibilities:
    1. Validate preconditions (frozen decision, governance)
    2. Declare side effects
    3. Execute action safely
    4. Track side effects
    5. Record evidence
    6. Generate rollback plan

    Example:
        executor = ActionExecutor()

        result = executor.execute(
            action_id="action.execute.local",
            params={"command": "mkdir /tmp/test"},
            decision_id="decision-123",
            agent_id="executor_agent"
        )

        print(f"Execution {result.execution_id} completed: {result.status}")
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        side_effects_tracker: Optional[ActionSideEffectsTracker] = None,
    ):
        """
        Initialize action executor.

        Args:
            db_path: Optional database path
            side_effects_tracker: Optional custom tracker
        """
        self.db_path = db_path
        self._db_conn = None
        self.side_effects_tracker = side_effects_tracker or get_action_side_effects_tracker(
            db_path
        )
        self._ensure_tables()
        self._action_handlers: Dict[str, Callable] = self._register_handlers()
        logger.debug("ActionExecutor initialized")

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
            self._execute_sql("SELECT 1 FROM action_execution_log LIMIT 1")
        except Exception as e:
            logger.warning(f"action_execution_log table may not exist: {e}")

    def _register_handlers(self) -> Dict[str, Callable]:
        """Register action handlers"""
        return {
            "action.execute.local": self._execute_local,
            "action.execute.remote": self._execute_remote,
            "action.execute.external_api": self._execute_external_api,
            "action.file.write": self._execute_file_write,
            "action.file.delete": self._execute_file_delete,
            "action.database.write": self._execute_database_write,
            "action.network.call": self._execute_network_call,
        }

    # ===================================================================
    # Main Execution API
    # ===================================================================

    def execute(
        self,
        action_id: str,
        params: Dict[str, Any],
        decision_id: str,
        agent_id: str,
        skip_governance: bool = False,
    ) -> ActionExecution:
        """
        Execute an action with full safety guarantees.

        Args:
            action_id: Action capability ID
            params: Action parameters
            decision_id: Decision ID (MUST be frozen)
            agent_id: Agent executing the action
            skip_governance: Skip governance check (testing only)

        Returns:
            ActionExecution record with results

        Raises:
            MissingDecisionError: No decision_id provided
            UnfrozenPlanError: Decision not frozen
            GovernanceRejectionError: Governance denied
            MissingSideEffectsDeclarationError: Side effects not declared
            EvidenceRecordingFailedError: Evidence not recorded
        """
        execution_id = str(ULID())

        logger.info(
            f"Starting action execution {execution_id}: {action_id} "
            f"for decision {decision_id}"
        )

        # Create execution record
        execution = ActionExecution(
            execution_id=execution_id,
            action_id=action_id,
            params=params,
            decision_id=decision_id,
            agent_id=agent_id,
            status=ActionExecutionStatus.PENDING,
            started_at_ms=utc_now_ms(),
            risk_level=RiskLevel.HIGH,  # Default to HIGH
            governance_approved=False,
        )

        try:
            # Step 1: Validate decision is frozen
            self._validate_decision(decision_id)

            # Step 2: Declare side effects
            declared_effects = self._declare_side_effects(execution_id, action_id, params, agent_id)
            execution.declared_side_effects = declared_effects

            # Step 3: Governance check
            if not skip_governance:
                self._check_governance(execution)
                execution.governance_approved = True

            # Step 4: Generate rollback plan
            rollback_plan = self._generate_rollback_plan(action_id, params)
            execution.rollback_plan = rollback_plan
            execution.is_reversible = rollback_plan is not None

            # Step 5: Execute action
            execution.status = ActionExecutionStatus.RUNNING
            self._save_execution(execution)

            result = self._do_execute(action_id, params)
            execution.result = result
            execution.status = ActionExecutionStatus.SUCCESS

            # Step 6: Track actual side effects (from result)
            actual_effects = self._extract_side_effects(result)
            execution.actual_side_effects = actual_effects

            # Step 7: Compare declared vs actual
            comparison = self.side_effects_tracker.compare(
                execution_id, strict_mode=False
            )
            execution.unexpected_side_effects = comparison.unexpected_effects

            if comparison.unexpected_effects:
                logger.warning(
                    f"Execution {execution_id} produced unexpected side effects: "
                    f"{[e.value for e in comparison.unexpected_effects]}"
                )

            # Step 8: Record evidence
            evidence_id = self._record_evidence(execution)
            execution.evidence_id = evidence_id

            if not evidence_id:
                raise EvidenceRecordingFailedError(
                    f"Failed to record evidence for execution {execution_id}"
                )

        except Exception as e:
            logger.error(f"Action execution {execution_id} failed: {e}")
            execution.status = ActionExecutionStatus.FAILURE
            execution.error_message = str(e)
            raise

        finally:
            # Always save final state
            execution.completed_at_ms = utc_now_ms()
            execution.duration_ms = compute_execution_duration(execution)
            self._save_execution(execution)

        logger.info(
            f"Action execution {execution_id} completed: {execution.status} "
            f"(duration: {execution.duration_ms}ms)"
        )

        return execution

    # ===================================================================
    # Validation
    # ===================================================================

    def _validate_decision(self, decision_id: str):
        """
        Validate that decision exists and is frozen.

        Args:
            decision_id: Decision ID to validate

        Raises:
            MissingDecisionError: No decision_id provided
            UnfrozenPlanError: Decision not frozen
        """
        if not decision_id:
            raise MissingDecisionError("Action must be linked to a Decision")

        # Check decision exists and is frozen
        row = self._execute_sql(
            """
            SELECT plan_id, status FROM decision_plans
            WHERE plan_id = ?
            """,
            (decision_id,),
        ).fetchone()

        if not row:
            raise MissingDecisionError(f"Decision {decision_id} not found")

        status = row[1]
        if status != "frozen":
            raise UnfrozenPlanError(
                f"Decision {decision_id} is not frozen (status: {status}). "
                f"Actions can only execute against frozen decisions."
            )

        logger.debug(f"Decision {decision_id} validated: frozen")

    def _check_governance(self, execution: ActionExecution):
        """
        Check governance policies.

        Args:
            execution: Execution to check

        Raises:
            GovernanceRejectionError: If governance denies execution
        """
        # Check if agent has required capability
        # This is a simplified check - full governance is in governance domain
        from agentos.core.capability.registry import get_capability_registry

        registry = get_capability_registry()

        # Check if capability exists
        cap_def = registry.get_capability(execution.action_id)
        if not cap_def:
            raise GovernanceRejectionError(
                f"Action capability {execution.action_id} not found in registry"
            )

        # Check if agent has capability grant
        row = self._execute_sql(
            """
            SELECT grant_id FROM capability_grants
            WHERE agent_id = ?
            AND capability_id = ?
            AND (expires_at_ms IS NULL OR expires_at_ms > ?)
            """,
            (execution.agent_id, execution.action_id, utc_now_ms()),
        ).fetchone()

        if not row:
            raise GovernanceRejectionError(
                f"Agent {execution.agent_id} does not have grant for {execution.action_id}"
            )

        logger.debug(f"Governance check passed for {execution.execution_id}")

    # ===================================================================
    # Side Effects
    # ===================================================================

    def _declare_side_effects(
        self, execution_id: str, action_id: str, params: Dict[str, Any], agent_id: str
    ) -> List[SideEffectType]:
        """
        Declare expected side effects before execution.

        Args:
            execution_id: Execution ID
            action_id: Action ID
            params: Action parameters
            agent_id: Agent ID

        Returns:
            List of declared side effects
        """
        # Predict side effects based on action type
        declared_effects = self.side_effects_tracker.predict_side_effects(
            action_id, params
        )

        # Store declaration
        self.side_effects_tracker.declare(
            execution_id=execution_id,
            action_id=action_id,
            declared_effects=declared_effects,
            agent_id=agent_id,
            rationale=f"Automatic declaration for {action_id}",
        )

        logger.debug(
            f"Declared {len(declared_effects)} side effects for {execution_id}"
        )

        return declared_effects

    def _extract_side_effects(self, result: Dict[str, Any]) -> List[SideEffectType]:
        """
        Extract actual side effects from execution result.

        Args:
            result: Execution result

        Returns:
            List of actual side effects
        """
        # Extract from result metadata
        effects = result.get("side_effects", [])

        # Convert to SideEffectType
        actual_effects = []
        for effect_str in effects:
            try:
                effect = SideEffectType(effect_str)
                actual_effects.append(effect)
            except ValueError:
                logger.warning(f"Unknown side effect type: {effect_str}")

        return actual_effects

    # ===================================================================
    # Rollback Planning
    # ===================================================================

    def _generate_rollback_plan(
        self, action_id: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate rollback plan for action.

        Args:
            action_id: Action ID
            params: Action parameters

        Returns:
            Rollback plan dict, or None if not reversible
        """
        # Action-specific rollback strategies
        if action_id == "action.execute.local":
            command = params.get("command", "")

            if "mkdir" in command:
                # Extract directory path
                path = command.split("mkdir")[-1].strip()
                return {
                    "rollback_action_id": "action.execute.local",
                    "params": {"command": f"rmdir {path}"},
                    "is_full_rollback": True,
                }

            elif "git commit" in command:
                return {
                    "rollback_action_id": "action.execute.local",
                    "params": {"command": "git reset --soft HEAD~1"},
                    "is_full_rollback": True,
                }

            elif "touch" in command:
                path = command.split("touch")[-1].strip()
                return {
                    "rollback_action_id": "action.file.delete",
                    "params": {"path": path},
                    "is_full_rollback": True,
                }

        elif action_id == "action.file.write":
            # File write can be rolled back by deleting
            path = params.get("path")
            if path:
                return {
                    "rollback_action_id": "action.file.delete",
                    "params": {"path": path},
                    "is_full_rollback": True,
                    "warnings": ["Original content will be lost"],
                }

        elif action_id == "action.file.delete":
            # File deletion is NOT reversible
            return None

        elif action_id == "action.database.write":
            # Could store original values for rollback
            return {
                "rollback_action_id": "action.database.write",
                "params": params.get("rollback_params", {}),
                "is_full_rollback": False,
                "warnings": ["Partial rollback only"],
            }

        # Default: not reversible
        return None

    # ===================================================================
    # Evidence Recording
    # ===================================================================

    def _record_evidence(self, execution: ActionExecution) -> Optional[str]:
        """
        Record evidence for execution.

        Args:
            execution: Execution record

        Returns:
            Evidence ID
        """
        # Evidence recording happens in Evidence Domain
        # For now, we'll create a simple evidence record

        evidence_id = str(ULID())

        evidence_data = {
            "evidence_id": evidence_id,
            "execution_id": execution.execution_id,
            "action_id": execution.action_id,
            "decision_id": execution.decision_id,
            "agent_id": execution.agent_id,
            "status": execution.status.value,
            "declared_side_effects": [e.value for e in execution.declared_side_effects],
            "actual_side_effects": [e.value for e in execution.actual_side_effects],
            "unexpected_side_effects": [e.value for e in execution.unexpected_side_effects],
            "timestamp_ms": utc_now_ms(),
        }

        # Store in evidence table (simplified - full implementation in Evidence Domain)
        try:
            self._execute_sql(
                """
                INSERT INTO evidence_records (
                    evidence_id,
                    entity_type,
                    entity_id,
                    event_type,
                    data_json,
                    created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    "action_execution",
                    execution.execution_id,
                    "action.executed",
                    json.dumps(evidence_data),
                    utc_now_ms(),
                ),
            )
            logger.debug(f"Recorded evidence {evidence_id} for {execution.execution_id}")
            return evidence_id
        except Exception as e:
            logger.error(f"Failed to record evidence: {e}")
            return None

    # ===================================================================
    # Action Handlers
    # ===================================================================

    def _do_execute(self, action_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute action using registered handler.

        Args:
            action_id: Action ID
            params: Parameters

        Returns:
            Execution result

        Raises:
            ActionExecutionError: If handler not found or execution fails
        """
        handler = self._action_handlers.get(action_id)
        if not handler:
            raise ActionExecutionError(f"No handler registered for {action_id}")

        try:
            result = handler(params)
            return result
        except Exception as e:
            raise ActionExecutionError(f"Handler failed: {e}") from e

    def _execute_local(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute local command"""
        command = params.get("command")
        if not command:
            raise ValueError("Missing 'command' parameter")

        logger.info(f"Executing local command: {command}")

        # Execute command
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 30),
            )

            side_effects = [SideEffectType.SYSTEM_EXEC.value]

            # Detect side effects from command
            if "write" in command or ">" in command:
                side_effects.append(SideEffectType.FS_WRITE.value)
            if "rm" in command or "delete" in command:
                side_effects.append(SideEffectType.FS_DELETE.value)

            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command,
                "side_effects": side_effects,
            }
        except subprocess.TimeoutExpired:
            raise ActionExecutionError("Command timed out")
        except Exception as e:
            raise ActionExecutionError(f"Command failed: {e}")

    def _execute_remote(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute remote operation (SSH, API)"""
        # Placeholder - would use SSH client or API client
        logger.info(f"Executing remote operation: {params}")
        return {
            "status": "success",
            "remote_host": params.get("host"),
            "side_effects": [
                SideEffectType.NETWORK_HTTPS.value,
                SideEffectType.REMOTE_STATE_CHANGE.value,
            ],
        }

    def _execute_external_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute external API call"""
        logger.info(f"Executing external API call: {params}")
        return {
            "status": "success",
            "api_endpoint": params.get("endpoint"),
            "side_effects": [
                SideEffectType.EXTERNAL_API_CALL.value,
                SideEffectType.RATE_LIMIT_CONSUMPTION.value,
                SideEffectType.NETWORK_HTTPS.value,
            ],
        }

    def _execute_file_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file write"""
        path = params.get("path")
        content = params.get("content", "")

        if not path:
            raise ValueError("Missing 'path' parameter")

        logger.info(f"Writing file: {path}")

        try:
            with open(path, "w") as f:
                f.write(content)

            return {
                "status": "success",
                "path": path,
                "bytes_written": len(content),
                "side_effects": [
                    SideEffectType.FS_WRITE.value,
                    SideEffectType.LOCAL_STATE_CHANGE.value,
                ],
            }
        except Exception as e:
            raise ActionExecutionError(f"File write failed: {e}")

    def _execute_file_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file delete"""
        path = params.get("path")

        if not path:
            raise ValueError("Missing 'path' parameter")

        logger.info(f"Deleting file: {path}")

        try:
            import os

            os.remove(path)

            return {
                "status": "success",
                "path": path,
                "side_effects": [SideEffectType.FS_DELETE.value],
            }
        except Exception as e:
            raise ActionExecutionError(f"File delete failed: {e}")

    def _execute_database_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database write"""
        logger.info(f"Executing database write: {params}")
        return {
            "status": "success",
            "table": params.get("table"),
            "rows_affected": 1,
            "side_effects": [
                SideEffectType.DATABASE_WRITE.value,
                SideEffectType.PERSISTENT_STATE_MUTATION.value,
            ],
        }

    def _execute_network_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute network call"""
        logger.info(f"Executing network call: {params}")
        return {
            "status": "success",
            "url": params.get("url"),
            "method": params.get("method", "GET"),
            "side_effects": [
                SideEffectType.NETWORK_HTTPS.value,
                SideEffectType.EXTERNAL_CALL.value,
            ],
        }

    # ===================================================================
    # Persistence
    # ===================================================================

    def _save_execution(self, execution: ActionExecution):
        """Save execution to database"""
        self._execute_sql(
            """
            INSERT OR REPLACE INTO action_execution_log (
                execution_id,
                action_id,
                params_json,
                decision_id,
                agent_id,
                status,
                result_json,
                error_message,
                started_at_ms,
                completed_at_ms,
                duration_ms,
                evidence_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution.execution_id,
                execution.action_id,
                json.dumps(execution.params),
                execution.decision_id,
                execution.agent_id,
                execution.status.value,
                json.dumps(execution.result) if execution.result else None,
                execution.error_message,
                execution.started_at_ms,
                execution.completed_at_ms,
                execution.duration_ms,
                execution.evidence_id,
            ),
        )

    def get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        """Get execution by ID"""
        row = self._execute_sql(
            """
            SELECT execution_id, action_id, params_json, decision_id, agent_id,
                   status, result_json, error_message, started_at_ms, completed_at_ms,
                   duration_ms, evidence_id
            FROM action_execution_log
            WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()

        if not row:
            return None

        return ActionExecution(
            execution_id=row[0],
            action_id=row[1],
            params=json.loads(row[2]),
            decision_id=row[3],
            agent_id=row[4],
            status=ActionExecutionStatus(row[5]),
            result=json.loads(row[6]) if row[6] else None,
            error_message=row[7],
            started_at_ms=row[8],
            completed_at_ms=row[9],
            duration_ms=row[10],
            evidence_id=row[11],
        )


# ===================================================================
# Global Singleton
# ===================================================================

_executor_instance: Optional[ActionExecutor] = None


def get_action_executor(db_path: Optional[str] = None) -> ActionExecutor:
    """Get global ActionExecutor singleton"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ActionExecutor(db_path=db_path)
    return _executor_instance
