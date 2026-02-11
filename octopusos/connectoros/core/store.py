from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.core.storage.paths import component_db_path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConnectorStore:
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
                CREATE TABLE IF NOT EXISTS connector_assets (
                    connector_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    auth_type TEXT NOT NULL DEFAULT 'api_key',
                    auth_header TEXT NOT NULL DEFAULT 'Authorization',
                    api_key TEXT,
                    default_headers_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 100,
                    deleted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_endpoints (
                    endpoint_id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    query_schema_json TEXT NOT NULL DEFAULT '{}',
                    response_schema_json TEXT NOT NULL DEFAULT '{}',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(connector_id, endpoint_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_endpoint_samples (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    sample_json TEXT NOT NULL,
                    sample_hash TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_endpoint_profile_proposals (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    llm_model TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    sample_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_endpoint_profile_versions (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    validation_report_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    last_failed_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_usage_cards (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    profile_version_id TEXT,
                    content_md TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_import_versions (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    summary_json TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_connector_endpoints_conn ON connector_endpoints(connector_id, enabled, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_connector_profiles_endpoint ON connector_endpoint_profile_versions(connector_id, endpoint_key, version DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_connector_import_versions ON connector_import_versions(connector_id, created_at DESC)"
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row, mask_secret: bool = True) -> Dict[str, Any]:
        d = dict(row)
        for key in ("default_headers_json", "query_schema_json", "response_schema_json", "tags_json", "sample_json", "proposal_json", "profile_json", "validation_report_json"):
            if key in d:
                try:
                    d[key.replace("_json", "")] = json.loads(d.get(key) or "{}")
                except json.JSONDecodeError:
                    d[key.replace("_json", "")] = {}
                del d[key]
        if "api_key" in d:
            raw = str(d.get("api_key") or "")
            d["has_api_key"] = bool(raw)
            d["api_key"] = "" if mask_secret else raw
        return d

    def list_connectors(self, include_disabled: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM connector_assets WHERE deleted = 0"
        if not include_disabled:
            sql += " AND enabled = 1"
        sql += " ORDER BY priority ASC, updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_dict(r, mask_secret=True) for r in rows]

    def get_connector(self, connector_id: str, *, mask_secret: bool = True) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM connector_assets WHERE connector_id = ? AND deleted = 0 LIMIT 1", (connector_id,)).fetchone()
        return self._row_to_dict(row, mask_secret=mask_secret) if row else None

    def upsert_connector(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        connector_id = str(payload.get("connector_id") or "").strip() or f"conn-{uuid.uuid4().hex[:12]}"
        name = str(payload.get("name") or connector_id).strip()
        base_url = str(payload.get("base_url") or "").strip()
        if not base_url:
            raise ValueError("base_url is required")
        auth_type = str(payload.get("auth_type") or "api_key").strip() or "api_key"
        auth_header = str(payload.get("auth_header") or "Authorization").strip() or "Authorization"
        api_key = payload.get("api_key")
        default_headers = payload.get("default_headers") or {}
        if not isinstance(default_headers, dict):
            raise ValueError("default_headers must be object")
        enabled = 1 if bool(payload.get("enabled", True)) else 0
        priority = int(payload.get("priority") or 100)
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at, api_key FROM connector_assets WHERE connector_id = ? LIMIT 1", (connector_id,)).fetchone()
            if existing and (api_key is None or str(api_key).strip() == ""):
                api_key = existing["api_key"]
            created_at = str(existing["created_at"]) if existing else now
            conn.execute(
                """
                INSERT INTO connector_assets (
                    connector_id, name, base_url, auth_type, auth_header, api_key,
                    default_headers_json, enabled, priority, deleted, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(connector_id) DO UPDATE SET
                    name = excluded.name,
                    base_url = excluded.base_url,
                    auth_type = excluded.auth_type,
                    auth_header = excluded.auth_header,
                    api_key = excluded.api_key,
                    default_headers_json = excluded.default_headers_json,
                    enabled = excluded.enabled,
                    priority = excluded.priority,
                    deleted = 0,
                    updated_at = excluded.updated_at
                """,
                (
                    connector_id,
                    name,
                    base_url,
                    auth_type,
                    auth_header,
                    str(api_key or "").strip() or None,
                    json.dumps(default_headers, ensure_ascii=False, sort_keys=True),
                    enabled,
                    priority,
                    created_at,
                    now,
                ),
            )
        result = self.get_connector(connector_id)
        if not result:
            raise RuntimeError("failed to save connector")
        return result

    def delete_connector(self, connector_id: str) -> bool:
        with self._connect() as conn:
            in_use = conn.execute("SELECT COUNT(1) AS c FROM connector_endpoints WHERE connector_id = ?", (connector_id,)).fetchone()
            if in_use and int(in_use["c"] or 0) > 0:
                raise ValueError("connector has endpoints")
            cur = conn.execute("UPDATE connector_assets SET deleted = 1, updated_at = ? WHERE connector_id = ?", (utc_now_iso(), connector_id))
            return cur.rowcount > 0

    def list_endpoints(self, connector_id: str, include_disabled: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM connector_endpoints WHERE connector_id = ?"
        params: List[Any] = [connector_id]
        if not include_disabled:
            sql += " AND enabled = 1"
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_dict(r, mask_secret=True) for r in rows]

    def get_endpoint(self, connector_id: str, endpoint_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_endpoints WHERE connector_id = ? AND endpoint_id = ? LIMIT 1",
                (connector_id, endpoint_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def upsert_endpoint(self, connector_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint_id = str(payload.get("endpoint_id") or "").strip() or f"ep-{uuid.uuid4().hex[:12]}"
        endpoint_key = str(payload.get("endpoint_key") or "").strip()
        if not endpoint_key:
            raise ValueError("endpoint_key is required")
        name = str(payload.get("name") or endpoint_key).strip()
        capability_id = str(payload.get("capability_id") or "").strip()
        item_id = str(payload.get("item_id") or "").strip()
        if not capability_id or not item_id:
            raise ValueError("capability_id and item_id are required")
        method = str(payload.get("method") or "GET").upper()
        path = str(payload.get("path") or "").strip()
        if not path:
            raise ValueError("path is required")
        query_schema = payload.get("query_schema") or {}
        response_schema = payload.get("response_schema") or {}
        tags = payload.get("tags") or []
        enabled = 1 if bool(payload.get("enabled", True)) else 0
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM connector_endpoints WHERE connector_id = ? AND endpoint_id = ? LIMIT 1",
                (connector_id, endpoint_id),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            conn.execute(
                """
                INSERT INTO connector_endpoints (
                    endpoint_id, connector_id, endpoint_key, name, capability_id, item_id,
                    method, path, query_schema_json, response_schema_json, tags_json, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(endpoint_id) DO UPDATE SET
                    endpoint_key = excluded.endpoint_key,
                    name = excluded.name,
                    capability_id = excluded.capability_id,
                    item_id = excluded.item_id,
                    method = excluded.method,
                    path = excluded.path,
                    query_schema_json = excluded.query_schema_json,
                    response_schema_json = excluded.response_schema_json,
                    tags_json = excluded.tags_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    endpoint_id,
                    connector_id,
                    endpoint_key,
                    name,
                    capability_id,
                    item_id,
                    method,
                    path,
                    json.dumps(query_schema, ensure_ascii=False, sort_keys=True),
                    json.dumps(response_schema, ensure_ascii=False, sort_keys=True),
                    json.dumps(tags, ensure_ascii=False),
                    enabled,
                    created_at,
                    now,
                ),
            )
        result = self.get_endpoint(connector_id, endpoint_id)
        if not result:
            raise RuntimeError("failed to save endpoint")
        return result

    def delete_endpoint(self, connector_id: str, endpoint_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM connector_endpoints WHERE connector_id = ? AND endpoint_id = ?",
                (connector_id, endpoint_id),
            )
            return cur.rowcount > 0

    def save_sample(
        self,
        *,
        connector_id: str,
        endpoint_id: str,
        endpoint_key: str,
        sample_json: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        sample_id = f"smp-{uuid.uuid4().hex}"
        now = utc_now_iso()
        sample_text = json.dumps(sample_json, ensure_ascii=False, sort_keys=True)
        import hashlib
        sample_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_endpoint_samples (
                    id, connector_id, endpoint_id, endpoint_key, sample_json, sample_hash, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sample_id, connector_id, endpoint_id, endpoint_key, sample_text, sample_hash, created_by, now),
            )
        return {
            "id": sample_id,
            "connector_id": connector_id,
            "endpoint_id": endpoint_id,
            "endpoint_key": endpoint_key,
            "sample_json": sample_json,
            "sample_hash": sample_hash,
            "created_by": created_by,
            "created_at": now,
        }

    def save_proposal(
        self,
        *,
        connector_id: str,
        endpoint_id: str,
        endpoint_key: str,
        proposal_json: Dict[str, Any],
        confidence: float,
        llm_model: str,
        prompt_hash: str,
        sample_id: str,
    ) -> Dict[str, Any]:
        proposal_id = f"prp-{uuid.uuid4().hex}"
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_endpoint_profile_proposals (
                    id, connector_id, endpoint_id, endpoint_key, proposal_json,
                    confidence, llm_model, prompt_hash, sample_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    connector_id,
                    endpoint_id,
                    endpoint_key,
                    json.dumps(proposal_json, ensure_ascii=False, sort_keys=True),
                    float(confidence),
                    llm_model,
                    prompt_hash,
                    sample_id,
                    now,
                ),
            )
        return {
            "id": proposal_id,
            "connector_id": connector_id,
            "endpoint_id": endpoint_id,
            "endpoint_key": endpoint_key,
            "proposal_json": proposal_json,
            "confidence": float(confidence),
            "llm_model": llm_model,
            "prompt_hash": prompt_hash,
            "sample_id": sample_id,
            "created_at": now,
        }

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_endpoint_profile_proposals WHERE id = ? LIMIT 1",
                (proposal_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def latest_sample(self, connector_id: str, endpoint_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM connector_endpoint_samples
                WHERE connector_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (connector_id, endpoint_key),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def create_profile_version(
        self,
        *,
        connector_id: str,
        endpoint_id: str,
        endpoint_key: str,
        profile_json: Dict[str, Any],
        validation_report: Dict[str, Any],
        status: str,
        approved_by: Optional[str],
    ) -> Dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS v
                FROM connector_endpoint_profile_versions
                WHERE connector_id = ? AND endpoint_key = ?
                """,
                (connector_id, endpoint_key),
            ).fetchone()
            next_version = int((row["v"] if row else 0) or 0) + 1
            version_id = f"ver-{uuid.uuid4().hex}"
            conn.execute(
                """
                INSERT INTO connector_endpoint_profile_versions (
                    id, connector_id, endpoint_id, endpoint_key,
                    profile_json, validation_report_json, status, version,
                    approved_by, approved_at, fail_count, last_failed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (
                    version_id,
                    connector_id,
                    endpoint_id,
                    endpoint_key,
                    json.dumps(profile_json, ensure_ascii=False, sort_keys=True),
                    json.dumps(validation_report, ensure_ascii=False, sort_keys=True),
                    status,
                    next_version,
                    approved_by,
                    now if status == "active" else None,
                    now,
                ),
            )
            if status == "active":
                conn.execute(
                    """
                    UPDATE connector_endpoint_profile_versions
                    SET status = 'archived'
                    WHERE connector_id = ? AND endpoint_key = ? AND id != ? AND status = 'active'
                    """,
                    (connector_id, endpoint_key, version_id),
                )
        return self.get_version(version_id) or {}

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_endpoint_profile_versions WHERE id = ? LIMIT 1",
                (version_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_profiles(self, connector_id: str, endpoint_key: str, limit: int = 20) -> Dict[str, Any]:
        with self._connect() as conn:
            versions = conn.execute(
                """
                SELECT * FROM connector_endpoint_profile_versions
                WHERE connector_id = ? AND endpoint_key = ?
                ORDER BY version DESC LIMIT ?
                """,
                (connector_id, endpoint_key, int(limit)),
            ).fetchall()
            proposals = conn.execute(
                """
                SELECT * FROM connector_endpoint_profile_proposals
                WHERE connector_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (connector_id, endpoint_key, int(limit)),
            ).fetchall()
            samples = conn.execute(
                """
                SELECT * FROM connector_endpoint_samples
                WHERE connector_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (connector_id, endpoint_key, int(limit)),
            ).fetchall()
        version_dicts = [self._row_to_dict(r) for r in versions]
        active = next((v for v in version_dicts if str(v.get("status")) == "active"), None)
        return {
            "active_version_id": (active or {}).get("id"),
            "versions": version_dicts,
            "proposals": [self._row_to_dict(r) for r in proposals],
            "samples": [self._row_to_dict(r) for r in samples],
        }

    def save_usage_card(
        self,
        *,
        connector_id: str,
        endpoint_id: str,
        endpoint_key: str,
        profile_version_id: Optional[str],
        content_md: str,
    ) -> Dict[str, Any]:
        card_id = f"card-{uuid.uuid4().hex}"
        now = utc_now_iso()
        import hashlib
        content_hash = hashlib.sha256(content_md.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_usage_cards (
                    id, connector_id, endpoint_id, endpoint_key,
                    profile_version_id, content_md, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (card_id, connector_id, endpoint_id, endpoint_key, profile_version_id, content_md, content_hash, now),
            )
        return {
            "id": card_id,
            "connector_id": connector_id,
            "endpoint_id": endpoint_id,
            "endpoint_key": endpoint_key,
            "profile_version_id": profile_version_id,
            "content_md": content_md,
            "content_hash": content_hash,
            "created_at": now,
        }

    def latest_usage_card(self, connector_id: str, endpoint_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM connector_usage_cards
                WHERE connector_id = ? AND endpoint_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (connector_id, endpoint_id),
            ).fetchone()
        return dict(row) if row else None

    def get_endpoint_by_key(self, connector_id: str, endpoint_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM connector_endpoints
                WHERE connector_id = ? AND endpoint_key = ?
                LIMIT 1
                """,
                (connector_id, endpoint_key),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def save_import_version(
        self,
        *,
        connector_id: str,
        source_type: str,
        source_ref: Optional[str],
        summary: Dict[str, Any],
        spec_obj: Dict[str, Any],
    ) -> Dict[str, Any]:
        import_id = f"imp-{uuid.uuid4().hex}"
        now = utc_now_iso()
        spec_text = json.dumps(spec_obj, ensure_ascii=False, sort_keys=True)
        spec_hash = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_import_versions (
                    id, connector_id, source_type, source_ref, summary_json, spec_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    connector_id,
                    source_type,
                    source_ref,
                    json.dumps(summary, ensure_ascii=False, sort_keys=True),
                    spec_hash,
                    now,
                ),
            )
        return {
            "id": import_id,
            "connector_id": connector_id,
            "source_type": source_type,
            "source_ref": source_ref,
            "summary": summary,
            "spec_hash": spec_hash,
            "created_at": now,
        }

    def list_import_versions(self, connector_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM connector_import_versions
                WHERE connector_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (connector_id, int(limit)),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["summary"] = json.loads(item.get("summary_json") or "{}")
            except json.JSONDecodeError:
                item["summary"] = {}
            item.pop("summary_json", None)
            out.append(item)
        return out
