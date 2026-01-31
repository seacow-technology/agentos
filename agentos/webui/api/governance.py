"""
Governance API - Decision Replay, Audit, and Capability Governance

Core endpoints for answering "Why was this task allowed/paused/blocked?"
and providing Capability Governance data visualization.

Supervisor Decision Endpoints:
GET /api/governance/tasks/{task_id}/summary - Task governance overview
GET /api/governance/tasks/{task_id}/decision-trace - Complete decision trace
GET /api/governance/decisions/{decision_id} - Single decision details
GET /api/governance/stats/blocked-reasons - Blocked tasks TopN
GET /api/governance/stats/decision-types - Decision type distribution
GET /api/governance/stats/decision-lag - Decision lag percentiles

Capability Governance Endpoints (PR-1):
GET /api/governance/summary - Governance system overview
GET /api/governance/quotas - Quota status list
GET /api/governance/trust-tiers - Trust tier configurations
GET /api/governance/provenance/{invocation_id} - Provenance query
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

from agentos.core.supervisor.trace.replay import TraceAssembler, format_trace_item
from agentos.core.supervisor.trace.storage import TraceStorage
from agentos.core.supervisor.trace.stats import StatsCalculator
from agentos.store import get_db
from agentos.webui.api.contracts import ReasonCode
from agentos.webui.api.time_format import iso_z

# Capability Governance imports (PR-1)
from agentos.core.capabilities.registry import CapabilityRegistry
from agentos.core.capabilities.quota_manager import QuotaManager
from agentos.core.extensions.registry import ExtensionRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])

# Global instances for Capability Governance (initialized lazily)
_capability_registry: Optional[CapabilityRegistry] = None
_quota_manager: Optional[QuotaManager] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get capability registry instance (lazy initialization)"""
    global _capability_registry
    if _capability_registry is None:
        ext_registry = ExtensionRegistry()
        _capability_registry = CapabilityRegistry(ext_registry)
    return _capability_registry


