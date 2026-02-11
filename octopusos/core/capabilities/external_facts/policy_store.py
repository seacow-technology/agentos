"""SQLite-backed policy store for ExternalFactsCapability."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from octopusos.core.storage.paths import component_db_path

from .source_catalog import merge_with_catalog
from .types import FactKind, SUPPORTED_FACT_KINDS, SourcePolicy, utc_now_iso


class ExternalFactsPolicyStore:
    """Persist per-mode/per-kind source policy for external facts."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = Path(db_path) if db_path else component_db_path("octopusos")
        self.db_path = str(path)
        self._ensure_schema()
        self._ensure_defaults()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_facts_policy (
                    policy_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_external_facts_policy_mode_kind "
                "ON external_facts_policy(mode, kind)"
            )

    def _ensure_defaults(self) -> None:
        for mode in ("chat", "discussion"):
            for kind in SUPPORTED_FACT_KINDS:
                self.upsert(mode=mode, kind=kind, policy=self.default_policy(kind), only_if_missing=True)

    @staticmethod
    def _capability_id_for_kind(kind: FactKind) -> str:
        return "exchange_rate" if str(kind) == "fx" else str(kind)

    @staticmethod
    def default_policy(kind: FactKind) -> SourcePolicy:
        default_sources = merge_with_catalog(kind, [])
        base = SourcePolicy(
            prefer_structured=True,
            allow_search_fallback=True,
            max_sources=3,
            require_freshness_seconds=3600,
            source_whitelist=default_sources,
            source_blacklist=["reddit.com"],
            min_confidence="low",
        )
        if ExternalFactsPolicyStore._capability_id_for_kind(kind) == "exchange_rate":
            base.require_freshness_seconds = 1800
        return base

    def get(self, mode: str, kind: FactKind) -> SourcePolicy:
        mode = (mode or "chat").strip().lower()
        kind = kind.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT config_json
                FROM external_facts_policy
                WHERE mode = ? AND kind = ?
                LIMIT 1
                """,
                (mode, kind),
            ).fetchone()
        if not row:
            return self.default_policy(kind)  # type: ignore[arg-type]
        try:
            config = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError:
            return self.default_policy(kind)  # type: ignore[arg-type]
        policy = self._dict_to_policy(config, self.default_policy(kind))  # type: ignore[arg-type]
        policy.source_whitelist = merge_with_catalog(kind, policy.source_whitelist)  # type: ignore[arg-type]
        policy.max_sources = max(3, int(policy.max_sources or 3))
        return policy

    def list(self) -> List[Dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT policy_key, mode, kind, config_json, updated_at
                FROM external_facts_policy
                ORDER BY mode ASC, kind ASC
                """
            ).fetchall()
        result: List[Dict[str, object]] = []
        for row in rows:
            try:
                config = json.loads(row["config_json"] or "{}")
            except json.JSONDecodeError:
                config = {}
            result.append(
                {
                    "policy_key": row["policy_key"],
                    "mode": row["mode"],
                    "kind": row["kind"],
                    "config": config,
                    "updated_at": row["updated_at"],
                }
            )
        return result

    def upsert(
        self,
        mode: str,
        kind: FactKind,
        policy: SourcePolicy,
        only_if_missing: bool = False,
    ) -> None:
        mode = (mode or "chat").strip().lower()
        kind = kind.strip().lower()
        policy_key = f"{mode}:{kind}"
        payload = json.dumps(asdict(policy), ensure_ascii=False, sort_keys=True)
        now = utc_now_iso()
        with self._connect() as conn:
            if only_if_missing:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO external_facts_policy (
                        policy_key, mode, kind, config_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (policy_key, mode, kind, payload, now),
                )
                return
            conn.execute(
                """
                INSERT INTO external_facts_policy (
                    policy_key, mode, kind, config_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(policy_key) DO UPDATE SET
                    config_json=excluded.config_json,
                    updated_at=excluded.updated_at
                """,
                (policy_key, mode, kind, payload, now),
            )

    @staticmethod
    def _dict_to_policy(data: Dict[str, object], defaults: SourcePolicy) -> SourcePolicy:
        policy = SourcePolicy(**asdict(defaults))
        if "prefer_structured" in data:
            policy.prefer_structured = bool(data["prefer_structured"])
        if "allow_search_fallback" in data:
            policy.allow_search_fallback = bool(data["allow_search_fallback"])
        if "max_sources" in data:
            try:
                policy.max_sources = max(1, int(data["max_sources"]))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                pass
        if "require_freshness_seconds" in data:
            raw = data["require_freshness_seconds"]
            if raw in (None, "", "null"):
                policy.require_freshness_seconds = None
            else:
                try:
                    policy.require_freshness_seconds = max(0, int(raw))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pass
        if "source_whitelist" in data and isinstance(data["source_whitelist"], list):
            policy.source_whitelist = [str(v).strip() for v in data["source_whitelist"] if str(v).strip()]
        if "source_blacklist" in data and isinstance(data["source_blacklist"], list):
            policy.source_blacklist = [str(v).strip() for v in data["source_blacklist"] if str(v).strip()]
        if "min_confidence" in data:
            value = str(data["min_confidence"]).lower()
            if value in {"high", "medium", "low"}:
                policy.min_confidence = value  # type: ignore[assignment]
        return policy
