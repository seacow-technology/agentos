"""NetworkOS Data Store - Tunnel and Event Management"""

import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path

from agentos.core.storage.paths import ensure_db_exists
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


@dataclass
class Tunnel:
    """Tunnel configuration and status"""
    tunnel_id: str
    provider: str  # cloudflare, ngrok, etc.
    name: str
    is_enabled: bool
    public_hostname: str
    local_target: str
    mode: str  # http, tcp, https
    health_status: str  # unknown, up, down
    last_heartbeat_at: Optional[int]
    last_error_code: Optional[str]
    last_error_message: Optional[str]
    created_at: int
    updated_at: int


@dataclass
class TunnelEvent:
    """Tunnel event log"""
    event_id: str
    tunnel_id: str
    level: str  # info, warn, error
    event_type: str
    message: str
    data_json: Optional[str]
    created_at: int


class NetworkOSStore:
    """NetworkOS SQLite Store"""

    # Schema is handled by migration v54 (schema_v54_networkos.sql)
    # This ensures the store uses the exact same table names as the migration
    SCHEMA = """
    -- NetworkOS schema is defined in migration v54
    -- Tables: network_tunnels, network_routes, network_events, tunnel_secrets
    -- This schema definition is kept for backward compatibility with existing store instances

    CREATE TABLE IF NOT EXISTS network_tunnels (
        tunnel_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        name TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 0,
        public_hostname TEXT NOT NULL,
        local_target TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'http',
        health_status TEXT NOT NULL DEFAULT 'unknown',
        last_heartbeat_at INTEGER,
        last_error_code TEXT,
        last_error_message TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(provider, name)
    );

    CREATE INDEX IF NOT EXISTS idx_network_tunnels_provider ON network_tunnels(provider);
    CREATE INDEX IF NOT EXISTS idx_network_tunnels_enabled ON network_tunnels(is_enabled);

    CREATE TABLE IF NOT EXISTS network_routes (
        route_id TEXT PRIMARY KEY,
        tunnel_id TEXT NOT NULL,
        path_prefix TEXT NOT NULL,
        local_target TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1,
        priority INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE,
        UNIQUE(tunnel_id, path_prefix)
    );

    CREATE INDEX IF NOT EXISTS idx_network_routes_tunnel ON network_routes(tunnel_id, priority DESC);

    CREATE TABLE IF NOT EXISTS network_events (
        event_id TEXT PRIMARY KEY,
        tunnel_id TEXT NOT NULL,
        level TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT NOT NULL,
        data_json TEXT,
        created_at INTEGER NOT NULL,
        FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_network_events_tunnel ON network_events(tunnel_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_network_events_level ON network_events(level, created_at DESC);

    CREATE TABLE IF NOT EXISTS tunnel_secrets (
        tunnel_id TEXT PRIMARY KEY,
        token TEXT,
        secret_ref TEXT,
        is_migrated INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_ref ON tunnel_secrets(secret_ref);
    CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_migrated ON tunnel_secrets(is_migrated) WHERE is_migrated = 0;
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize NetworkOS store

        Args:
            db_path: Optional custom database path. If None, uses standard component path.
        """
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = str(ensure_db_exists("networkos"))

        self._init_schema()
        logger.info(f"NetworkOS store initialized: {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(self.SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Create database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        return conn

    # Tunnel CRUD

    def create_tunnel(self, tunnel: Tunnel) -> None:
        """Create a new tunnel"""
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO network_tunnels (
                    tunnel_id, provider, name, is_enabled,
                    public_hostname, local_target, mode,
                    health_status, last_heartbeat_at,
                    last_error_code, last_error_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tunnel.tunnel_id,
                tunnel.provider,
                tunnel.name,
                1 if tunnel.is_enabled else 0,
                tunnel.public_hostname,
                tunnel.local_target,
                tunnel.mode,
                tunnel.health_status,
                tunnel.last_heartbeat_at,
                tunnel.last_error_code,
                tunnel.last_error_message,
                tunnel.created_at,
                tunnel.updated_at
            ))
            conn.commit()
            logger.info(f"Created tunnel: {tunnel.tunnel_id}")
        finally:
            conn.close()

    def get_tunnel(self, tunnel_id: str) -> Optional[Tunnel]:
        """Get tunnel by ID"""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM network_tunnels WHERE tunnel_id = ?",
                (tunnel_id,)
            ).fetchone()

            if not row:
                return None

            return Tunnel(
                tunnel_id=row['tunnel_id'],
                provider=row['provider'],
                name=row['name'],
                is_enabled=bool(row['is_enabled']),
                public_hostname=row['public_hostname'],
                local_target=row['local_target'],
                mode=row['mode'],
                health_status=row['health_status'],
                last_heartbeat_at=row['last_heartbeat_at'],
                last_error_code=row['last_error_code'],
                last_error_message=row['last_error_message'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        finally:
            conn.close()

    def list_tunnels(self) -> List[Tunnel]:
        """List all tunnels"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM network_tunnels ORDER BY created_at DESC"
            ).fetchall()

            return [
                Tunnel(
                    tunnel_id=row['tunnel_id'],
                    provider=row['provider'],
                    name=row['name'],
                    is_enabled=bool(row['is_enabled']),
                    public_hostname=row['public_hostname'],
                    local_target=row['local_target'],
                    mode=row['mode'],
                    health_status=row['health_status'],
                    last_heartbeat_at=row['last_heartbeat_at'],
                    last_error_code=row['last_error_code'],
                    last_error_message=row['last_error_message'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]
        finally:
            conn.close()

    def set_enabled(self, tunnel_id: str, enabled: bool) -> None:
        """Enable or disable a tunnel"""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE network_tunnels SET is_enabled = ?, updated_at = ? WHERE tunnel_id = ?",
                (1 if enabled else 0, utc_now_ms(), tunnel_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_health(
        self,
        tunnel_id: str,
        health_status: str,
        error_code: Optional[str],
        error_message: Optional[str]
    ) -> None:
        """Update tunnel health status"""
        conn = self._connect()
        try:
            conn.execute("""
                UPDATE network_tunnels
                SET health_status = ?,
                    last_heartbeat_at = ?,
                    last_error_code = ?,
                    last_error_message = ?,
                    updated_at = ?
                WHERE tunnel_id = ?
            """, (
                health_status,
                utc_now_ms(),
                error_code,
                error_message,
                utc_now_ms(),
                tunnel_id
            ))
            conn.commit()
        finally:
            conn.close()

    def delete_tunnel(self, tunnel_id: str) -> None:
        """Delete a tunnel"""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM network_tunnels WHERE tunnel_id = ?", (tunnel_id,))
            conn.commit()
            logger.info(f"Deleted tunnel: {tunnel_id}")
        finally:
            conn.close()

    # Event Management

    def append_event(self, event: Dict[str, Any]) -> None:
        """Append an event to the log"""
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO network_events (
                    event_id, tunnel_id, level, event_type,
                    message, data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event['event_id'],
                event['tunnel_id'],
                event['level'],
                event['event_type'],
                event['message'],
                event.get('data_json'),
                event['created_at']
            ))
            conn.commit()
        finally:
            conn.close()

    def get_recent_events(self, tunnel_id: str, limit: int = 50) -> List[TunnelEvent]:
        """Get recent events for a tunnel"""
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT * FROM network_events
                WHERE tunnel_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (tunnel_id, limit)).fetchall()

            return [
                TunnelEvent(
                    event_id=row['event_id'],
                    tunnel_id=row['tunnel_id'],
                    level=row['level'],
                    event_type=row['event_type'],
                    message=row['message'],
                    data_json=row['data_json'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
        finally:
            conn.close()

    # Secret Management (v55: secret_ref pattern)

    def save_tunnel_secret_ref(self, tunnel_id: str, secret_ref: str) -> None:
        """Save tunnel secret reference (recommended method)

        Args:
            tunnel_id: Tunnel ID
            secret_ref: Reference to secure storage key (e.g., "networkos:tunnel:cf-abc123")
        """
        now = utc_now_ms()
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO tunnel_secrets (tunnel_id, secret_ref, is_migrated, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(tunnel_id) DO UPDATE SET
                    secret_ref = excluded.secret_ref,
                    is_migrated = 1,
                    updated_at = excluded.updated_at
            """, (tunnel_id, secret_ref, now, now))
            conn.commit()
            logger.info(f"Saved secret_ref for tunnel {tunnel_id}")
        finally:
            conn.close()

    def get_tunnel_secret_ref(self, tunnel_id: str) -> Optional[str]:
        """Get tunnel secret reference

        Returns:
            secret_ref if migrated, None if not found or not migrated
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT secret_ref, is_migrated FROM tunnel_secrets WHERE tunnel_id = ?",
                (tunnel_id,)
            ).fetchone()

            if row and row['is_migrated']:
                return row['secret_ref']
            return None
        finally:
            conn.close()

    def get_tunnel_token_legacy(self, tunnel_id: str) -> Optional[str]:
        """Get tunnel token (DEPRECATED: legacy method)

        ⚠️  DEPRECATED: Only for backward compatibility. New code should use get_tunnel_secret_ref()

        If legacy token is accessed, logs a warning event to encourage migration.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token, is_migrated FROM tunnel_secrets WHERE tunnel_id = ?",
                (tunnel_id,)
            ).fetchone()

            if row and row['token'] and not row['is_migrated']:
                # Log warning event: still using legacy token
                import uuid
                import json
                self.append_event({
                    'event_id': str(uuid.uuid4()),
                    'tunnel_id': tunnel_id,
                    'level': 'warn',
                    'event_type': 'legacy_token_access',
                    'message': f'Tunnel {tunnel_id} still using legacy token storage. Please migrate to secret_ref.',
                    'data_json': None,
                    'created_at': utc_now_ms()
                })
                return row['token']
            return None
        finally:
            conn.close()

    def list_unmigrated_tunnels(self) -> List[str]:
        """Get list of tunnel IDs that haven't been migrated to secret_ref

        Returns:
            List of tunnel_ids still using plaintext token storage
        """
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT tunnel_id FROM tunnel_secrets
                WHERE is_migrated = 0 AND token IS NOT NULL
            """).fetchall()
            return [row['tunnel_id'] for row in rows]
        finally:
            conn.close()

    def migrate_token_to_secret_ref(
        self,
        tunnel_id: str,
        secret_storage_save_fn
    ) -> bool:
        """Migrate legacy token to secret_ref pattern

        Args:
            tunnel_id: Tunnel ID
            secret_storage_save_fn: Function to save to secure storage (key, value) -> None

        Returns:
            True if migrated successfully, False if no token to migrate
        """
        # 1. Read legacy token
        old_token = self.get_tunnel_token_legacy(tunnel_id)
        if not old_token:
            logger.info(f"No legacy token to migrate for tunnel {tunnel_id}")
            return False

        # 2. Generate secret_ref key
        secret_ref = f"networkos:tunnel:{tunnel_id}"

        # 3. Save to secure storage
        try:
            secret_storage_save_fn(secret_ref, old_token)
        except Exception as e:
            logger.error(f"Failed to save to secure storage: {e}")
            raise

        # 4. Update DB with secret_ref
        self.save_tunnel_secret_ref(tunnel_id, secret_ref)

        # 5. Optional: Clear old token (kept for compatibility period)
        # conn.execute("UPDATE tunnel_secrets SET token = NULL WHERE tunnel_id = ?", (tunnel_id,))

        # 6. Record migration event
        import uuid
        import json
        self.append_event({
            'event_id': str(uuid.uuid4()),
            'tunnel_id': tunnel_id,
            'level': 'info',
            'event_type': 'token_migrated',
            'message': f'Tunnel {tunnel_id} migrated from legacy token to secret_ref',
            'data_json': json.dumps({'secret_ref': secret_ref}),
            'created_at': utc_now_ms()
        })

        logger.info(f"Successfully migrated tunnel {tunnel_id} to secret_ref")
        return True

    # Legacy methods (backward compatibility)

    def save_token(self, tunnel_id: str, token: str) -> None:
        """Save tunnel token (DEPRECATED: legacy method)

        ⚠️  DEPRECATED: Use save_tunnel_secret_ref() for new code.
        This method saves tokens in plaintext and is kept only for backward compatibility.
        """
        conn = self._connect()
        try:
            now = utc_now_ms()
            conn.execute("""
                INSERT OR REPLACE INTO tunnel_secrets (
                    tunnel_id, token, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
            """, (tunnel_id, token, now, now))
            conn.commit()
            logger.warning(f"Using legacy save_token for {tunnel_id}. Consider migrating to secret_ref.")
        finally:
            conn.close()

    def get_token(self, tunnel_id: str) -> Optional[str]:
        """Get tunnel token (DEPRECATED: legacy method)

        ⚠️  DEPRECATED: Use get_tunnel_secret_ref() for new code.
        This method returns plaintext tokens and is kept only for backward compatibility.
        """
        return self.get_tunnel_token_legacy(tunnel_id)
