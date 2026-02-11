"""User-configured external fact providers (URL + API key + priority)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.core.storage.paths import component_db_path

from .endpoint_map_schema import validate_endpoint_map
from .types import FactKind, SUPPORTED_FACT_KINDS, utc_now_iso


class ExternalFactsProviderStore:
    """Persist user-defined provider entries by fact kind."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = Path(db_path) if db_path else component_db_path("octopusos")
        self.db_path = str(path)
        self._ensure_schema()

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
                CREATE TABLE IF NOT EXISTS external_facts_providers (
                    provider_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    endpoint_url TEXT NOT NULL,
                    api_key TEXT,
                    api_key_header TEXT NOT NULL DEFAULT 'Authorization',
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    supported_items_json TEXT NOT NULL DEFAULT '{}',
                    endpoint_map_json TEXT NOT NULL DEFAULT '{}',
                    endpoint_map_version INTEGER NOT NULL DEFAULT 1,
                    endpoint_map_schema_valid INTEGER NOT NULL DEFAULT 0,
                    active_mapping_versions_json TEXT NOT NULL DEFAULT '{}',
                    last_validation_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_facts_providers_kind_priority "
                "ON external_facts_providers(kind, enabled, priority, updated_at)"
            )
            # Lightweight additive migration for old tables.
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(external_facts_providers)").fetchall()
            }
            if "supported_items_json" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN supported_items_json TEXT NOT NULL DEFAULT '{}'")
            if "endpoint_map_json" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN endpoint_map_json TEXT NOT NULL DEFAULT '{}'")
            if "endpoint_map_version" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN endpoint_map_version INTEGER NOT NULL DEFAULT 1")
            if "endpoint_map_schema_valid" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN endpoint_map_schema_valid INTEGER NOT NULL DEFAULT 0")
            if "active_mapping_versions_json" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN active_mapping_versions_json TEXT NOT NULL DEFAULT '{}'")
            if "last_validation_error" not in columns:
                conn.execute("ALTER TABLE external_facts_providers ADD COLUMN last_validation_error TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _validate_kind(kind: str) -> str:
        value = (kind or "").strip().lower()
        if value not in SUPPORTED_FACT_KINDS:
            raise ValueError(f"Unsupported kind: {kind}")
        return value

    def list(self, kind: Optional[str] = None, include_disabled: bool = True) -> List[Dict[str, Any]]:
        if kind:
            normalized_kind = self._validate_kind(kind)
            query = (
                "SELECT * FROM external_facts_providers "
                "WHERE kind = ?"
                + ("" if include_disabled else " AND enabled = 1")
                + " ORDER BY priority ASC, updated_at DESC"
            )
            params: tuple[Any, ...] = (normalized_kind,)
        else:
            query = (
                "SELECT * FROM external_facts_providers "
                "WHERE 1 = 1"
                + ("" if include_disabled else " AND enabled = 1")
                + " ORDER BY kind ASC, priority ASC, updated_at DESC"
            )
            params = ()

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_dict(row, mask_secret=True) for row in rows]

    def list_enabled_for_kind(self, kind: FactKind) -> List[Dict[str, Any]]:
        normalized_kind = self._validate_kind(kind)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM external_facts_providers
                WHERE kind = ? AND enabled = 1
                ORDER BY priority ASC, updated_at DESC
                """,
                (normalized_kind,),
            ).fetchall()
        return [self._row_to_dict(row, mask_secret=False) for row in rows]

    def get(self, provider_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM external_facts_providers WHERE provider_id = ? LIMIT 1",
                (provider_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row, mask_secret=True)

    def upsert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_id = str(payload.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError("provider_id is required")

        kind = self._validate_kind(str(payload.get("kind") or ""))
        name = str(payload.get("name") or "").strip() or provider_id
        endpoint_url = str(payload.get("endpoint_url") or "").strip()
        if not endpoint_url:
            raise ValueError("endpoint_url is required")

        api_key = str(payload.get("api_key") or "").strip() or None
        api_key_header = str(payload.get("api_key_header") or "Authorization").strip() or "Authorization"
        priority = int(payload.get("priority") or 100)
        enabled = 1 if bool(payload.get("enabled", True)) else 0
        config = payload.get("config") or {}
        if not isinstance(config, dict):
            raise ValueError("config must be an object")
        supported_items = payload.get("supported_items") or {}
        if not isinstance(supported_items, dict):
            raise ValueError("supported_items must be an object")
        endpoint_map = payload.get("endpoint_map") or {}
        if not isinstance(endpoint_map, dict):
            raise ValueError("endpoint_map must be an object")
        active_mapping_versions = payload.get("active_mapping_versions") or {}
        if not isinstance(active_mapping_versions, dict):
            raise ValueError("active_mapping_versions must be an object")
        endpoint_map_version = int(payload.get("endpoint_map_version") or 1)
        validation = validate_endpoint_map(
            endpoint_map=endpoint_map,
            supported_items={str(k): list(v) for k, v in supported_items.items() if isinstance(v, list)},
            version=endpoint_map_version,
        )
        endpoint_map_schema_valid = 1 if validation.ok else 0
        last_validation_error = "; ".join(validation.errors[:5]) if validation.errors else ""

        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT provider_id, api_key, created_at, supported_items_json, endpoint_map_json, endpoint_map_version, active_mapping_versions_json FROM external_facts_providers WHERE provider_id = ? LIMIT 1",
                (provider_id,),
            ).fetchone()
            if existing and api_key is None:
                api_key = str(existing["api_key"] or "").strip() or None
            if existing and not supported_items:
                try:
                    supported_items = json.loads(existing["supported_items_json"] or "{}")
                except json.JSONDecodeError:
                    supported_items = {}
            if existing and not endpoint_map:
                try:
                    endpoint_map = json.loads(existing["endpoint_map_json"] or "{}")
                except json.JSONDecodeError:
                    endpoint_map = {}
            if existing and not payload.get("endpoint_map_version"):
                endpoint_map_version = int(existing["endpoint_map_version"] or 1)
            if existing and not active_mapping_versions:
                try:
                    active_mapping_versions = json.loads(existing["active_mapping_versions_json"] or "{}")
                except json.JSONDecodeError:
                    active_mapping_versions = {}
            if existing and (not validation.ok and not payload.get("endpoint_map")):
                # Keep legacy rows writable even without full platform config.
                endpoint_map_schema_valid = 0
                last_validation_error = "endpoint_map_missing_or_invalid"
            created_at = str(existing["created_at"]) if existing else now

            conn.execute(
                """
                INSERT INTO external_facts_providers (
                    provider_id, kind, name, endpoint_url, api_key, api_key_header,
                    priority, enabled, config_json, supported_items_json, endpoint_map_json,
                    endpoint_map_version, endpoint_map_schema_valid, active_mapping_versions_json, last_validation_error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    kind = excluded.kind,
                    name = excluded.name,
                    endpoint_url = excluded.endpoint_url,
                    api_key = excluded.api_key,
                    api_key_header = excluded.api_key_header,
                    priority = excluded.priority,
                    enabled = excluded.enabled,
                    config_json = excluded.config_json,
                    supported_items_json = excluded.supported_items_json,
                    endpoint_map_json = excluded.endpoint_map_json,
                    endpoint_map_version = excluded.endpoint_map_version,
                    endpoint_map_schema_valid = excluded.endpoint_map_schema_valid,
                    active_mapping_versions_json = excluded.active_mapping_versions_json,
                    last_validation_error = excluded.last_validation_error,
                    updated_at = excluded.updated_at
                """,
                (
                    provider_id,
                    kind,
                    name,
                    endpoint_url,
                    api_key,
                    api_key_header,
                    priority,
                    enabled,
                    json.dumps(config, ensure_ascii=False, sort_keys=True),
                    json.dumps(supported_items, ensure_ascii=False, sort_keys=True),
                    json.dumps(endpoint_map, ensure_ascii=False, sort_keys=True),
                    endpoint_map_version,
                    endpoint_map_schema_valid,
                    json.dumps(active_mapping_versions, ensure_ascii=False, sort_keys=True),
                    last_validation_error,
                    created_at,
                    now,
                ),
            )

        item = self.get(provider_id)
        if not item:
            raise RuntimeError("Failed to persist provider")
        return item

    def delete(self, provider_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM external_facts_providers WHERE provider_id = ?", (provider_id,))
            return cur.rowcount > 0

    def set_active_mapping_version(self, provider_id: str, endpoint_key: str, version_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT active_mapping_versions_json FROM external_facts_providers WHERE provider_id = ? LIMIT 1",
                (provider_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"provider not found: {provider_id}")
            try:
                active_map = json.loads(row["active_mapping_versions_json"] or "{}")
            except json.JSONDecodeError:
                active_map = {}
            if not isinstance(active_map, dict):
                active_map = {}
            active_map[str(endpoint_key)] = str(version_id)
            conn.execute(
                """
                UPDATE external_facts_providers
                SET active_mapping_versions_json = ?, updated_at = ?
                WHERE provider_id = ?
                """,
                (json.dumps(active_map, ensure_ascii=False, sort_keys=True), utc_now_iso(), provider_id),
            )

    def _row_to_dict(self, row: sqlite3.Row, *, mask_secret: bool) -> Dict[str, Any]:
        try:
            config = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError:
            config = {}
        try:
            supported_items = json.loads(row["supported_items_json"] or "{}")
        except json.JSONDecodeError:
            supported_items = {}
        try:
            endpoint_map = json.loads(row["endpoint_map_json"] or "{}")
        except json.JSONDecodeError:
            endpoint_map = {}
        try:
            active_mapping_versions = json.loads(row["active_mapping_versions_json"] or "{}")
        except json.JSONDecodeError:
            active_mapping_versions = {}
        api_key = str(row["api_key"] or "")
        return {
            "provider_id": row["provider_id"],
            "kind": row["kind"],
            "name": row["name"],
            "endpoint_url": row["endpoint_url"],
            "api_key": "********" if (mask_secret and api_key) else api_key,
            "has_api_key": bool(api_key),
            "api_key_header": row["api_key_header"],
            "priority": int(row["priority"]),
            "enabled": bool(row["enabled"]),
            "config": config,
            "supported_items": supported_items,
            "endpoint_map": endpoint_map,
            "endpoint_map_version": int(row["endpoint_map_version"] or 1),
            "endpoint_map_schema_valid": bool(row["endpoint_map_schema_valid"]),
            "active_mapping_versions": active_mapping_versions if isinstance(active_mapping_versions, dict) else {},
            "last_validation_error": str(row["last_validation_error"] or ""),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
