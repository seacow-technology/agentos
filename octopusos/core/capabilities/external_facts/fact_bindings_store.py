from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.core.storage.paths import component_db_path
from .types import utc_now_iso


class FactBindingsStore:
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
                CREATE TABLE IF NOT EXISTS external_facts_bindings (
                    binding_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    connector_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    profile_version_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    validation_report_json TEXT NOT NULL DEFAULT '{}',
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    rollback_info_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(capability_id, item_id)
                )
                """
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("validation_report_json", "rollback_info_json"):
            try:
                d[key.replace("_json", "")] = json.loads(d.get(key) or "{}")
            except json.JSONDecodeError:
                d[key.replace("_json", "")] = {}
            del d[key]
        return d

    def list(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM external_facts_bindings ORDER BY updated_at DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, capability_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM external_facts_bindings WHERE capability_id = ? AND item_id = ? LIMIT 1",
                (capability_id, item_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def upsert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        capability_id = str(payload.get("capability_id") or "").strip()
        item_id = str(payload.get("item_id") or "").strip()
        connector_id = str(payload.get("connector_id") or "").strip()
        endpoint_id = str(payload.get("endpoint_id") or "").strip()
        if not capability_id or not item_id or not connector_id or not endpoint_id:
            raise ValueError("capability_id,item_id,connector_id,endpoint_id are required")
        profile_version_id = str(payload.get("profile_version_id") or "").strip() or None
        status = str(payload.get("status") or "active").strip() or "active"
        validation_report = payload.get("validation_report") if isinstance(payload.get("validation_report"), dict) else {}
        rollback_info = payload.get("rollback_info") if isinstance(payload.get("rollback_info"), dict) else {}
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT binding_id, created_at, fail_count FROM external_facts_bindings WHERE capability_id = ? AND item_id = ? LIMIT 1",
                (capability_id, item_id),
            ).fetchone()
            binding_id = str(row["binding_id"]) if row else f"bind-{uuid.uuid4().hex[:12]}"
            created_at = str(row["created_at"]) if row else now
            fail_count = int(row["fail_count"] or 0) if row else 0
            conn.execute(
                """
                INSERT INTO external_facts_bindings (
                    binding_id, capability_id, item_id, connector_id, endpoint_id,
                    profile_version_id, status, validation_report_json, fail_count,
                    rollback_info_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(binding_id) DO UPDATE SET
                    connector_id = excluded.connector_id,
                    endpoint_id = excluded.endpoint_id,
                    profile_version_id = excluded.profile_version_id,
                    status = excluded.status,
                    validation_report_json = excluded.validation_report_json,
                    rollback_info_json = excluded.rollback_info_json,
                    updated_at = excluded.updated_at
                """,
                (
                    binding_id,
                    capability_id,
                    item_id,
                    connector_id,
                    endpoint_id,
                    profile_version_id,
                    status,
                    json.dumps(validation_report, ensure_ascii=False, sort_keys=True),
                    fail_count,
                    json.dumps(rollback_info, ensure_ascii=False, sort_keys=True),
                    created_at,
                    now,
                ),
            )
        result = self.get(capability_id, item_id)
        if not result:
            raise RuntimeError("failed to save binding")
        return result

    def delete(self, capability_id: str, item_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM external_facts_bindings WHERE capability_id = ? AND item_id = ?",
                (capability_id, item_id),
            )
            return cur.rowcount > 0
