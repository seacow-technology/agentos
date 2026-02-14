"""
Capability Registry - Central management for OctopusOS v3 capabilities

This is the core registry that:
1. Loads all 27 capability definitions at startup
2. Manages capability grants to agents
3. Performs permission checks (< 10ms with cache)
4. Validates capability definition completeness
5. Provides SQLite persistence

Design Philosophy:
- Singleton pattern for global access
- LRU cache for permission checks (60s TTL)
- Fail-safe defaults (unknown agent → no permissions)
- Complete audit trail of all checks

Performance Targets:
- Permission check: < 10ms (cached)
- Grant operation: < 20ms
- Bulk query: < 100ms for 1000 grants
"""

import sqlite3
import json
import logging
import os
from typing import Dict, List, Optional, Set
from functools import lru_cache
from datetime import datetime, timedelta
from pathlib import Path

from octopusos.core.capability.models import (
    CapabilityDefinition,
    CapabilityGrant,
    CapabilityDomain,
    CapabilityLevel,
    get_default_capabilities,
    validate_capability_definition,
)
from octopusos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


class PermissionDenied(Exception):
    """
    Raised when an agent attempts an operation without required capability.

    Attributes:
        agent_id: Agent identifier
        capability_id: Required capability
        operation: Operation attempted
        reason: Why denied
    """

    def __init__(self, agent_id: str, capability_id: str, operation: str, reason: str):
        self.agent_id = agent_id
        self.capability_id = capability_id
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"Permission denied: Agent '{agent_id}' cannot perform '{operation}' "
            f"on capability '{capability_id}'. Reason: {reason}"
        )


