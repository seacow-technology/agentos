"""
Local Trust Bootstrap Module

Handles the importation of Marketplace capabilities into local environments
with trust decay and mandatory re-earning.

Core Principle:
"Global trust" cannot directly take effect - it must be re-proven locally.

Trust Decay Formula:
    local_initial_trust = inherited_trust * decay_factor
    where decay_factor = 0.7 (fixed in v0)

Red Lines:
- ❌ No "global trust direct effect"
- ❌ No skipping EARNING phase
- ❌ No direct STABLE without history
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from agentos.core.time.clock import utc_now, utc_now_ms
from agentos.core.capabilities.trust.state import TrustState
from agentos.core.capabilities.trust.models import TrustTier


# Fixed decay factor for v0
DECAY_FACTOR = 0.7


@dataclass
class MarketplaceCapability:
    """
    Marketplace capability metadata.

    Attributes:
        capability_id: Unique capability identifier
        publisher_id: Publisher identifier
        marketplace_trust: Trust score from marketplace (0-1)
        trust_tier: Trust tier in marketplace
        version: Capability version
    """
    capability_id: str
    publisher_id: str
    marketplace_trust: float
    trust_tier: str
    version: str


@dataclass
class LocalBootstrapResult:
    """
    Result of local trust bootstrap operation.

    Attributes:
        capability_id: Capability identifier
        marketplace_trust: Original marketplace trust
        local_initial_trust: Trust after decay
        trust_state: Initial trust state (always EARNING)
        trust_tier: Local trust tier
        decay_factor: Applied decay factor
        source: Import source (marketplace)
        bootstrapped_at: Timestamp of bootstrap
    """
    capability_id: str
    marketplace_trust: float
    local_initial_trust: float
    trust_state: TrustState
    trust_tier: TrustTier
    decay_factor: float
    source: str
    bootstrapped_at: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "capability_id": self.capability_id,
            "marketplace_trust": round(self.marketplace_trust, 3),
            "local_initial_trust": round(self.local_initial_trust, 3),
            "trust_state": self.trust_state.value,
            "trust_tier": self.trust_tier.value,
            "decay_factor": self.decay_factor,
            "source": self.source,
            "bootstrapped_at": int(self.bootstrapped_at.timestamp() * 1000)
        }


class LocalTrustBootstrap:
    """
    Local Trust Bootstrap System.

    Handles importation of Marketplace capabilities with mandatory trust decay
    and local re-earning.

    Responsibilities:
    - Apply trust decay to marketplace trust
    - Initialize local trust state (always EARNING)
    - Record import source and history
    - Start local trust evolution (Phase E)
    """

    def __init__(self, db_path: str):
        """
        Initialize local trust bootstrap system.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure marketplace import schema exists."""
        with sqlite3.connect(self.db_path) as conn:
            # Marketplace capability imports table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_imports (
                    import_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    publisher_id TEXT NOT NULL,
                    marketplace_trust REAL NOT NULL,
                    marketplace_tier TEXT NOT NULL,
                    local_initial_trust REAL NOT NULL,
                    local_tier TEXT NOT NULL,
                    decay_factor REAL NOT NULL,
                    version TEXT NOT NULL,
                    imported_at_ms INTEGER NOT NULL,
                    metadata_json TEXT
                )
            """)

            conn.commit()

    def apply_decay(
        self,
        marketplace_trust: float,
        decay_factor: Optional[float] = None
    ) -> float:
        """
        Apply trust decay to marketplace trust.

        Trust Decay Formula:
            local_initial_trust = marketplace_trust * decay_factor

        Args:
            marketplace_trust: Trust score from marketplace (0-1)
            decay_factor: Decay factor (default: 0.7)

        Returns:
            Decayed trust score for local environment

        Examples:
            >>> bootstrap = LocalTrustBootstrap(db_path)
            >>> bootstrap.apply_decay(0.68)
            0.476
            >>> bootstrap.apply_decay(0.80, decay_factor=0.5)
            0.4
        """
        if decay_factor is None:
            decay_factor = DECAY_FACTOR

        if not (0 <= marketplace_trust <= 1):
            raise ValueError(f"Marketplace trust must be in [0, 1], got {marketplace_trust}")

        if not (0 < decay_factor <= 1):
            raise ValueError(f"Decay factor must be in (0, 1], got {decay_factor}")

        return marketplace_trust * decay_factor

    def import_capability(
        self,
        capability: MarketplaceCapability,
        metadata: Optional[Dict] = None
    ) -> LocalBootstrapResult:
        """
        Import a Marketplace capability to local environment.

        Process:
        1. Apply trust decay
        2. Map to local trust tier
        3. Initialize trust state as EARNING
        4. Record import metadata

        Args:
            capability: Marketplace capability metadata
            metadata: Optional additional metadata

        Returns:
            Bootstrap result with local trust configuration

        Red Lines:
        - ❌ Trust state must be EARNING (no direct STABLE)
        - ❌ Trust must be decayed (no direct inheritance)
        - ❌ Local evolution must start from zero history
        """
        # Step 1: Apply decay
        local_initial_trust = self.apply_decay(capability.marketplace_trust)

        # Step 2: Map to local trust tier based on decayed trust
        # Note: This is based on local risk calculation, not marketplace tier
        local_tier = self._map_to_local_tier(local_initial_trust)

        # Step 3: Trust state is ALWAYS EARNING (red line)
        trust_state = TrustState.EARNING

        # Step 4: Record import
        import_id = self._record_import(
            capability=capability,
            local_initial_trust=local_initial_trust,
            local_tier=local_tier,
            metadata=metadata
        )

        # Step 5: Initialize local trust in Phase E system
        self._initialize_local_trust(
            capability_id=capability.capability_id,
            initial_trust=local_initial_trust,
            trust_tier=local_tier
        )

        return LocalBootstrapResult(
            capability_id=capability.capability_id,
            marketplace_trust=capability.marketplace_trust,
            local_initial_trust=local_initial_trust,
            trust_state=trust_state,
            trust_tier=local_tier,
            decay_factor=DECAY_FACTOR,
            source="marketplace",
            bootstrapped_at=utc_now()
        )

    def _map_to_local_tier(self, trust_score: float) -> TrustTier:
        """
        Map trust score to local trust tier.

        This is conservative - lower trust scores map to lower tiers.

        Args:
            trust_score: Trust score (0-1)

        Returns:
            Local trust tier
        """
        # Convert to percentage (0-100)
        trust_percentage = trust_score * 100

        # Map to tier (conservative)
        if trust_percentage < 30:
            return TrustTier.LOW
        elif trust_percentage < 70:
            return TrustTier.MEDIUM
        else:
            return TrustTier.HIGH

    def _record_import(
        self,
        capability: MarketplaceCapability,
        local_initial_trust: float,
        local_tier: TrustTier,
        metadata: Optional[Dict]
    ) -> str:
        """Record marketplace import in database."""
        import uuid

        import_id = str(uuid.uuid4())
        now_ms = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO marketplace_imports (
                    import_id, capability_id, publisher_id,
                    marketplace_trust, marketplace_tier,
                    local_initial_trust, local_tier,
                    decay_factor, version,
                    imported_at_ms, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                import_id,
                capability.capability_id,
                capability.publisher_id,
                capability.marketplace_trust,
                capability.trust_tier,
                local_initial_trust,
                local_tier.value,
                DECAY_FACTOR,
                capability.version,
                now_ms,
                json.dumps(metadata or {})
            ))

            conn.commit()

        return import_id

    def _initialize_local_trust(
        self,
        capability_id: str,
        initial_trust: float,
        trust_tier: TrustTier
    ) -> None:
        """
        Initialize local trust state in Phase E system.

        This integrates with the Trust Trajectory Engine to start
        local evolution from EARNING state.

        Args:
            capability_id: Capability identifier
            initial_trust: Initial trust score after decay
            trust_tier: Local trust tier
        """
        # Initialize trust state with EARNING
        # This will be picked up by Phase E Trust Trajectory Engine
        with sqlite3.connect(self.db_path) as conn:
            now_ms = utc_now_ms()

            # Check if already exists
            cursor = conn.execute("""
                SELECT 1 FROM trust_states
                WHERE extension_id = ? AND action_id = '*'
            """, (capability_id,))

            if not cursor.fetchone():
                conn.execute("""
                    INSERT INTO trust_states (
                        extension_id, action_id, current_state,
                        consecutive_successes, consecutive_failures,
                        policy_rejections, high_risk_events,
                        state_entered_at_ms, last_event_at_ms, updated_at_ms
                    ) VALUES (?, ?, ?, 0, 0, 0, 0, ?, ?, ?)
                """, (
                    capability_id,
                    "*",
                    TrustState.EARNING.value,
                    now_ms,
                    now_ms,
                    now_ms
                ))

                conn.commit()

    def get_import_history(
        self,
        capability_id: str
    ) -> Optional[Dict]:
        """
        Get import history for a capability.

        Args:
            capability_id: Capability identifier

        Returns:
            Import record or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT * FROM marketplace_imports
                WHERE capability_id = ?
                ORDER BY imported_at_ms DESC
                LIMIT 1
            """, (capability_id,))

            row = cursor.fetchone()
            if row:
                return {
                    "import_id": row["import_id"],
                    "capability_id": row["capability_id"],
                    "publisher_id": row["publisher_id"],
                    "marketplace_trust": row["marketplace_trust"],
                    "marketplace_tier": row["marketplace_tier"],
                    "local_initial_trust": row["local_initial_trust"],
                    "local_tier": row["local_tier"],
                    "decay_factor": row["decay_factor"],
                    "version": row["version"],
                    "imported_at_ms": row["imported_at_ms"],
                    "metadata": json.loads(row["metadata_json"])
                }

        return None

    def start_earning_phase(
        self,
        capability_id: str
    ) -> Dict:
        """
        Start the earning phase for an imported capability.

        This is called after import to begin Phase E trust evolution.

        Args:
            capability_id: Capability identifier

        Returns:
            Current trust trajectory info
        """
        # Get import history
        import_record = self.get_import_history(capability_id)
        if not import_record:
            raise ValueError(f"No import record found for {capability_id}")

        # Get current trust state (should be EARNING)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT * FROM trust_states
                WHERE extension_id = ? AND action_id = '*'
            """, (capability_id,))

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Trust state not initialized for {capability_id}")

            return {
                "capability_id": capability_id,
                "trust_state": row["current_state"],
                "marketplace_trust": import_record["marketplace_trust"],
                "local_initial_trust": import_record["local_initial_trust"],
                "decay_factor": import_record["decay_factor"],
                "consecutive_successes": row["consecutive_successes"],
                "consecutive_failures": row["consecutive_failures"],
                "state_entered_at_ms": row["state_entered_at_ms"],
                "message": "Earning phase started. Trust must be proven through local execution history."
            }