def get_quota_manager() -> QuotaManager:
    """Get quota manager instance (lazy initialization)"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager


# Response Models
class AdminValidateResponse(BaseModel):
    """Admin validation response"""
    valid: bool
    message: str = "Admin access validated"


class TaskGovernanceSummaryResponse(BaseModel):
    """Task governance summary response"""
    task_id: str
    status: str
    last_decision_type: Optional[str] = None
    last_decision_ts: Optional[str] = None
    blocked_reason_code: Optional[str] = None
    inbox_backlog: int
    decision_count: int


class DecisionTraceResponse(BaseModel):
    """Decision trace response with pagination"""
    task_id: str
    trace_items: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    count: int


class DecisionDetailResponse(BaseModel):
    """Single decision detail response"""
    decision_id: str
    decision_snapshot: Dict[str, Any]


class BlockedReasonsStatsResponse(BaseModel):
    """Blocked reasons statistics response"""
    window: str
    top_n: int
    blocked_tasks: List[Dict[str, Any]]


class DecisionTypesStatsResponse(BaseModel):
    """Decision types statistics response"""
    window: str
    decision_types: Dict[str, int]
    total: int


class DecisionLagSample(BaseModel):
    """Single decision lag sample"""
    decision_id: str
    lag_ms: int
    source: str  # "columns" or "payload"


class DecisionLagStatsResponse(BaseModel):
    """Decision lag statistics response"""
    window: str
    percentile: int
    p50: Optional[float] = None
    p95: Optional[float] = None
    count: int
    samples: List[DecisionLagSample] = []
    query_method: str  # "columns" or "payload_fallback"
    redundant_column_coverage: float  # 0.0-1.0


# ============================================
# Capability Governance Response Models (PR-1)
# ============================================

class CapabilitySummary(BaseModel):
    """Capabilities summary"""
    total: int = Field(description="Total number of capabilities")
    by_trust_tier: Dict[str, int] = Field(description="Count by trust tier")
    by_source: Dict[str, int] = Field(description="Count by source type")


class QuotaSummary(BaseModel):
    """Quota summary"""
    warnings: int = Field(description="Number of quotas in warning state (80-100%)")
    denied: int = Field(description="Number of quotas that have denied requests (>100%)")
    total_tracked: int = Field(description="Total number of tracked quotas")


class GovernanceEvent(BaseModel):
    """Governance event"""
    timestamp: str = Field(description="Event timestamp (ISO 8601)")
    event_type: str = Field(description="Event type (quota_warning | quota_denied | gate_blocked)")
    capability_id: str = Field(description="Capability ID")
    message: str = Field(description="Event message")


class GovernanceSummaryResponse(BaseModel):
    """Governance summary response"""
    capabilities: CapabilitySummary
    quota: QuotaSummary
    recent_events: List[GovernanceEvent] = Field(description="Recent governance events (max 10)")


class QuotaLimitStatus(BaseModel):
    """Quota limit status"""
    limit: int
    used: int
    usage_percent: float


class QuotaStatus(BaseModel):
    """Quota status for a capability"""
    capability_id: str
    tool_id: str
    trust_tier: str
    quota: Dict[str, QuotaLimitStatus] = Field(description="Quota limits and usage")
    status: str = Field(description="Status: ok | warning | denied")
    last_triggered: Optional[str] = Field(None, description="Last triggered timestamp")


class QuotasResponse(BaseModel):
    """Quotas list response"""
    quotas: List[QuotaStatus]


class TrustTierPolicy(BaseModel):
    """Trust tier default policy"""
    risk_level: str = Field(description="Default risk level")
    requires_admin_token: bool = Field(description="Requires admin token")
    default_quota_profile: Dict[str, Any] = Field(description="Default quota profile")


class TrustTierInfo(BaseModel):
    """Trust tier information"""
    tier: str = Field(description="Tier ID (T0, T1, T2, T3)")
    name: str = Field(description="Tier name")
    capabilities: List[str] = Field(description="List of capability IDs in this tier")
    count: int = Field(description="Number of capabilities")
    default_policy: TrustTierPolicy


class TrustTiersResponse(BaseModel):
    """Trust tiers response"""
    tiers: List[TrustTierInfo]


class ExecutionEnvInfo(BaseModel):
    """Execution environment info"""
    hostname: str
    pid: int
    container_id: Optional[str] = None


class AuditEvent(BaseModel):
    """Audit chain event"""
    event_type: str
    timestamp: str
    gate: Optional[str] = None
    result: str


class ProvenanceInfo(BaseModel):
    """Provenance information"""
    capability_id: str
    tool_id: str
    capability_type: str = Field(description="extension | mcp")
    source_id: str
    execution_env: ExecutionEnvInfo
    trust_tier: str
    timestamp: str
    invocation_id: str


class ProvenanceResponse(BaseModel):
    """Provenance query response"""
    provenance: ProvenanceInfo
    audit_chain: List[AuditEvent] = Field(description="Audit event chain")


def _parse_window(window: str) -> int:
    """
    Parse window string to hours

    Args:
        window: Window string (24h, 7d, 30d)

    Returns:
        Hours as integer

    Raises:
        ValueError: If window format is invalid
    """
    if window == "24h":
        return 24
    elif window == "7d":
        return 7 * 24
    elif window == "30d":
        return 30 * 24
    else:
        raise ValueError(f"Invalid window format: {window}")


@router.get("/admin/validate", response_model=AdminValidateResponse)
async def validate_admin() -> AdminValidateResponse:
    """
    Validate admin access

    Currently returns valid=True in local mode.
    In cloud deployments, this would check for admin tokens/permissions.

    Returns:
        AdminValidateResponse with valid field
    """
    # For local mode, always valid
    # In future cloud deployments, implement proper auth check
    return AdminValidateResponse(valid=True, message="Local mode - admin access granted")


@router.get("/tasks/{task_id}/summary", response_model=TaskGovernanceSummaryResponse)
async def get_task_governance_summary(task_id: str) -> TaskGovernanceSummaryResponse:
    """
    Get task governance summary

    Returns:
    - Task basic info (status, created_at)
    - Supervisor statistics (decision count, last decision, blocked reason)
    - Inbox backlog (if any)
    - Last N key audit events

    Args:
        task_id: Task ID

    Returns:
        Task governance summary

    Raises:
        HTTPException: 404 if task not found

    Example:
        ```bash
        curl http://localhost:8080/api/governance/tasks/task-123/summary
        ```
    """
    try:
        conn = get_db()  # Shared thread-local connection
        storage = TraceStorage(conn)
        assembler = TraceAssembler(storage)

        summary = assembler.get_summary(task_id)

        if summary is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        return TaskGovernanceSummaryResponse(
            task_id=summary.task_id,
            status=summary.status,
            last_decision_type=summary.last_decision_type,
            last_decision_ts=summary.last_decision_ts,
            blocked_reason_code=summary.blocked_reason_code,
            inbox_backlog=summary.inbox_backlog,
            decision_count=summary.decision_count,
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tasks/{task_id}/decision-trace", response_model=DecisionTraceResponse)
async def get_task_decision_trace(
    task_id: str,
    limit: int = Query(200, ge=1, le=500, description="Maximum number of trace items to return"),
    cursor: Optional[str] = Query(None, description="Pagination cursor (timestamp_id)")
) -> DecisionTraceResponse:
    """
    Get task decision trace (core endpoint)

    Returns time-ordered trace items:
    - event (from task_events / inbox)
    - supervisor_audit (with decision_snapshot)
    - resulting_state_change (task state changes)
    - gate_state_change (pause/enforcer records, if any)

    Args:
        task_id: Task ID
        limit: Maximum number of trace items (1-500, default 200)
        cursor: Pagination cursor for next page

    Returns:
        Decision trace with pagination support

    Raises:
        HTTPException: 400 if parameters invalid, 404 if task not found

    Example:
        ```bash
        # Get first page
        curl http://localhost:8080/api/governance/tasks/task-123/decision-trace?limit=50

        # Get next page
        curl http://localhost:8080/api/governance/tasks/task-123/decision-trace?limit=50&cursor=2024-01-01T00:00:00Z_123
        ```
    """
    try:
        # Validate limit
        if limit < 1 or limit > 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

        conn = get_db()  # Shared thread-local connection
        storage = TraceStorage(conn)
        assembler = TraceAssembler(storage)

        # Check if task exists
        task_info = storage.get_task_info(task_id)
        if task_info is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # Get decision trace
        trace_items, next_cursor = assembler.get_decision_trace(
            task_id=task_id,
            limit=limit,
            cursor=cursor
        )

        # Format trace items for JSON response
        formatted_items = [format_trace_item(item) for item in trace_items]

        return DecisionTraceResponse(
            task_id=task_id,
            trace_items=formatted_items,
            next_cursor=next_cursor,
            count=len(formatted_items)
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/decisions/{decision_id}", response_model=DecisionDetailResponse)
async def get_decision(decision_id: str) -> DecisionDetailResponse:
    """
    Get single decision details

    Directly fetches decision_snapshot from audit.payload (no need to join many tables)

    Args:
        decision_id: Decision ID

    Returns:
        Complete decision snapshot

    Raises:
        HTTPException: 404 if decision not found

    Example:
        ```bash
        curl http://localhost:8080/api/governance/decisions/dec-123
        ```
    """
    try:
        conn = get_db()  # Shared thread-local connection
        storage = TraceStorage(conn)
        assembler = TraceAssembler(storage)

        decision_snapshot = assembler.get_decision(decision_id)

        if decision_snapshot is None:
            raise HTTPException(
                status_code=404,
                detail=f"Decision not found: {decision_id}"
            )

        return DecisionDetailResponse(
            decision_id=decision_id,
            decision_snapshot=decision_snapshot
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats/blocked-reasons", response_model=BlockedReasonsStatsResponse)
async def stats_blocked_reasons(
    window: str = Query("7d", pattern="^(24h|7d|30d)$", description="Time window (24h, 7d, 30d)"),
    top_n: int = Query(20, ge=1, le=100, description="Number of top results")
) -> BlockedReasonsStatsResponse:
    """
    Statistics: Blocked/Paused TopN (for Dashboard)

    Returns top N tasks by block count, useful for identifying problematic patterns

    Args:
        window: Time window (24h, 7d, 30d)
        top_n: Number of top results (1-100, default 20)

    Returns:
        Top N blocked tasks with reason codes

    Example:
        ```bash
        curl http://localhost:8080/api/governance/stats/blocked-reasons?window=7d&top_n=10
        ```
    """
    try:
        # Validate parameters
        if top_n < 1 or top_n > 100:
            raise HTTPException(status_code=400, detail="top_n must be between 1 and 100")

        conn = get_db()  # Shared thread-local connection
        calculator = StatsCalculator(conn)

        blocked_tasks = calculator.get_blocked_tasks_topn(limit=top_n)

        return BlockedReasonsStatsResponse(
            window=window,
            top_n=top_n,
            blocked_tasks=blocked_tasks
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats/decision-types", response_model=DecisionTypesStatsResponse)
async def stats_decision_types(
    window: str = Query("24h", pattern="^(24h|7d|30d)$", description="Time window (24h, 7d, 30d)")
) -> DecisionTypesStatsResponse:
    """
    Statistics: Decision type distribution

    Returns count of each decision type (ALLOW, PAUSE, BLOCK, RETRY) within time window

    Args:
        window: Time window (24h, 7d, 30d)

    Returns:
        Decision type distribution statistics

    Example:
        ```bash
        curl http://localhost:8080/api/governance/stats/decision-types?window=24h
        ```
    """
    try:
        hours = _parse_window(window)

        conn = get_db()  # Shared thread-local connection
        calculator = StatsCalculator(conn)

        decision_types = calculator.get_decision_type_stats(hours=hours)
        total = sum(decision_types.values())

        return DecisionTypesStatsResponse(
            window=window,
            decision_types=decision_types,
            total=total
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats/decision-lag", response_model=DecisionLagStatsResponse)
async def stats_decision_lag(
    window: str = Query("24h", pattern="^(24h|7d|30d)$", description="Time window (24h, 7d, 30d)"),
    pctl: int = Query(95, ge=50, le=99, description="Percentile to calculate (50-99)")
) -> DecisionLagStatsResponse:
    """
    Statistics: Decision lag percentiles

    Calculates decision processing lag (time from event to decision) percentiles

    v21+ Enhancement: Returns data source information (redundant columns vs payload)

    Args:
        window: Time window (24h, 7d, 30d)
        pctl: Percentile to calculate (50-99, default 95)

    Returns:
        Decision lag statistics with:
        - p50, p95: Percentile values (seconds)
        - count: Total samples
        - samples: High-lag samples with data source tags
        - query_method: "columns" (v21+ fast) or "payload_fallback" (v20 compat)
        - redundant_column_coverage: Percentage using v21 columns (0.0-1.0)

    Example:
        ```bash
        curl http://localhost:8080/api/governance/stats/decision-lag?window=24h&pctl=95
        ```
    """
    try:
        # Validate percentile
        if pctl < 50 or pctl > 99:
            raise HTTPException(status_code=400, detail="pctl must be between 50 and 99")

        hours = _parse_window(window)

        conn = get_db()  # Shared thread-local connection
        calculator = StatsCalculator(conn)

        lag_stats = calculator.get_decision_lag_percentiles(hours=hours)

        # Convert samples to response model
        samples = [
            DecisionLagSample(
                decision_id=s["decision_id"],
                lag_ms=s["lag_ms"],
                source=s["source"]
            )
            for s in lag_stats.get("samples", [])
        ]

        return DecisionLagStatsResponse(
            window=window,
            percentile=pctl,
            p50=lag_stats.get("p50"),
            p95=lag_stats.get("p95"),
            count=lag_stats.get("count", 0),
            samples=samples,
            query_method=lag_stats.get("query_method", "payload_fallback"),
            redundant_column_coverage=lag_stats.get("redundant_column_coverage", 0.0)
        )
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================
# Capability Governance Endpoints (PR-1)
# ============================================

@router.get("/summary", response_model=GovernanceSummaryResponse)
async def get_capability_governance_summary():
    """
    Get capability governance system overview

    Returns summary of:
    - Capabilities (total, by trust tier, by source)
    - Quotas (warnings, denials, total tracked)
    - Recent governance events (max 10)

    This is a read-only endpoint with no side effects.
    Part of PR-1: Governance APIs (Backend Read-Only Interface)
    """
    try:
        registry = get_capability_registry()
        quota_manager = get_quota_manager()

        # Get all capabilities
        all_tools = registry.list_tools(enabled_only=False)

        # Calculate capabilities summary
        by_trust_tier = {}
        by_source = {}

        for tool in all_tools:
            # Count by trust tier
            tier = tool.trust_tier.value
            by_trust_tier[tier] = by_trust_tier.get(tier, 0) + 1

            # Count by source
            source = tool.source_type.value
            by_source[source] = by_source.get(source, 0) + 1

        capabilities = CapabilitySummary(
            total=len(all_tools),
            by_trust_tier=by_trust_tier,
            by_source=by_source
        )

        # Calculate quota summary
        warnings = 0
        denied = 0
        total_tracked = len(quota_manager.states)

        for quota_id, state in quota_manager.states.items():
            quota = quota_manager.quotas.get(quota_id)
            if not quota or not quota.enabled:
                continue

            # Check for warnings (80-100% usage)
            if quota.limit.calls_per_minute:
                usage_percent = state.used_calls / quota.limit.calls_per_minute
                if usage_percent >= 0.8 and usage_percent < 1.0:
                    warnings += 1
                elif usage_percent >= 1.0:
                    denied += 1

        quota_summary = QuotaSummary(
            warnings=warnings,
            denied=denied,
            total_tracked=total_tracked
        )

        # Get recent governance events from audit system
        recent_events = []

        # Try to get recent events from task_audits table
        try:
            from agentos.core.storage.paths import component_db_path
            import sqlite3

            db_path = component_db_path("agentos")
            if db_path.exists():
                # Create new connection for this specific query (not using get_db())
                audit_conn = sqlite3.connect(str(db_path))
                try:
                    cursor = audit_conn.cursor()

                    # Query recent governance events
                    cursor.execute("""
                        SELECT created_at, event_type, payload
                        FROM task_audits
                        WHERE event_type IN ('quota_warning', 'quota_exceeded', 'policy_violation')
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)

                    rows = cursor.fetchall()
                    for row in rows:
                        timestamp, event_type, payload_json = row
                        import json
                        payload = json.loads(payload_json) if payload_json else {}

                        recent_events.append(GovernanceEvent(
                            timestamp=timestamp,
                            event_type=event_type,
                            capability_id=payload.get('tool_id', 'unknown'),
                            message=payload.get('reason', payload.get('error', 'No message'))
                        ))
                finally:
                    audit_conn.close()  # Close explicitly created connection
        except Exception as e:
            logger.warning(f"Failed to load recent events: {e}")
            # Graceful degradation - continue without events

        return GovernanceSummaryResponse(
            capabilities=capabilities,
            quota=quota_summary,
            recent_events=recent_events
        )

    except Exception as e:
        logger.error(f"Failed to get governance summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get governance summary",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/quotas", response_model=QuotasResponse)
async def get_capability_quotas():
    """
    Get quota status for all tracked capabilities

    Returns list of quota statuses including:
    - Capability and tool IDs
    - Current usage vs limits
    - Status (ok | warning | denied)
    - Last triggered timestamp

    This is a read-only endpoint with no side effects.
    Part of PR-1: Governance APIs (Backend Read-Only Interface)
    """
    try:
        quota_manager = get_quota_manager()
        registry = get_capability_registry()

        quotas_list = []

        for quota_id, quota_config in quota_manager.quotas.items():
            if not quota_config.enabled:
                continue

            state = quota_manager.states.get(quota_id)
            if not state:
                # No state yet, create default
                state = quota_manager._get_or_create_state(quota_id)

            # Calculate status
            status = "ok"
            quota_details = {}

            # Calls per minute
            if quota_config.limit.calls_per_minute:
                # H-9 Fix: Clamp negative usage values to 0
                used_calls = max(0, state.used_calls)
                limit_calls = max(1, quota_config.limit.calls_per_minute)  # Prevent division by zero
                usage_percent = min((used_calls / limit_calls) * 100, 100)  # Clamp to 0-100%

                quota_details["calls_per_minute"] = QuotaLimitStatus(
                    limit=quota_config.limit.calls_per_minute,
                    used=used_calls,
                    usage_percent=round(usage_percent, 2)
                )

                # H-10 Fix: Use >= to mark exactly 100% as denied
                if usage_percent >= 100:
                    status = "denied"
                elif usage_percent >= 80:
                    status = "warning"

            # Max concurrent
            if quota_config.limit.max_concurrent:
                # H-9 Fix: Clamp negative usage values to 0
                used_concurrent = max(0, state.current_concurrent)
                limit_concurrent = max(1, quota_config.limit.max_concurrent)  # Prevent division by zero
                usage_percent = min((used_concurrent / limit_concurrent) * 100, 100)  # Clamp to 0-100%

                quota_details["max_concurrent"] = QuotaLimitStatus(
                    limit=quota_config.limit.max_concurrent,
                    used=used_concurrent,
                    usage_percent=round(usage_percent, 2)
                )

                # H-10 Fix: Use >= to mark exactly 100% as denied
                if usage_percent >= 100 and status != "denied":
                    status = "denied"
                elif usage_percent >= 80 and status == "ok":
                    status = "warning"

            # Max runtime
            if quota_config.limit.max_runtime_ms:
                # H-9 Fix: Clamp negative usage values to 0
                used_runtime = max(0, state.used_runtime_ms)
                limit_runtime = max(1, quota_config.limit.max_runtime_ms)  # Prevent division by zero
                usage_percent = min((used_runtime / limit_runtime) * 100, 100)  # Clamp to 0-100%

                quota_details["max_runtime_ms"] = QuotaLimitStatus(
                    limit=quota_config.limit.max_runtime_ms,
                    used=used_runtime,
                    usage_percent=round(usage_percent, 2)
                )

                # H-10 Fix: Use >= to mark exactly 100% as denied
                if usage_percent >= 100 and status != "denied":
                    status = "denied"
                elif usage_percent >= 80 and status == "ok":
                    status = "warning"

            # Try to get tool info
            tool = registry.get_tool(quota_config.target_id)
            tool_id = quota_config.target_id
            trust_tier = "unknown"

            if tool:
                trust_tier = tool.trust_tier.value

            quotas_list.append(QuotaStatus(
                capability_id=quota_id,
                tool_id=tool_id,
                trust_tier=trust_tier,
                quota=quota_details,
                status=status,
                last_triggered=iso_z(state.last_reset) if state.last_reset else None
            ))

        return QuotasResponse(quotas=quotas_list)

    except Exception as e:
        logger.error(f"Failed to get quotas: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get quota information",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/trust-tiers", response_model=TrustTiersResponse)
async def get_capability_trust_tiers():
    """
    Get trust tier configurations

    Returns information about each trust tier including:
    - Tier ID and name
    - Capabilities in this tier
    - Default policy settings

    This is a read-only endpoint with no side effects.
    Part of PR-1: Governance APIs (Backend Read-Only Interface)
    """
    try:
        registry = get_capability_registry()

        # Get all capabilities
        all_tools = registry.list_tools(enabled_only=False)

        # Group by trust tier
        tiers_data = {}
        for tool in all_tools:
            tier = tool.trust_tier.value
            if tier not in tiers_data:
                tiers_data[tier] = []
            tiers_data[tier].append(tool.tool_id)

        # Define trust tier policies
        tier_policies = {
            "T0": TrustTierPolicy(
                risk_level="LOW",
                requires_admin_token=False,
                default_quota_profile={
                    "calls_per_minute": 1000,
                    "max_concurrent": 10,
                    "max_runtime_ms": 300000
                }
            ),
            "T1": TrustTierPolicy(
                risk_level="MED",
                requires_admin_token=False,
                default_quota_profile={
                    "calls_per_minute": 500,
                    "max_concurrent": 5,
                    "max_runtime_ms": 180000
                }
            ),
            "T2": TrustTierPolicy(
                risk_level="MED",
                requires_admin_token=False,
                default_quota_profile={
                    "calls_per_minute": 200,
                    "max_concurrent": 3,
                    "max_runtime_ms": 120000
                }
            ),
            "T3": TrustTierPolicy(
                risk_level="HIGH",
                requires_admin_token=True,
                default_quota_profile={
                    "calls_per_minute": 100,
                    "max_concurrent": 2,
                    "max_runtime_ms": 60000
                }
            )
        }

        # Map tier values to names
        tier_names = {
            "local_extension": ("T0", "Local Extension"),
            "local_mcp": ("T1", "Local MCP"),
            "remote_mcp": ("T2", "Remote MCP"),
            "cloud_mcp": ("T3", "Cloud MCP")
        }

        tiers_list = []
        for tier_value, capability_ids in tiers_data.items():
            tier_id, tier_name = tier_names.get(tier_value, (tier_value, tier_value))
            policy = tier_policies.get(tier_id, tier_policies["T3"])  # Default to most restrictive

            tiers_list.append(TrustTierInfo(
                tier=tier_id,
                name=tier_name,
                capabilities=capability_ids,
                count=len(capability_ids),
                default_policy=policy
            ))

        # Sort by tier (T0, T1, T2, T3)
        tiers_list.sort(key=lambda t: t.tier)

        return TrustTiersResponse(tiers=tiers_list)

    except Exception as e:
        logger.error(f"Failed to get trust tiers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get trust tier information",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/provenance/{invocation_id}", response_model=ProvenanceResponse)
async def get_capability_provenance(invocation_id: str):
    """
    Get provenance information for a specific invocation

    Returns:
    - Provenance stamp (capability, source, execution env, trust tier)
    - Audit event chain

    This is a read-only endpoint with no side effects.
    Part of PR-1: Governance APIs (Backend Read-Only Interface)

    Args:
        invocation_id: Invocation ID to query
    """
    try:
        # Query audit logs for provenance information
        from agentos.core.storage.paths import component_db_path
        import sqlite3
        import json
        from datetime import datetime

        db_path = component_db_path("agentos")
        if not db_path.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"No audit data found for invocation: {invocation_id}",
                    "hint": "Audit database not initialized or invocation not found",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        # Create new connection for this specific query (not using get_db())
        audit_conn = sqlite3.connect(str(db_path))
        try:
            cursor = audit_conn.cursor()

            # Query provenance snapshot
            cursor.execute("""
                SELECT payload
                FROM task_audits
                WHERE event_type = 'provenance_snapshot'
                AND payload LIKE ?
                LIMIT 1
            """, (f'%"invocation_id": "{invocation_id}"%',))

            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "ok": False,
                        "data": None,
                        "error": f"Provenance not found for invocation: {invocation_id}",
                        "hint": "Check the invocation ID and ensure the invocation has completed",
                        "reason_code": ReasonCode.NOT_FOUND
                    }
                )

            payload = json.loads(row[0])

            # Build provenance info
            provenance = ProvenanceInfo(
                capability_id=payload.get('capability_id', 'unknown'),
                tool_id=payload.get('tool_id', 'unknown'),
                capability_type=payload.get('capability_type', 'unknown'),
                source_id=payload.get('source_id', 'unknown'),
                execution_env=ExecutionEnvInfo(
                    hostname=payload.get('execution_env', {}).get('host', 'unknown'),
                    pid=payload.get('execution_env', {}).get('pid', 0),
                    container_id=payload.get('execution_env', {}).get('container_id')
                ),
                trust_tier=payload.get('trust_tier', 'unknown'),
                timestamp=payload.get('timestamp', iso_z(datetime.now())),
                invocation_id=invocation_id
            )

            # Query audit chain
            cursor.execute("""
                SELECT created_at, event_type, payload
                FROM task_audits
                WHERE payload LIKE ?
                ORDER BY created_at ASC
            """, (f'%"invocation_id": "{invocation_id}"%',))

            rows = cursor.fetchall()
            audit_chain = []

            for row in rows:
                timestamp, event_type, payload_json = row
                event_payload = json.loads(payload_json) if payload_json else {}

                audit_chain.append(AuditEvent(
                    event_type=event_type,
                    timestamp=timestamp,
                    gate=event_payload.get('gate'),
                    result=event_payload.get('result', 'success' if event_type.endswith('_end') else 'pending')
                ))

            return ProvenanceResponse(
                provenance=provenance,
                audit_chain=audit_chain
            )
        finally:
            audit_conn.close()  # Close explicitly created connection

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provenance: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get provenance information",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )
