"""LLM usage events recorder.

Goal: every LLM invocation (cloud + local) should be recorded in `llm_usage_events`
so we can query tokens/cost and correlate to chat/task context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from octopusos.core.time.clock import utc_now_ms
from octopusos.store import get_db

from .pricing import PricingCatalog, compute_cost_usd

logger = logging.getLogger(__name__)


def _ulid() -> str:
    from ulid import ULID
    return str(ULID())


@dataclass(frozen=True)
class LLMUsageEvent:
    provider: str
    operation: str
    model: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    message_id: Optional[str] = None
    context_snapshot_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    confidence: str = "HIGH"  # HIGH|LOW|ESTIMATED
    pricing_source: Optional[str] = None
    usage_raw: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


def ensure_context_snapshot_provider_model(
    *,
    snapshot_id: str,
    provider: Optional[str],
    model: Optional[str],
) -> None:
    """Best-effort backfill of context_snapshots.provider/model."""
    if not snapshot_id:
        return
    p = (provider or "").strip()
    m = (model or "").strip()
    if not p and not m:
        return
    try:
        conn = get_db()
        conn.execute(
            "UPDATE context_snapshots SET provider = COALESCE(provider, ?), model = COALESCE(model, ?) WHERE snapshot_id = ?",
            (p or None, m or None, snapshot_id),
        )
        conn.commit()
    except Exception as e:
        logger.debug("Failed to backfill context snapshot provider/model: %s", e)


def record_llm_usage_event(event: LLMUsageEvent) -> str:
    """Insert an event row. Raises on failure."""
    event_id = _ulid()
    created_at_ms = utc_now_ms()

    provider = (event.provider or "").strip().lower()
    operation = (event.operation or "").strip()
    if not provider:
        provider = "unknown"
    if not operation:
        operation = "unknown"

    model = (event.model or "").strip() or None

    # Optional computed cost (if not provided)
    cost_usd = event.cost_usd
    pricing_source = event.pricing_source
    if cost_usd is None and provider and model:
        catalog = PricingCatalog.from_sources()
        computed, source = compute_cost_usd(
            catalog=catalog,
            provider=provider,
            model=model,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
        )
        if computed is not None:
            cost_usd = computed
            pricing_source = pricing_source or source

    usage_raw_json = json.dumps(event.usage_raw, ensure_ascii=False) if event.usage_raw else None
    metadata_json = json.dumps(event.metadata, ensure_ascii=False) if event.metadata else None

    conn = get_db()
    conn.execute(
        """
        INSERT INTO llm_usage_events (
            event_id, created_at_ms,
            provider, model, operation,
            session_id, task_id, message_id, context_snapshot_id,
            trace_id, span_id, parent_span_id,
            prompt_tokens, completion_tokens, total_tokens,
            cost_usd, cost_currency,
            confidence, pricing_source,
            usage_raw_json, metadata_json
        ) VALUES (
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, 'USD',
            ?, ?,
            ?, ?
        )
        """,
        (
            event_id,
            created_at_ms,
            provider,
            model,
            operation,
            event.session_id,
            event.task_id,
            event.message_id,
            event.context_snapshot_id,
            event.trace_id,
            event.span_id,
            event.parent_span_id,
            event.prompt_tokens,
            event.completion_tokens,
            event.total_tokens,
            cost_usd,
            (event.confidence or "HIGH"),
            pricing_source,
            usage_raw_json,
            metadata_json,
        ),
    )
    conn.commit()
    return event_id


def record_llm_usage_event_best_effort(event: LLMUsageEvent) -> Optional[str]:
    try:
        return record_llm_usage_event(event)
    except Exception as e:
        logger.debug("Failed to record llm usage event (best-effort): %s", e)
        return None
