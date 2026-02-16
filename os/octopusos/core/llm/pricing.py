"""LLM pricing catalog used for cost estimation.

This module intentionally does not hardcode vendor prices, because they are
subject to change. Instead, it loads an optional JSON mapping from env/config.

Env:
  OCTOPUSOS_LLM_PRICING_JSON:
    {
      "openai": {
        "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60, "source": "manual-2026-02-15"}
      },
      "anthropic": {
        "claude-3-5-sonnet-20241022": {"input_per_1m": 3.0, "output_per_1m": 15.0, "source": "manual"}
      }
    }
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass(frozen=True)
class Pricing:
    input_per_1m: float
    output_per_1m: float
    source: str = "unknown"


class PricingCatalog:
    def __init__(self, mapping: Optional[Dict[str, Any]] = None):
        self._mapping = mapping or {}

    @classmethod
    def from_env(cls) -> "PricingCatalog":
        raw = (os.getenv("OCTOPUSOS_LLM_PRICING_JSON") or "").strip()
        if not raw:
            return cls({})
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return cls(data)
        except Exception:
            pass
        return cls({})

    @classmethod
    def from_db(cls, *, ttl_ms: int = 5_000) -> "PricingCatalog":
        """Load pricing from DB (best-effort), with a small TTL cache."""
        # Module-level cache so frequent LLM calls don't hit SQLite every time.
        global _DB_CACHE  # type: ignore[name-defined]
        global _DB_CACHE_AT_MS  # type: ignore[name-defined]
        try:
            from octopusos.core.time.clock import utc_now_ms
            now_ms = utc_now_ms()
        except Exception:
            now_ms = 0

        try:
            if _DB_CACHE is not None and _DB_CACHE_AT_MS is not None and now_ms and (now_ms - _DB_CACHE_AT_MS) < ttl_ms:
                return cls(_DB_CACHE)
        except Exception:
            pass

        mapping: Dict[str, Any] = {}
        try:
            from octopusos.store import get_db
            conn = get_db()
            # Table may not exist if migrations not applied yet.
            rows = conn.execute(
                "SELECT provider, model, input_per_1m, output_per_1m, COALESCE(source, 'db') AS source "
                "FROM llm_model_pricing WHERE enabled = 1"
            ).fetchall()
            for row in rows:
                provider = str(row["provider"] or "").strip().lower()
                model = str(row["model"] or "").strip()
                if not provider or not model:
                    continue
                mapping.setdefault(provider, {})
                mapping[provider][model] = {
                    "input_per_1m": float(row["input_per_1m"]),
                    "output_per_1m": float(row["output_per_1m"]),
                    "source": str(row["source"] or "db"),
                }
        except Exception:
            mapping = {}

        try:
            _DB_CACHE = mapping
            _DB_CACHE_AT_MS = now_ms
        except Exception:
            pass
        return cls(mapping)

    @classmethod
    def from_sources(cls) -> "PricingCatalog":
        """Merge pricing sources (DB first, then env). DB overrides env."""
        db = cls.from_db()
        env = cls.from_env()
        merged: Dict[str, Any] = {}
        for provider, models in (env._mapping or {}).items():
            if isinstance(models, dict):
                merged[provider] = dict(models)
        for provider, models in (db._mapping or {}).items():
            if not isinstance(models, dict):
                continue
            if provider not in merged or not isinstance(merged.get(provider), dict):
                merged[provider] = {}
            merged[provider].update(models)
        return cls(merged)

    def get(self, provider: str, model: str) -> Optional[Pricing]:
        provider_key = (provider or "").strip().lower()
        model_key = (model or "").strip()
        if not provider_key or not model_key:
            return None
        node = self._mapping.get(provider_key, {})
        if not isinstance(node, dict):
            return None
        entry = node.get(model_key)
        if not isinstance(entry, dict):
            return None
        try:
            return Pricing(
                input_per_1m=float(entry.get("input_per_1m")),
                output_per_1m=float(entry.get("output_per_1m")),
                source=str(entry.get("source") or "unknown"),
            )
        except Exception:
            return None


def compute_cost_usd(
    *,
    catalog: PricingCatalog,
    provider: str,
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
) -> Tuple[Optional[float], Optional[str]]:
    """Return (cost_usd, pricing_source)."""
    if prompt_tokens is None and completion_tokens is None:
        return None, None
    pricing = catalog.get(provider, model)
    if not pricing:
        return None, None
    in_tok = int(prompt_tokens or 0)
    out_tok = int(completion_tokens or 0)
    cost = (in_tok / 1_000_000.0) * pricing.input_per_1m + (out_tok / 1_000_000.0) * pricing.output_per_1m
    return float(cost), pricing.source


_DB_CACHE: Optional[Dict[str, Any]] = None
_DB_CACHE_AT_MS: Optional[int] = None


def invalidate_pricing_db_cache() -> None:
    global _DB_CACHE, _DB_CACHE_AT_MS
    _DB_CACHE = None
    _DB_CACHE_AT_MS = None
