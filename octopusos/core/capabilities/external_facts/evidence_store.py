"""SQLite-backed evidence store for external facts."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from octopusos.core.storage.paths import component_db_path

from .types import EvidenceItem, FactKind, SourceRef


class EvidenceStore:
    """Persist and retrieve evidence items for audit/replay."""

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
                CREATE TABLE IF NOT EXISTS external_facts_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    query TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT,
                    captured_at TEXT NOT NULL,
                    content_snippet TEXT NOT NULL,
                    raw_ref TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_facts_evidence_kind_query "
                "ON external_facts_evidence(kind, query)"
            )

    def save(self, item: EvidenceItem) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO external_facts_evidence (
                    evidence_id, kind, query, type, source_name, source_type,
                    source_url, captured_at, content_snippet, raw_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.evidence_id,
                    item.kind,
                    item.query,
                    item.type,
                    item.source.name,
                    item.source.type,
                    item.source.url,
                    item.captured_at,
                    item.content_snippet,
                    item.raw_ref,
                ),
            )
        return item.evidence_id

    def get(self, evidence_id: str) -> Optional[EvidenceItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM external_facts_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        return self._row_to_item(row) if row else None

    def list(
        self,
        kind: Optional[FactKind] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[EvidenceItem]:
        clauses = []
        params: List[object] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if query:
            clauses.append("query = ?")
            params.append(query)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, int(limit)))
        sql = (
            "SELECT * FROM external_facts_evidence "
            f"{where} ORDER BY captured_at DESC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_item(row) for row in rows if row is not None]

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=row["evidence_id"],
            kind=row["kind"],
            query=row["query"],
            type=row["type"],
            source=SourceRef(
                name=row["source_name"],
                type=row["source_type"],
                url=row["source_url"],
                retrieved_at=row["captured_at"],
            ),
            captured_at=row["captured_at"],
            content_snippet=row["content_snippet"],
            raw_ref=row["raw_ref"],
        )

