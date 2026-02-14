from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.channels.teams.models import TeamsConnectionStatus, TeamsOrganizationConnection
from octopusos.core.storage.paths import component_db_dir
from octopusos.store.timestamp_utils import now_ms


class TeamsConnectionStore:
    """Local connection store for Teams org onboarding (single instance, multi tenant)."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = component_db_dir("octopusos") / "teams_connections.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teams_org_connections (
                    tenant_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Disconnected',
                    teams_app_id TEXT NOT NULL DEFAULT '',
                    bot_id TEXT NOT NULL DEFAULT '',
                    deployment_strategy TEXT NOT NULL DEFAULT 'shared',
                    token_ref TEXT NOT NULL DEFAULT '',
                    token_expires_at_ms INTEGER NOT NULL DEFAULT 0,
                    scopes TEXT NOT NULL DEFAULT '',
                    last_evidence_path TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teams_oauth_states (
                    state TEXT PRIMARY KEY,
                    tenant_hint TEXT NOT NULL DEFAULT '',
                    code_verifier TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    created_at_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teams_org_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'info',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teams_reconcile_locks (
                    tenant_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_teams_org_events_tenant ON teams_org_events(tenant_id, created_at_ms DESC)"
            )
            conn.commit()

    def upsert_connection(self, conn_obj: TeamsOrganizationConnection) -> TeamsOrganizationConnection:
        now = now_ms()
        existing = self.get_connection(conn_obj.tenant_id)
        created_at_ms = existing.created_at_ms if existing else now
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO teams_org_connections (
                    tenant_id, display_name, status, teams_app_id, bot_id,
                    deployment_strategy, token_ref, token_expires_at_ms, scopes,
                    last_evidence_path, metadata_json, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    status=excluded.status,
                    teams_app_id=excluded.teams_app_id,
                    bot_id=excluded.bot_id,
                    deployment_strategy=excluded.deployment_strategy,
                    token_ref=excluded.token_ref,
                    token_expires_at_ms=excluded.token_expires_at_ms,
                    scopes=excluded.scopes,
                    last_evidence_path=excluded.last_evidence_path,
                    metadata_json=excluded.metadata_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (
                    conn_obj.tenant_id,
                    conn_obj.display_name,
                    conn_obj.status,
                    conn_obj.teams_app_id,
                    conn_obj.bot_id,
                    conn_obj.deployment_strategy,
                    conn_obj.token_ref,
                    int(conn_obj.token_expires_at_ms or 0),
                    conn_obj.scopes,
                    conn_obj.last_evidence_path,
                    json.dumps(conn_obj.metadata_json or {}, ensure_ascii=False),
                    int(created_at_ms),
                    int(now),
                ),
            )
            conn.commit()
        obj = self.get_connection(conn_obj.tenant_id)
        if not obj:
            raise RuntimeError("failed_to_persist_connection")
        return obj

    def get_connection(self, tenant_id: str) -> Optional[TeamsOrganizationConnection]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM teams_org_connections WHERE tenant_id = ?",
                (str(tenant_id),),
            ).fetchone()
        if not row:
            return None
        return self._row_to_connection(row)

    def list_connections(self) -> List[TeamsOrganizationConnection]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM teams_org_connections ORDER BY updated_at_ms DESC"
            ).fetchall()
        return [self._row_to_connection(r) for r in rows]

    def has_connection(self, tenant_id: str) -> bool:
        obj = self.get_connection(tenant_id)
        return bool(obj and obj.status != "Disconnected")

    def update_status(
        self,
        tenant_id: str,
        *,
        status: TeamsConnectionStatus,
        teams_app_id: Optional[str] = None,
        last_evidence_path: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> TeamsOrganizationConnection:
        current = self.get_connection(tenant_id)
        if not current:
            current = TeamsOrganizationConnection(tenant_id=str(tenant_id))
        current.status = status
        if teams_app_id is not None:
            current.teams_app_id = teams_app_id
        if last_evidence_path is not None:
            current.last_evidence_path = last_evidence_path
        if display_name is not None:
            current.display_name = display_name
        return self.upsert_connection(current)

    def delete_connection(self, tenant_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM teams_org_connections WHERE tenant_id = ?",
                (str(tenant_id),),
            )
            conn.commit()
            return (cur.rowcount or 0) > 0

    def save_oauth_state(
        self,
        *,
        state: str,
        tenant_hint: str,
        code_verifier: str,
        redirect_uri: str,
        scopes: str,
        ttl_ms: int,
    ) -> None:
        now = now_ms()
        expires = now + max(int(ttl_ms), 60_000)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO teams_oauth_states(state, tenant_hint, code_verifier, redirect_uri, scopes, expires_at_ms, created_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (state, tenant_hint, code_verifier, redirect_uri, scopes, expires, now),
            )
            conn.commit()

    def consume_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        now = now_ms()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM teams_oauth_states WHERE state = ?",
                (state,),
            ).fetchone()
            conn.execute("DELETE FROM teams_oauth_states WHERE state = ?", (state,))
            conn.execute("DELETE FROM teams_oauth_states WHERE expires_at_ms < ?", (now,))
            conn.commit()
        if not row:
            return None
        if int(row["expires_at_ms"] or 0) < now:
            return None
        return {
            "state": row["state"],
            "tenant_hint": row["tenant_hint"],
            "code_verifier": row["code_verifier"],
            "redirect_uri": row["redirect_uri"],
            "scopes": row["scopes"],
        }

    def log_event(self, tenant_id: str, event_type: str, *, level: str = "info", payload: Optional[Dict[str, Any]] = None) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO teams_org_events(tenant_id, event_type, level, payload_json, created_at_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(tenant_id),
                    str(event_type),
                    str(level),
                    json.dumps(payload or {}, ensure_ascii=False),
                    now_ms(),
                ),
            )
            conn.commit()

    def list_events(self, tenant_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, tenant_id, event_type, level, payload_json, created_at_ms
                FROM teams_org_events
                WHERE tenant_id = ?
                ORDER BY created_at_ms DESC
                LIMIT ?
                """,
                (str(tenant_id), int(limit)),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:
                payload = {}
            out.append(
                {
                    "id": int(row["id"]),
                    "tenant_id": row["tenant_id"],
                    "event_type": row["event_type"],
                    "level": row["level"],
                    "payload": payload,
                    "created_at_ms": int(row["created_at_ms"]),
                }
            )
        return out

    def acquire_reconcile_lock(self, tenant_id: str, *, owner: str, ttl_ms: int = 120_000) -> bool:
        now = now_ms()
        expires = now + max(int(ttl_ms), 10_000)
        with self._conn() as conn:
            conn.execute("DELETE FROM teams_reconcile_locks WHERE expires_at_ms < ?", (now,))
            row = conn.execute(
                "SELECT tenant_id FROM teams_reconcile_locks WHERE tenant_id = ?",
                (str(tenant_id),),
            ).fetchone()
            if row:
                conn.commit()
                return False
            conn.execute(
                """
                INSERT INTO teams_reconcile_locks(tenant_id, owner, expires_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?)
                """,
                (str(tenant_id), str(owner), int(expires), int(now)),
            )
            conn.commit()
            return True

    def release_reconcile_lock(self, tenant_id: str, *, owner: Optional[str] = None) -> None:
        with self._conn() as conn:
            if owner:
                conn.execute(
                    "DELETE FROM teams_reconcile_locks WHERE tenant_id = ? AND owner = ?",
                    (str(tenant_id), str(owner)),
                )
            else:
                conn.execute(
                    "DELETE FROM teams_reconcile_locks WHERE tenant_id = ?",
                    (str(tenant_id),),
                )
            conn.commit()

    @staticmethod
    def _row_to_connection(row: sqlite3.Row) -> TeamsOrganizationConnection:
        try:
            metadata_json = json.loads(row["metadata_json"] or "{}")
        except Exception:
            metadata_json = {}
        obj = TeamsOrganizationConnection(
            tenant_id=str(row["tenant_id"]),
            display_name=str(row["display_name"] or ""),
            status=str(row["status"] or "Disconnected"),
            teams_app_id=str(row["teams_app_id"] or ""),
            bot_id=str(row["bot_id"] or ""),
            deployment_strategy=str(row["deployment_strategy"] or "shared"),
            token_ref=str(row["token_ref"] or ""),
            token_expires_at_ms=int(row["token_expires_at_ms"] or 0),
            scopes=str(row["scopes"] or ""),
            last_evidence_path=str(row["last_evidence_path"] or ""),
            metadata_json=metadata_json if isinstance(metadata_json, dict) else {},
            created_at_ms=int(row["created_at_ms"] or 0),
            updated_at_ms=int(row["updated_at_ms"] or 0),
        )
        return obj
