"""
Capability Governance API - AgentOS v3 Task #29

Provides REST API endpoints for Capability Governance UI to display:
- Dashboard statistics (5 domains, invocations, risk distribution)
- Decision timeline (all decision plans with freeze status)
- Action execution log (all actions with side effects and rollbacks)
- Evidence chain visualization (graph data for cytoscape.js)
- Governance audit (permission checks, risk scores, policy evaluations)
- Agent capability matrix (agent x capability grants)

Endpoints:
- GET /api/capability/dashboard/stats - Dashboard statistics
- GET /api/capability/decisions/timeline - Decision timeline
- GET /api/capability/actions/log - Action execution log
- GET /api/capability/evidence/chain/<chain_id> - Evidence chain graph
- GET /api/capability/governance/audit - Governance audit log
- GET /api/capability/agents/matrix - Agent capability matrix
- POST /api/capability/grants - Grant capability to agent
- DELETE /api/capability/grants/<agent_id>/<capability_id> - Revoke grant
"""

import logging
import json
import sqlite3
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class CapabilityGrantRequest(BaseModel):
    """Request to grant a capability to an agent"""
    agent_id: str = Field(..., description="Agent ID (e.g., 'chat_agent', 'user:alice')")
    capability_id: str = Field(..., description="Capability ID (e.g., 'state.memory.read')")
    granted_by: str = Field(..., description="Who is granting (user_id or 'system')")
    reason: str = Field(..., description="Reason for granting")
    scope: Optional[str] = Field(None, description="Optional scope (e.g., 'project:proj-123')")
    expires_at_ms: Optional[int] = Field(None, description="Optional expiration timestamp (epoch ms)")


# ============================================================================
# Helper Functions
# ============================================================================

def get_registry_db_path() -> Path:
    """
    Get AgentOS registry database path

    Returns path to the main registry database containing all capability tables.
    """
    db_path_str = os.environ.get('AGENTOS_DB_PATH')
    if db_path_str:
        return Path(db_path_str)

    # Default path
    from agentos.core.storage.paths import component_db_path
    return component_db_path("registry")


