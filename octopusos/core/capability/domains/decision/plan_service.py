"""
Plan Service - Plan lifecycle management for Decision Domain

This service implements DC-001 and DC-002:
- decision.plan.create: Create draft plans
- decision.plan.freeze: Freeze plans (make immutable)

Key Design Principles:
1. Plans start in DRAFT state (modifiable)
2. Freeze is irreversible (semantic freeze)
3. Frozen plans generate SHA-256 hash
4. Plans must be based on frozen context
5. Evidence is recorded for all operations
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional
from ulid import ULID

from agentos.core.capability.domains.decision.models import (
    Plan,
    PlanStep,
    Alternative,
    PlanStatus,
    ImmutablePlanError,
    InvalidPlanHashError,
    PlanNotFrozenError,
    DecisionContextNotFrozenError,
)
from agentos.core.capability.path_validator import PathValidator, CapabilityDomain
from agentos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


class PlanService:
    """
    Service for managing Plan lifecycle.

    Capabilities implemented:
    - decision.plan.create (DC-001)
    - decision.plan.freeze (DC-002)
    - decision.plan.rollback (DC-005, emergency only)

    Usage:
        service = PlanService(db_path="...")

        # Create draft plan
        plan = service.create_plan(
            task_id="task-123",
            steps=[...],
            rationale="...",
            created_by="agent-1"
        )

        # Freeze plan (make immutable)
        frozen_plan = service.freeze_plan(plan.plan_id)

        # Verify plan hash before execution
        if not service.verify_plan(plan.plan_id, expected_hash):
            raise InvalidPlanHashError(...)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize plan service.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        self.path_validator = PathValidator(db_path=db_path)
        logger.info(f"PlanService initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # DC-001: decision.plan.create
    # ===================================================================

    def create_plan(
        self,
        task_id: str,
        steps: List[PlanStep],
        rationale: str,
        created_by: str,
        alternatives: Optional[List[Alternative]] = None,
        context_snapshot_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Plan:
        """
        Create a new execution plan in DRAFT state.

        Implements: decision.plan.create (DC-001)

        The plan is initially mutable. It must be frozen before execution.

        Args:
            task_id: Task this plan belongs to
            steps: List of execution steps
            rationale: Why this plan was chosen
            created_by: Agent/user creating the plan
            alternatives: Alternative plans considered (optional)
            context_snapshot_id: Frozen context snapshot ID (optional but recommended)
            metadata: Additional metadata

        Returns:
            Created Plan in DRAFT state

        Raises:
            DecisionContextNotFrozenError: If context_snapshot_id is not frozen
        """
        # Validate context is frozen (if provided)
        if context_snapshot_id:
            if not self._is_context_frozen(context_snapshot_id):
                raise DecisionContextNotFrozenError(
                    f"Context snapshot {context_snapshot_id} is not frozen"
                )

        # Generate plan ID
        plan_id = f"plan-{ULID()}"
        created_at_ms = utc_now_ms()

        # Create plan object
        plan = Plan(
            plan_id=plan_id,
            task_id=task_id,
            steps=steps,
            alternatives=alternatives or [],
            rationale=rationale,
            status=PlanStatus.DRAFT,
            frozen_at_ms=None,
            plan_hash=None,
            created_by=created_by,
            created_at_ms=created_at_ms,
            updated_at_ms=None,
            context_snapshot_id=context_snapshot_id,
            metadata=metadata or {},
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        steps_json = json.dumps([step.model_dump() for step in steps])
        alternatives_json = json.dumps([alt.model_dump() for alt in plan.alternatives])
        metadata_json = json.dumps(metadata or {})

        cursor.execute(
            """
            INSERT INTO decision_plans (
                plan_id, task_id, steps_json, alternatives_json, rationale,
                status, frozen_at_ms, plan_hash, created_by, created_at_ms,
                updated_at_ms, context_snapshot_id, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                task_id,
                steps_json,
                alternatives_json,
                rationale,
                PlanStatus.DRAFT.value,
                None,
                None,
                created_by,
                created_at_ms,
                None,
                context_snapshot_id,
                metadata_json,
            ),
        )

        conn.commit()
        conn.close()

        logger.info(f"Created plan {plan_id} for task {task_id} (status: DRAFT)")

        # Record evidence
        self._record_evidence(
            operation="plan.create",
            plan_id=plan_id,
            params={
                "task_id": task_id,
                "num_steps": len(steps),
                "created_by": created_by,
            },
            result={"plan_id": plan_id, "status": "draft"},
        )

        return plan

    def _is_context_frozen(self, context_snapshot_id: str) -> bool:
        """
        Check if context snapshot is frozen.

        For now, we assume context is frozen if it exists.
        In production, this would check the context service.
        """
        # TODO: Integrate with context snapshot service
        return True

    # ===================================================================
    # DC-002: decision.plan.freeze
    # ===================================================================

    def freeze_plan(self, plan_id: str, frozen_by: str) -> Plan:
        """
        Freeze a plan (make immutable).

        Implements: decision.plan.freeze (DC-002)

        Once frozen:
        - Status changes from DRAFT to FROZEN
        - plan_hash is computed (SHA-256)
        - No further modifications allowed
        - Plan can now be executed by Executor

        Args:
            plan_id: Plan to freeze
            frozen_by: Who is freezing (agent/user)

        Returns:
            Frozen plan with plan_hash

        Raises:
            ImmutablePlanError: If plan is already frozen
            ValueError: If plan not found
        """
        # Load plan
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Plan not found: {plan_id}")

        # Check if already frozen
        if plan.status == PlanStatus.FROZEN:
            raise ImmutablePlanError(
                plan_id, "Plan is already frozen and cannot be modified"
            )

        # Update status and compute hash
        frozen_at_ms = utc_now_ms()
        plan.status = PlanStatus.FROZEN
        plan.frozen_at_ms = frozen_at_ms
        plan.plan_hash = plan.compute_hash()

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE decision_plans
            SET status = ?, frozen_at_ms = ?, plan_hash = ?, updated_at_ms = ?
            WHERE plan_id = ?
            """,
            (
                PlanStatus.FROZEN.value,
                frozen_at_ms,
                plan.plan_hash,
                frozen_at_ms,
                plan_id,
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Frozen plan {plan_id} (hash: {plan.plan_hash[:8]}..., frozen_by: {frozen_by})"
        )

        # Record evidence
        self._record_evidence(
            operation="plan.freeze",
            plan_id=plan_id,
            params={"frozen_by": frozen_by},
            result={
                "plan_id": plan_id,
                "status": "frozen",
                "plan_hash": plan.plan_hash,
                "frozen_at_ms": frozen_at_ms,
            },
        )

        return plan

    # ===================================================================
    # Query Methods
    # ===================================================================

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """
        Get plan by ID.

        Args:
            plan_id: Plan identifier

        Returns:
            Plan object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT plan_id, task_id, steps_json, alternatives_json, rationale,
                   status, frozen_at_ms, plan_hash, created_by, created_at_ms,
                   updated_at_ms, context_snapshot_id, metadata
            FROM decision_plans
            WHERE plan_id = ?
            """,
            (plan_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Parse JSON fields
        steps_data = json.loads(row["steps_json"])
        steps = [PlanStep(**step) for step in steps_data]

        alternatives_data = json.loads(row["alternatives_json"] or "[]")
        alternatives = [Alternative(**alt) for alt in alternatives_data]

        metadata = json.loads(row["metadata"] or "{}")

        return Plan(
            plan_id=row["plan_id"],
            task_id=row["task_id"],
            steps=steps,
            alternatives=alternatives,
            rationale=row["rationale"],
            status=PlanStatus(row["status"]),
            frozen_at_ms=row["frozen_at_ms"],
            plan_hash=row["plan_hash"],
            created_by=row["created_by"],
            created_at_ms=row["created_at_ms"],
            updated_at_ms=row["updated_at_ms"],
            context_snapshot_id=row["context_snapshot_id"],
            metadata=metadata,
        )

    def verify_plan(self, plan_id: str, expected_hash: str) -> bool:
        """
        Verify plan hash matches expected value.

        Used by Executor before executing a plan.

        Args:
            plan_id: Plan to verify
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise

        Raises:
            ValueError: If plan not found
            PlanNotFrozenError: If plan is not frozen
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Plan not found: {plan_id}")

        if not plan.is_frozen():
            raise PlanNotFrozenError(
                plan_id, "Cannot verify hash of non-frozen plan"
            )

        return plan.verify_hash(expected_hash)

    def list_plans(
        self,
        task_id: Optional[str] = None,
        status: Optional[PlanStatus] = None,
        limit: int = 100,
    ) -> List[Plan]:
        """
        List plans with optional filters.

        Args:
            task_id: Filter by task (optional)
            status: Filter by status (optional)
            limit: Max results

        Returns:
            List of plans
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT plan_id, task_id, steps_json, alternatives_json, rationale,
                   status, frozen_at_ms, plan_hash, created_by, created_at_ms,
                   updated_at_ms, context_snapshot_id, metadata
            FROM decision_plans
            WHERE 1=1
        """
        params = []

        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at_ms DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        plans = []
        for row in rows:
            steps_data = json.loads(row["steps_json"])
            steps = [PlanStep(**step) for step in steps_data]

            alternatives_data = json.loads(row["alternatives_json"] or "[]")
            alternatives = [Alternative(**alt) for alt in alternatives_data]

            metadata = json.loads(row["metadata"] or "{}")

            plan = Plan(
                plan_id=row["plan_id"],
                task_id=row["task_id"],
                steps=steps,
                alternatives=alternatives,
                rationale=row["rationale"],
                status=PlanStatus(row["status"]),
                frozen_at_ms=row["frozen_at_ms"],
                plan_hash=row["plan_hash"],
                created_by=row["created_by"],
                created_at_ms=row["created_at_ms"],
                updated_at_ms=row["updated_at_ms"],
                context_snapshot_id=row["context_snapshot_id"],
                metadata=metadata,
            )
            plans.append(plan)

        return plans

    # ===================================================================
    # Modification (DRAFT only)
    # ===================================================================

    def update_plan(
        self,
        plan_id: str,
        steps: Optional[List[PlanStep]] = None,
        rationale: Optional[str] = None,
        alternatives: Optional[List[Alternative]] = None,
    ) -> Plan:
        """
        Update a DRAFT plan.

        Args:
            plan_id: Plan to update
            steps: New steps (optional)
            rationale: New rationale (optional)
            alternatives: New alternatives (optional)

        Returns:
            Updated plan

        Raises:
            ImmutablePlanError: If plan is frozen
            ValueError: If plan not found
        """
        # Load plan
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Plan not found: {plan_id}")

        # Check if frozen
        if plan.is_frozen():
            raise ImmutablePlanError(
                plan_id, "Cannot modify frozen plan"
            )

        # Update fields
        if steps is not None:
            plan.steps = steps
        if rationale is not None:
            plan.rationale = rationale
        if alternatives is not None:
            plan.alternatives = alternatives

        plan.updated_at_ms = utc_now_ms()

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        steps_json = json.dumps([step.model_dump() for step in plan.steps])
        alternatives_json = json.dumps([alt.model_dump() for alt in plan.alternatives])

        cursor.execute(
            """
            UPDATE decision_plans
            SET steps_json = ?, alternatives_json = ?, rationale = ?, updated_at_ms = ?
            WHERE plan_id = ?
            """,
            (steps_json, alternatives_json, plan.rationale, plan.updated_at_ms, plan_id),
        )

        conn.commit()
        conn.close()

        logger.info(f"Updated plan {plan_id}")

        return plan

    # ===================================================================
    # Evidence Recording
    # ===================================================================

    def _record_evidence(
        self, operation: str, plan_id: str, params: Dict, result: Dict
    ):
        """
        Record evidence for plan operations.

        This integrates with Evidence Domain (capability: evidence.record).
        """
        # For now, just log to info
        # In production, this would call evidence.record capability
        logger.info(
            f"Evidence: {operation} on plan {plan_id} | params={params} | result={result}"
        )

        # TODO: Integrate with evidence service
        # evidence_service.record(
        #     operation_type="decision.plan",
        #     operation_id=plan_id,
        #     params=params,
        #     result=result
        # )


# ===================================================================
# Global instance
# ===================================================================

_plan_service_instance: Optional[PlanService] = None


def get_plan_service(db_path: Optional[str] = None) -> PlanService:
    """
    Get global plan service singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton PlanService instance
    """
    global _plan_service_instance
    if _plan_service_instance is None:
        _plan_service_instance = PlanService(db_path=db_path)
    return _plan_service_instance
