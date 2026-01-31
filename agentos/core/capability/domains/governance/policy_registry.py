"""
Policy Registry - Dynamic policy management system

Implements:
- GC-002: governance.policy.evaluate
- GC-006: governance.policy.evolve

Features:
- Dynamic policy loading (no code changes needed)
- Version management (semver)
- Hot reload (policies can be updated without restart)
- YAML/JSON policy definitions
- Complete audit trail of policy changes

Design Philosophy:
- Policy ≠ hard-coded rules
- Policy = evolvable decision logic
- All policy changes are versioned and auditable
"""

import logging
import sqlite3
import json
import yaml
from typing import Dict, List, Optional
from pathlib import Path

from agentos.core.time import utc_now_ms
from agentos.core.capability.domains.governance.models import (
    Policy,
    PolicyRule,
    PolicyEvolutionRecord,
    ConditionType,
    PolicyAction,
)


logger = logging.getLogger(__name__)


class PolicyRegistry:
    """
    Central registry for governance policies.

    This registry:
    - Loads policies from YAML/JSON files
    - Stores policies in database
    - Manages policy versions
    - Supports hot reload (no restart needed)
    - Tracks policy evolution history

    Usage:
        registry = PolicyRegistry(db_path)
        registry.register_policy(policy)
        policy = registry.load_policy("budget_enforcement", version="2.0.0")
        policies = registry.list_policies(domain="governance")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize policy registry.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        self._policies: Dict[str, Policy] = {}  # In-memory cache

        logger.info(f"PolicyRegistry initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # Policy Registration
    # ===================================================================

    def register_policy(
        self,
        policy: Policy,
        created_by: str = "system",
    ):
        """
        Register a new policy or new version of existing policy.

        Args:
            policy: Policy definition
            created_by: Who is registering the policy

        Raises:
            ValueError: If policy already exists with same version
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if this policy+version already exists
        cursor.execute(
            """
            SELECT 1 FROM governance_policies
            WHERE policy_id = ? AND version = ?
            """,
            (policy.policy_id, policy.version),
        )
        if cursor.fetchone():
            conn.close()
            raise ValueError(
                f"Policy {policy.policy_id} version {policy.version} already exists"
            )

        # Store policy in database
        rules_json = json.dumps([r.model_dump() for r in policy.rules])
        created_at_ms = utc_now_ms()

        cursor.execute(
            """
            INSERT INTO governance_policies (
                policy_id, version, rules_json, change_reason,
                active, created_by, created_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy.policy_id,
                policy.version,
                rules_json,
                policy.metadata.get("change_reason", "Initial version"),
                int(policy.active),
                created_by,
                created_at_ms,
            ),
        )

        conn.commit()
        conn.close()

        # Cache in memory
        cache_key = f"{policy.policy_id}:{policy.version}"
        self._policies[cache_key] = policy

        logger.info(f"Registered policy: {policy.policy_id} v{policy.version}")

    def register_from_yaml(
        self,
        yaml_path: str,
        created_by: str = "system",
    ):
        """
        Register policy from YAML file.

        Args:
            yaml_path: Path to YAML policy definition
            created_by: Who is registering

        Raises:
            FileNotFoundError: If YAML file not found
            ValueError: If YAML is invalid
        """
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Policy file not found: {yaml_path}")

        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        # Parse YAML into Policy object
        policy_data = data.get("policy", {})

        rules = []
        for rule_data in policy_data.get("rules", []):
            rule = PolicyRule(
                condition=rule_data["condition"],
                condition_type=ConditionType(rule_data.get("condition_type", "expression")),
                action=PolicyAction(rule_data["action"]),
                rationale=rule_data["rationale"],
                priority=rule_data.get("priority", 100),
            )
            rules.append(rule)

        evolution_history = []
        for evo_data in policy_data.get("evolution_history", []):
            evo = PolicyEvolutionRecord(
                version=evo_data["version"],
                changes=evo_data["changes"],
                reason=evo_data.get("reason", ""),
                changed_by=evo_data.get("changed_by", "unknown"),
                date=evo_data["date"],
            )
            evolution_history.append(evo)

        policy = Policy(
            policy_id=policy_data["id"],
            version=policy_data["version"],
            domain=policy_data["domain"],
            name=policy_data.get("name", policy_data["id"]),
            description=policy_data.get("description", ""),
            rules=rules,
            active=policy_data.get("active", True),
            evolution_history=evolution_history,
            metadata=policy_data.get("metadata", {}),
        )

        self.register_policy(policy, created_by=created_by)
        logger.info(f"Registered policy from YAML: {yaml_path}")

    # ===================================================================
    # Policy Loading
    # ===================================================================

    def load_policy(
        self,
        policy_id: str,
        version: Optional[str] = None,
    ) -> Optional[Policy]:
        """
        Load policy by ID and optional version.

        If version is not specified, loads the latest active version.

        Args:
            policy_id: Policy identifier
            version: Optional specific version (default: latest active)

        Returns:
            Policy object or None if not found
        """
        # Check memory cache first
        if version:
            cache_key = f"{policy_id}:{version}"
            if cache_key in self._policies:
                return self._policies[cache_key]

        conn = self._get_connection()
        cursor = conn.cursor()

        if version:
            # Load specific version
            cursor.execute(
                """
                SELECT policy_id, version, rules_json, change_reason,
                       active, created_by, created_at_ms
                FROM governance_policies
                WHERE policy_id = ? AND version = ?
                """,
                (policy_id, version),
            )
        else:
            # Load latest active version
            cursor.execute(
                """
                SELECT policy_id, version, rules_json, change_reason,
                       active, created_by, created_at_ms
                FROM governance_policies
                WHERE policy_id = ? AND active = 1
                ORDER BY created_at_ms DESC
                LIMIT 1
                """,
                (policy_id,),
            )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Parse rules from JSON
        rules_data = json.loads(row["rules_json"])
        rules = [PolicyRule(**rule_data) for rule_data in rules_data]

        policy = Policy(
            policy_id=row["policy_id"],
            version=row["version"],
            domain="unknown",  # Would need to store domain in DB
            name=row["policy_id"],
            description="",
            rules=rules,
            active=bool(row["active"]),
            evolution_history=[],
            metadata={"change_reason": row["change_reason"] or ""},
        )

        # Cache in memory
        cache_key = f"{policy.policy_id}:{policy.version}"
        self._policies[cache_key] = policy

        return policy

    def list_policies(
        self,
        domain: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Policy]:
        """
        List all policies (optionally filtered by domain).

        Args:
            domain: Optional domain filter
            active_only: Only return active policies

        Returns:
            List of Policy objects
        """
        # For now, return all policies from memory cache
        # In production, would query database with proper filtering
        policies = []

        conn = self._get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute(
                """
                SELECT DISTINCT policy_id
                FROM governance_policies
                WHERE active = 1
                """
            )
        else:
            cursor.execute(
                """
                SELECT DISTINCT policy_id
                FROM governance_policies
                """
            )

        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            policy_id = row["policy_id"]
            policy = self.load_policy(policy_id)
            if policy:
                # Filter by domain if specified
                if domain is None or policy.domain == domain:
                    policies.append(policy)

        return policies

    # ===================================================================
    # GC-006: Policy Evolution
    # ===================================================================

    def evolve_policy(
        self,
        policy_id: str,
        new_rules: List[PolicyRule],
        change_reason: str,
        changed_by: str,
        new_version: Optional[str] = None,
    ) -> Policy:
        """
        Evolve a policy to a new version (GC-006).

        This creates a new version of the policy with updated rules.
        The old version is preserved for audit.

        Args:
            policy_id: Policy to evolve
            new_rules: New rule set
            change_reason: Why the policy is being changed (required)
            changed_by: Who is making the change
            new_version: New version string (default: auto-increment)

        Returns:
            New Policy version

        Raises:
            ValueError: If policy not found or change_reason too short
        """
        if len(change_reason) < 10:
            raise ValueError("change_reason must be at least 10 characters")

        # Load current policy
        current_policy = self.load_policy(policy_id)
        if current_policy is None:
            raise ValueError(f"Policy not found: {policy_id}")

        # Determine new version
        if new_version is None:
            # Auto-increment patch version
            version_parts = current_policy.version.split(".")
            if len(version_parts) == 3:
                major, minor, patch = version_parts
                new_version = f"{major}.{minor}.{int(patch) + 1}"
            else:
                new_version = "1.0.1"

        # Create evolution record
        evolution_record = PolicyEvolutionRecord(
            version=new_version,
            changes=change_reason,
            reason=change_reason,
            changed_by=changed_by,
            date=utc_now_ms(),
        )

        # Create new policy version
        new_policy = Policy(
            policy_id=policy_id,
            version=new_version,
            domain=current_policy.domain,
            name=current_policy.name,
            description=current_policy.description,
            rules=new_rules,
            active=True,
            evolution_history=current_policy.evolution_history + [evolution_record],
            metadata={
                "change_reason": change_reason,
                "changed_by": changed_by,
            },
        )

        # Deactivate old version
        self._deactivate_policy_version(policy_id, current_policy.version)

        # Register new version
        self.register_policy(new_policy, created_by=changed_by)

        logger.info(
            f"Evolved policy {policy_id} from v{current_policy.version} to v{new_version}: "
            f"{change_reason}"
        )

        return new_policy

    def _deactivate_policy_version(self, policy_id: str, version: str):
        """Deactivate a specific policy version"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE governance_policies
            SET active = 0
            WHERE policy_id = ? AND version = ?
            """,
            (policy_id, version),
        )

        conn.commit()
        conn.close()

        # Remove from cache
        cache_key = f"{policy_id}:{version}"
        if cache_key in self._policies:
            del self._policies[cache_key]

    # ===================================================================
    # Hot Reload
    # ===================================================================

    def reload_policies(self):
        """
        Reload all policies from database (hot reload).

        This allows policy changes to take effect without restarting.
        """
        self._policies.clear()
        logger.info("Policy cache cleared, will reload on next access")

    def reload_from_directory(
        self,
        policy_dir: str,
        created_by: str = "system",
    ):
        """
        Reload all policies from a directory of YAML files.

        Args:
            policy_dir: Directory containing .yaml policy files
            created_by: Who is loading the policies
        """
        policy_path = Path(policy_dir)
        if not policy_path.exists():
            logger.warning(f"Policy directory not found: {policy_dir}")
            return

        loaded_count = 0
        for yaml_file in policy_path.glob("*.yaml"):
            try:
                self.register_from_yaml(str(yaml_file), created_by=created_by)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load policy from {yaml_file}: {e}")

        logger.info(f"Reloaded {loaded_count} policies from {policy_dir}")

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict[str, int]:
        """Get policy registry statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total policies
        cursor.execute("SELECT COUNT(DISTINCT policy_id) as count FROM governance_policies")
        stats["total_policies"] = cursor.fetchone()["count"]

        # Active policies
        cursor.execute(
            "SELECT COUNT(DISTINCT policy_id) as count FROM governance_policies WHERE active = 1"
        )
        stats["active_policies"] = cursor.fetchone()["count"]

        # Total versions
        cursor.execute("SELECT COUNT(*) as count FROM governance_policies")
        stats["total_versions"] = cursor.fetchone()["count"]

        conn.close()

        return stats


# ===================================================================
# Global singleton
# ===================================================================

_policy_registry_instance: Optional[PolicyRegistry] = None


def get_policy_registry(db_path: Optional[str] = None) -> PolicyRegistry:
    """
    Get global policy registry singleton.

    Args:
        db_path: Optional database path (only used on first call)

    Returns:
        Singleton PolicyRegistry instance
    """
    global _policy_registry_instance
    if _policy_registry_instance is None:
        _policy_registry_instance = PolicyRegistry(db_path=db_path)
    return _policy_registry_instance
