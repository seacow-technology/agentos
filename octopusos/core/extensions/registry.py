"""Extension registry for database operations"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from agentos.core.extensions.exceptions import RegistryError
from agentos.core.extensions.models import (
    ExtensionRecord,
    ExtensionManifest,
    ExtensionStatus,
    InstallSource,
    ExtensionCapability,
    InstallStatus,
    ExtensionInstallRecord,
    ExtensionConfig,
)

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Registry for managing extension database operations"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize registry

        Args:
            db_path: Database file path (optional, defaults to AgentOS registry)
        """
        if db_path is None:
            from agentos.store import get_db_path, ensure_migrations
            db_path = get_db_path()

            # Ensure database schema is up-to-date
            # This is critical for extension tables (extensions, extension_installs, extension_configs)
            # These tables are defined in schema_v33.sql
            try:
                ensure_migrations(db_path)
            except Exception as e:
                logger.warning(f"Failed to ensure migrations: {e}")
                # Don't block initialization, but log the issue

        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _execute_write(self, operation_fn, *args, **kwargs):
        """
        Execute write operation using SQLiteWriter or direct connection

        Args:
            operation_fn: Function that takes conn as first argument
            *args, **kwargs: Additional arguments for operation_fn

        Returns:
            Result from operation_fn
        """
        # For testing with custom db_path, use direct connection
        # For production, use SQLiteWriter
        try:
            from agentos.store import get_db_path
            if self.db_path == get_db_path():
                # Production path: use SQLiteWriter
                from agentos.store import get_writer
                writer = get_writer()

                def wrapped_operation(conn):
                    return operation_fn(conn, *args, **kwargs)

                return writer.submit(wrapped_operation, timeout=10.0)
        except:
            pass

        # Testing path or custom db: use direct connection
        conn = self._get_connection()
        try:
            result = operation_fn(conn, *args, **kwargs)
            return result
        finally:
            conn.close()

    def register_extension(
        self,
        manifest: ExtensionManifest,
        sha256: str,
        source: InstallSource,
        source_url: Optional[str] = None,
        icon_path: Optional[str] = None
    ) -> ExtensionRecord:
        """
        Register a new extension in the database

        Args:
            manifest: Extension manifest
            sha256: SHA256 hash of the zip package
            source: Installation source
            source_url: Original URL (if source is URL)
            icon_path: Path to icon file

        Returns:
            ExtensionRecord

        Raises:
            RegistryError: If registration fails
        """
        logger.info(f"Registering extension: {manifest.id} v{manifest.version}")

        def _insert(conn: sqlite3.Connection):
            try:
                # Check if extension already exists
                cursor = conn.execute(
                    "SELECT id, status FROM extensions WHERE id = ?",
                    (manifest.id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Allow re-registration if previous installation was incomplete
                    if existing['status'] in ('INSTALLING', 'FAILED', 'UNINSTALLED'):
                        logger.info(f"Extension '{manifest.id}' exists with status {existing['status']}, allowing re-registration")
                        # Will be replaced by INSERT OR REPLACE
                    elif existing['status'] == 'INSTALLED':
                        # Extension is properly installed - this is likely a duplicate call
                        logger.warning(f"Extension '{manifest.id}' is already properly installed, skipping registration")
                        # Continue anyway - INSERT OR REPLACE will update it
                        # This makes the operation idempotent
                    else:
                        logger.warning(f"Extension '{manifest.id}' has unknown status: {existing['status']}")

                # Prepare JSON fields
                permissions_json = json.dumps(manifest.permissions_required)
                capabilities_json = json.dumps(
                    [cap.model_dump() for cap in manifest.capabilities]
                )
                metadata_json = json.dumps({
                    'author': manifest.author,
                    'license': manifest.license,
                    'platforms': manifest.platforms,
                })

                # Insert or replace extension record
                conn.execute("""
                    INSERT OR REPLACE INTO extensions (
                        id, name, version, description, icon_path,
                        installed_at, enabled, status,
                        sha256, source, source_url,
                        permissions_required, capabilities, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    manifest.id,
                    manifest.name,
                    manifest.version,
                    manifest.description,
                    icon_path or manifest.icon,
                    datetime.now().isoformat(),
                    True,  # enabled by default
                    ExtensionStatus.INSTALLED.value,
                    sha256,
                    source.value,
                    source_url,
                    permissions_json,
                    capabilities_json,
                    metadata_json,
                ))

                conn.commit()

                logger.info(f"Extension registered successfully: {manifest.id}")

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to register extension: {e}")

        self._execute_write(_insert)

        # Return the registered record
        return self.get_extension(manifest.id)

    def get_extension(self, extension_id: str) -> Optional[ExtensionRecord]:
        """
        Get extension by ID

        Args:
            extension_id: Extension ID

        Returns:
            ExtensionRecord or None if not found
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute(
                "SELECT * FROM extensions WHERE id = ?",
                (extension_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_extension_record(row)

        finally:
            conn.close()

    def list_extensions(
        self,
        enabled_only: bool = False,
        status_filter: Optional[ExtensionStatus] = None
    ) -> List[ExtensionRecord]:
        """
        List all extensions

        Args:
            enabled_only: Only return enabled extensions
            status_filter: Filter by status

        Returns:
            List of ExtensionRecord
        """
        conn = self._get_connection()

        try:
            query = "SELECT * FROM extensions WHERE 1=1"
            params = []

            if enabled_only:
                query += " AND enabled = ?"
                params.append(True)

            if status_filter:
                query += " AND status = ?"
                params.append(status_filter.value)

            query += " ORDER BY name"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_extension_record(row) for row in rows]

        finally:
            conn.close()

    def set_status(self, extension_id: str, status: ExtensionStatus) -> None:
        """
        Set extension status

        Args:
            extension_id: Extension ID
            status: New status

        Raises:
            RegistryError: If operation fails
        """
        logger.info(f"Setting extension status: {extension_id} -> {status.value}")

        def _update(conn: sqlite3.Connection):
            try:
                cursor = conn.execute(
                    "UPDATE extensions SET status = ? WHERE id = ?",
                    (status.value, extension_id)
                )

                if cursor.rowcount == 0:
                    raise RegistryError(f"Extension not found: {extension_id}")

                conn.commit()

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to set extension status: {e}")

        self._execute_write(_update)

    def set_enabled(self, extension_id: str, enabled: bool) -> None:
        """
        Set extension enabled state

        Args:
            extension_id: Extension ID
            enabled: True to enable, False to disable

        Raises:
            RegistryError: If operation fails
        """
        action = "Enabling" if enabled else "Disabling"
        logger.info(f"{action} extension: {extension_id}")

        def _update(conn: sqlite3.Connection):
            try:
                cursor = conn.execute(
                    "UPDATE extensions SET enabled = ? WHERE id = ?",
                    (enabled, extension_id)
                )

                if cursor.rowcount == 0:
                    raise RegistryError(f"Extension not found: {extension_id}")

                conn.commit()
                logger.info(f"Extension {action.lower()}: {extension_id}")

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to {action.lower()} extension: {e}")

        self._execute_write(_update)

    def enable_extension(self, extension_id: str) -> None:
        """
        Enable an extension

        Args:
            extension_id: Extension ID

        Raises:
            RegistryError: If operation fails
        """
        self.set_enabled(extension_id, True)

    def disable_extension(self, extension_id: str) -> None:
        """
        Disable an extension

        Args:
            extension_id: Extension ID

        Raises:
            RegistryError: If operation fails
        """
        self.set_enabled(extension_id, False)

    def uninstall_extension(self, extension_id: str) -> None:
        """
        Mark extension as uninstalled

        Args:
            extension_id: Extension ID

        Raises:
            RegistryError: If operation fails
        """
        logger.info(f"Marking extension as uninstalled: {extension_id}")

        def _update(conn: sqlite3.Connection):
            try:
                cursor = conn.execute("""
                    UPDATE extensions
                    SET status = ?, enabled = ?
                    WHERE id = ?
                """, (ExtensionStatus.UNINSTALLED.value, False, extension_id))

                if cursor.rowcount == 0:
                    raise RegistryError(f"Extension not found: {extension_id}")

                conn.commit()
                logger.info(f"Extension marked as uninstalled: {extension_id}")

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to uninstall extension: {e}")

        self._execute_write(_update)

    def unregister_extension(self, extension_id: str) -> None:
        """
        Completely remove extension from registry (used during uninstall)

        Args:
            extension_id: Extension ID

        Raises:
            RegistryError: If operation fails
        """
        logger.info(f"Unregistering extension from database: {extension_id}")

        def _delete(conn: sqlite3.Connection):
            try:
                # Delete from extensions table
                cursor = conn.execute(
                    "DELETE FROM extensions WHERE id = ?",
                    (extension_id,)
                )

                if cursor.rowcount == 0:
                    raise RegistryError(f"Extension not found: {extension_id}")

                # Also delete any config records
                conn.execute(
                    "DELETE FROM extension_configs WHERE extension_id = ?",
                    (extension_id,)
                )

                conn.commit()
                logger.info(f"Extension unregistered: {extension_id}")

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to unregister extension: {e}")

        self._execute_write(_delete)

    def get_enabled_capabilities(self) -> List[Dict[str, Any]]:
        """
        Get all capabilities from enabled extensions

        Returns:
            List of capability dictionaries with extension_id
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute("""
                SELECT id, capabilities
                FROM extensions
                WHERE enabled = ? AND status = ?
            """, (True, ExtensionStatus.INSTALLED.value))

            rows = cursor.fetchall()

            all_capabilities = []
            for row in rows:
                extension_id = row['id']
                capabilities_json = row['capabilities']

                try:
                    capabilities = json.loads(capabilities_json)
                    for cap in capabilities:
                        cap['extension_id'] = extension_id
                        all_capabilities.append(cap)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse capabilities for {extension_id}: {e}"
                    )

            return all_capabilities

        finally:
            conn.close()

    def create_install_record(
        self,
        install_id: str,
        extension_id: str,
        status: InstallStatus = InstallStatus.INSTALLING
    ) -> ExtensionInstallRecord:
        """
        Create installation progress record

        Args:
            install_id: Unique install ID
            extension_id: Extension ID (must exist in extensions table)
            status: Initial status

        Returns:
            ExtensionInstallRecord

        Raises:
            RegistryError: If creation fails
        """
        logger.info(f"Creating install record: {install_id} for {extension_id}")

        def _insert(conn: sqlite3.Connection):
            try:
                conn.execute("""
                    INSERT INTO extension_installs (
                        install_id, extension_id, status, progress, started_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    install_id,
                    extension_id,
                    status.value,
                    0,
                    datetime.now().isoformat(),
                ))

                conn.commit()

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to create install record: {e}")

        self._execute_write(_insert)

        # Return the created record
        return self.get_install_record(install_id)

    def create_install_record_without_fk(
        self,
        install_id: str,
        extension_id: str = "unknown",
        status: InstallStatus = InstallStatus.INSTALLING
    ) -> None:
        """
        Create installation record without foreign key constraint
        (for early creation before extension is validated)

        Args:
            install_id: Unique install ID
            extension_id: Extension ID (can be placeholder)
            status: Initial status
        """
        logger.info(f"Creating install record (no FK check): {install_id}")

        def _insert(conn: sqlite3.Connection):
            try:
                # Temporarily disable foreign key checks
                conn.execute("PRAGMA foreign_keys = OFF")

                conn.execute("""
                    INSERT INTO extension_installs (
                        install_id, extension_id, status, progress, started_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    install_id,
                    extension_id,
                    status.value,
                    0,
                    datetime.now().isoformat(),
                ))

                conn.commit()

                # Re-enable foreign key checks
                conn.execute("PRAGMA foreign_keys = ON")

            except sqlite3.Error as e:
                logger.error(f"Failed to create install record: {e}")
                raise RegistryError(f"Failed to create install record: {e}")

        self._execute_write(_insert)

    def update_install_progress(
        self,
        install_id: str,
        progress: int,
        current_step: Optional[str] = None,
        extension_id: Optional[str] = None
    ) -> None:
        """
        Update installation progress

        Args:
            install_id: Install ID
            progress: Progress percentage (0-100)
            current_step: Current step description
            extension_id: Optional extension ID to update (once manifest is extracted)

        Raises:
            RegistryError: If update fails
        """
        def _update(conn: sqlite3.Connection):
            try:
                if extension_id is not None:
                    # When updating extension_id, temporarily disable foreign key checks
                    # This is needed because the extension record might not exist yet
                    # (created later in the installation process)
                    conn.execute("PRAGMA foreign_keys = OFF")

                    # Update extension_id, progress, and current_step
                    conn.execute("""
                        UPDATE extension_installs
                        SET extension_id = ?, progress = ?, current_step = ?
                        WHERE install_id = ?
                    """, (extension_id, progress, current_step, install_id))

                    conn.commit()

                    # Re-enable foreign key checks
                    conn.execute("PRAGMA foreign_keys = ON")
                else:
                    # Update only progress and current_step
                    conn.execute("""
                        UPDATE extension_installs
                        SET progress = ?, current_step = ?
                        WHERE install_id = ?
                    """, (progress, current_step, install_id))

                    conn.commit()

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to update install progress: {e}")

        self._execute_write(_update)

    def complete_install(
        self,
        install_id: str,
        status: InstallStatus,
        error: Optional[str] = None
    ) -> None:
        """
        Mark installation as complete

        Args:
            install_id: Install ID
            status: Final status (COMPLETED or FAILED)
            error: Error message if failed

        Raises:
            RegistryError: If update fails
        """
        logger.info(f"Completing install {install_id} with status {status.value}")

        def _update(conn: sqlite3.Connection):
            try:
                conn.execute("""
                    UPDATE extension_installs
                    SET status = ?, ended_at = ?, error = ?, progress = ?
                    WHERE install_id = ?
                """, (
                    status.value,
                    datetime.now().isoformat(),
                    error,
                    100 if status == InstallStatus.COMPLETED else None,
                    install_id
                ))

                conn.commit()

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to complete install: {e}")

        self._execute_write(_update)

    def get_install_record(self, install_id: str) -> Optional[ExtensionInstallRecord]:
        """
        Get installation record by ID

        Args:
            install_id: Install ID

        Returns:
            ExtensionInstallRecord or None
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute(
                "SELECT * FROM extension_installs WHERE install_id = ?",
                (install_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return ExtensionInstallRecord(
                install_id=row['install_id'],
                extension_id=row['extension_id'],
                status=InstallStatus(row['status']),
                progress=row['progress'] if row['progress'] is not None else 0,
                current_step=row['current_step'],
                started_at=datetime.fromisoformat(row['started_at']),
                ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                error=row['error'],
            )

        finally:
            conn.close()

    def get_config(self, extension_id: str) -> Optional[ExtensionConfig]:
        """
        Get extension configuration

        Args:
            extension_id: Extension ID

        Returns:
            ExtensionConfig or None if not found
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute(
                "SELECT * FROM extension_configs WHERE extension_id = ?",
                (extension_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            config_json = json.loads(row['config_json']) if row['config_json'] else None

            return ExtensionConfig(
                extension_id=row['extension_id'],
                config_json=config_json,
                secrets_ref=row['secrets_ref'],
                updated_at=datetime.fromisoformat(row['updated_at']),
            )

        finally:
            conn.close()

    def save_config(self, extension_id: str, config: Dict[str, Any]) -> None:
        """
        Save extension configuration

        Args:
            extension_id: Extension ID
            config: Configuration dictionary

        Raises:
            RegistryError: If operation fails
        """
        logger.info(f"Saving configuration for extension: {extension_id}")

        def _upsert(conn: sqlite3.Connection):
            try:
                # Check if extension exists
                cursor = conn.execute(
                    "SELECT id FROM extensions WHERE id = ?",
                    (extension_id,)
                )
                if not cursor.fetchone():
                    raise RegistryError(f"Extension not found: {extension_id}")

                # Upsert configuration
                config_json = json.dumps(config)
                conn.execute("""
                    INSERT INTO extension_configs (extension_id, config_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(extension_id) DO UPDATE SET
                        config_json = excluded.config_json,
                        updated_at = excluded.updated_at
                """, (extension_id, config_json, datetime.now().isoformat()))

                conn.commit()
                logger.info(f"Configuration saved for extension: {extension_id}")

            except sqlite3.Error as e:
                raise RegistryError(f"Failed to save configuration: {e}")

        self._execute_write(_upsert)

    def _row_to_extension_record(self, row: sqlite3.Row) -> ExtensionRecord:
        """Convert database row to ExtensionRecord"""
        try:
            permissions = json.loads(row['permissions_required']) if row['permissions_required'] else []
            capabilities_data = json.loads(row['capabilities']) if row['capabilities'] else []
            capabilities = [ExtensionCapability(**cap) for cap in capabilities_data]
            metadata = json.loads(row['metadata']) if row['metadata'] else None

            return ExtensionRecord(
                id=row['id'],
                name=row['name'],
                version=row['version'],
                description=row['description'],
                icon_path=row['icon_path'],
                installed_at=datetime.fromisoformat(row['installed_at']),
                enabled=bool(row['enabled']),
                status=ExtensionStatus(row['status']),
                sha256=row['sha256'],
                source=InstallSource(row['source']),
                source_url=row['source_url'],
                permissions_required=permissions,
                capabilities=capabilities,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to parse extension record: {e}")
            raise RegistryError(f"Invalid extension record in database: {e}")
