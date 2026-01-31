"""
Action Side Effects Tracker for AgentOS v3

Specialized side effects tracker for Action Domain.

Key Features:
1. Pre-execution declaration (predict side effects)
2. Runtime tracking (record actual side effects)
3. Post-execution comparison (declared vs actual)
4. Unexpected side effect detection (security)

Design:
- Integrates with global SideEffectsTracker
- Stores declarations in database
- Provides compliance reports
- Alerts on violations

Safety:
- MUST declare before execution
- Unexpected effects trigger alerts
- All records stored in DB for audit
"""

import logging
import json
from typing import Dict, List, Optional, Set
from ulid import ULID

from agentos.core.capability.domains.action.models import (
    ActionExecution,
    SideEffectType,
    SideEffectDeclaration,
    SideEffectComparison,
    ActionSideEffect,
    RiskLevel,
    get_side_effect_risk,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


class MissingSideEffectDeclarationError(Exception):
    """Raised when action execution attempted without declaration"""
    pass


class UnexpectedSideEffectDetectedError(Exception):
    """Raised when action produces undeclared side effect"""
    pass


class ActionSideEffectsTracker:
    """
    Side effects tracker specialized for Action Domain.

    Workflow:
    1. declare() - Declare expected side effects before execution
    2. track() - Record actual side effects during execution
    3. compare() - Compare declared vs actual after execution
    4. alert() - Alert if unexpected side effects detected

    Example:
        tracker = ActionSideEffectsTracker()

        # 1. Declare
        declaration = tracker.declare(
            execution_id="exec-123",
            action_id="action.execute.local",
            declared_effects=[SideEffectType.FS_WRITE, SideEffectType.PROCESS_SPAWN],
            agent_id="executor_agent"
        )

        # 2. Execute action (records side effects)
        ...

        # 3. Track actual
        tracker.record_side_effect(
            execution_id="exec-123",
            effect_type=SideEffectType.FS_WRITE,
            details={"path": "/tmp/output.txt"}
        )

        # 4. Compare
        comparison = tracker.compare(execution_id="exec-123")
        if not comparison.is_compliant:
            logger.error(f"Unexpected side effects: {comparison.unexpected_effects}")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize tracker.

        Args:
            db_path: Optional database path (default: use global store)
        """
        self.db_path = db_path
        self._db_conn = None
        self._ensure_tables()
        logger.debug("ActionSideEffectsTracker initialized")

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
        """Ensure required tables exist (from schema v49)"""
        # Tables created by migration, just validate
        try:
            self._execute_sql("SELECT 1 FROM action_side_effects LIMIT 1")
        except Exception as e:
            logger.warning(f"action_side_effects table may not exist: {e}")

    # ===================================================================
    # Declaration (Pre-Execution)
    # ===================================================================

    def declare(
        self,
        execution_id: str,
        action_id: str,
        declared_effects: List[SideEffectType],
        agent_id: str,
        rationale: Optional[str] = None,
    ) -> SideEffectDeclaration:
        """
        Declare expected side effects before action execution.

        This is REQUIRED before executing any action.

        Args:
            execution_id: Unique execution ID
            action_id: Action capability ID
            declared_effects: List of expected side effects
            agent_id: Agent making the declaration
            rationale: Optional explanation

        Returns:
            SideEffectDeclaration record
        """
        declaration = SideEffectDeclaration(
            declaration_id=str(ULID()),
            execution_id=execution_id,
            action_id=action_id,
            declared_effects=declared_effects,
            declared_at_ms=utc_now_ms(),
            agent_id=agent_id,
            rationale=rationale,
        )

        # Store in database (in action_side_effects table)
        declared_json = json.dumps([e.value for e in declared_effects])

        # Note: We store declarations in action_side_effects table with
        # declared_effects_json populated and actual_effects_json empty
        self._execute_sql(
            """
            INSERT INTO action_side_effects (
                execution_id,
                declared_effects_json,
                actual_effects_json,
                unexpected_effects_json,
                declared_at_ms,
                tracked_at_ms
            ) VALUES (?, ?, '[]', NULL, ?, ?)
            ON CONFLICT(execution_id) DO UPDATE SET
                declared_effects_json = excluded.declared_effects_json,
                declared_at_ms = excluded.declared_at_ms
            """,
            (
                execution_id,
                declared_json,
                declaration.declared_at_ms,
                declaration.declared_at_ms,  # Same as declared for now
            ),
        )

        logger.info(
            f"Declared side effects for {execution_id}: "
            f"{[e.value for e in declared_effects]}"
        )

        return declaration

    def get_declaration(self, execution_id: str) -> Optional[SideEffectDeclaration]:
        """
        Get side effect declaration for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            SideEffectDeclaration if found, None otherwise
        """
        row = self._execute_sql(
            """
            SELECT execution_id, declared_effects_json, declared_at_ms
            FROM action_side_effects
            WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()

        if not row:
            return None

        declared_effects_data = json.loads(row[1])
        declared_effects = [SideEffectType(e) for e in declared_effects_data]

        return SideEffectDeclaration(
            declaration_id=str(ULID()),  # Not stored separately
            execution_id=row[0],
            action_id="",  # Would need to join with action_execution_log
            declared_effects=declared_effects,
            declared_at_ms=row[2],
            agent_id="",  # Would need to join
        )

    def has_declaration(self, execution_id: str) -> bool:
        """Check if execution has side effect declaration"""
        row = self._execute_sql(
            """
            SELECT 1 FROM action_side_effects
            WHERE execution_id = ?
            AND declared_effects_json != '[]'
            """,
            (execution_id,),
        ).fetchone()
        return row is not None

    # ===================================================================
    # Tracking (During Execution)
    # ===================================================================

    def record_side_effect(
        self,
        execution_id: str,
        effect_type: SideEffectType,
        details: Optional[Dict] = None,
        was_declared: Optional[bool] = None,
    ) -> ActionSideEffect:
        """
        Record a side effect that occurred during execution.

        Args:
            execution_id: Execution ID
            effect_type: Type of side effect
            details: Additional details (file path, URL, etc.)
            was_declared: Whether this was declared (auto-detected if None)

        Returns:
            ActionSideEffect record
        """
        # Auto-detect if declared
        if was_declared is None:
            declaration = self.get_declaration(execution_id)
            if declaration:
                was_declared = effect_type in declaration.declared_effects
            else:
                was_declared = False

        severity = get_side_effect_risk(effect_type)

        side_effect = ActionSideEffect(
            side_effect_id=0,  # Will be auto-incremented
            execution_id=execution_id,
            effect_type=effect_type,
            was_declared=was_declared,
            details=details,
            timestamp_ms=utc_now_ms(),
            severity=severity,
        )

        # Insert into database
        # Note: We'll track individual effects separately and also update
        # the action_side_effects table's actual_effects_json
        cursor = self._execute_sql(
            """
            INSERT INTO action_side_effects_individual (
                execution_id,
                effect_type,
                was_declared,
                details_json,
                timestamp_ms,
                severity
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                effect_type.value,
                was_declared,
                json.dumps(details) if details else None,
                side_effect.timestamp_ms,
                severity.value,
            ),
        )

        side_effect.side_effect_id = cursor.lastrowid

        # Update actual_effects_json in action_side_effects table
        self._update_actual_effects(execution_id, effect_type)

        if not was_declared:
            logger.warning(
                f"UNEXPECTED SIDE EFFECT: {execution_id} produced {effect_type.value} "
                f"(not declared!)"
            )

        return side_effect

    def _update_actual_effects(self, execution_id: str, effect_type: SideEffectType):
        """Update actual_effects_json for execution"""
        # Get current actual effects
        row = self._execute_sql(
            """
            SELECT actual_effects_json FROM action_side_effects
            WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()

        if row:
            actual_effects = json.loads(row[0])
            if effect_type.value not in actual_effects:
                actual_effects.append(effect_type.value)

                self._execute_sql(
                    """
                    UPDATE action_side_effects
                    SET actual_effects_json = ?,
                        tracked_at_ms = ?
                    WHERE execution_id = ?
                    """,
                    (json.dumps(actual_effects), utc_now_ms(), execution_id),
                )

    def get_side_effects(self, execution_id: str) -> List[ActionSideEffect]:
        """Get all side effects for an execution"""
        rows = self._execute_sql(
            """
            SELECT side_effect_id, execution_id, effect_type, was_declared,
                   details_json, timestamp_ms, severity
            FROM action_side_effects_individual
            WHERE execution_id = ?
            ORDER BY timestamp_ms ASC
            """,
            (execution_id,),
        ).fetchall()

        side_effects = []
        for row in rows:
            details = json.loads(row[4]) if row[4] else None
            side_effect = ActionSideEffect(
                side_effect_id=row[0],
                execution_id=row[1],
                effect_type=SideEffectType(row[2]),
                was_declared=bool(row[3]),
                details=details,
                timestamp_ms=row[5],
                severity=RiskLevel(row[6]),
            )
            side_effects.append(side_effect)

        return side_effects

    # ===================================================================
    # Comparison (Post-Execution)
    # ===================================================================

    def compare(
        self, execution_id: str, strict_mode: bool = True
    ) -> SideEffectComparison:
        """
        Compare declared vs actual side effects.

        Args:
            execution_id: Execution ID
            strict_mode: If True, raise error on unexpected effects

        Returns:
            SideEffectComparison with analysis

        Raises:
            UnexpectedSideEffectDetectedError: If unexpected effects found (strict mode)
        """
        # Get declaration
        declaration = self.get_declaration(execution_id)
        if not declaration:
            raise MissingSideEffectDeclarationError(
                f"No side effect declaration found for execution {execution_id}"
            )

        # Get actual effects
        side_effects = self.get_side_effects(execution_id)
        actual_effects = [se.effect_type for se in side_effects]

        # Compute sets
        declared_set = set(declaration.declared_effects)
        actual_set = set(actual_effects)

        expected = list(declared_set & actual_set)  # Intersection
        unexpected = list(actual_set - declared_set)  # In actual but not declared
        missing = list(declared_set - actual_set)  # In declared but not actual

        is_compliant = len(unexpected) == 0

        comparison = SideEffectComparison(
            execution_id=execution_id,
            declared_effects=declaration.declared_effects,
            actual_effects=actual_effects,
            expected_effects=expected,
            unexpected_effects=unexpected,
            missing_effects=missing,
            is_compliant=is_compliant,
            compared_at_ms=utc_now_ms(),
        )

        # Update database with unexpected effects
        if unexpected:
            unexpected_json = json.dumps([e.value for e in unexpected])
            self._execute_sql(
                """
                UPDATE action_side_effects
                SET unexpected_effects_json = ?
                WHERE execution_id = ?
                """,
                (unexpected_json, execution_id),
            )

        # Log results
        if is_compliant:
            logger.info(
                f"Side effects compliant for {execution_id}: "
                f"all {len(actual_effects)} effects were declared"
            )
        else:
            logger.error(
                f"SIDE EFFECTS VIOLATION for {execution_id}:\n"
                f"  Declared: {[e.value for e in declaration.declared_effects]}\n"
                f"  Actual: {[e.value for e in actual_effects]}\n"
                f"  Unexpected: {[e.value for e in unexpected]}\n"
                f"  Missing: {[e.value for e in missing]}"
            )

            if strict_mode:
                raise UnexpectedSideEffectDetectedError(
                    f"Execution {execution_id} produced unexpected side effects: "
                    f"{[e.value for e in unexpected]}"
                )

        return comparison

    # ===================================================================
    # Prediction (Pre-Declaration)
    # ===================================================================

    def predict_side_effects(
        self, action_id: str, params: Dict[str, Any]
    ) -> List[SideEffectType]:
        """
        Predict side effects based on action ID and parameters.

        This helps agents declare side effects automatically.

        Args:
            action_id: Action capability ID
            params: Action parameters

        Returns:
            List of predicted side effects
        """
        effects: List[SideEffectType] = []

        # Rule-based prediction
        if action_id == "action.execute.local":
            effects.append(SideEffectType.SYSTEM_EXEC)
            command = params.get("command", "")

            if "write" in command or ">" in command:
                effects.append(SideEffectType.FS_WRITE)
            if "rm " in command or "delete" in command:
                effects.append(SideEffectType.FS_DELETE)
            if "&" in command or "spawn" in command:
                effects.append(SideEffectType.PROCESS_SPAWN)

        elif action_id == "action.execute.remote":
            effects.append(SideEffectType.NETWORK_HTTPS)
            effects.append(SideEffectType.REMOTE_STATE_CHANGE)

        elif action_id == "action.execute.external_api":
            effects.append(SideEffectType.EXTERNAL_API_CALL)
            effects.append(SideEffectType.RATE_LIMIT_CONSUMPTION)
            effects.append(SideEffectType.NETWORK_HTTPS)

        elif action_id == "action.file.write":
            effects.append(SideEffectType.FS_WRITE)
            effects.append(SideEffectType.LOCAL_STATE_CHANGE)

        elif action_id == "action.file.delete":
            effects.append(SideEffectType.FS_DELETE)

        elif action_id == "action.database.write":
            effects.append(SideEffectType.DATABASE_WRITE)
            effects.append(SideEffectType.PERSISTENT_STATE_MUTATION)

        elif action_id == "action.network.call":
            effects.append(SideEffectType.NETWORK_HTTPS)
            effects.append(SideEffectType.EXTERNAL_CALL)

        return effects

    # ===================================================================
    # Queries & Reports
    # ===================================================================

    def get_compliance_report(
        self, agent_id: Optional[str] = None, limit: int = 100
    ) -> Dict[str, Any]:
        """
        Generate compliance report for side effects.

        Args:
            agent_id: Optional filter by agent
            limit: Maximum executions to analyze

        Returns:
            Report with compliance statistics
        """
        # Get recent executions with comparisons
        sql = """
            SELECT
                ase.execution_id,
                ase.declared_effects_json,
                ase.actual_effects_json,
                ase.unexpected_effects_json,
                ael.agent_id,
                ael.action_id,
                ael.started_at_ms
            FROM action_side_effects ase
            JOIN action_execution_log ael ON ase.execution_id = ael.execution_id
        """
        params = []

        if agent_id:
            sql += " WHERE ael.agent_id = ?"
            params.append(agent_id)

        sql += " ORDER BY ael.started_at_ms DESC LIMIT ?"
        params.append(limit)

        rows = self._execute_sql(sql, tuple(params)).fetchall()

        total_executions = len(rows)
        compliant = 0
        violations = 0
        violation_details = []

        for row in rows:
            unexpected_json = row[3]
            if unexpected_json and unexpected_json != "null":
                unexpected = json.loads(unexpected_json)
                if unexpected:
                    violations += 1
                    violation_details.append(
                        {
                            "execution_id": row[0],
                            "agent_id": row[4],
                            "action_id": row[5],
                            "unexpected_effects": unexpected,
                        }
                    )
                else:
                    compliant += 1
            else:
                compliant += 1

        compliance_rate = (compliant / total_executions * 100) if total_executions > 0 else 0

        return {
            "total_executions": total_executions,
            "compliant_executions": compliant,
            "violations": violations,
            "compliance_rate_percent": round(compliance_rate, 2),
            "violation_details": violation_details[:10],  # Top 10
            "agent_id": agent_id,
            "generated_at_ms": utc_now_ms(),
        }

    def get_most_common_violations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most common unexpected side effects"""
        # This would require more complex SQL to parse JSON
        # Simplified version: return unique unexpected effects
        rows = self._execute_sql(
            """
            SELECT unexpected_effects_json, COUNT(*) as count
            FROM action_side_effects
            WHERE unexpected_effects_json IS NOT NULL
            AND unexpected_effects_json != '[]'
            AND unexpected_effects_json != 'null'
            GROUP BY unexpected_effects_json
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        violations = []
        for row in rows:
            effects = json.loads(row[0])
            violations.append({"unexpected_effects": effects, "occurrence_count": row[1]})

        return violations


# ===================================================================
# Global Singleton
# ===================================================================

_tracker_instance: Optional[ActionSideEffectsTracker] = None


def get_action_side_effects_tracker(
    db_path: Optional[str] = None,
) -> ActionSideEffectsTracker:
    """
    Get global ActionSideEffectsTracker singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton instance
    """
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ActionSideEffectsTracker(db_path=db_path)
    return _tracker_instance
