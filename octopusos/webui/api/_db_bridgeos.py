"""BridgeOS sqlite helpers (SSH/SFTP/Local shell persistent state).

We store SSH/SFTP inventory and terminal event streams in BridgeOS, while
writing governance/audit signals into OctopusOS compat_audit_events.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from octopusos.core.storage.paths import ensure_db_exists, resolve_component_db_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def bridgeos_db_path() -> Path:
    override = (os.getenv("OCTOPUSOS_BRIDGEOS_DB_PATH") or "").strip()
    if override:
        # Tests/CI can set a temp path. We still keep the default boundary in prod.
        p = resolve_component_db_path("bridgeos", override, allow_override=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return ensure_db_exists("bridgeos")


def connect_bridgeos() -> sqlite3.Connection:
    db_path = bridgeos_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _ensure_column(conn: sqlite3.Connection, *, table: str, column: str, decl_sql: str) -> None:
    """Best-effort schema evolution for SQLite without a full migrator.

    We only ever ADD columns, so this stays safe and idempotent.
    """
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    cols = {str(r[1]) for r in rows}  # pragma: no cover (sqlite row shape)
    if column in cols:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {decl_sql}")


def ensure_bridgeos_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema for bridge-managed SSH/SFTP/shell tables."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS terminal_sessions (
          session_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          cwd TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS terminal_events (
          session_id TEXT NOT NULL,
          seq INTEGER NOT NULL,
          ts TEXT NOT NULL,
          type TEXT NOT NULL,
          data_json TEXT NOT NULL,
          PRIMARY KEY (session_id, seq)
        );

        CREATE INDEX IF NOT EXISTS idx_terminal_events_session_seq
          ON terminal_events(session_id, seq);

        CREATE TABLE IF NOT EXISTS hosts (
          host_id TEXT PRIMARY KEY,
          label TEXT,
          hostname TEXT NOT NULL,
          port INTEGER NOT NULL DEFAULT 22,
          tags_json TEXT,
          meta_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS known_hosts (
          known_host_id TEXT PRIMARY KEY,
          host TEXT NOT NULL,
          port INTEGER NOT NULL DEFAULT 22,
          fingerprint TEXT NOT NULL,
          algo TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS known_hosts_replace_requests (
          request_id TEXT PRIMARY KEY,
          host TEXT NOT NULL,
          port INTEGER NOT NULL DEFAULT 22,
          fingerprint TEXT NOT NULL,
          algo TEXT,
          status TEXT NOT NULL,
          reason TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_known_hosts_replace_requests_host_port
          ON known_hosts_replace_requests(host, port);

        CREATE TABLE IF NOT EXISTS secrets (
          secret_id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          label TEXT,
          secret_ref TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ssh_connections (
          connection_id TEXT PRIMARY KEY,
          host_id TEXT NOT NULL,
          status TEXT NOT NULL,
          label TEXT,
          mode TEXT NOT NULL DEFAULT 'ssh',
          auth_ref TEXT,
          probe_only INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_seen_at TEXT,
          detached_at TEXT,
          error_code TEXT,
          error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ssh_connections_host_id ON ssh_connections(host_id);
        CREATE INDEX IF NOT EXISTS idx_ssh_connections_status ON ssh_connections(status);

        CREATE TABLE IF NOT EXISTS ssh_connection_events (
          connection_id TEXT NOT NULL,
          seq INTEGER NOT NULL,
          ts TEXT NOT NULL,
          type TEXT NOT NULL,
          data_json TEXT NOT NULL,
          PRIMARY KEY (connection_id, seq)
        );

        CREATE INDEX IF NOT EXISTS idx_ssh_connection_events_conn_seq
          ON ssh_connection_events(connection_id, seq);

        CREATE TABLE IF NOT EXISTS sftp_sessions (
          sftp_session_id TEXT PRIMARY KEY,
          connection_id TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sftp_sessions_conn_id ON sftp_sessions(connection_id);

        CREATE TABLE IF NOT EXISTS sftp_transfers (
          transfer_id TEXT PRIMARY KEY,
          sftp_session_id TEXT NOT NULL,
          direction TEXT NOT NULL,
          remote_path TEXT NOT NULL,
          bytes_total INTEGER,
          bytes_done INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          sha256 TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_sftp_transfers_session_id ON sftp_transfers(sftp_session_id);
        CREATE INDEX IF NOT EXISTS idx_sftp_transfers_status ON sftp_transfers(status);
        """
    )
    # Lightweight schema evolution: add columns for newer phases.
    try:
        _ensure_column(conn, table="secrets", column="encrypted_blob", decl_sql="encrypted_blob TEXT")
        _ensure_column(conn, table="secrets", column="enc_version", decl_sql="enc_version INTEGER NOT NULL DEFAULT 1")
    except Exception:
        # If secrets table does not exist yet, CREATE TABLE above will have created it.
        # This is defensive for older DBs.
        pass

    try:
        _ensure_column(conn, table="ssh_connections", column="username", decl_sql="username TEXT")
        _ensure_column(conn, table="ssh_connections", column="detach_grace_ms", decl_sql="detach_grace_ms INTEGER")
        _ensure_column(conn, table="ssh_connections", column="hard_ttl_ms", decl_sql="hard_ttl_ms INTEGER")
        _ensure_column(conn, table="ssh_connections", column="last_activity_at", decl_sql="last_activity_at TEXT")
    except Exception:
        pass
    conn.commit()


def insert_terminal_event(conn: sqlite3.Connection, *, session_id: str, event_type: str, data_json: str) -> int:
    """Append one terminal event and return its seq."""
    ensure_bridgeos_schema(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM terminal_events WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    seq = int(row["max_seq"] or 0) + 1
    conn.execute(
        """
        INSERT INTO terminal_events (session_id, seq, ts, type, data_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, seq, _now_iso(), event_type, data_json),
    )
    conn.execute(
        "UPDATE terminal_sessions SET updated_at = ? WHERE session_id = ?",
        (_now_iso(), session_id),
    )
    conn.commit()
    return seq


def insert_ssh_connection_event(
    conn: sqlite3.Connection, *, connection_id: str, event_type: str, data_json: str
) -> int:
    ensure_bridgeos_schema(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM ssh_connection_events WHERE connection_id = ?",
        (connection_id,),
    ).fetchone()
    seq = int(row["max_seq"] or 0) + 1
    conn.execute(
        """
        INSERT INTO ssh_connection_events (connection_id, seq, ts, type, data_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (connection_id, seq, _now_iso(), event_type, data_json),
    )
    conn.execute(
        "UPDATE ssh_connections SET updated_at = ? WHERE connection_id = ?",
        (_now_iso(), connection_id),
    )
    conn.commit()
    return seq
