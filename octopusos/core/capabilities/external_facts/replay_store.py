"""Replay store for extraction and verification artifacts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from octopusos.core.storage.paths import component_db_path

from .types import ExtractionRecord, VerificationRecord


class ReplayStore:
    """Persist extraction/verification replay artifacts."""

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
                CREATE TABLE IF NOT EXISTS external_facts_extractions (
                    extraction_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    missing_fields_json TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_facts_verifications (
                    verification_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    confidence_reason TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_facts_extractions_evidence_id "
                "ON external_facts_extractions(evidence_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_facts_verifications_evidence_id "
                "ON external_facts_verifications(evidence_id)"
            )

    def save_extraction(self, record: ExtractionRecord) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO external_facts_extractions (
                    extraction_id, evidence_id, kind, schema_version, status,
                    extracted_json, missing_fields_json, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.extraction_id,
                    record.evidence_id,
                    record.kind,
                    record.schema_version,
                    record.status,
                    json.dumps(record.extracted, ensure_ascii=False),
                    json.dumps(record.missing_fields, ensure_ascii=False),
                    record.notes,
                    record.created_at,
                ),
            )
        return record.extraction_id

    def save_verification(self, record: VerificationRecord) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO external_facts_verifications (
                    verification_id, evidence_id, kind, status, confidence,
                    confidence_reason, checks_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.verification_id,
                    record.evidence_id,
                    record.kind,
                    record.status,
                    record.confidence,
                    record.confidence_reason,
                    json.dumps(record.checks, ensure_ascii=False),
                    record.created_at,
                ),
            )
        return record.verification_id

    def list_extractions(self, evidence_id: str) -> List[ExtractionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM external_facts_extractions WHERE evidence_id = ? ORDER BY created_at ASC",
                (evidence_id,),
            ).fetchall()
        items: List[ExtractionRecord] = []
        for row in rows:
            items.append(
                ExtractionRecord(
                    extraction_id=row["extraction_id"],
                    evidence_id=row["evidence_id"],
                    kind=row["kind"],
                    schema_version=row["schema_version"],
                    status=row["status"],
                    extracted=json.loads(row["extracted_json"] or "{}"),
                    missing_fields=list(json.loads(row["missing_fields_json"] or "[]")),
                    notes=row["notes"],
                    created_at=row["created_at"],
                )
            )
        return items

    def list_verifications(self, evidence_id: str) -> List[VerificationRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM external_facts_verifications WHERE evidence_id = ? ORDER BY created_at ASC",
                (evidence_id,),
            ).fetchall()
        items: List[VerificationRecord] = []
        for row in rows:
            items.append(
                VerificationRecord(
                    verification_id=row["verification_id"],
                    evidence_id=row["evidence_id"],
                    kind=row["kind"],
                    status=row["status"],
                    confidence=row["confidence"],
                    confidence_reason=row["confidence_reason"],
                    checks=json.loads(row["checks_json"] or "{}"),
                    created_at=row["created_at"],
                )
            )
        return items