class CapabilityRegistry:
    """
    Central capability registry for OctopusOS v3.

    This singleton manages:
    - 27 atomic capability definitions
    - Agent capability grants
    - Permission checks with caching
    - Complete audit trail

    Usage:
        registry = CapabilityRegistry.get_instance()
        registry.load_definitions()  # Load 27 capabilities
        registry.grant_capability(agent_id="chat_agent", capability_id="state.memory.read", ...)
        has_perm = registry.has_capability(agent_id="chat_agent", capability_id="state.memory.read")
    """

    _instance: Optional["CapabilityRegistry"] = None
    _lock = None  # Will be threading.Lock() if needed

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize registry.

        Args:
            db_path: Path to SQLite database (default: store/registry.sqlite)
        """
        if db_path is None:
            from octopusos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        self._definitions: Dict[str, CapabilityDefinition] = {}
        # Execution alias map is the SoT for WebUI execution surfaces (SSH/SFTP/shell/logs).
        # Keep this separate from the v3 "27 atomic capabilities" list.
        self._execution_alias_index: Dict[str, str] = {}
        self._cache_enabled = True
        self._cache_ttl_seconds = 60
        self._execution_alias_meta: Dict[str, Dict[str, object]] = {}
        self._execution_alias_source: Dict[str, str] = {}

        # Ensure schema exists
        self._ensure_schema()

        logger.info(f"CapabilityRegistry initialized with db: {db_path}")

        # Keep singleton in sync for callers using get_capability_registry()
        if CapabilityRegistry._instance is None or CapabilityRegistry._instance.db_path != self.db_path:
            CapabilityRegistry._instance = self

        # Execution alias resolution is independently loadable (does not require schema migrations).
        # Keep it best-effort and never fail registry initialization.
        try:
            self.load_execution_aliases()
        except Exception as e:
            logger.warning(f"Failed to load execution aliases: {e}")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "CapabilityRegistry":
        """
        Get singleton instance.

        Args:
            db_path: Optional database path (only used on first call)

        Returns:
            Singleton CapabilityRegistry instance
        """
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def _ensure_schema(self):
        """Ensure v47 schema tables exist"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if capability_definitions table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='capability_definitions'"
        )
        if cursor.fetchone() is None:
            logger.warning(
                "Schema v47 tables not found. Creating minimal schema for tests."
            )
            conn.close()
            self._create_minimal_schema()
            return
        conn.close()

    def _create_minimal_schema(self) -> None:
        """Create minimal capability registry schema for testing."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_definitions (
                capability_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                level TEXT NOT NULL,
                version TEXT NOT NULL,
                definition_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_grants (
                grant_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                granted_by TEXT NOT NULL,
                granted_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER,
                scope TEXT,
                reason TEXT,
                metadata TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_invocations (
                invocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT,
                context_json TEXT,
                timestamp_ms INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_grant_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                grant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                changed_at_ms INTEGER NOT NULL,
                reason TEXT,
                metadata TEXT
            )
            """
        )

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass
        return conn

    # ===================================================================
    # Capability Definition Management
    # ===================================================================

    def load_definitions(self, definitions: Optional[List[CapabilityDefinition]] = None):
        """
        Load capability definitions into registry.

        This should be called at startup to load all 27 capabilities.

        Args:
            definitions: List of capability definitions (default: load all 27 from models)

        Raises:
            ValueError: If any definition is invalid
        """
        if definitions is None:
            definitions = get_default_capabilities()

        logger.info(f"Loading {len(definitions)} capability definitions")

        conn = self._get_connection()
        cursor = conn.cursor()

        loaded_count = 0
        for cap_def in definitions:
            # Validate definition
            is_valid, error = validate_capability_definition(cap_def)
            if not is_valid:
                raise ValueError(f"Invalid capability definition: {error}")

            # Store in memory
            self._definitions[cap_def.capability_id] = cap_def

            # Store in database
            definition_json = cap_def.model_dump_json()
            created_at_ms = utc_now_ms()

            cursor.execute(
                """
                INSERT OR REPLACE INTO capability_definitions (
                    capability_id, domain, level, version, definition_json, created_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cap_def.capability_id,
                    cap_def.domain.value,
                    cap_def.level.value,
                    cap_def.version,
                    definition_json,
                    created_at_ms,
                ),
            )
            loaded_count += 1

        conn.commit()
        conn.close()

    # ===================================================================
    # Execution Alias Resolution (builtin < file < db)
    # ===================================================================

    @staticmethod
    def _builtin_execution_aliases() -> Dict[str, Dict[str, object]]:
        # Single stable default, same as execution_aliases.default.json
        return {
            "ssh.exec": {
                "capability_id": "action.network.call",
                "requires_trust": True,
                "requires_confirm": False,
                "source": "builtin",
            },
            "sftp.transfer": {
                "capability_id": "action.file.write",
                "requires_trust": True,
                "requires_confirm": True,
                "source": "builtin",
            },
            "local.shell": {
                "capability_id": "action.execute",
                "requires_trust": False,
                "requires_confirm": False,
                "source": "builtin",
            },
            "logs.query": {
                "capability_id": "evidence.query",
                "requires_trust": False,
                "requires_confirm": False,
                "source": "builtin",
            },
        }

    @staticmethod
    def _default_execution_aliases_path() -> Path:
        return Path(__file__).with_name("execution_aliases.default.json")

    def _read_execution_aliases_file(self) -> Dict[str, Dict[str, object]]:
        path = (os.getenv("OCTO_EXECUTION_ALIASES_PATH") or "").strip()
        p = Path(path) if path else self._default_execution_aliases_path()
        if not p.exists():
            return {}
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("execution aliases file must be a JSON object")
        if int(raw.get("version") or 0) != 1:
            raise ValueError("execution aliases file version must be 1")
        aliases = raw.get("aliases")
        if not isinstance(aliases, list):
            raise ValueError("execution aliases file must contain 'aliases' list")

        out: Dict[str, Dict[str, object]] = {}
        for item in aliases:
            if not isinstance(item, dict):
                continue
            alias = str(item.get("alias") or "").strip()
            capability_id = str(item.get("capability_id") or "").strip()
            if not alias or not capability_id:
                continue
            out[alias] = {
                "capability_id": capability_id,
                "requires_trust": bool(item.get("requires_trust", False)),
                "requires_confirm": bool(item.get("requires_confirm", False)),
                "source": "file",
            }
        return out

    def _read_execution_aliases_db(self) -> Dict[str, Dict[str, object]]:
        # DB layer is optional: if table doesn't exist, treat as empty.
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_aliases'"
            )
            if cur.fetchone() is None:
                return {}

            rows = cur.execute(
                "SELECT alias, capability_id, requires_trust, requires_confirm FROM execution_aliases"
            ).fetchall()
            out: Dict[str, Dict[str, object]] = {}
            for r in rows:
                try:
                    alias = str(r["alias"]).strip()
                    cap_id = str(r["capability_id"]).strip()
                    if not alias or not cap_id:
                        continue
                    out[alias] = {
                        "capability_id": cap_id,
                        "requires_trust": bool(int(r["requires_trust"] or 0)),
                        "requires_confirm": bool(int(r["requires_confirm"] or 0)),
                        "source": "db",
                    }
                except Exception:
                    continue
            return out
        finally:
            if conn is not None:
                conn.close()

    def load_execution_aliases(self) -> None:
        """Load execution aliases with priority: builtin < file < db.

        Contract:
        - Invalid inputs are ignored (and logged) rather than crashing startup.
        - If a higher-priority source is invalid, it does not erase the last-known-good map.
        """
        # Ensure definitions are present for validation.
        if not self._definitions:
            try:
                self.load_definitions()
            except Exception as e:
                logger.warning(f"Cannot validate execution aliases without v3 definitions: {e}")

        base = self._builtin_execution_aliases()
        merged: Dict[str, Dict[str, object]] = dict(base)

        # file overrides builtin
        try:
            for k, v in self._read_execution_aliases_file().items():
                merged[k] = v
        except Exception as e:
            logger.warning(f"Failed to load execution aliases from file: {e}")

        # db overrides file
        try:
            for k, v in self._read_execution_aliases_db().items():
                merged[k] = v
        except Exception as e:
            logger.warning(f"Failed to load execution aliases from db: {e}")

        # Validate: only keep aliases pointing to known v3 capability_ids.
        valid_index: Dict[str, str] = {}
        valid_meta: Dict[str, Dict[str, object]] = {}
        valid_source: Dict[str, str] = {}
        for alias, cfg in merged.items():
            cap_id = str(cfg.get("capability_id") or "").strip()
            if not cap_id:
                continue
            if self._definitions and cap_id not in self._definitions:
                logger.warning(
                    f"Invalid execution alias mapping ignored: {alias} -> {cap_id} (unknown v3 capability_id)"
                )
                continue
            valid_index[alias] = cap_id
            valid_meta[alias] = {
                "requires_trust": bool(cfg.get("requires_trust", False)),
                "requires_confirm": bool(cfg.get("requires_confirm", False)),
            }
            valid_source[alias] = str(cfg.get("source") or "builtin")

        # Only swap in after successful merge+validate to keep last-known-good.
        self._execution_alias_index = valid_index
        self._execution_alias_meta = valid_meta
        self._execution_alias_source = valid_source

    def resolve_execution_alias(self, execution_alias: str) -> Optional[Dict[str, object]]:
        alias = str(execution_alias or "").strip()
        if not alias:
            return None
        if not self._execution_alias_index:
            self.load_execution_aliases()
        cap_id = self._execution_alias_index.get(alias)
        if not cap_id:
            return None
        meta = self._execution_alias_meta.get(alias) or {}
        return {
            "alias": alias,
            "capability_id": cap_id,
            "requires_trust": bool(meta.get("requires_trust", False)),
            "requires_confirm": bool(meta.get("requires_confirm", False)),
            "source": self._execution_alias_source.get(alias, "builtin"),
        }

    def get_execution_definition(self, execution_alias: str) -> Optional[CapabilityDefinition]:
        resolved = self.resolve_execution_alias(execution_alias)
        if not resolved:
            return None
        cap_id = str(resolved.get("capability_id") or "").strip()
        if not cap_id:
            return None
        if not self._definitions:
            try:
                self.load_definitions()
            except Exception:
                return None
        return self._definitions.get(cap_id)

    def get_execution_meta(self, execution_alias: str) -> Dict[str, object]:
        resolved = self.resolve_execution_alias(execution_alias)
        if not resolved:
            return {}
        return {
            "requires_trust": bool(resolved.get("requires_trust", False)),
            "requires_confirm": bool(resolved.get("requires_confirm", False)),
            "source": str(resolved.get("source") or "builtin"),
        }

        logger.info(f"Loaded {loaded_count} capability definitions into registry")

        # Clear permission cache after loading
        if self._cache_enabled:
            self._clear_cache()

    def register_capability(self, cap_def: CapabilityDefinition):
        """
        Register a single capability definition.

        Args:
            cap_def: Capability definition to register

        Raises:
            ValueError: If definition is invalid or already exists
        """
        # Validate
        is_valid, error = validate_capability_definition(cap_def)
        if not is_valid:
            raise ValueError(f"Invalid capability definition: {error}")

        if cap_def.capability_id in self._definitions:
            raise ValueError(f"Capability already registered: {cap_def.capability_id}")

        # Store in memory
        self._definitions[cap_def.capability_id] = cap_def

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        definition_json = cap_def.model_dump_json()
        created_at_ms = utc_now_ms()

        cursor.execute(
            """
            INSERT INTO capability_definitions (
                capability_id, domain, level, version, definition_json, created_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cap_def.capability_id,
                cap_def.domain.value,
                cap_def.level.value,
                cap_def.version,
                definition_json,
                created_at_ms,
            ),
        )

        conn.commit()
        conn.close()

        logger.info(f"Registered capability: {cap_def.capability_id}")

    def get_capability(self, capability_id: str) -> Optional[CapabilityDefinition]:
        """
        Get capability definition by ID.

        Args:
            capability_id: Capability identifier

        Returns:
            CapabilityDefinition if found, None otherwise
        """
        # Check memory cache first
        if capability_id in self._definitions:
            return self._definitions[capability_id]

        # Load from database
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT definition_json FROM capability_definitions WHERE capability_id = ?",
            (capability_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            definition_json = row["definition_json"]
            cap_def = CapabilityDefinition.model_validate_json(definition_json)
            # Cache in memory
            self._definitions[capability_id] = cap_def
            return cap_def

        return None

    def list_by_domain(self, domain: CapabilityDomain) -> List[CapabilityDefinition]:
        """
        List all capabilities in a domain.

        Args:
            domain: Domain to query

        Returns:
            List of capabilities in the domain
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT definition_json FROM capability_definitions WHERE domain = ?",
            (domain.value,),
        )
        rows = cursor.fetchall()
        conn.close()

        capabilities = []
        for row in rows:
            definition_json = row["definition_json"]
            cap_def = CapabilityDefinition.model_validate_json(definition_json)
            capabilities.append(cap_def)

        return capabilities

    def list_all_capabilities(self) -> List[CapabilityDefinition]:
        """
        List all capability definitions.

        Returns:
            List of all capabilities (27 in default setup)
        """
        if self._definitions:
            return list(self._definitions.values())

        # Load from database
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT definition_json FROM capability_definitions")
        rows = cursor.fetchall()
        conn.close()

        capabilities = []
        for row in rows:
            definition_json = row["definition_json"]
            cap_def = CapabilityDefinition.model_validate_json(definition_json)
            capabilities.append(cap_def)
            # Cache in memory
            self._definitions[cap_def.capability_id] = cap_def

        return capabilities

    # ===================================================================
    # Capability Grant Management
    # ===================================================================

    def grant_capability(
        self,
        agent_id: str,
        capability_id: str,
        granted_by: str,
        reason: Optional[str] = None,
        expires_at_ms: Optional[int] = None,
        scope: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Grant a capability to an agent.

        Args:
            agent_id: Agent identifier (e.g., "chat_agent", "user:alice")
            capability_id: Capability to grant (e.g., "state.memory.read")
            granted_by: Who is granting (user_id or "system")
            reason: Human-readable reason for grant
            expires_at_ms: Optional expiration time (epoch ms)
            scope: Optional scope restriction (e.g., "project:proj-123")
            metadata: Additional metadata dict

        Returns:
            grant_id: Unique grant identifier

        Raises:
            ValueError: If capability does not exist
        """
        # Validate capability exists
        cap_def = self.get_capability(capability_id)
        if cap_def is None:
            raise ValueError(f"Capability not found: {capability_id}")

        # Generate grant ID
        try:
            from ulid import ULID
            grant_id = f"grant-{ULID()}"
        except Exception:
            import uuid
            grant_id = f"grant-{uuid.uuid4().hex}"
        granted_at_ms = utc_now_ms()

        # Insert grant
        conn = self._get_connection()
        cursor = conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO capability_grants (
                grant_id, agent_id, capability_id, granted_by, granted_at_ms,
                expires_at_ms, scope, reason, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grant_id,
                agent_id,
                capability_id,
                granted_by,
                granted_at_ms,
                expires_at_ms,
                scope,
                reason,
                metadata_json,
            ),
        )

        # Audit trail
        cursor.execute(
            """
            INSERT INTO capability_grant_audit (
                grant_id, agent_id, capability_id, action, changed_by, changed_at_ms, reason, metadata
            )
            VALUES (?, ?, ?, 'grant', ?, ?, ?, ?)
            """,
            (grant_id, agent_id, capability_id, granted_by, granted_at_ms, reason, metadata_json),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Granted capability '{capability_id}' to agent '{agent_id}' (grant_id: {grant_id})"
        )

        # Clear cache for this agent
        if self._cache_enabled:
            self._clear_agent_cache(agent_id)

        return grant_id

    def revoke_capability(
        self,
        agent_id: str,
        capability_id: str,
        revoked_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke a capability grant.

        Args:
            agent_id: Agent whose grant to revoke
            capability_id: Capability to revoke
            revoked_by: Who is revoking
            reason: Reason for revocation

        Returns:
            True if revoked, False if no grant found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Find active grant
        cursor.execute(
            """
            SELECT grant_id FROM capability_grants
            WHERE agent_id = ? AND capability_id = ?
            AND (expires_at_ms IS NULL OR expires_at_ms > ?)
            """,
            (agent_id, capability_id, utc_now_ms()),
        )
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return False

        grant_id = row["grant_id"]
        revoked_at_ms = utc_now_ms()

        # Delete grant
        cursor.execute(
            "DELETE FROM capability_grants WHERE grant_id = ?",
            (grant_id,),
        )

        # Audit trail
        cursor.execute(
            """
            INSERT INTO capability_grant_audit (
                grant_id, agent_id, capability_id, action, changed_by, changed_at_ms, reason, metadata
            )
            VALUES (?, ?, ?, 'revoke', ?, ?, ?, NULL)
            """,
            (grant_id, agent_id, capability_id, revoked_by, revoked_at_ms, reason),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Revoked capability '{capability_id}' from agent '{agent_id}' (grant_id: {grant_id})"
        )

        # Clear cache
        if self._cache_enabled:
            self._clear_agent_cache(agent_id)

        return True

    def list_agent_grants(
        self, agent_id: str, include_expired: bool = False
    ) -> List[CapabilityGrant]:
        """
        List all capability grants for an agent.

        Args:
            agent_id: Agent identifier
            include_expired: Include expired grants

        Returns:
            List of CapabilityGrant objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if include_expired:
            cursor.execute(
                """
                SELECT grant_id, agent_id, capability_id, granted_by, granted_at_ms,
                       expires_at_ms, scope, reason, metadata
                FROM capability_grants
                WHERE agent_id = ?
                ORDER BY granted_at_ms DESC
                """,
                (agent_id,),
            )
        else:
            cursor.execute(
                """
                SELECT grant_id, agent_id, capability_id, granted_by, granted_at_ms,
                       expires_at_ms, scope, reason, metadata
                FROM capability_grants
                WHERE agent_id = ?
                AND (expires_at_ms IS NULL OR expires_at_ms > ?)
                ORDER BY granted_at_ms DESC
                """,
                (agent_id, utc_now_ms()),
            )

        rows = cursor.fetchall()
        conn.close()

        grants = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            grant = CapabilityGrant(
                grant_id=row["grant_id"],
                agent_id=row["agent_id"],
                capability_id=row["capability_id"],
                granted_by=row["granted_by"],
                granted_at_ms=row["granted_at_ms"],
                expires_at_ms=row["expires_at_ms"],
                scope=row["scope"],
                reason=row["reason"],
                metadata=metadata,
            )
            grants.append(grant)

        return grants

    # ===================================================================
    # Permission Checks
    # ===================================================================

    def has_capability(
        self,
        agent_id: str,
        capability_id: str,
        scope: Optional[str] = None,
        log_invocation: bool = True,
    ) -> bool:
        """
        Check if agent has a capability (non-raising).

        This method returns True/False without raising exceptions.
        For enforcement use check_capability().

        Args:
            agent_id: Agent identifier
            capability_id: Capability to check
            scope: Optional scope restriction

        Returns:
            True if agent has capability, False otherwise
        """
        # Use cache if enabled
        if self._cache_enabled:
            cache_key = f"{agent_id}:{capability_id}:{scope or ''}"
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        conn = self._get_connection()
        cursor = conn.cursor()

        # Query active grants
        if scope:
            cursor.execute(
                """
                SELECT 1 FROM capability_grants
                WHERE agent_id = ? AND capability_id = ?
                AND (expires_at_ms IS NULL OR expires_at_ms > ?)
                AND (scope IS NULL OR scope = ?)
                LIMIT 1
                """,
                (agent_id, capability_id, utc_now_ms(), scope),
            )
        else:
            cursor.execute(
                """
                SELECT 1 FROM capability_grants
                WHERE agent_id = ? AND capability_id = ?
                AND (expires_at_ms IS NULL OR expires_at_ms > ?)
                LIMIT 1
                """,
                (agent_id, capability_id, utc_now_ms()),
            )

        has_grant = cursor.fetchone() is not None
        conn.close()

        if log_invocation:
            self._log_invocation(
                agent_id=agent_id,
                capability_id=capability_id,
                operation="has_capability",
                allowed=has_grant,
                reason=None if has_grant else "No active grant found",
                context={"scope": scope} if scope else None,
            )

        # Cache result
        if self._cache_enabled:
            cache_key = f"{agent_id}:{capability_id}:{scope or ''}"
            self._put_in_cache(cache_key, has_grant)

        return has_grant

    def check_capability(
        self,
        agent_id: str,
        capability_id: str,
        operation: str,
        context: Optional[Dict] = None,
        scope: Optional[str] = None,
    ):
        """
        Check capability with enforcement (raises on denial).

        This is the primary permission check method. It:
        1. Checks if agent has capability
        2. Logs to audit trail
        3. Raises PermissionDenied if not allowed

        Args:
            agent_id: Agent identifier
            capability_id: Capability required
            operation: Operation being performed
            context: Additional context for audit
            scope: Optional scope restriction

        Raises:
            PermissionDenied: If agent lacks capability
        """
        allowed = self.has_capability(agent_id, capability_id, scope, log_invocation=False)

        # Log invocation
        self._log_invocation(
            agent_id=agent_id,
            capability_id=capability_id,
            operation=operation,
            allowed=allowed,
            reason=None if allowed else "No active grant found",
            context=context,
        )

        if not allowed:
            raise PermissionDenied(
                agent_id=agent_id,
                capability_id=capability_id,
                operation=operation,
                reason="Agent does not have required capability",
            )

    def _log_invocation(
        self,
        agent_id: str,
        capability_id: str,
        operation: str,
        allowed: bool,
        reason: Optional[str],
        context: Optional[Dict],
    ):
        """Log capability invocation to audit trail"""
        conn = self._get_connection()
        cursor = conn.cursor()

        timestamp_ms = utc_now_ms()
        context_json = json.dumps(context) if context else None

        cursor.execute(
            """
            INSERT INTO capability_invocations (
                agent_id, capability_id, operation, allowed, reason, context_json, timestamp_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (agent_id, capability_id, operation, int(allowed), reason, context_json, timestamp_ms),
        )

        conn.commit()
        conn.close()

        if not allowed:
            logger.warning(
                f"Capability check DENIED: agent='{agent_id}', capability='{capability_id}', "
                f"operation='{operation}', reason='{reason}'"
            )

    # ===================================================================
    # Cache Management
    # ===================================================================

    def _get_from_cache(self, key: str) -> Optional[bool]:
        """Get permission check result from cache"""
        # Simple dict cache (in production use Redis/memcached)
        if not hasattr(self, "_cache"):
            self._cache = {}

        if key in self._cache:
            value, expires_at = self._cache[key]
            if datetime.now() < expires_at:
                return value
            else:
                del self._cache[key]

        return None

    def _put_in_cache(self, key: str, value: bool):
        """Put permission check result in cache"""
        if not hasattr(self, "_cache"):
            self._cache = {}

        expires_at = datetime.now() + timedelta(seconds=self._cache_ttl_seconds)
        self._cache[key] = (value, expires_at)

    def _clear_cache(self):
        """Clear entire cache"""
        if hasattr(self, "_cache"):
            self._cache.clear()
        logger.debug("Cache cleared")

    def _clear_agent_cache(self, agent_id: str):
        """Clear cache for specific agent"""
        if not hasattr(self, "_cache"):
            return

        keys_to_delete = [key for key in self._cache.keys() if key.startswith(f"{agent_id}:")]
        for key in keys_to_delete:
            del self._cache[key]

        logger.debug(f"Cache cleared for agent: {agent_id}")

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict:
        """
        Get registry statistics.

        Returns:
            Dict with counts and metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Count definitions
        cursor.execute("SELECT COUNT(*) as count FROM capability_definitions")
        stats["total_capabilities"] = cursor.fetchone()["count"]

        # Count active grants
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM capability_grants
            WHERE expires_at_ms IS NULL OR expires_at_ms > ?
            """,
            (utc_now_ms(),),
        )
        stats["active_grants"] = cursor.fetchone()["count"]

        # Count total invocations
        cursor.execute("SELECT COUNT(*) as count FROM capability_invocations")
        stats["total_invocations"] = cursor.fetchone()["count"]

        # Count denials
        cursor.execute("SELECT COUNT(*) as count FROM capability_invocations WHERE allowed = 0")
        stats["denied_invocations"] = cursor.fetchone()["count"]

        # Cache stats
        if hasattr(self, "_cache"):
            stats["cache_size"] = len(self._cache)
        else:
            stats["cache_size"] = 0

        conn.close()

        return stats


# Global singleton access
_registry_instance: Optional[CapabilityRegistry] = None


def get_capability_registry(db_path: Optional[str] = None) -> CapabilityRegistry:
    """
    Get global capability registry singleton.

    Args:
        db_path: Optional database path (only used on first call)

    Returns:
        Singleton CapabilityRegistry instance
    """
    if db_path is not None:
        if (
            CapabilityRegistry._instance is None
            or CapabilityRegistry._instance.db_path != db_path
        ):
            CapabilityRegistry._instance = CapabilityRegistry(db_path=db_path)
        return CapabilityRegistry._instance
    return CapabilityRegistry.get_instance(db_path=db_path)
