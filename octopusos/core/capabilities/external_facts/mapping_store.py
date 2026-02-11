"""Persistence for endpoint mapping samples/proposals/versions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from octopusos.core.storage.paths import component_db_path

from .types import utc_now_iso


class ExternalFactsMappingStore:
    """Store endpoint samples, LLM proposals, and versioned mappings."""

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
                CREATE TABLE IF NOT EXISTS provider_endpoint_samples (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    sample_json TEXT NOT NULL,
                    sample_hash TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_provider_endpoint_samples_lookup "
                "ON provider_endpoint_samples(provider_id, endpoint_key, created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_mapping_proposals (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    llm_model TEXT NOT NULL DEFAULT '',
                    prompt_hash TEXT NOT NULL DEFAULT '',
                    sample_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_provider_mapping_proposals_lookup "
                "ON provider_mapping_proposals(provider_id, endpoint_key, created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_mapping_versions (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    endpoint_key TEXT NOT NULL,
                    mapping_json TEXT NOT NULL,
                    validation_report TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
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
                "CREATE INDEX IF NOT EXISTS idx_provider_mapping_versions_lookup "
                "ON provider_mapping_versions(provider_id, endpoint_key, version DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_provider_mapping_versions_status "
                "ON provider_mapping_versions(provider_id, endpoint_key, status)"
            )

    def save_sample(
        self,
        *,
        provider_id: str,
        endpoint_key: str,
        capability_id: str,
        item_id: str,
        sample_json: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        sample_id = str(uuid4())
        sample_text = json.dumps(sample_json, ensure_ascii=False, sort_keys=True)
        sample_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_endpoint_samples (
                    id, provider_id, endpoint_key, capability_id, item_id, sample_json, sample_hash, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    provider_id,
                    endpoint_key,
                    capability_id,
                    item_id,
                    sample_text,
                    sample_hash,
                    created_by,
                    now,
                ),
            )
        return {
            "id": sample_id,
            "provider_id": provider_id,
            "endpoint_key": endpoint_key,
            "capability_id": capability_id,
            "item_id": item_id,
            "sample_json": sample_json,
            "sample_hash": sample_hash,
            "created_by": created_by,
            "created_at": now,
        }

    def save_proposal(
        self,
        *,
        provider_id: str,
        endpoint_key: str,
        proposal_json: Dict[str, Any],
        confidence: float,
        llm_model: str,
        prompt_hash: str,
        sample_id: str,
    ) -> Dict[str, Any]:
        proposal_id = str(uuid4())
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_mapping_proposals (
                    id, provider_id, endpoint_key, proposal_json, confidence, llm_model, prompt_hash, sample_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    provider_id,
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
            "provider_id": provider_id,
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
                "SELECT * FROM provider_mapping_proposals WHERE id = ? LIMIT 1",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        return self._proposal_row(row)

    def create_mapping_version(
        self,
        *,
        provider_id: str,
        endpoint_key: str,
        mapping_json: Dict[str, Any],
        validation_report: Dict[str, Any],
        status: str,
        approved_by: Optional[str],
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS max_version FROM provider_mapping_versions WHERE provider_id = ? AND endpoint_key = ?",
                (provider_id, endpoint_key),
            ).fetchone()
            next_version = int(row["max_version"] or 0) + 1
            version_id = str(uuid4())
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO provider_mapping_versions (
                    id, provider_id, endpoint_key, mapping_json, validation_report, status, version,
                    approved_by, approved_at, fail_count, last_failed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (
                    version_id,
                    provider_id,
                    endpoint_key,
                    json.dumps(mapping_json, ensure_ascii=False, sort_keys=True),
                    json.dumps(validation_report, ensure_ascii=False, sort_keys=True),
                    status,
                    next_version,
                    approved_by if status == "active" else None,
                    now if status == "active" else None,
                    now,
                ),
            )
            if status == "active":
                conn.execute(
                    """
                    UPDATE provider_mapping_versions
                    SET status = 'archived'
                    WHERE provider_id = ? AND endpoint_key = ? AND status = 'active' AND id != ?
                    """,
                    (provider_id, endpoint_key, version_id),
                )
        return self.get_version(version_id) or {}

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM provider_mapping_versions WHERE id = ? LIMIT 1",
                (version_id,),
            ).fetchone()
        if not row:
            return None
        return self._version_row(row)

    def list_endpoint_bundle(self, *, provider_id: str, endpoint_key: str, limit: int = 20) -> Dict[str, Any]:
        with self._connect() as conn:
            versions = conn.execute(
                """
                SELECT * FROM provider_mapping_versions
                WHERE provider_id = ? AND endpoint_key = ?
                ORDER BY version DESC
                LIMIT ?
                """,
                (provider_id, endpoint_key, int(limit)),
            ).fetchall()
            proposals = conn.execute(
                """
                SELECT * FROM provider_mapping_proposals
                WHERE provider_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (provider_id, endpoint_key, int(limit)),
            ).fetchall()
            samples = conn.execute(
                """
                SELECT * FROM provider_endpoint_samples
                WHERE provider_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (provider_id, endpoint_key, int(limit)),
            ).fetchall()
            active = conn.execute(
                """
                SELECT id FROM provider_mapping_versions
                WHERE provider_id = ? AND endpoint_key = ? AND status = 'active'
                ORDER BY version DESC
                LIMIT 1
                """,
                (provider_id, endpoint_key),
            ).fetchone()
        return {
            "active_version_id": str(active["id"]) if active else None,
            "versions": [self._version_row(v) for v in versions],
            "proposals": [self._proposal_row(p) for p in proposals],
            "samples": [self._sample_row(s) for s in samples],
        }

    def get_latest_sample(self, *, provider_id: str, endpoint_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM provider_endpoint_samples
                WHERE provider_id = ? AND endpoint_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (provider_id, endpoint_key),
            ).fetchone()
        if not row:
            return None
        return self._sample_row(row)

    def record_failure_and_maybe_rollback(
        self,
        *,
        provider_id: str,
        endpoint_key: str,
        failed_version_id: str,
        threshold: int = 3,
    ) -> Optional[str]:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT fail_count, version, status
                FROM provider_mapping_versions
                WHERE id = ? AND provider_id = ? AND endpoint_key = ?
                LIMIT 1
                """,
                (failed_version_id, provider_id, endpoint_key),
            ).fetchone()
            if not row:
                return None
            next_fail = int(row["fail_count"] or 0) + 1
            conn.execute(
                """
                UPDATE provider_mapping_versions
                SET fail_count = ?, last_failed_at = ?
                WHERE id = ?
                """,
                (next_fail, now, failed_version_id),
            )
            if next_fail < int(threshold):
                return None
            failed_version_num = int(row["version"] or 0)
            rollback = conn.execute(
                """
                SELECT id, version FROM provider_mapping_versions
                WHERE provider_id = ? AND endpoint_key = ? AND status IN ('active','archived') AND version < ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (provider_id, endpoint_key, failed_version_num),
            ).fetchone()
            if not rollback:
                return None
            rollback_id = str(rollback["id"])
            conn.execute(
                "UPDATE provider_mapping_versions SET status = 'archived' WHERE id = ?",
                (failed_version_id,),
            )
            conn.execute(
                "UPDATE provider_mapping_versions SET status = 'active', approved_at = ? WHERE id = ?",
                (now, rollback_id),
            )
            return rollback_id

    @staticmethod
    def _sample_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "provider_id": row["provider_id"],
            "endpoint_key": row["endpoint_key"],
            "capability_id": row["capability_id"],
            "item_id": row["item_id"],
            "sample_json": json.loads(row["sample_json"] or "{}"),
            "sample_hash": row["sample_hash"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _proposal_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "provider_id": row["provider_id"],
            "endpoint_key": row["endpoint_key"],
            "proposal_json": json.loads(row["proposal_json"] or "{}"),
            "confidence": float(row["confidence"] or 0.0),
            "llm_model": row["llm_model"],
            "prompt_hash": row["prompt_hash"],
            "sample_id": row["sample_id"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _version_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "provider_id": row["provider_id"],
            "endpoint_key": row["endpoint_key"],
            "mapping_json": json.loads(row["mapping_json"] or "{}"),
            "validation_report": json.loads(row["validation_report"] or "{}"),
            "status": row["status"],
            "version": int(row["version"] or 0),
            "approved_by": row["approved_by"],
            "approved_at": row["approved_at"],
            "fail_count": int(row["fail_count"] or 0),
            "last_failed_at": row["last_failed_at"],
            "created_at": row["created_at"],
        }
