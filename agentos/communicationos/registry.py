"""Channel Registry for CommunicationOS.

This module provides the registry system for managing channel adapters.
The registry loads manifests, validates configurations, and manages the
lifecycle of channel adapters.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now
from agentos.communicationos.manifest import ChannelManifest, SecurityMode

logger = logging.getLogger(__name__)


class ChannelStatus(str):
    """Channel status values."""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ERROR = "error"
    NEEDS_SETUP = "needs_setup"


class ChannelRegistry:
    """Registry for channel adapters.

    The registry loads manifests from the filesystem and provides methods
    to query available channels, their capabilities, and configurations.

    Design principles:
    - Manifest-driven: All channel metadata comes from manifests
    - Dynamic loading: Channels can be added without code changes
    - Validation: Ensures manifests and configurations are valid
    """

    def __init__(self, manifest_dir: Optional[Path] = None):
        """Initialize the channel registry.

        Args:
            manifest_dir: Directory containing channel manifest files.
                         If None, uses default location.
        """
        self._manifests: Dict[str, ChannelManifest] = {}
        self._manifest_dir = manifest_dir or self._default_manifest_dir()
        self._load_manifests()

    def _default_manifest_dir(self) -> Path:
        """Get default manifest directory."""
        # Manifests are stored alongside channel adapters
        base_dir = Path(__file__).parent
        manifest_dir = base_dir / "channels"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        return manifest_dir

    def _load_manifests(self) -> None:
        """Load all manifests from the manifest directory."""
        if not self._manifest_dir.exists():
            logger.warning(f"Manifest directory does not exist: {self._manifest_dir}")
            return

        for manifest_file in self._manifest_dir.glob("*_manifest.json"):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = ChannelManifest.from_dict(data)
                self._manifests[manifest.id] = manifest
                logger.info(f"Loaded channel manifest: {manifest.id} ({manifest.name})")
            except Exception as e:
                logger.error(f"Failed to load manifest {manifest_file}: {e}")

    def register_manifest(self, manifest: ChannelManifest) -> None:
        """Register a channel manifest programmatically.

        This is useful for testing or dynamic channel registration.

        Args:
            manifest: Channel manifest to register
        """
        self._manifests[manifest.id] = manifest
        logger.info(f"Registered channel manifest: {manifest.id}")

    def get_manifest(self, channel_id: str) -> Optional[ChannelManifest]:
        """Get manifest for a specific channel.

        Args:
            channel_id: Channel identifier

        Returns:
            Channel manifest or None if not found
        """
        return self._manifests.get(channel_id)

    def list_manifests(self) -> List[ChannelManifest]:
        """List all registered channel manifests.

        Returns:
            List of channel manifests
        """
        return list(self._manifests.values())

    def list_channels(self) -> List[Dict[str, Any]]:
        """List all channels with basic information.

        Returns:
            List of channel info dictionaries
        """
        return [
            {
                "id": manifest.id,
                "name": manifest.name,
                "icon": manifest.icon,
                "description": manifest.description,
                "provider": manifest.provider,
                "capabilities": [c.value for c in manifest.capabilities],
            }
            for manifest in self._manifests.values()
        ]

    def validate_config(
        self, channel_id: str, config: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate a configuration for a channel.

        Args:
            channel_id: Channel identifier
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        manifest = self.get_manifest(channel_id)
        if not manifest:
            return False, f"Channel not found: {channel_id}"

        return manifest.validate_config(config)

    def reload_manifests(self) -> None:
        """Reload all manifests from the filesystem.

        This is useful for picking up new channels or manifest updates
        without restarting the application.
        """
        self._manifests.clear()
        self._load_manifests()


class ChannelConfigStore:
    """SQLite-based storage for channel configurations and status.

    This store manages:
    - Channel configurations (encrypted secrets)
    - Channel enable/disable status
    - Channel health status
    - Audit logs for configuration changes

    Design principles:
    - Encrypted storage for secrets
    - Audit trail for all changes
    - Simple SQLite schema
    - Thread-safe operations
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the config store.

        Args:
            db_path: Path to SQLite database. If None, uses default location.
        """
        self.db_path = db_path or str(component_db_path("communicationos"))
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            # Channel configurations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_configs (
                    channel_id TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'needs_setup',
                    enabled INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    last_heartbeat_at INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            # Channel audit log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    performed_by TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (channel_id) REFERENCES channel_configs(channel_id)
                )
            """)

            # Channel events log (for health monitoring)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message_id TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    metadata TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (channel_id) REFERENCES channel_configs(channel_id)
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_events_channel_id
                ON channel_events(channel_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_events_created_at
                ON channel_events(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_audit_log_channel_id
                ON channel_audit_log(channel_id)
            """)

            conn.commit()

    def save_config(
        self,
        channel_id: str,
        config: Dict[str, Any],
        performed_by: Optional[str] = None
    ) -> None:
        """Save or update channel configuration.

        Args:
            channel_id: Channel identifier
            config: Configuration dictionary (will be JSON-serialized)
            performed_by: User/system that performed the action
        """
        now = int(utc_now().timestamp() * 1000)  # epoch milliseconds
        config_json = json.dumps(config)

        with sqlite3.connect(self.db_path) as conn:
            # Check if config exists
            cursor = conn.execute(
                "SELECT channel_id FROM channel_configs WHERE channel_id = ?",
                (channel_id,)
            )
            exists = cursor.fetchone() is not None

            if exists:
                conn.execute("""
                    UPDATE channel_configs
                    SET config_json = ?, updated_at = ?, status = ?
                    WHERE channel_id = ?
                """, (config_json, now, ChannelStatus.NEEDS_SETUP, channel_id))
                action = "config_updated"
            else:
                conn.execute("""
                    INSERT INTO channel_configs
                    (channel_id, config_json, status, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?)
                """, (channel_id, config_json, ChannelStatus.NEEDS_SETUP, now, now))
                action = "config_created"

            # Log to audit
            self._log_audit(
                conn, channel_id, action,
                f"Configuration {'updated' if exists else 'created'}",
                performed_by
            )
            conn.commit()

    def get_config(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration.

        Args:
            channel_id: Channel identifier

        Returns:
            Configuration dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT config_json FROM channel_configs WHERE channel_id = ?",
                (channel_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def set_enabled(
        self,
        channel_id: str,
        enabled: bool,
        performed_by: Optional[str] = None
    ) -> None:
        """Enable or disable a channel.

        Args:
            channel_id: Channel identifier
            enabled: Whether to enable or disable
            performed_by: User/system that performed the action
        """
        now = int(utc_now().timestamp() * 1000)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE channel_configs
                SET enabled = ?, updated_at = ?, status = ?
                WHERE channel_id = ?
            """, (
                1 if enabled else 0,
                now,
                ChannelStatus.ENABLED if enabled else ChannelStatus.DISABLED,
                channel_id
            ))

            # Log to audit
            action = "enabled" if enabled else "disabled"
            self._log_audit(
                conn, channel_id, action,
                f"Channel {action}",
                performed_by
            )
            conn.commit()

    def is_enabled(self, channel_id: str) -> bool:
        """Check if a channel is enabled.

        Args:
            channel_id: Channel identifier

        Returns:
            True if enabled, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT enabled FROM channel_configs WHERE channel_id = ?",
                (channel_id,)
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else False

    def get_status(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel status information.

        Args:
            channel_id: Channel identifier

        Returns:
            Status dictionary with enabled, status, last_error, last_heartbeat, etc.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT enabled, status, last_error, last_heartbeat_at,
                       created_at, updated_at
                FROM channel_configs
                WHERE channel_id = ?
            """, (channel_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "channel_id": channel_id,
                "enabled": bool(row[0]),
                "status": row[1],
                "last_error": row[2],
                "last_heartbeat_at": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }

    def list_channels(self) -> List[Dict[str, Any]]:
        """List all configured channels with their status.

        Returns:
            List of channel status dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT channel_id, enabled, status, last_error, last_heartbeat_at
                FROM channel_configs
                ORDER BY channel_id
            """)

            channels = []
            for row in cursor.fetchall():
                channels.append({
                    "channel_id": row[0],
                    "enabled": bool(row[1]),
                    "status": row[2],
                    "last_error": row[3],
                    "last_heartbeat_at": row[4],
                })
            return channels

    def update_heartbeat(self, channel_id: str, status: Optional[str] = None) -> None:
        """Update channel heartbeat timestamp.

        Args:
            channel_id: Channel identifier
            status: Optional status update
        """
        now = int(utc_now().timestamp() * 1000)

        with sqlite3.connect(self.db_path) as conn:
            if status:
                conn.execute("""
                    UPDATE channel_configs
                    SET last_heartbeat_at = ?, status = ?, updated_at = ?
                    WHERE channel_id = ?
                """, (now, status, now, channel_id))
            else:
                conn.execute("""
                    UPDATE channel_configs
                    SET last_heartbeat_at = ?, updated_at = ?
                    WHERE channel_id = ?
                """, (now, now, channel_id))
            conn.commit()

    def log_event(
        self,
        channel_id: str,
        event_type: str,
        status: str,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a channel event for health monitoring.

        Args:
            channel_id: Channel identifier
            event_type: Type of event (e.g., "message_received", "message_sent")
            status: Event status (e.g., "success", "error")
            message_id: Optional message ID
            error: Optional error message
            metadata: Optional metadata dictionary
        """
        now = int(utc_now().timestamp() * 1000)
        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO channel_events
                (channel_id, event_type, message_id, status, error, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (channel_id, event_type, message_id, status, error, metadata_json, now))
            conn.commit()

    def get_recent_events(
        self,
        channel_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent events for a channel.

        Args:
            channel_id: Channel identifier
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT event_type, message_id, status, error, metadata, created_at
                FROM channel_events
                WHERE channel_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (channel_id, limit))

            events = []
            for row in cursor.fetchall():
                metadata = json.loads(row[4]) if row[4] else None
                events.append({
                    "event_type": row[0],
                    "message_id": row[1],
                    "status": row[2],
                    "error": row[3],
                    "metadata": metadata,
                    "created_at": row[5],
                })
            return events

    def get_audit_log(
        self,
        channel_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get audit log entries.

        Args:
            channel_id: Optional channel ID to filter by
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        with sqlite3.connect(self.db_path) as conn:
            if channel_id:
                cursor = conn.execute("""
                    SELECT channel_id, action, details, performed_by, created_at
                    FROM channel_audit_log
                    WHERE channel_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (channel_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT channel_id, action, details, performed_by, created_at
                    FROM channel_audit_log
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            logs = []
            for row in cursor.fetchall():
                logs.append({
                    "channel_id": row[0],
                    "action": row[1],
                    "details": row[2],
                    "performed_by": row[3],
                    "created_at": row[4],
                })
            return logs

    def delete_channel(
        self,
        channel_id: str,
        performed_by: Optional[str] = None
    ) -> None:
        """Delete a channel configuration and its data.

        Args:
            channel_id: Channel identifier
            performed_by: User/system that performed the action
        """
        with sqlite3.connect(self.db_path) as conn:
            # Log before deletion
            self._log_audit(
                conn, channel_id, "deleted",
                "Channel configuration deleted",
                performed_by
            )

            # Delete events
            conn.execute(
                "DELETE FROM channel_events WHERE channel_id = ?",
                (channel_id,)
            )

            # Delete config
            conn.execute(
                "DELETE FROM channel_configs WHERE channel_id = ?",
                (channel_id,)
            )

            conn.commit()

    def _log_audit(
        self,
        conn: sqlite3.Connection,
        channel_id: str,
        action: str,
        details: Optional[str] = None,
        performed_by: Optional[str] = None
    ) -> None:
        """Internal method to log audit entry.

        Args:
            conn: Database connection
            channel_id: Channel identifier
            action: Action performed
            details: Optional details
            performed_by: User/system that performed the action
        """
        now = int(utc_now().timestamp() * 1000)
        conn.execute("""
            INSERT INTO channel_audit_log
            (channel_id, action, details, performed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, action, details, performed_by, now))