def get_db_connection() -> sqlite3.Connection:
    """
    Create database connection with proper configuration

    Returns:
        SQLite connection with row factory enabled
    """
    db_path = get_registry_db_path()

    if not db_path.exists():
        raise FileNotFoundError(
            f"Registry database not found at {db_path}. "
            "Please initialize AgentOS first."
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn


def format_timestamp(ts_ms: Optional[int]) -> Optional[str]:
    """
    Format epoch milliseconds to ISO 8601 string

    Args:
        ts_ms: Epoch milliseconds timestamp

    Returns:
        ISO 8601 formatted string or None
    """
    if ts_ms is None:
        return None
    return iso_z(datetime.fromtimestamp(ts_ms / 1000.0))


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/capability/dashboard/stats")
async def get_dashboard_stats():
    """
    Get dashboard statistics

    Returns:
        {
            "domains": {
                "state": {"count": 6, "active_agents": 12},
                "decision": {"count": 5, "active_agents": 8},
                ...
            },
            "today_stats": {
                "total_invocations": 1234,
                "allowed": 1180,
                "denied": 54
            },
            "risk_distribution": {
                "LOW": 70, "MEDIUM": 20, "HIGH": 8, "CRITICAL": 2
            }
        }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get domain statistics (capability count per domain)
        cursor.execute("""
            SELECT domain, COUNT(*) as count
            FROM capability_definitions
            GROUP BY domain
        """)
        domain_counts = {row['domain']: row['count'] for row in cursor.fetchall()}

        # Get active agents per domain
        cursor.execute("""
            SELECT cd.domain, COUNT(DISTINCT cg.agent_id) as active_agents
            FROM capability_grants cg
            JOIN capability_definitions cd ON cg.capability_id = cd.capability_id
            WHERE cg.expires_at_ms IS NULL OR cg.expires_at_ms > ?
            GROUP BY cd.domain
        """, (int(utc_now().timestamp() * 1000),))
        domain_agents = {row['domain']: row['active_agents'] for row in cursor.fetchall()}

        # Build domains dict
        domains = {}
        for domain in ['state', 'decision', 'action', 'governance', 'evidence']:
            domains[domain] = {
                "count": domain_counts.get(domain, 0),
                "active_agents": domain_agents.get(domain, 0)
            }

        # Get today's invocation stats
        today_start_ms = int((utc_now().replace(hour=0, minute=0, second=0, microsecond=0)).timestamp() * 1000)

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN allowed = 1 THEN 1 ELSE 0 END) as allowed,
                SUM(CASE WHEN allowed = 0 THEN 1 ELSE 0 END) as denied
            FROM capability_invocations
            WHERE timestamp_ms >= ?
        """, (today_start_ms,))

        today_row = cursor.fetchone()
        today_stats = {
            "total_invocations": today_row['total'] or 0,
            "allowed": today_row['allowed'] or 0,
            "denied": today_row['denied'] or 0
        }

        # Get risk distribution (simplified - based on capability level)
        # In real implementation, this would query risk_scores table
        cursor.execute("""
            SELECT
                CASE
                    WHEN level = 'read' THEN 'LOW'
                    WHEN level = 'propose' THEN 'MEDIUM'
                    WHEN level = 'write' THEN 'HIGH'
                    WHEN level = 'admin' THEN 'CRITICAL'
                    ELSE 'LOW'
                END as risk_level,
                COUNT(*) as count
            FROM capability_definitions
            GROUP BY risk_level
        """)

        risk_distribution = {row['risk_level']: row['count'] for row in cursor.fetchall()}

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "domains": domains,
                "today_stats": today_stats,
                "risk_distribution": risk_distribution
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/capability/decisions/timeline")
async def get_decisions_timeline(
    status: Optional[str] = Query(None, description="Filter by status (draft/frozen/archived)"),
    task_id: Optional[str] = Query(None, description="Filter by task_id"),
    limit: int = Query(50, description="Max records to return", ge=1, le=500),
    offset: int = Query(0, description="Offset for pagination", ge=0)
):
    """
    Get decision plans timeline

    Args:
        status: Filter by status (draft, frozen, archived, rolled_back)
        task_id: Filter by task ID
        limit: Maximum records to return (1-500)
        offset: Pagination offset

    Returns:
        List of decision plans with freeze status and related actions
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT
                plan_id,
                task_id,
                steps_json,
                alternatives_json,
                rationale,
                status,
                frozen_at_ms,
                plan_hash,
                created_by,
                created_at_ms,
                updated_at_ms,
                context_snapshot_id
            FROM decision_plans
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        query += " ORDER BY created_at_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)

        decisions = []
        for row in cursor.fetchall():
            # Get related actions for this plan
            cursor.execute("""
                SELECT COUNT(*) as action_count
                FROM action_execution_log
                WHERE decision_id = ?
            """, (row['plan_id'],))
            action_row = cursor.fetchone()

            decisions.append({
                "plan_id": row['plan_id'],
                "task_id": row['task_id'],
                "steps": json.loads(row['steps_json']) if row['steps_json'] else [],
                "alternatives": json.loads(row['alternatives_json']) if row['alternatives_json'] else [],
                "rationale": row['rationale'],
                "status": row['status'],
                "frozen_at": format_timestamp(row['frozen_at_ms']),
                "plan_hash": row['plan_hash'],
                "created_by": row['created_by'],
                "created_at": format_timestamp(row['created_at_ms']),
                "updated_at": format_timestamp(row['updated_at_ms']),
                "context_snapshot_id": row['context_snapshot_id'],
                "related_actions_count": action_row['action_count'] if action_row else 0
            })

        # Get total count for pagination
        count_query = "SELECT COUNT(*) as total FROM decision_plans WHERE 1=1"
        count_params = []

        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        if task_id:
            count_query += " AND task_id = ?"
            count_params.append(task_id)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "decisions": decisions,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total
                }
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get decisions timeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/capability/actions/log")
async def get_actions_log(
    status: Optional[str] = Query(None, description="Filter by status (success/failure/rolled_back)"),
    agent_id: Optional[str] = Query(None, description="Filter by agent_id"),
    decision_id: Optional[str] = Query(None, description="Filter by decision_id"),
    limit: int = Query(50, description="Max records to return", ge=1, le=500),
    offset: int = Query(0, description="Offset for pagination", ge=0)
):
    """
    Get action execution log

    Args:
        status: Filter by status (success, failure, rolled_back)
        agent_id: Filter by agent ID
        decision_id: Filter by decision ID
        limit: Maximum records to return (1-500)
        offset: Pagination offset

    Returns:
        List of action executions with side effects and rollback history
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT
                execution_id,
                action_type,
                agent_id,
                decision_id,
                input_params_json,
                output_json,
                status,
                error_message,
                execution_time_ms,
                executed_at_ms,
                rollback_id
            FROM action_execution_log
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        if decision_id:
            query += " AND decision_id = ?"
            params.append(decision_id)

        query += " ORDER BY executed_at_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)

        actions = []
        for row in cursor.fetchall():
            # Get side effects for this action
            cursor.execute("""
                SELECT side_effect_type, description, severity
                FROM action_side_effects
                WHERE execution_id = ?
            """, (row['execution_id'],))
            side_effects = [
                {
                    "type": se['side_effect_type'],
                    "description": se['description'],
                    "severity": se['severity']
                }
                for se in cursor.fetchall()
            ]

            # Get rollback history if rolled back
            rollback_info = None
            if row['rollback_id']:
                cursor.execute("""
                    SELECT
                        rollback_id,
                        rollback_action_type,
                        rollback_params_json,
                        rolled_back_by,
                        rolled_back_at_ms,
                        rollback_status,
                        rollback_error
                    FROM action_rollback_history
                    WHERE rollback_id = ?
                """, (row['rollback_id'],))
                rb = cursor.fetchone()
                if rb:
                    rollback_info = {
                        "rollback_id": rb['rollback_id'],
                        "action_type": rb['rollback_action_type'],
                        "rolled_back_by": rb['rolled_back_by'],
                        "rolled_back_at": format_timestamp(rb['rolled_back_at_ms']),
                        "status": rb['rollback_status'],
                        "error": rb['rollback_error']
                    }

            actions.append({
                "execution_id": row['execution_id'],
                "action_type": row['action_type'],
                "agent_id": row['agent_id'],
                "decision_id": row['decision_id'],
                "input_params": json.loads(row['input_params_json']) if row['input_params_json'] else {},
                "output": json.loads(row['output_json']) if row['output_json'] else {},
                "status": row['status'],
                "error_message": row['error_message'],
                "execution_time_ms": row['execution_time_ms'],
                "executed_at": format_timestamp(row['executed_at_ms']),
                "side_effects": side_effects,
                "rollback_info": rollback_info
            })

        # Get total count for pagination
        count_query = "SELECT COUNT(*) as total FROM action_execution_log WHERE 1=1"
        count_params = []

        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        if agent_id:
            count_query += " AND agent_id = ?"
            count_params.append(agent_id)

        if decision_id:
            count_query += " AND decision_id = ?"
            count_params.append(decision_id)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "actions": actions,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total
                }
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get actions log: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/capability/evidence/chain/{chain_id}")
async def get_evidence_chain(chain_id: str):
    """
    Get evidence chain as graph data for visualization

    Args:
        chain_id: Evidence chain ID

    Returns:
        Graph data with nodes and edges for Cytoscape.js
        {
            "nodes": [
                {"data": {"id": "dec-123", "type": "decision", "label": "Plan: Fix Bug"}},
                {"data": {"id": "act-456", "type": "action", "label": "Execute: pytest"}}
            ],
            "edges": [
                {"data": {"source": "dec-123", "target": "act-456", "label": "caused_by"}}
            ]
        }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get chain metadata
        cursor.execute("""
            SELECT chain_id, chain_type, root_entity_id, root_entity_type, created_at_ms
            FROM evidence_chains
            WHERE chain_id = ?
        """, (chain_id,))

        chain_row = cursor.fetchone()
        if not chain_row:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "data": None, "error": f"Evidence chain {chain_id} not found"}
            )

        # Get chain links
        cursor.execute("""
            SELECT
                link_id,
                from_entity_id,
                from_entity_type,
                to_entity_id,
                to_entity_type,
                relationship_type,
                evidence_refs_json,
                created_at_ms
            FROM evidence_chain_links
            WHERE chain_id = ?
        """, (chain_id,))

        links = cursor.fetchall()

        # Build nodes and edges
        nodes_dict = {}
        edges = []

        # Add root node
        root_id = chain_row['root_entity_id']
        root_type = chain_row['root_entity_type']
        nodes_dict[root_id] = {
            "data": {
                "id": root_id,
                "type": root_type,
                "label": f"{root_type.title()}: {root_id[:8]}...",
                "root": True
            }
        }

        # Process links
        for link in links:
            from_id = link['from_entity_id']
            from_type = link['from_entity_type']
            to_id = link['to_entity_id']
            to_type = link['to_entity_type']
            rel_type = link['relationship_type']

            # Add nodes
            if from_id not in nodes_dict:
                nodes_dict[from_id] = {
                    "data": {
                        "id": from_id,
                        "type": from_type,
                        "label": f"{from_type.title()}: {from_id[:8]}..."
                    }
                }

            if to_id not in nodes_dict:
                nodes_dict[to_id] = {
                    "data": {
                        "id": to_id,
                        "type": to_type,
                        "label": f"{to_type.title()}: {to_id[:8]}..."
                    }
                }

            # Add edge
            edges.append({
                "data": {
                    "id": link['link_id'],
                    "source": from_id,
                    "target": to_id,
                    "label": rel_type
                }
            })

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "chain_id": chain_id,
                "chain_type": chain_row['chain_type'],
                "nodes": list(nodes_dict.values()),
                "edges": edges,
                "created_at": format_timestamp(chain_row['created_at_ms'])
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get evidence chain: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/capability/governance/audit")
async def get_governance_audit(
    agent_id: Optional[str] = Query(None, description="Filter by agent_id"),
    capability_id: Optional[str] = Query(None, description="Filter by capability_id"),
    allowed: Optional[bool] = Query(None, description="Filter by allowed (true/false)"),
    limit: int = Query(100, description="Max records to return", ge=1, le=1000),
    offset: int = Query(0, description="Offset for pagination", ge=0)
):
    """
    Get governance audit log (capability invocations)

    Args:
        agent_id: Filter by agent ID
        capability_id: Filter by capability ID
        allowed: Filter by allowed (true) or denied (false)
        limit: Maximum records to return (1-1000)
        offset: Pagination offset

    Returns:
        List of capability invocations with permission check results
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT
                invocation_id,
                agent_id,
                capability_id,
                operation,
                allowed,
                reason,
                context_json,
                timestamp_ms
            FROM capability_invocations
            WHERE 1=1
        """
        params = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        if capability_id:
            query += " AND capability_id = ?"
            params.append(capability_id)

        if allowed is not None:
            query += " AND allowed = ?"
            params.append(1 if allowed else 0)

        query += " ORDER BY timestamp_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)

        invocations = []
        for row in cursor.fetchall():
            invocations.append({
                "invocation_id": row['invocation_id'],
                "agent_id": row['agent_id'],
                "capability_id": row['capability_id'],
                "operation": row['operation'],
                "allowed": bool(row['allowed']),
                "reason": row['reason'],
                "context": json.loads(row['context_json']) if row['context_json'] else {},
                "timestamp": format_timestamp(row['timestamp_ms'])
            })

        # Get statistics
        stats_query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN allowed = 1 THEN 1 ELSE 0 END) as allowed_count,
                SUM(CASE WHEN allowed = 0 THEN 1 ELSE 0 END) as denied_count
            FROM capability_invocations
            WHERE 1=1
        """
        stats_params = []

        if agent_id:
            stats_query += " AND agent_id = ?"
            stats_params.append(agent_id)

        if capability_id:
            stats_query += " AND capability_id = ?"
            stats_params.append(capability_id)

        cursor.execute(stats_query, stats_params)
        stats_row = cursor.fetchone()

        stats = {
            "total": stats_row['total'],
            "allowed": stats_row['allowed_count'],
            "denied": stats_row['denied_count'],
            "success_rate": round(100.0 * stats_row['allowed_count'] / stats_row['total'], 2) if stats_row['total'] > 0 else 0
        }

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "invocations": invocations,
                "stats": stats,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < stats['total']
                }
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get governance audit: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/capability/agents/matrix")
async def get_agents_matrix():
    """
    Get agent capability matrix (agent x capability grants)

    Returns:
        {
            "agents": ["chat_agent", "user:alice", ...],
            "capabilities": ["state.memory.read", "decision.plan.create", ...],
            "matrix": {
                "chat_agent": {
                    "state.memory.read": {"status": "allowed", "granted_at": "...", "grant_id": "..."},
                    "decision.plan.create": {"status": "denied", "reason": "Not granted"}
                },
                ...
            }
        }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all capability definitions
        cursor.execute("""
            SELECT capability_id, domain, level
            FROM capability_definitions
            ORDER BY domain, capability_id
        """)
        capabilities = [row['capability_id'] for row in cursor.fetchall()]

        # Get all agents with active grants
        now_ms = int(utc_now().timestamp() * 1000)
        cursor.execute("""
            SELECT DISTINCT agent_id
            FROM capability_grants
            WHERE expires_at_ms IS NULL OR expires_at_ms > ?
            ORDER BY agent_id
        """, (now_ms,))
        agents = [row['agent_id'] for row in cursor.fetchall()]

        # Get all active grants
        cursor.execute("""
            SELECT
                grant_id,
                agent_id,
                capability_id,
                granted_by,
                granted_at_ms,
                expires_at_ms,
                scope,
                reason
            FROM capability_grants
            WHERE expires_at_ms IS NULL OR expires_at_ms > ?
            ORDER BY agent_id, capability_id
        """, (now_ms,))

        # Build matrix
        matrix = {}
        for agent in agents:
            matrix[agent] = {}
            for capability in capabilities:
                matrix[agent][capability] = {
                    "status": "denied",
                    "reason": "Not granted"
                }

        # Fill in granted capabilities
        for row in cursor.fetchall():
            agent = row['agent_id']
            cap = row['capability_id']

            if agent not in matrix:
                matrix[agent] = {}

            matrix[agent][cap] = {
                "status": "allowed",
                "grant_id": row['grant_id'],
                "granted_by": row['granted_by'],
                "granted_at": format_timestamp(row['granted_at_ms']),
                "expires_at": format_timestamp(row['expires_at_ms']),
                "scope": row['scope'],
                "reason": row['reason']
            }

        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "agents": agents,
                "capabilities": capabilities,
                "matrix": matrix
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get agents matrix: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.post("/api/capability/grants")
async def grant_capability(request: CapabilityGrantRequest):
    """
    Grant a capability to an agent

    Args:
        request: Grant request with agent_id, capability_id, granted_by, reason

    Returns:
        Created grant record
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify capability exists
        cursor.execute("""
            SELECT capability_id FROM capability_definitions
            WHERE capability_id = ?
        """, (request.capability_id,))

        if not cursor.fetchone():
            return JSONResponse(
                status_code=404,
                content={"ok": False, "data": None, "error": f"Capability {request.capability_id} not found"}
            )

        # Check if grant already exists
        now_ms = int(utc_now().timestamp() * 1000)
        cursor.execute("""
            SELECT grant_id FROM capability_grants
            WHERE agent_id = ? AND capability_id = ?
              AND (expires_at_ms IS NULL OR expires_at_ms > ?)
        """, (request.agent_id, request.capability_id, now_ms))

        existing_grant = cursor.fetchone()
        if existing_grant:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": "Grant already exists for this agent/capability"}
            )

        # Create grant
        from ulid import ULID
        grant_id = str(ULID())

        cursor.execute("""
            INSERT INTO capability_grants (
                grant_id, agent_id, capability_id, granted_by, granted_at_ms,
                expires_at_ms, scope, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            grant_id,
            request.agent_id,
            request.capability_id,
            request.granted_by,
            now_ms,
            request.expires_at_ms,
            request.scope,
            request.reason
        ))

        # Record in audit log
        cursor.execute("""
            INSERT INTO capability_grant_audit (
                grant_id, agent_id, capability_id, action, changed_by, changed_at_ms, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            grant_id,
            request.agent_id,
            request.capability_id,
            'grant',
            request.granted_by,
            now_ms,
            request.reason
        ))

        conn.commit()
        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "grant_id": grant_id,
                "agent_id": request.agent_id,
                "capability_id": request.capability_id,
                "granted_by": request.granted_by,
                "granted_at": format_timestamp(now_ms),
                "expires_at": format_timestamp(request.expires_at_ms),
                "scope": request.scope,
                "reason": request.reason
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to grant capability: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.delete("/api/capability/grants/{agent_id}/{capability_id}")
async def revoke_capability(agent_id: str, capability_id: str, revoked_by: str = Query(...)):
    """
    Revoke a capability grant from an agent

    Args:
        agent_id: Agent ID
        capability_id: Capability ID
        revoked_by: Who is revoking (user_id or 'system')

    Returns:
        Success status
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find active grant
        now_ms = int(utc_now().timestamp() * 1000)
        cursor.execute("""
            SELECT grant_id FROM capability_grants
            WHERE agent_id = ? AND capability_id = ?
              AND (expires_at_ms IS NULL OR expires_at_ms > ?)
        """, (agent_id, capability_id, now_ms))

        grant_row = cursor.fetchone()
        if not grant_row:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "data": None, "error": "Active grant not found"}
            )

        grant_id = grant_row['grant_id']

        # Soft delete: set expiration to now
        cursor.execute("""
            UPDATE capability_grants
            SET expires_at_ms = ?
            WHERE grant_id = ?
        """, (now_ms, grant_id))

        # Record in audit log
        cursor.execute("""
            INSERT INTO capability_grant_audit (
                grant_id, agent_id, capability_id, action, changed_by, changed_at_ms, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            grant_id,
            agent_id,
            capability_id,
            'revoke',
            revoked_by,
            now_ms,
            'Manually revoked via API'
        ))

        conn.commit()
        conn.close()

        return JSONResponse(content={
            "ok": True,
            "data": {
                "grant_id": grant_id,
                "agent_id": agent_id,
                "capability_id": capability_id,
                "revoked_by": revoked_by,
                "revoked_at": format_timestamp(now_ms)
            },
            "error": None
        })

    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "data": None, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to revoke capability: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )
