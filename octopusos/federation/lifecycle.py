"""
Federated Trust Lifecycle (Phase G4)

This module manages the lifecycle of federated trust relationships between
AgentOS systems. Trust is time-bound, revocable, and degradable.

Core Principle:
    Federated trust must be temporary, auditable, and locally controllable.
    Remote systems cannot extend or revoke local trust.

Trust Lifecycle States:
    ACTIVE     - Trust is valid and within TTL
    EXPIRED    - Trust TTL exceeded, needs renewal
    REVOKED    - Trust manually revoked, cannot be renewed
    DEGRADED   - Trust downgraded to lower level

Red Lines (MUST NOT):
    ❌ No unlimited trust (must have TTL)
    ❌ No remote revoke of local trust
    ❌ No silent expiration (must log)
    ❌ No automatic escalation

Database Schema:
    federated_trust:
        - trust_id: Unique identifier
        - remote_system_id: Remote system identifier
        - established_at: When trust was established (epoch ms)
        - expires_at: When trust expires (epoch ms)
        - trust_level: Trust level (MINIMAL, LIMITED, STANDARD)
        - status: Status (ACTIVE, EXPIRED, REVOKED, DEGRADED)
        - can_revoke: Whether trust can be revoked
        - revoke_reason: Reason for revocation (if revoked)

Created: 2026-02-02
Author: Phase G4 Agent
Reference: Phase G Task Cards (plan1.md)
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Trust level for federated systems."""
    MINIMAL = "MINIMAL"      # Very limited trust, high restrictions
    LIMITED = "LIMITED"      # Limited trust, moderate restrictions
    STANDARD = "STANDARD"    # Standard trust, normal restrictions


class TrustStatus(str, Enum):
    """Trust relationship status."""
    ACTIVE = "ACTIVE"        # Trust is valid and active
    EXPIRED = "EXPIRED"      # Trust has expired (TTL exceeded)
    REVOKED = "REVOKED"      # Trust has been revoked
    DEGRADED = "DEGRADED"    # Trust has been downgraded


class FederatedTrustError(Exception):
    """Base exception for federated trust errors."""
    pass


class TrustExpiredError(FederatedTrustError):
    """Raised when trust has expired."""
    pass


class TrustRevokedError(FederatedTrustError):
    """Raised when trust has been revoked."""
    pass


class TrustNotFoundError(FederatedTrustError):
    """Raised when trust relationship not found."""
    pass


@dataclass
class FederatedTrust:
    """
    Federated trust relationship between two AgentOS systems.

    Attributes:
        trust_id: Unique identifier
        remote_system_id: Remote system identifier
        established_at: When trust was established
        expires_at: When trust expires
        trust_level: Current trust level
        status: Current status
        can_revoke: Whether trust can be revoked
        revoke_reason: Reason for revocation (if revoked)
        metadata: Additional metadata (JSON)
    """
    trust_id: str
    remote_system_id: str
    established_at: datetime
    expires_at: datetime
    trust_level: TrustLevel
    status: TrustStatus
    can_revoke: bool = True
    revoke_reason: Optional[str] = None
    metadata: Optional[Dict] = None

    @property
    def is_active(self) -> bool:
        """Check if trust is active."""
        return self.status == TrustStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        """Check if trust has expired."""
        return datetime.now() > self.expires_at or self.status == TrustStatus.EXPIRED

    @property
    def is_revoked(self) -> bool:
        """Check if trust has been revoked."""
        return self.status == TrustStatus.REVOKED

    @property
    def time_remaining(self) -> timedelta:
        """Get time remaining until expiration."""
        if self.is_expired:
            return timedelta(0)
        return self.expires_at - datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "trust_id": self.trust_id,
            "remote_system_id": self.remote_system_id,
            "established_at": int(self.established_at.timestamp() * 1000),
            "expires_at": int(self.expires_at.timestamp() * 1000),
            "trust_level": self.trust_level.value,
            "status": self.status.value,
            "can_revoke": self.can_revoke,
            "revoke_reason": self.revoke_reason,
            "time_remaining_seconds": int(self.time_remaining.total_seconds()),
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "is_revoked": self.is_revoked,
            "metadata": self.metadata,
        }


class TrustLifecycle:
    """
    Manages lifecycle of federated trust relationships.

    Operations:
        - establish_trust: Create new trust relationship
        - renew_trust: Extend trust expiration
        - revoke_trust: Revoke trust relationship
        - downgrade_trust: Downgrade trust level
        - check_expiration: Check and update expired trust

    Usage:
        lifecycle = TrustLifecycle(db_path="agentos.db")

        # Establish trust with 24-hour TTL
        trust = lifecycle.establish_trust(
            remote_system_id="official-agentos",
            trust_level=TrustLevel.LIMITED,
            ttl_hours=24
        )

        # Check expiration
        expired = lifecycle.check_expiration(trust.trust_id)

        # Revoke trust
        lifecycle.revoke_trust(trust.trust_id, reason="Security concern")
    """

    # Default TTL (24 hours)
    DEFAULT_TTL_HOURS = 24

    # Maximum TTL (7 days)
    MAX_TTL_HOURS = 168

    def __init__(self, db_path: str):
        """
        Initialize Trust Lifecycle Manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"Trust Lifecycle Manager initialized: {db_path}")

    def establish_trust(
        self,
        remote_system_id: str,
        trust_level: TrustLevel = TrustLevel.LIMITED,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        metadata: Optional[Dict] = None
    ) -> FederatedTrust:
        """
        Establish trust with a remote system.

        Creates a new federated trust relationship with specified TTL.
        Trust is initially set to ACTIVE status.

        Args:
            remote_system_id: Remote system identifier
            trust_level: Initial trust level (default: LIMITED)
            ttl_hours: Time-to-live in hours (default: 24)
            metadata: Additional metadata

        Returns:
            FederatedTrust object

        Raises:
            ValueError: If ttl_hours exceeds maximum
        """
        if ttl_hours > self.MAX_TTL_HOURS:
            raise ValueError(
                f"TTL {ttl_hours} hours exceeds maximum {self.MAX_TTL_HOURS} hours"
            )

        now = datetime.now()
        trust_id = f"trust-{uuid.uuid4()}"
        expires_at = now + timedelta(hours=ttl_hours)

        logger.info(
            f"Establishing trust with '{remote_system_id}': "
            f"level={trust_level.value}, ttl={ttl_hours}h"
        )

        trust = FederatedTrust(
            trust_id=trust_id,
            remote_system_id=remote_system_id,
            established_at=now,
            expires_at=expires_at,
            trust_level=trust_level,
            status=TrustStatus.ACTIVE,
            can_revoke=True,
            metadata=metadata
        )

        self._store_trust(trust)
        self._log_history(trust_id, "ESTABLISH", f"Trust established with {trust_level.value} level")

        logger.info(f"Trust established: {trust_id} (expires: {expires_at})")
        return trust

    def renew_trust(
        self,
        trust_id: str,
        extend_hours: int = DEFAULT_TTL_HOURS
    ) -> FederatedTrust:
        """
        Renew trust by extending expiration.

        Extends the expiration time of an active trust relationship.
        Cannot renew revoked trust.

        Args:
            trust_id: Trust identifier
            extend_hours: Hours to extend (default: 24)

        Returns:
            Updated FederatedTrust object

        Raises:
            TrustNotFoundError: If trust not found
            TrustRevokedError: If trust is revoked
            ValueError: If new expiration exceeds maximum
        """
        trust = self.get_trust(trust_id)

        if trust.is_revoked:
            raise TrustRevokedError(f"Cannot renew revoked trust: {trust_id}")

        new_expires_at = datetime.now() + timedelta(hours=extend_hours)
        max_expires = trust.established_at + timedelta(hours=self.MAX_TTL_HOURS)

        if new_expires_at > max_expires:
            raise ValueError(
                f"Renewal would exceed maximum lifetime "
                f"({self.MAX_TTL_HOURS} hours from establishment)"
            )

        logger.info(f"Renewing trust '{trust_id}': extending {extend_hours}h")

        trust.expires_at = new_expires_at
        trust.status = TrustStatus.ACTIVE

        self._update_trust(trust)
        self._log_history(trust_id, "RENEW", f"Trust renewed for {extend_hours}h")

        logger.info(f"Trust renewed: {trust_id} (new expiration: {new_expires_at})")
        return trust

    def revoke_trust(
        self,
        trust_id: str,
        reason: str
    ) -> FederatedTrust:
        """
        Revoke trust relationship.

        Permanently revokes trust. Revoked trust cannot be renewed.

        Args:
            trust_id: Trust identifier
            reason: Reason for revocation

        Returns:
            Updated FederatedTrust object

        Raises:
            TrustNotFoundError: If trust not found
            FederatedTrustError: If trust cannot be revoked
        """
        trust = self.get_trust(trust_id)

        if not trust.can_revoke:
            raise FederatedTrustError(
                f"Trust '{trust_id}' cannot be revoked (can_revoke=False)"
            )

        logger.warning(f"Revoking trust '{trust_id}': {reason}")

        trust.status = TrustStatus.REVOKED
        trust.revoke_reason = reason

        self._update_trust(trust)
        self._log_history(trust_id, "REVOKE", f"Trust revoked: {reason}")

        logger.info(f"Trust revoked: {trust_id}")
        return trust

    def downgrade_trust(
        self,
        trust_id: str,
        new_level: TrustLevel,
        reason: str
    ) -> FederatedTrust:
        """
        Downgrade trust to lower level.

        Reduces trust level while keeping trust active.
        Cannot upgrade trust (only downgrade).

        Args:
            trust_id: Trust identifier
            new_level: New trust level (must be lower)
            reason: Reason for downgrade

        Returns:
            Updated FederatedTrust object

        Raises:
            TrustNotFoundError: If trust not found
            ValueError: If trying to upgrade
        """
        trust = self.get_trust(trust_id)

        # Define trust level hierarchy
        level_order = {
            TrustLevel.MINIMAL: 0,
            TrustLevel.LIMITED: 1,
            TrustLevel.STANDARD: 2,
        }

        current_order = level_order[trust.trust_level]
        new_order = level_order[new_level]

        if new_order >= current_order:
            raise ValueError(
                f"Cannot downgrade from {trust.trust_level.value} to {new_level.value} "
                "(new level must be lower)"
            )

        logger.warning(
            f"Downgrading trust '{trust_id}': "
            f"{trust.trust_level.value} -> {new_level.value} ({reason})"
        )

        old_level = trust.trust_level
        trust.trust_level = new_level
        trust.status = TrustStatus.DEGRADED

        self._update_trust(trust)
        self._log_history(
            trust_id,
            "DOWNGRADE",
            f"Trust downgraded: {old_level.value} -> {new_level.value} ({reason})"
        )

        logger.info(f"Trust downgraded: {trust_id} -> {new_level.value}")
        return trust

    def check_expiration(self, trust_id: str) -> bool:
        """
        Check if trust has expired and update status.

        Args:
            trust_id: Trust identifier

        Returns:
            True if trust is expired, False otherwise

        Raises:
            TrustNotFoundError: If trust not found
        """
        trust = self.get_trust(trust_id)

        if trust.is_expired and trust.status == TrustStatus.ACTIVE:
            logger.warning(f"Trust expired: {trust_id}")

            trust.status = TrustStatus.EXPIRED
            self._update_trust(trust)
            self._log_history(trust_id, "EXPIRE", "Trust expired (TTL exceeded)")

        return trust.is_expired

    def get_trust(self, trust_id: str) -> FederatedTrust:
        """
        Get trust by ID.

        Args:
            trust_id: Trust identifier

        Returns:
            FederatedTrust object

        Raises:
            TrustNotFoundError: If trust not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    trust_id,
                    remote_system_id,
                    established_at,
                    expires_at,
                    trust_level,
                    status,
                    can_revoke,
                    revoke_reason,
                    metadata
                FROM federated_trust
                WHERE trust_id = ?
            """, (trust_id,))

            row = cursor.fetchone()
            if not row:
                raise TrustNotFoundError(f"Trust not found: {trust_id}")

            return FederatedTrust(
                trust_id=row[0],
                remote_system_id=row[1],
                established_at=datetime.fromtimestamp(row[2] / 1000),
                expires_at=datetime.fromtimestamp(row[3] / 1000),
                trust_level=TrustLevel(row[4]),
                status=TrustStatus(row[5]),
                can_revoke=bool(row[6]),
                revoke_reason=row[7],
                metadata=eval(row[8]) if row[8] else None
            )

    def get_trust_by_remote(self, remote_system_id: str) -> Optional[FederatedTrust]:
        """
        Get active trust for remote system.

        Args:
            remote_system_id: Remote system identifier

        Returns:
            FederatedTrust object or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    trust_id,
                    remote_system_id,
                    established_at,
                    expires_at,
                    trust_level,
                    status,
                    can_revoke,
                    revoke_reason,
                    metadata
                FROM federated_trust
                WHERE remote_system_id = ?
                  AND status = 'ACTIVE'
                ORDER BY established_at DESC
                LIMIT 1
            """, (remote_system_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return FederatedTrust(
                trust_id=row[0],
                remote_system_id=row[1],
                established_at=datetime.fromtimestamp(row[2] / 1000),
                expires_at=datetime.fromtimestamp(row[3] / 1000),
                trust_level=TrustLevel(row[4]),
                status=TrustStatus(row[5]),
                can_revoke=bool(row[6]),
                revoke_reason=row[7],
                metadata=eval(row[8]) if row[8] else None
            )

    def list_active_trusts(self) -> List[FederatedTrust]:
        """
        List all active trust relationships.

        Returns:
            List of FederatedTrust objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    trust_id,
                    remote_system_id,
                    established_at,
                    expires_at,
                    trust_level,
                    status,
                    can_revoke,
                    revoke_reason,
                    metadata
                FROM federated_trust
                WHERE status = 'ACTIVE'
                ORDER BY established_at DESC
            """)

            trusts = []
            for row in cursor.fetchall():
                trusts.append(FederatedTrust(
                    trust_id=row[0],
                    remote_system_id=row[1],
                    established_at=datetime.fromtimestamp(row[2] / 1000),
                    expires_at=datetime.fromtimestamp(row[3] / 1000),
                    trust_level=TrustLevel(row[4]),
                    status=TrustStatus(row[5]),
                    can_revoke=bool(row[6]),
                    revoke_reason=row[7],
                    metadata=eval(row[8]) if row[8] else None
                ))

            return trusts

    def _store_trust(self, trust: FederatedTrust) -> None:
        """Store trust in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO federated_trust (
                    trust_id,
                    remote_system_id,
                    established_at,
                    expires_at,
                    trust_level,
                    status,
                    can_revoke,
                    revoke_reason,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trust.trust_id,
                trust.remote_system_id,
                int(trust.established_at.timestamp() * 1000),
                int(trust.expires_at.timestamp() * 1000),
                trust.trust_level.value,
                trust.status.value,
                int(trust.can_revoke),
                trust.revoke_reason,
                str(trust.metadata) if trust.metadata else None
            ))
            conn.commit()

    def _update_trust(self, trust: FederatedTrust) -> None:
        """Update trust in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE federated_trust
                SET
                    expires_at = ?,
                    trust_level = ?,
                    status = ?,
                    revoke_reason = ?
                WHERE trust_id = ?
            """, (
                int(trust.expires_at.timestamp() * 1000),
                trust.trust_level.value,
                trust.status.value,
                trust.revoke_reason,
                trust.trust_id
            ))
            conn.commit()

    def _log_history(self, trust_id: str, action: str, description: str) -> None:
        """Log trust lifecycle event."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO federated_trust_history (
                    history_id,
                    trust_id,
                    action,
                    description,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                f"hist-{uuid.uuid4()}",
                trust_id,
                action,
                description,
                int(datetime.now().timestamp() * 1000)
            ))
            conn.commit()


# Convenience functions

def establish_trust(
    db_path: str,
    remote_system_id: str,
    trust_level: TrustLevel = TrustLevel.LIMITED,
    ttl_hours: int = TrustLifecycle.DEFAULT_TTL_HOURS,
    metadata: Optional[Dict] = None
) -> FederatedTrust:
    """
    Establish trust with remote system.

    Args:
        db_path: Database path
        remote_system_id: Remote system identifier
        trust_level: Trust level (default: LIMITED)
        ttl_hours: Time-to-live in hours (default: 24)
        metadata: Additional metadata

    Returns:
        FederatedTrust object
    """
    lifecycle = TrustLifecycle(db_path)
    return lifecycle.establish_trust(remote_system_id, trust_level, ttl_hours, metadata)


def renew_trust(
    db_path: str,
    trust_id: str,
    extend_hours: int = TrustLifecycle.DEFAULT_TTL_HOURS
) -> FederatedTrust:
    """
    Renew trust by extending expiration.

    Args:
        db_path: Database path
        trust_id: Trust identifier
        extend_hours: Hours to extend (default: 24)

    Returns:
        Updated FederatedTrust object
    """
    lifecycle = TrustLifecycle(db_path)
    return lifecycle.renew_trust(trust_id, extend_hours)


def revoke_trust(
    db_path: str,
    trust_id: str,
    reason: str
) -> FederatedTrust:
    """
    Revoke trust relationship.

    Args:
        db_path: Database path
        trust_id: Trust identifier
        reason: Reason for revocation

    Returns:
        Updated FederatedTrust object
    """
    lifecycle = TrustLifecycle(db_path)
    return lifecycle.revoke_trust(trust_id, reason)


def downgrade_trust(
    db_path: str,
    trust_id: str,
    new_level: TrustLevel,
    reason: str
) -> FederatedTrust:
    """
    Downgrade trust to lower level.

    Args:
        db_path: Database path
        trust_id: Trust identifier
        new_level: New trust level
        reason: Reason for downgrade

    Returns:
        Updated FederatedTrust object
    """
    lifecycle = TrustLifecycle(db_path)
    return lifecycle.downgrade_trust(trust_id, new_level, reason)


def check_expiration(
    db_path: str,
    trust_id: str
) -> bool:
    """
    Check if trust has expired.

    Args:
        db_path: Database path
        trust_id: Trust identifier

    Returns:
        True if expired, False otherwise
    """
    lifecycle = TrustLifecycle(db_path)
    return lifecycle.check_expiration(trust_id)
