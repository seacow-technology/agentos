"""
Evidence Collector for AgentOS v3

Automatic evidence collection for all Capability invocations.

Core Responsibilities:
1. Auto-collect evidence for ALL capability invocations (decorator-based)
2. Generate complete evidence packages (input, output, side effects, context)
3. Compute cryptographic hashes for integrity
4. Store evidence immutably in database
5. Provide query API for evidence retrieval

Design Principles:
- Zero-overhead collection (async storage)
- Immutable evidence (no updates after creation)
- Complete traceability (all operations must have evidence)
- Cryptographic integrity (SHA256 + signatures)

Performance Targets:
- Collection overhead: < 5ms per operation
- Storage: async (non-blocking)
- Query: < 50ms for single evidence
- Bulk query: < 200ms for 1000 records

Schema: v51 (evidence_log, evidence_chains)
"""

import logging
import json
import sqlite3
from functools import wraps
from typing import Dict, List, Optional, Any, Callable
from ulid import ULID

from agentos.core.capability.domains.evidence.models import (
    Evidence,
    EvidenceType,
    OperationType,
    SideEffectEvidence,
    generate_provenance,
    create_evidence_integrity,
    hash_content,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class EvidenceCollectionError(Exception):
    """Raised when evidence collection fails"""
    pass


class EvidenceNotFoundError(Exception):
    """Raised when evidence record not found"""
    pass


class EvidenceImmutableError(Exception):
    """Raised when attempting to modify immutable evidence"""
    pass


# ===================================================================
# Evidence Collector
# ===================================================================

class EvidenceCollector:
    """
    Core evidence collection engine for AgentOS v3.

    This is the護城河 (moat) for compliance, audit, and forensics.

    All Capability invocations MUST go through this collector.

    Example:
        collector = EvidenceCollector()

        # Manual collection
        evidence_id = collector.collect(
            operation_type=OperationType.ACTION,
            operation_id="exec-123",
            capability_id="action.execute.local",
            params={"command": "mkdir /tmp/test"},
            result={"status": "success"},
            context={
                "agent_id": "chat_agent",
                "session_id": "sess-456",
                "decision_id": "dec-abc"
            }
        )

        # Automatic collection via decorator
        @collector.auto_collect_decorator(capability_id="state.memory.read")
        def read_memory(memory_id: str):
            return {"content": "..."}
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize evidence collector.

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path
        self._db_conn = None
        self._ensure_tables()
        self._enabled = True
        logger.debug("EvidenceCollector initialized")

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
        """Ensure evidence tables exist"""
        try:
            self._execute_sql("SELECT 1 FROM evidence_log LIMIT 1")
        except Exception as e:
            logger.warning(f"evidence_log table may not exist: {e}")
            # Create minimal schema for testing
            self._create_minimal_schema()

    def _create_minimal_schema(self):
        """Create minimal evidence schema for testing"""
        logger.info("Creating minimal evidence schema")
        conn = self._get_db()

        # Evidence log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_log (
                evidence_id TEXT PRIMARY KEY,
                timestamp_ms INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                operation_capability_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                session_id TEXT,
                project_id TEXT,
                decision_id TEXT,
                input_params_hash TEXT NOT NULL,
                input_params_summary TEXT,
                output_result_hash TEXT NOT NULL,
                output_result_summary TEXT,
                side_effects_declared_json TEXT,
                side_effects_actual_json TEXT,
                provenance_json TEXT NOT NULL,
                integrity_hash TEXT NOT NULL,
                integrity_signature TEXT,
                immutable INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Create indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_operation "
            "ON evidence_log(operation_type, operation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_agent "
            "ON evidence_log(agent_id, timestamp_ms DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_decision "
            "ON evidence_log(decision_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_timestamp "
            "ON evidence_log(timestamp_ms DESC)"
        )

        conn.commit()
        logger.info("Minimal evidence schema created")

    # ===================================================================
    # Core Collection API
    # ===================================================================

    def collect(
        self,
        operation_type: OperationType,
        operation_id: str,
        capability_id: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        context: Dict[str, Any],
        side_effects: Optional[SideEffectEvidence] = None,
    ) -> str:
        """
        Collect evidence for a Capability invocation.

        This is the core collection method called by all capabilities.

        Args:
            operation_type: Type of operation (state|decision|action|governance)
            operation_id: Unique operation identifier
            capability_id: Capability ID (e.g., "action.execute.local")
            params: Operation parameters
            result: Operation result
            context: Execution context (agent_id, session_id, etc.)
            side_effects: Optional side effect evidence

        Returns:
            evidence_id: Unique evidence identifier

        Raises:
            EvidenceCollectionError: If collection fails
        """
        if not self._enabled:
            logger.warning("EvidenceCollector is disabled, skipping collection")
            return None

        try:
            # Generate evidence ID
            evidence_id = f"ev-{ULID()}"
            timestamp_ms = utc_now_ms()

            # Generate provenance
            provenance = generate_provenance()

            # Compute input/output hashes
            input_hash = hash_content(json.dumps(params, sort_keys=True))
            output_hash = hash_content(json.dumps(result, sort_keys=True))

            # Summarize input/output (for quick viewing)
            input_summary = self._summarize(params)
            output_summary = self._summarize(result)

            # Create evidence object
            evidence = Evidence(
                evidence_id=evidence_id,
                timestamp_ms=timestamp_ms,
                evidence_type=EvidenceType.OPERATION_COMPLETE,
                operation={
                    "type": operation_type.value,
                    "id": operation_id,
                    "capability_id": capability_id,
                },
                context=context,
                input={
                    "params_hash": input_hash,
                    "params_summary": input_summary,
                    "params": params,  # Store full params
                },
                output={
                    "result_hash": output_hash,
                    "result_summary": output_summary,
                    "result": result,  # Store full result
                },
                side_effects=side_effects,
                provenance=provenance,
                integrity=create_evidence_integrity(
                    evidence_content=f"{evidence_id}:{timestamp_ms}:{input_hash}:{output_hash}",
                    signed_by=context.get("agent_id"),
                ),
            )

            # Store evidence
            self._store_evidence(evidence)

            logger.debug(
                f"Collected evidence {evidence_id} for {operation_type.value} "
                f"operation {operation_id}"
            )

            return evidence_id

        except Exception as e:
            logger.error(f"Evidence collection failed: {e}")
            raise EvidenceCollectionError(f"Failed to collect evidence: {e}") from e

    def _summarize(self, data: Dict[str, Any], max_length: int = 200) -> str:
        """
        Create human-readable summary of data.

        Args:
            data: Data to summarize
            max_length: Maximum summary length

        Returns:
            Summary string
        """
        if not data:
            return ""

        try:
            # Convert to JSON
            json_str = json.dumps(data, ensure_ascii=False)

            # Truncate if too long
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + "..."

            return json_str

        except Exception as e:
            return f"<error: {e}>"

    def _store_evidence(self, evidence: Evidence):
        """
        Store evidence in database.

        Args:
            evidence: Evidence to store

        Raises:
            EvidenceCollectionError: If storage fails
        """
        conn = self._get_db()

        # Extract fields
        agent_id = evidence.context.get("agent_id", "unknown")
        session_id = evidence.context.get("session_id")
        project_id = evidence.context.get("project_id")
        decision_id = evidence.context.get("decision_id")

        # Side effects JSON
        side_effects_declared = None
        side_effects_actual = None
        if evidence.side_effects:
            side_effects_declared = json.dumps(evidence.side_effects.declared)
            side_effects_actual = json.dumps(evidence.side_effects.actual)

        # Provenance JSON
        provenance_json = evidence.provenance.model_dump_json()

        # Insert evidence
        conn.execute(
            """
            INSERT INTO evidence_log (
                evidence_id,
                timestamp_ms,
                operation_type,
                operation_capability_id,
                operation_id,
                agent_id,
                session_id,
                project_id,
                decision_id,
                input_params_hash,
                input_params_summary,
                output_result_hash,
                output_result_summary,
                side_effects_declared_json,
                side_effects_actual_json,
                provenance_json,
                integrity_hash,
                integrity_signature,
                immutable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.timestamp_ms,
                evidence.operation["type"],
                evidence.operation["capability_id"],
                evidence.operation["id"],
                agent_id,
                session_id,
                project_id,
                decision_id,
                evidence.input["params_hash"],
                evidence.input.get("params_summary"),
                evidence.output["result_hash"],
                evidence.output.get("result_summary"),
                side_effects_declared,
                side_effects_actual,
                provenance_json,
                evidence.integrity.hash,
                evidence.integrity.signature,
                1,  # immutable=True
            ),
        )

        conn.commit()

    # ===================================================================
    # Query API
    # ===================================================================

    def get(self, evidence_id: str) -> Optional[Evidence]:
        """
        Get evidence by ID.

        Args:
            evidence_id: Evidence identifier

        Returns:
            Evidence record if found, None otherwise
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT * FROM evidence_log WHERE evidence_id = ?
            """,
            (evidence_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_evidence(row)

    def query(
        self,
        agent_id: Optional[str] = None,
        operation_type: Optional[OperationType] = None,
        capability_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        limit: int = 100,
    ) -> List[Evidence]:
        """
        Query evidence records with filters.

        Args:
            agent_id: Filter by agent
            operation_type: Filter by operation type
            capability_id: Filter by capability
            decision_id: Filter by decision
            start_time_ms: Filter by start time (epoch ms)
            end_time_ms: Filter by end time (epoch ms)
            limit: Maximum number of records

        Returns:
            List of Evidence records
        """
        conn = self._get_db()

        # Build query
        where_clauses = []
        params = []

        if agent_id:
            where_clauses.append("agent_id = ?")
            params.append(agent_id)

        if operation_type:
            where_clauses.append("operation_type = ?")
            params.append(operation_type.value)

        if capability_id:
            where_clauses.append("operation_capability_id = ?")
            params.append(capability_id)

        if decision_id:
            where_clauses.append("decision_id = ?")
            params.append(decision_id)

        if start_time_ms:
            where_clauses.append("timestamp_ms >= ?")
            params.append(start_time_ms)

        if end_time_ms:
            where_clauses.append("timestamp_ms <= ?")
            params.append(end_time_ms)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Execute query
        cursor = conn.execute(
            f"""
            SELECT * FROM evidence_log
            WHERE {where_sql}
            ORDER BY timestamp_ms DESC
            LIMIT ?
            """,
            params + [limit],
        )

        rows = cursor.fetchall()

        # Convert to Evidence objects
        evidences = []
        for row in rows:
            evidence = self._row_to_evidence(row)
            if evidence:
                evidences.append(evidence)

        return evidences

    def _row_to_evidence(self, row) -> Optional[Evidence]:
        """
        Convert database row to Evidence object.

        Args:
            row: SQLite row

        Returns:
            Evidence object
        """
        try:
            # Parse provenance
            provenance_json = row["provenance_json"]
            from agentos.core.capability.domains.evidence.models import EvidenceProvenance
            provenance = EvidenceProvenance.model_validate_json(provenance_json)

            # Parse side effects
            side_effects = None
            if row["side_effects_declared_json"]:
                declared = json.loads(row["side_effects_declared_json"])
                actual = json.loads(row["side_effects_actual_json"] or "[]")
                side_effects = SideEffectEvidence(
                    declared=declared,
                    actual=actual,
                    unexpected=[],
                    missing=[],
                )

            # Create integrity
            from agentos.core.capability.domains.evidence.models import EvidenceIntegrity
            integrity = EvidenceIntegrity(
                hash=row["integrity_hash"],
                signature=row["integrity_signature"],
                algorithm="sha256",
                verified=False,
            )

            # Create Evidence
            evidence = Evidence(
                evidence_id=row["evidence_id"],
                timestamp_ms=row["timestamp_ms"],
                evidence_type=EvidenceType.OPERATION_COMPLETE,
                operation={
                    "type": row["operation_type"],
                    "id": row["operation_id"],
                    "capability_id": row["operation_capability_id"],
                },
                context={
                    "agent_id": row["agent_id"],
                    "session_id": row["session_id"],
                    "project_id": row["project_id"],
                    "decision_id": row["decision_id"],
                },
                input={
                    "params_hash": row["input_params_hash"],
                    "params_summary": row["input_params_summary"],
                },
                output={
                    "result_hash": row["output_result_hash"],
                    "result_summary": row["output_result_summary"],
                },
                side_effects=side_effects,
                provenance=provenance,
                integrity=integrity,
            )

            return evidence

        except Exception as e:
            logger.error(f"Failed to parse evidence row: {e}")
            return None

    # ===================================================================
    # Decorator for Auto-Collection
    # ===================================================================

    def auto_collect_decorator(
        self,
        capability_id: str,
        operation_type: OperationType = OperationType.ACTION,
    ):
        """
        Decorator for automatic evidence collection.

        Wraps a function to automatically collect evidence on invocation.

        Args:
            capability_id: Capability ID
            operation_type: Operation type

        Returns:
            Decorator function

        Example:
            @collector.auto_collect_decorator(capability_id="state.memory.read")
            def read_memory(memory_id: str):
                return {"content": "..."}
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate operation ID
                operation_id = f"op-{ULID()}"

                # Extract context (from kwargs or context manager)
                context = kwargs.pop("_evidence_context", {})
                if "agent_id" not in context:
                    context["agent_id"] = "unknown"

                # Record start time
                start_ms = utc_now_ms()

                try:
                    # Execute function
                    result = func(*args, **kwargs)

                    # Collect evidence
                    self.collect(
                        operation_type=operation_type,
                        operation_id=operation_id,
                        capability_id=capability_id,
                        params={"args": args, "kwargs": kwargs},
                        result={"return_value": result},
                        context=context,
                    )

                    return result

                except Exception as e:
                    # Collect evidence for failure
                    self.collect(
                        operation_type=operation_type,
                        operation_id=operation_id,
                        capability_id=capability_id,
                        params={"args": args, "kwargs": kwargs},
                        result={"error": str(e)},
                        context=context,
                    )
                    raise

            return wrapper
        return decorator

    # ===================================================================
    # State Management
    # ===================================================================

    def is_enabled(self) -> bool:
        """Check if evidence collector is enabled"""
        return self._enabled

    def enable(self):
        """Enable evidence collection"""
        self._enabled = True
        logger.info("Evidence collection enabled")

    def disable(self):
        """Disable evidence collection (testing only)"""
        self._enabled = False
        logger.warning("Evidence collection DISABLED (testing mode)")

    def update_evidence(self, evidence_id: str, **kwargs):
        """
        Attempt to update evidence (ALWAYS RAISES).

        Evidence is IMMUTABLE and cannot be modified.

        Raises:
            EvidenceImmutableError: Always
        """
        raise EvidenceImmutableError(
            f"Evidence {evidence_id} is immutable and cannot be modified. "
            f"Create a new evidence record instead."
        )


# ===================================================================
# Global Singleton
# ===================================================================

_collector_instance: Optional[EvidenceCollector] = None


def get_evidence_collector(db_path: Optional[str] = None) -> EvidenceCollector:
    """
    Get global EvidenceCollector singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton EvidenceCollector instance
    """
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = EvidenceCollector(db_path=db_path)
    return _collector_instance
