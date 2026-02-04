"""Marketplace Governance (Phase F5) - Platform Self-Regulation.

This module implements marketplace governance capabilities with strict boundaries:

✅ What Marketplace CAN do:
1. Delist capabilities - Remove from marketplace registry
2. Flag capabilities - Mark security/policy risks
3. Suspend publishers - Block new capability publications

❌ What Marketplace CANNOT do (Red Lines):
1. Cannot grant trust - Trust decisions are local
2. Cannot remote revoke - Local capabilities are autonomous
3. Cannot bypass policy - Local Policy Engine has final say

Design Philosophy:
- Marketplace provides INFORMATION, not DECISIONS
- Local systems use marketplace flags as INPUT, not COMMANDS
- Separation of concerns: Governance != Authorization
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any


# ===================================================================
# Custom Exceptions (Red Line Enforcement)
# ===================================================================

class GovernanceError(Exception):
    """Base exception for governance operations."""
    pass


class PermissionDeniedError(GovernanceError):
    """Raised when attempting prohibited operations (red line violations)."""
    pass


class InvalidActionError(GovernanceError):
    """Raised when governance action parameters are invalid."""
    pass


class TargetNotFoundError(GovernanceError):
    """Raised when governance target (capability/publisher) not found."""
    pass


# ===================================================================
# Data Models
# ===================================================================

@dataclass
class GovernanceAction:
    """Represents a governance action record."""
    action_id: int
    action_type: str  # delist | suspend | restore
    target_type: str  # capability | publisher
    target_id: str
    reason: str
    admin_id: str
    created_at_ms: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CapabilityFlag:
    """Represents a capability risk flag."""
    flag_id: int
    capability_id: str
    flag_type: str  # security | policy | malicious | suspicious
    severity: str  # low | medium | high | critical
    description: str
    flagged_at_ms: int
    resolved_at_ms: Optional[int]
    admin_id: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class GovernanceStatus:
    """Represents the governance status of a capability."""
    capability_id: str
    delisted: bool
    flags: List[CapabilityFlag]
    publisher_suspended: bool


# ===================================================================
# Marketplace Governance Engine
# ===================================================================

class MarketplaceGovernance:
    """
    Marketplace Governance Engine - Platform Self-Regulation.

    This class enforces marketplace governance boundaries:
    - CAN govern marketplace content (delist, flag, suspend)
    - CANNOT authorize local systems (trust, revoke, policy)

    All governance actions are:
    1. Audited (recorded in governance_actions table)
    2. Reversible (restore capability/publisher)
    3. Informational (local systems decide how to use)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Marketplace Governance.

        Args:
            db_path: Path to marketplace database (default: agentos.db)
        """
        if db_path is None:
            from agentos.store import get_store
            store = get_store()
            db_path = store.db_path

        self.db_path = Path(db_path)
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Ensure database and governance tables exist."""
        if not self.db_path.exists():
            raise GovernanceError(f"Database not found: {self.db_path}")

        # Verify governance tables exist
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (
                    'marketplace_governance_actions',
                    'marketplace_flags',
                    'marketplace_publisher_suspensions'
                )
            """)
            tables = {row[0] for row in cursor.fetchall()}

            required_tables = {
                'marketplace_governance_actions',
                'marketplace_flags',
                'marketplace_publisher_suspensions'
            }

            if not required_tables.issubset(tables):
                missing = required_tables - tables
                raise GovernanceError(
                    f"Missing governance tables: {missing}. "
                    "Run schema_v73_marketplace_registry.sql migration."
                )

    # ===================================================================
    # Core Governance Operations (ALLOWED)
    # ===================================================================

    def delist_capability(
        self,
        capability_id: str,
        reason: str,
        admin_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delist a capability from the marketplace.

        This action:
        - Marks capability as 'removed' in marketplace_capabilities
        - Records governance action in audit log
        - Does NOT affect local installations (they are autonomous)

        Args:
            capability_id: Full capability ID (e.g., "malicious.ext.v1.0.0")
            reason: Human-readable reason for delisting
            admin_id: ID of admin performing action
            metadata: Optional additional context

        Returns:
            Dict with action details

        Raises:
            TargetNotFoundError: If capability not found
            InvalidActionError: If capability already delisted
        """
        timestamp_ms = int(time.time() * 1000)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Verify capability exists and is not already delisted
            cursor.execute("""
                SELECT status FROM marketplace_capabilities
                WHERE capability_id = ?
            """, (capability_id,))

            row = cursor.fetchone()
            if row is None:
                raise TargetNotFoundError(
                    f"Capability not found: {capability_id}"
                )

            current_status = row[0]
            if current_status == 'removed':
                raise InvalidActionError(
                    f"Capability already delisted: {capability_id}"
                )

            # Mark capability as removed
            cursor.execute("""
                UPDATE marketplace_capabilities
                SET status = 'removed', removed_at_ms = ?
                WHERE capability_id = ?
            """, (timestamp_ms, capability_id))

            # Record governance action
            cursor.execute("""
                INSERT INTO marketplace_governance_actions
                (action_type, target_type, target_id, reason, admin_id, created_at_ms, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                'delist',
                'capability',
                capability_id,
                reason,
                admin_id,
                timestamp_ms,
                json.dumps(metadata) if metadata else None
            ))

            # Record in marketplace audit log
            cursor.execute("""
                INSERT INTO marketplace_audit_log
                (capability_id, publisher_id, action, actor, timestamp_ms, reason, metadata)
                SELECT capability_id, publisher_id, 'remove', ?, ?, ?, ?
                FROM marketplace_capabilities
                WHERE capability_id = ?
            """, (admin_id, timestamp_ms, reason, json.dumps(metadata) if metadata else None, capability_id))

            conn.commit()

            return {
                "action": "delist",
                "capability_id": capability_id,
                "reason": reason,
                "admin_id": admin_id,
                "timestamp_ms": timestamp_ms,
                "note": "Capability delisted from Marketplace (local instances unaffected)"
            }

    def flag_capability(
        self,
        capability_id: str,
        flag_type: str,
        severity: str,
        description: str,
        admin_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Flag a capability with a risk marker.

        This action:
        - Adds risk flag to marketplace_flags table
        - Provides information for local systems to evaluate
        - Does NOT prevent local execution (Policy Engine decides)

        Args:
            capability_id: Full capability ID
            flag_type: Type of flag (security | policy | malicious | suspicious)
            severity: Severity level (low | medium | high | critical)
            description: Detailed description of issue
            admin_id: ID of admin creating flag
            metadata: Optional additional context

        Returns:
            Dict with flag details

        Raises:
            InvalidActionError: If flag_type or severity invalid
        """
        # Validate inputs
        valid_flag_types = {'security', 'policy', 'malicious', 'suspicious'}
        valid_severities = {'low', 'medium', 'high', 'critical'}

        if flag_type not in valid_flag_types:
            raise InvalidActionError(
                f"Invalid flag_type: {flag_type}. Must be one of {valid_flag_types}"
            )

        if severity not in valid_severities:
            raise InvalidActionError(
                f"Invalid severity: {severity}. Must be one of {valid_severities}"
            )

        timestamp_ms = int(time.time() * 1000)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Create flag
            cursor.execute("""
                INSERT INTO marketplace_flags
                (capability_id, flag_type, severity, description, flagged_at_ms, admin_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                capability_id,
                flag_type,
                severity,
                description,
                timestamp_ms,
                admin_id,
                json.dumps(metadata) if metadata else None
            ))

            flag_id = cursor.lastrowid
            conn.commit()

            return {
                "action": "flag",
                "flag_id": flag_id,
                "capability_id": capability_id,
                "flag_type": flag_type,
                "severity": severity,
                "description": description,
                "admin_id": admin_id,
                "timestamp_ms": timestamp_ms,
                "note": "Flag added (local systems decide how to use this info)"
            }

    def suspend_publisher(
        self,
        publisher_id: str,
        reason: str,
        admin_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Suspend a publisher from publishing new capabilities.

        This action:
        - Adds suspension record to marketplace_publisher_suspensions
        - Blocks new capability registrations from this publisher
        - Does NOT affect existing published capabilities
        - Does NOT revoke local installations

        Args:
            publisher_id: Publisher ID to suspend
            reason: Human-readable reason for suspension
            admin_id: ID of admin performing action
            metadata: Optional additional context

        Returns:
            Dict with suspension details

        Raises:
            TargetNotFoundError: If publisher not found
            InvalidActionError: If publisher already suspended
        """
        timestamp_ms = int(time.time() * 1000)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Verify publisher exists
            cursor.execute("""
                SELECT publisher_id FROM marketplace_publishers
                WHERE publisher_id = ?
            """, (publisher_id,))

            if cursor.fetchone() is None:
                raise TargetNotFoundError(
                    f"Publisher not found: {publisher_id}"
                )

            # Check if already suspended
            cursor.execute("""
                SELECT suspension_id FROM marketplace_publisher_suspensions
                WHERE publisher_id = ? AND restored_at_ms IS NULL
            """, (publisher_id,))

            if cursor.fetchone() is not None:
                raise InvalidActionError(
                    f"Publisher already suspended: {publisher_id}"
                )

            # Create suspension
            cursor.execute("""
                INSERT INTO marketplace_publisher_suspensions
                (publisher_id, suspended_at_ms, reason, admin_id, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                publisher_id,
                timestamp_ms,
                reason,
                admin_id,
                json.dumps(metadata) if metadata else None
            ))

            suspension_id = cursor.lastrowid

            # Record governance action
            cursor.execute("""
                INSERT INTO marketplace_governance_actions
                (action_type, target_type, target_id, reason, admin_id, created_at_ms, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                'suspend',
                'publisher',
                publisher_id,
                reason,
                admin_id,
                timestamp_ms,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()

            return {
                "action": "suspend_publisher",
                "suspension_id": suspension_id,
                "publisher_id": publisher_id,
                "reason": reason,
                "admin_id": admin_id,
                "timestamp_ms": timestamp_ms,
                "note": "Publisher suspended (existing capabilities unaffected)"
            }

    def restore_publisher(
        self,
        publisher_id: str,
        admin_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Restore a suspended publisher.

        Args:
            publisher_id: Publisher ID to restore
            admin_id: ID of admin performing action
            metadata: Optional additional context

        Returns:
            Dict with restoration details

        Raises:
            TargetNotFoundError: If publisher not found or not suspended
        """
        timestamp_ms = int(time.time() * 1000)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Find active suspension
            cursor.execute("""
                SELECT suspension_id FROM marketplace_publisher_suspensions
                WHERE publisher_id = ? AND restored_at_ms IS NULL
            """, (publisher_id,))

            row = cursor.fetchone()
            if row is None:
                raise TargetNotFoundError(
                    f"No active suspension found for publisher: {publisher_id}"
                )

            suspension_id = row[0]

            # Restore publisher
            cursor.execute("""
                UPDATE marketplace_publisher_suspensions
                SET restored_at_ms = ?, restored_by = ?
                WHERE suspension_id = ?
            """, (timestamp_ms, admin_id, suspension_id))

            # Record governance action
            cursor.execute("""
                INSERT INTO marketplace_governance_actions
                (action_type, target_type, target_id, reason, admin_id, created_at_ms, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                'restore',
                'publisher',
                publisher_id,
                'Publisher restored',
                admin_id,
                timestamp_ms,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()

            return {
                "action": "restore_publisher",
                "suspension_id": suspension_id,
                "publisher_id": publisher_id,
                "admin_id": admin_id,
                "timestamp_ms": timestamp_ms,
                "note": "Publisher restored"
            }

    def get_governance_status(self, capability_id: str) -> GovernanceStatus:
        """
        Get governance status for a capability.

        Returns information about:
        - Whether capability is delisted
        - Active risk flags
        - Whether publisher is suspended

        This information is advisory only - local systems decide how to use it.

        Args:
            capability_id: Full capability ID

        Returns:
            GovernanceStatus object
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Check if delisted
            cursor.execute("""
                SELECT status, publisher_id FROM marketplace_capabilities
                WHERE capability_id = ?
            """, (capability_id,))

            row = cursor.fetchone()
            if row is None:
                # Capability not in marketplace
                return GovernanceStatus(
                    capability_id=capability_id,
                    delisted=False,
                    flags=[],
                    publisher_suspended=False
                )

            status, publisher_id = row
            delisted = (status == 'removed')

            # Get active flags
            cursor.execute("""
                SELECT flag_id, capability_id, flag_type, severity, description,
                       flagged_at_ms, resolved_at_ms, admin_id, metadata
                FROM marketplace_flags
                WHERE capability_id = ? AND resolved_at_ms IS NULL
                ORDER BY severity DESC, flagged_at_ms DESC
            """, (capability_id,))

            flags = []
            for row in cursor.fetchall():
                flag = CapabilityFlag(
                    flag_id=row[0],
                    capability_id=row[1],
                    flag_type=row[2],
                    severity=row[3],
                    description=row[4],
                    flagged_at_ms=row[5],
                    resolved_at_ms=row[6],
                    admin_id=row[7],
                    metadata=json.loads(row[8]) if row[8] else None
                )
                flags.append(flag)

            # Check if publisher suspended
            cursor.execute("""
                SELECT suspension_id FROM marketplace_publisher_suspensions
                WHERE publisher_id = ? AND restored_at_ms IS NULL
            """, (publisher_id,))

            publisher_suspended = cursor.fetchone() is not None

            return GovernanceStatus(
                capability_id=capability_id,
                delisted=delisted,
                flags=flags,
                publisher_suspended=publisher_suspended
            )

    def is_publisher_suspended(self, publisher_id: str) -> bool:
        """
        Check if a publisher is currently suspended.

        Args:
            publisher_id: Publisher ID to check

        Returns:
            True if suspended, False otherwise
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT suspension_id FROM marketplace_publisher_suspensions
                WHERE publisher_id = ? AND restored_at_ms IS NULL
            """, (publisher_id,))

            return cursor.fetchone() is not None

    # ===================================================================
    # Red Line Enforcement (FORBIDDEN OPERATIONS)
    # ===================================================================

    def grant_trust(self, capability_id: str, trust_score: int) -> None:
        """
        ❌ FORBIDDEN: Marketplace cannot grant trust.

        Trust decisions are made by local systems based on:
        - Local Trust Score calculation (Phase F3)
        - Local Policy Engine rules (Phase F4)
        - User preferences

        Marketplace can only provide information (flags, history).

        Raises:
            PermissionDeniedError: Always (red line violation)
        """
        raise PermissionDeniedError(
            "RED LINE VIOLATION: Marketplace cannot grant trust. "
            "Trust is calculated by local systems using Publisher Trust Score (Phase F3). "
            "Marketplace can only flag risks, not authorize capabilities."
        )

    def revoke_local_capability(
        self,
        capability_id: str,
        instance_id: str
    ) -> None:
        """
        ❌ FORBIDDEN: Marketplace cannot revoke local capabilities.

        Local capabilities are owned by the local system:
        - Local Policy Engine controls execution (Phase F4)
        - Local Revocation Manager handles local revokes (Phase F4)
        - Marketplace has no authority over local installations

        Marketplace can only:
        - Delist from marketplace (prevents new installs)
        - Flag risks (provides information to local systems)

        Raises:
            PermissionDeniedError: Always (red line violation)
        """
        raise PermissionDeniedError(
            "RED LINE VIOLATION: Cannot revoke local capabilities remotely. "
            "Local capabilities are autonomous and controlled by local Policy Engine. "
            "Marketplace can delist (prevent new installs) or flag (warn), but cannot "
            "disable existing local installations."
        )

    def override_local_policy(
        self,
        capability_id: str,
        instance_id: str,
        allow: bool
    ) -> None:
        """
        ❌ FORBIDDEN: Marketplace cannot override local policy.

        Policy decisions are made by local Policy Engine:
        - Local rules have final authority (Phase F4)
        - User overrides are respected
        - Marketplace flags are ONE INPUT, not a command

        Marketplace cannot:
        - Force allow execution
        - Force deny execution
        - Bypass local policy rules

        Raises:
            PermissionDeniedError: Always (red line violation)
        """
        raise PermissionDeniedError(
            "RED LINE VIOLATION: Cannot override local policy. "
            "Local Policy Engine has final authority over execution decisions. "
            "Marketplace flags are advisory input only, not execution commands."
        )


# ===================================================================
# Convenience Functions
# ===================================================================

def get_governance() -> MarketplaceGovernance:
    """Get default MarketplaceGovernance instance."""
    return MarketplaceGovernance()
