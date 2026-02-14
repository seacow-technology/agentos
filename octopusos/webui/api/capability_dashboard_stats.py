"""Capability dashboard stats aggregation for WebUI.

This is an MVP-grade aggregator that:
- Produces a stable, non-empty shape for the WebUI Capabilities dashboard.
- Prefers real local data sources when available.
- Degrades gracefully to zeros (but never returns stats={}).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from octopusos.core.capability.models import CapabilityDomain
from octopusos.core.capability.registry import get_capability_registry
from octopusos.webui.api.compat_state import ensure_schema


def _now_local() -> datetime:
    # Local time zone is "whatever the server is running in".
    # This matches user expectations for a dashboard "today" window.
    return datetime.now().astimezone()


def _today_window_utc(now_local: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now_local or _now_local()
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _safe_fromiso(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        # Stored timestamps are expected to be UTC in compat state; assume UTC if missing.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def default_capability_dashboard_stats() -> Dict[str, Any]:
    return {
        "domains": {
            "state": {"count": 0, "active_agents": 0},
            "decision": {"count": 0, "active_agents": 0},
            "action": {"count": 0, "active_agents": 0},
            "governance": {"count": 0, "active_agents": 0},
            "evidence": {"count": 0, "active_agents": 0},
        },
        "today_stats": {"total_invocations": 0, "allowed": 0, "denied": 0},
        "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
    }


def build_capability_dashboard_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Build the dashboard `stats` payload.

    The function must never raise: it is intended for UI health and should
    degrade to zeros while keeping the response shape stable.
    """
    stats = default_capability_dashboard_stats()

    try:
        ensure_schema(conn)
    except Exception:
        # DB exists but compat tables may not; keep zeros.
        return stats

    # 1) Domain stats: prefer v3 capability registry (27 atomic capabilities across 5 domains).
    try:
        registry = get_capability_registry()
        # Ensure defaults are present so a fresh DB still shows meaningful counts.
        try:
            caps = registry.list_all_capabilities()
        except Exception:
            caps = []
        if not caps:
            try:
                registry.load_definitions()
            except Exception:
                pass

        domain_counts: Dict[str, int] = {}
        for d in (
            CapabilityDomain.STATE,
            CapabilityDomain.DECISION,
            CapabilityDomain.ACTION,
            CapabilityDomain.GOVERNANCE,
            CapabilityDomain.EVIDENCE,
        ):
            try:
                domain_counts[d.value] = len(registry.list_by_domain(d))
            except Exception:
                domain_counts[d.value] = 0

        # Active agents per domain: distinct agents with non-expired grants.
        domain_active_agents: Dict[str, int] = {k: 0 for k in domain_counts.keys()}
        try:
            reg_conn = registry._get_connection()  # pylint: disable=protected-access
            try:
                rows = reg_conn.execute(
                    """
                    SELECT d.domain as domain, COUNT(DISTINCT g.agent_id) as agents
                    FROM capability_grants g
                    JOIN capability_definitions d ON d.capability_id = g.capability_id
                    WHERE g.expires_at_ms IS NULL OR g.expires_at_ms > ?
                    GROUP BY d.domain
                    """,
                    (int(time.time() * 1000),),
                ).fetchall()
                for r in rows:
                    dom = str(r["domain"] or "")
                    if dom in domain_active_agents:
                        domain_active_agents[dom] = int(r["agents"] or 0)
            finally:
                reg_conn.close()
        except Exception:
            # Missing tables or schema; keep zeros.
            pass

        for dom, count in domain_counts.items():
            if dom in stats["domains"]:
                stats["domains"][dom]["count"] = int(count)
                stats["domains"][dom]["active_agents"] = int(domain_active_agents.get(dom, 0))
    except Exception:
        # Keep zeros for domains.
        pass

    # 2) "Today" invocation stats: use compat audit events (fastest real source for WebUI).
    start_utc, end_utc = _today_window_utc()
    try:
        rows = conn.execute(
            """
            SELECT result_json, created_at
            FROM compat_audit_events
            WHERE created_at >= ? AND created_at < ?
            ORDER BY event_id DESC
            LIMIT 5000
            """,
            (start_utc.isoformat(), end_utc.isoformat()),
        ).fetchall()
    except Exception:
        rows = []

    allowed_count = 0
    denied_count = 0

    # 3) Risk distribution: prefer explicit risk fields in audit result when present;
    # otherwise derive a minimal distribution (allowed -> LOW, denied -> HIGH).
    risk = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    saw_explicit_risk = False

    for r in rows:
        result: Dict[str, Any] = {}
        raw = r["result_json"]
        if raw:
            try:
                result = json.loads(raw)
            except Exception:
                result = {}
        is_allowed = bool(result.get("allowed", True))
        if is_allowed:
            allowed_count += 1
        else:
            denied_count += 1

        raw_risk = (
            result.get("risk")
            or result.get("risk_level")
            or result.get("risk_tier")
            or result.get("riskLevel")
            or result.get("riskTier")
        )
        if isinstance(raw_risk, str):
            key = raw_risk.strip().upper()
            if key in risk:
                risk[key] += 1
                saw_explicit_risk = True
                continue

        # Derived minimal mapping (MVP): don't pretend it's precise.
        if is_allowed:
            risk["LOW"] += 1
        else:
            risk["HIGH"] += 1

    total = allowed_count + denied_count
    stats["today_stats"] = {"total_invocations": int(total), "allowed": int(allowed_count), "denied": int(denied_count)}
    stats["risk_distribution"] = {k: int(v) for k, v in risk.items()}
    stats["risk_distribution_source"] = "audit" if saw_explicit_risk else "derived_from_allowed"

    return stats

