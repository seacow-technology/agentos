"""Device binding store (M3).

Hard constraint:
- This store/audit is isolated from CommunicationOS message_audit.
- Device credential tokens are never stored in plaintext. Only SHA-256 hash is stored.
- The token value may be temporarily stored encrypted in SecretStore (secret://) until
  the paired device fetches it once; then the secret is deleted.

Security notes:
- Pairing codes are one-time, short-lived, and server-validated (fail-closed).
- The mobile device must present a poll secret to retrieve the issued credential
  token (prevents token theft if request_id leaks).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from octopusos.core.storage.paths import ensure_db_exists, resolve_component_db_path
from octopusos.core.time import utc_now_ms
from octopusos.webui.secrets import SecretStore


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def _rand_urlsafe(nbytes: int) -> str:
    # urlsafe avoids QR decoding issues across platforms.
    return secrets.token_urlsafe(max(1, int(nbytes)))


DEVICE_DB_COMPONENT = "device_binding"


SCHEMA = """
CREATE TABLE IF NOT EXISTS device_pairing_codes (
  id TEXT PRIMARY KEY,
  code_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  used_at INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_pairing_codes_expires ON device_pairing_codes(expires_at, used_at);

CREATE TABLE IF NOT EXISTS device_requests (
  id TEXT PRIMARY KEY,
  pairing_code_hash TEXT NOT NULL,
  device_fingerprint TEXT NOT NULL,
  device_name TEXT NOT NULL,
  client_pubkey TEXT,
  status TEXT NOT NULL, -- pending|approved|rejected|revoked
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_requests_status ON device_requests(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_requests_fingerprint ON device_requests(device_fingerprint);

CREATE TABLE IF NOT EXISTS device_credentials (
  id TEXT PRIMARY KEY,
  device_request_id TEXT NOT NULL,
  credential_hash TEXT NOT NULL,
  secret_ref TEXT, -- encrypted token stored temporarily for one-time retrieval
  issued_at INTEGER NOT NULL,
  expires_at INTEGER,
  revoked_at INTEGER,
  FOREIGN KEY (device_request_id) REFERENCES device_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_credentials_req ON device_credentials(device_request_id);

CREATE TABLE IF NOT EXISTS device_audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_request_id TEXT NOT NULL,
  event_type TEXT NOT NULL, -- REQUESTED|APPROVED|REJECTED|REVOKED|ROTATED
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  FOREIGN KEY (device_request_id) REFERENCES device_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_audit_req ON device_audit_log(device_request_id, created_at DESC);

CREATE TABLE IF NOT EXISTS device_sessions (
  device_request_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (device_request_id) REFERENCES device_requests(id) ON DELETE CASCADE
);

-- Multi-session support (client-managed IDs) for mobile clients.
CREATE TABLE IF NOT EXISTS device_session_links (
  device_request_id TEXT NOT NULL,
  client_session_id TEXT NOT NULL,
  server_session_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (device_request_id, client_session_id),
  FOREIGN KEY (device_request_id) REFERENCES device_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_session_links_req ON device_session_links(device_request_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS device_active_sessions (
  device_request_id TEXT PRIMARY KEY,
  client_session_id TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (device_request_id) REFERENCES device_requests(id) ON DELETE CASCADE
);
"""


@dataclass
class DeviceRequestRow:
    id: str
    device_fingerprint: str
    device_name: str
    status: str
    created_at: int
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_fingerprint": self.device_fingerprint,
            "device_name": self.device_name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DeviceStore:
    def __init__(self, db_path: Optional[str] = None):
        canonical = resolve_component_db_path(DEVICE_DB_COMPONENT, db_path)
        ensure_db_exists(DEVICE_DB_COMPONENT)
        self.db_path = str(canonical)
        self._init_schema()
        self.secrets = SecretStore()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        self._best_effort_migrate()

    def _best_effort_migrate(self) -> None:
        """Best-effort schema evolution without a separate migration runner.

        This component DB is isolated and uses CREATE TABLE IF NOT EXISTS. When we
        add columns, we must ALTER TABLE for existing DBs.
        """
        with self._connect() as conn:
            # device_requests: add pairing_code_id + poll_secret_hash for secure polling
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(device_requests)").fetchall()}
            if "pairing_code_id" not in cols:
                conn.execute("ALTER TABLE device_requests ADD COLUMN pairing_code_id TEXT")
            if "poll_secret_hash" not in cols:
                conn.execute("ALTER TABLE device_requests ADD COLUMN poll_secret_hash TEXT")
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def create_pairing_code(self, ttl_sec: int = 60) -> Dict[str, Any]:
        code = _rand_urlsafe(16)
        code_hash = _sha256_hex(code)
        now = utc_now_ms()
        expires_at = now + max(1, int(ttl_sec)) * 1000
        pid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_pairing_codes(id, code_hash, expires_at, used_at, created_at)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (pid, code_hash, int(expires_at), int(now)),
            )
            conn.commit()
        return {"pairing_code": code, "pairing_code_hash": code_hash, "expires_at_ms": int(expires_at), "ttl_sec": int(ttl_sec)}

    def _consume_pairing_code(self, *, pairing_code: str) -> Optional[str]:
        """Validate a pairing code and mark it used. Returns pairing_code_id."""
        if not pairing_code or not isinstance(pairing_code, str):
            return None
        code_hash = _sha256_hex(pairing_code.strip())
        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, expires_at, used_at
                FROM device_pairing_codes
                WHERE code_hash = ?
                LIMIT 1
                """,
                (code_hash,),
            ).fetchone()
            if not row:
                return None
            if row["used_at"] is not None:
                return None
            if int(row["expires_at"]) < int(now):
                return None
            conn.execute("UPDATE device_pairing_codes SET used_at = ? WHERE id = ? AND used_at IS NULL", (int(now), str(row["id"])))
            conn.commit()
            return str(row["id"])

    def create_device_request_from_pairing_code(
        self,
        *,
        pairing_code: str,
        device_fingerprint: str,
        device_name: str,
        client_pubkey: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a pending device request from a one-time pairing code.

        Returns {request, poll_secret}. poll_secret is required for polling and token retrieval.
        """
        pairing_code_id = self._consume_pairing_code(pairing_code=pairing_code)
        if not pairing_code_id:
            return None
        poll_secret = _rand_urlsafe(24)
        poll_secret_hash = _sha256_hex(poll_secret)
        rid = str(uuid.uuid4())
        now = utc_now_ms()
        pairing_code_hash = _sha256_hex(pairing_code.strip())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_requests(
                  id, pairing_code_hash, pairing_code_id, poll_secret_hash,
                  device_fingerprint, device_name, client_pubkey,
                  status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    rid,
                    pairing_code_hash,
                    pairing_code_id,
                    poll_secret_hash,
                    device_fingerprint,
                    device_name,
                    client_pubkey,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO device_audit_log(device_request_id, event_type, metadata_json, created_at)
                VALUES (?, 'REQUESTED', ?, ?)
                """,
                (
                    rid,
                    json.dumps({"fingerprint_hash": _sha256_hex(device_fingerprint)}, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            conn.commit()
        req = self.get_request(rid)
        if not req:
            return None
        return {"request": req.to_dict(), "poll_secret": poll_secret}

    def create_device_request(
        self,
        *,
        pairing_code_hash: str,
        device_fingerprint: str,
        device_name: str,
        client_pubkey: Optional[str] = None,
    ) -> DeviceRequestRow:
        # Backward-compatible entrypoint for older callers. New flow should use
        # create_device_request_from_pairing_code() to enforce TTL + one-time usage.
        rid = str(uuid.uuid4())
        now = utc_now_ms()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_requests(id, pairing_code_hash, device_fingerprint, device_name, client_pubkey, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (rid, pairing_code_hash, device_fingerprint, device_name, client_pubkey, now, now),
            )
            conn.execute(
                """
                INSERT INTO device_audit_log(device_request_id, event_type, metadata_json, created_at)
                VALUES (?, 'REQUESTED', ?, ?)
                """,
                (
                    rid,
                    json.dumps({"fingerprint_hash": _sha256_hex(device_fingerprint)}, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            conn.commit()
        return self.get_request(rid)  # type: ignore[return-value]

    def get_request(self, request_id: str) -> Optional[DeviceRequestRow]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM device_requests WHERE id = ?", (str(request_id),)).fetchone()
        if not row:
            return None
        return DeviceRequestRow(
            id=row["id"],
            device_fingerprint=row["device_fingerprint"],
            device_name=row["device_name"],
            status=row["status"],
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )

    def list_requests(self, *, status: Optional[str] = None, limit: int = 200) -> List[DeviceRequestRow]:
        sql = "SELECT * FROM device_requests "
        args: list[Any] = []
        if status:
            sql += "WHERE status = ? "
            args.append(str(status))
        sql += "ORDER BY updated_at DESC LIMIT ?"
        args.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [
            DeviceRequestRow(
                id=r["id"],
                device_fingerprint=r["device_fingerprint"],
                device_name=r["device_name"],
                status=r["status"],
                created_at=int(r["created_at"]),
                updated_at=int(r["updated_at"]),
            )
            for r in rows
        ]

    def approve(self, *, request_id: str, ttl_sec: int = 86400) -> Optional[Dict[str, Any]]:
        row = self.get_request(request_id)
        if not row:
            return None
        now = utc_now_ms()
        token = secrets.token_urlsafe(32)
        token_hash = _sha256_hex(token)
        cred_id = str(uuid.uuid4())
        expires_at = now + max(1, int(ttl_sec)) * 1000
        secret_ref = f"secret://devices/credentials/{cred_id}"
        self.secrets.set(secret_ref, token)
        with self._connect() as conn:
            conn.execute(
                "UPDATE device_requests SET status = 'approved', updated_at = ? WHERE id = ?",
                (now, str(request_id)),
            )
            conn.execute(
                """
                INSERT INTO device_credentials(id, device_request_id, credential_hash, secret_ref, issued_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (cred_id, str(request_id), token_hash, secret_ref, now, expires_at),
            )
            conn.execute(
                """
                INSERT INTO device_audit_log(device_request_id, event_type, metadata_json, created_at)
                VALUES (?, 'APPROVED', ?, ?)
                """,
                (str(request_id), json.dumps({"credential_hash": token_hash[:16]}, ensure_ascii=False), now),
            )
            conn.commit()
        return {"credential_id": cred_id, "secret_ref": secret_ref, "expires_at_ms": expires_at}

    def reject(self, *, request_id: str) -> bool:
        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM device_requests WHERE id = ?", (str(request_id),)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE device_requests SET status = 'rejected', updated_at = ? WHERE id = ?", (now, str(request_id)))
            conn.execute(
                "INSERT INTO device_audit_log(device_request_id, event_type, metadata_json, created_at) VALUES (?, 'REJECTED', '{}', ?)",
                (str(request_id), now),
            )
            conn.commit()
        return True

    def revoke(self, *, request_id: str) -> bool:
        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM device_requests WHERE id = ?", (str(request_id),)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE device_requests SET status = 'revoked', updated_at = ? WHERE id = ?", (now, str(request_id)))
            conn.execute(
                "UPDATE device_credentials SET revoked_at = ? WHERE device_request_id = ? AND revoked_at IS NULL",
                (now, str(request_id)),
            )
            conn.execute(
                "INSERT INTO device_audit_log(device_request_id, event_type, metadata_json, created_at) VALUES (?, 'REVOKED', '{}', ?)",
                (str(request_id), now),
            )
            conn.commit()
        return True

    def fetch_credential_once(self, *, request_id: str) -> Optional[str]:
        """Return the raw credential token once, then delete the encrypted secret.

        Returns None if not approved or already retrieved.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, secret_ref, revoked_at, expires_at
                FROM device_credentials
                WHERE device_request_id = ?
                ORDER BY issued_at DESC
                LIMIT 1
                """,
                (str(request_id),),
            ).fetchone()
        if not row:
            return None
        if row["revoked_at"] is not None:
            return None
        expires_at = row["expires_at"]
        if expires_at is not None and int(expires_at) < utc_now_ms():
            return None
        secret_ref = str(row["secret_ref"] or "").strip()
        if not secret_ref:
            return None
        token = self.secrets.get(secret_ref)
        if token:
            # delete after first retrieval
            self.secrets.delete(secret_ref)
            # clear secret_ref column so we know it's been fetched
            with self._connect() as conn:
                conn.execute(
                    "UPDATE device_credentials SET secret_ref = NULL WHERE id = ?",
                    (str(row["id"]),),
                )
                conn.commit()
            return token
        return None

    def validate_credential(self, token: str) -> Optional[str]:
        """Validate token and return device_request_id if valid."""
        if not token or not token.strip():
            return None
        token_hash = _sha256_hex(token.strip())
        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT device_request_id, revoked_at, expires_at
                FROM device_credentials
                WHERE credential_hash = ?
                ORDER BY issued_at DESC
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        if not row:
            return None
        if row["revoked_at"] is not None:
            return None
        exp = row["expires_at"]
        if exp is not None and int(exp) < now:
            return None
        # ensure request still approved
        req = self.get_request(str(row["device_request_id"]))
        if not req or req.status != "approved":
            return None
        return str(row["device_request_id"])

    def validate_poll_secret(self, *, request_id: str, poll_secret: str) -> bool:
        if not poll_secret or not poll_secret.strip():
            return False
        expected = _sha256_hex(poll_secret.strip())
        with self._connect() as conn:
            row = conn.execute("SELECT poll_secret_hash FROM device_requests WHERE id = ?", (str(request_id),)).fetchone()
        if not row:
            return False
        stored = str(row["poll_secret_hash"] or "").strip()
        if not stored:
            return False
        return stored == expected

    def get_or_create_device_session(self, *, request_id: str, create_session: Any) -> str:
        """Return stable chat session_id for a device request.

        create_session: callable() -> session_id
        """
        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute("SELECT session_id FROM device_sessions WHERE device_request_id = ?", (str(request_id),)).fetchone()
            if row and row["session_id"]:
                return str(row["session_id"])
            session_id = str(create_session())
            conn.execute(
                """
                INSERT INTO device_sessions(device_request_id, session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(request_id), session_id, int(now), int(now)),
            )
            conn.commit()
            return session_id

    def get_active_client_session_id(self, *, request_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT client_session_id FROM device_active_sessions WHERE device_request_id = ?",
                (str(request_id),),
            ).fetchone()
        if not row:
            return None
        value = str(row["client_session_id"] or "").strip()
        return value or None

    def set_active_client_session_id(self, *, request_id: str, client_session_id: str) -> None:
        safe = str(client_session_id or "").strip()
        if not safe:
            return
        now = utc_now_ms()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_active_sessions(device_request_id, client_session_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(device_request_id) DO UPDATE SET
                  client_session_id = excluded.client_session_id,
                  updated_at = excluded.updated_at
                """,
                (str(request_id), safe, int(now)),
            )
            conn.commit()

    def list_device_session_links(self, *, request_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(500, int(limit or 200)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT client_session_id, server_session_id, title, created_at, updated_at
                FROM device_session_links
                WHERE device_request_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (str(request_id), int(safe_limit)),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "client_session_id": str(r["client_session_id"]),
                    "server_session_id": str(r["server_session_id"]),
                    "title": str(r["title"] or ""),
                    "created_at_ms": int(r["created_at"] or 0),
                    "updated_at_ms": int(r["updated_at"] or 0),
                }
            )
        return out

    def get_device_session_link(self, *, request_id: str, client_session_id: str) -> Optional[Dict[str, Any]]:
        safe = str(client_session_id or "").strip()
        if not safe:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT client_session_id, server_session_id, title, created_at, updated_at
                FROM device_session_links
                WHERE device_request_id = ? AND client_session_id = ?
                LIMIT 1
                """,
                (str(request_id), safe),
            ).fetchone()
        if not row:
            return None
        return {
            "client_session_id": str(row["client_session_id"]),
            "server_session_id": str(row["server_session_id"]),
            "title": str(row["title"] or ""),
            "created_at_ms": int(row["created_at"] or 0),
            "updated_at_ms": int(row["updated_at"] or 0),
        }

    def get_or_create_device_session_link(
        self,
        *,
        request_id: str,
        client_session_id: str,
        title: str,
        create_session: Any,
    ) -> str:
        safe_client = str(client_session_id or "").strip()
        safe_title = str(title or "").strip() or "Chat"
        if not safe_client:
            raise ValueError("client_session_id is required")

        now = utc_now_ms()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT server_session_id
                FROM device_session_links
                WHERE device_request_id = ? AND client_session_id = ?
                LIMIT 1
                """,
                (str(request_id), safe_client),
            ).fetchone()
            if row and row["server_session_id"]:
                conn.execute(
                    "UPDATE device_session_links SET updated_at = ? WHERE device_request_id = ? AND client_session_id = ?",
                    (int(now), str(request_id), safe_client),
                )
                conn.commit()
                return str(row["server_session_id"])

            server_session_id = str(create_session(safe_title))
            conn.execute(
                """
                INSERT INTO device_session_links(device_request_id, client_session_id, server_session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(request_id), safe_client, server_session_id, safe_title, int(now), int(now)),
            )
            conn.commit()
            return server_session_id
