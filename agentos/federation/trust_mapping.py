"""
Trust Mapping Engine (Phase G3)

Maps remote trust to local trust with mandatory re-earning.

Core Principle: Mapping ≠ Copying
    Remote STABLE ≠ Local STABLE
    All remote trust must be re-proven locally through Phase E

Architecture:
    TrustMapper
      ├─ map_trust() - Main entry point
      ├─ map_trust_state() - State mapping
      ├─ map_trust_tier() - Tier mapping with ceiling
      ├─ apply_sandbox_constraints() - Sandbox enforcement
      └─ calculate_local_initial_trust() - Initial trust calculation

Red Lines:
    ❌ No HIGH → HIGH direct mapping
    ❌ No skipping local Phase E evolution
    ❌ No sandbox = forced LOW tier
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from .mapping_rules import (
    TrustState,
    TrustTier,
    StateMapping,
    TierMapping,
    SandboxConstraint
)

logger = logging.getLogger(__name__)


@dataclass
class RemoteTrustEvidence:
    """
    Remote trust evidence from another AgentOS system.

    This represents the trust state and evidence from a remote
    system that we want to map to local trust.

    Attributes:
        system_id: Remote system identifier
        extension_id: Extension/capability identifier
        trust_state: Remote trust state
        trust_tier: Remote trust tier
        risk_score: Remote risk score (0-100)
        has_sandbox: Whether remote has sandbox
        sandbox_level: Remote sandbox level
        verification_score: Verification score from G2 (0-100)
        execution_count: Number of executions in remote
        success_rate: Success rate in remote (0-1)
        metadata: Additional metadata
    """
    system_id: str
    extension_id: str
    trust_state: str
    trust_tier: str
    risk_score: float
    has_sandbox: bool
    sandbox_level: str
    verification_score: float
    execution_count: int = 0
    success_rate: float = 0.0
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "system_id": self.system_id,
            "extension_id": self.extension_id,
            "trust_state": self.trust_state,
            "trust_tier": self.trust_tier,
            "risk_score": round(self.risk_score, 2),
            "has_sandbox": self.has_sandbox,
            "sandbox_level": self.sandbox_level,
            "verification_score": round(self.verification_score, 2),
            "execution_count": self.execution_count,
            "success_rate": round(self.success_rate, 3),
            "metadata": self.metadata or {}
        }


@dataclass
class MappingResult:
    """
    Result of trust mapping operation.

    Attributes:
        extension_id: Extension identifier
        remote_system: Remote system ID
        local_trust_state: Mapped local state (always EARNING)
        local_trust_tier: Mapped local tier (capped)
        local_initial_trust: Calculated initial trust (0-100)
        must_evolve_locally: Must go through Phase E (always True)
        mapping_explanation: Human-readable explanation
        state_mapping: State mapping details
        tier_mapping: Tier mapping details
        sandbox_constraint: Sandbox constraint details
        calculated_at: Mapping timestamp
    """
    extension_id: str
    remote_system: str
    local_trust_state: TrustState
    local_trust_tier: TrustTier
    local_initial_trust: float
    must_evolve_locally: bool
    mapping_explanation: str
    state_mapping: Dict
    tier_mapping: Dict
    sandbox_constraint: Dict
    calculated_at: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        def serialize_value(value):
            """Recursively serialize values, handling enums"""
            if isinstance(value, (TrustState, TrustTier)):
                return value.value
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            else:
                return value

        return {
            "extension_id": self.extension_id,
            "remote_system": self.remote_system,
            "local_trust_state": self.local_trust_state.value,
            "local_trust_tier": self.local_trust_tier.value,
            "local_initial_trust": round(self.local_initial_trust, 2),
            "must_evolve_locally": self.must_evolve_locally,
            "mapping_explanation": self.mapping_explanation,
            "state_mapping": serialize_value(self.state_mapping),
            "tier_mapping": serialize_value(self.tier_mapping),
            "sandbox_constraint": serialize_value(self.sandbox_constraint),
            "calculated_at": int(self.calculated_at.timestamp() * 1000)
        }


class TrustMapper:
    """
    Trust Mapping Engine (Phase G3).

    Maps remote trust evidence to local trust configuration with
    mandatory re-earning through Phase E.

    Usage:
        mapper = TrustMapper()

        evidence = RemoteTrustEvidence(
            system_id="remote-agentos",
            extension_id="capability-123",
            trust_state="STABLE",
            trust_tier="HIGH",
            risk_score=15.0,
            has_sandbox=True,
            sandbox_level="high",
            verification_score=95.0
        )

        result = mapper.map_trust(evidence)
        print(f"Local State: {result.local_trust_state.value}")
        print(f"Local Tier: {result.local_trust_tier.value}")
        print(f"Initial Trust: {result.local_initial_trust}%")
    """

    # Red line thresholds
    HIGH_TIER_MAX_TRUST = 70.0  # Cannot exceed this
    MEDIUM_TIER_MAX_TRUST = 60.0
    LOW_TIER_MAX_TRUST = 40.0

    def __init__(self):
        """Initialize Trust Mapper"""
        logger.info("Trust Mapper initialized")

    def map_trust(self, evidence: RemoteTrustEvidence) -> MappingResult:
        """
        Map remote trust evidence to local trust configuration.

        This is the main entry point for trust mapping.

        Process:
        1. Map trust state (remote → local EARNING)
        2. Map trust tier (with HIGH ceiling)
        3. Apply sandbox constraints
        4. Calculate initial trust
        5. Generate explanation

        Args:
            evidence: Remote trust evidence

        Returns:
            MappingResult with local trust configuration

        Raises:
            ValueError: If evidence is invalid
        """
        # Validate evidence
        self._validate_evidence(evidence)

        logger.info(
            f"Mapping trust for {evidence.extension_id} from {evidence.system_id}: "
            f"Remote {evidence.trust_state}/{evidence.trust_tier}, "
            f"Verification {evidence.verification_score}%"
        )

        # Step 1: Map trust state
        state_mapping = self.map_trust_state(
            remote_state=TrustState(evidence.trust_state),
            verification_score=evidence.verification_score
        )

        # Step 2: Map trust tier (with ceiling)
        tier_mapping = self.map_trust_tier(
            remote_tier=TrustTier(evidence.trust_tier),
            initial_trust=state_mapping["initial_trust"]
        )

        # Step 3: Apply sandbox constraints
        sandbox_constraint = self.apply_sandbox_constraints(
            remote_has_sandbox=evidence.has_sandbox,
            remote_sandbox_level=evidence.sandbox_level,
            proposed_tier=tier_mapping["local_tier"],
            proposed_trust=tier_mapping["capped_trust"]
        )

        # Step 4: Calculate final local initial trust
        local_initial_trust = self.calculate_local_initial_trust(
            state_mapping=state_mapping,
            tier_mapping=tier_mapping,
            sandbox_constraint=sandbox_constraint,
            evidence=evidence
        )

        # Step 5: Determine final local state and tier
        local_state = state_mapping["local_state"]
        local_tier = sandbox_constraint["enforced_tier"]

        # Step 6: Generate explanation
        explanation = self._generate_explanation(
            evidence=evidence,
            local_state=local_state,
            local_tier=local_tier,
            local_initial_trust=local_initial_trust,
            state_mapping=state_mapping,
            tier_mapping=tier_mapping,
            sandbox_constraint=sandbox_constraint
        )

        result = MappingResult(
            extension_id=evidence.extension_id,
            remote_system=evidence.system_id,
            local_trust_state=local_state,
            local_trust_tier=local_tier,
            local_initial_trust=local_initial_trust,
            must_evolve_locally=True,  # RED LINE: Always true
            mapping_explanation=explanation,
            state_mapping=state_mapping,
            tier_mapping=tier_mapping,
            sandbox_constraint=sandbox_constraint,
            calculated_at=datetime.now()
        )

        logger.info(
            f"Trust mapped for {evidence.extension_id}: "
            f"Local {result.local_trust_state.value}/{result.local_trust_tier.value}, "
            f"Initial Trust {result.local_initial_trust:.1f}%"
        )

        return result

    def map_trust_state(
        self,
        remote_state: TrustState,
        verification_score: float
    ) -> Dict:
        """
        Map remote trust state to local state.

        Red Line: All remote states map to local EARNING.

        Args:
            remote_state: Remote trust state
            verification_score: Verification score (0-100)

        Returns:
            State mapping result
        """
        mapping = StateMapping.map_state(remote_state, verification_score)

        logger.debug(
            f"State mapping: Remote {remote_state.value} → "
            f"Local {mapping['local_state'].value}, "
            f"Trust {mapping['initial_trust']:.1f}%"
        )

        return mapping

    def map_trust_tier(
        self,
        remote_tier: TrustTier,
        initial_trust: float
    ) -> Dict:
        """
        Map remote trust tier to local tier with ceiling.

        Red Line: HIGH tier cannot be directly inherited.

        Args:
            remote_tier: Remote trust tier
            initial_trust: Initial trust score

        Returns:
            Tier mapping result
        """
        mapping = TierMapping.map_tier(remote_tier, initial_trust)

        logger.debug(
            f"Tier mapping: Remote {remote_tier.value} → "
            f"Local {mapping['local_tier'].value}, "
            f"Capped at {mapping['capped_trust']:.1f}%"
        )

        return mapping

    def apply_sandbox_constraints(
        self,
        remote_has_sandbox: bool,
        remote_sandbox_level: str,
        proposed_tier: TrustTier,
        proposed_trust: float
    ) -> Dict:
        """
        Apply sandbox constraints to proposed mapping.

        Red Line: No sandbox = forced LOW tier.

        Args:
            remote_has_sandbox: Whether remote has sandbox
            remote_sandbox_level: Remote sandbox level
            proposed_tier: Proposed local tier
            proposed_trust: Proposed trust score

        Returns:
            Sandbox constraint result
        """
        constraint = SandboxConstraint.apply_constraint(
            remote_has_sandbox=remote_has_sandbox,
            remote_sandbox_level=remote_sandbox_level,
            proposed_tier=proposed_tier,
            proposed_trust=proposed_trust
        )

        if constraint["sandbox_downgrade"]:
            logger.warning(
                f"Sandbox constraint enforced: {constraint['reason']}"
            )
        else:
            logger.debug(f"Sandbox constraint: {constraint['reason']}")

        return constraint

    def calculate_local_initial_trust(
        self,
        state_mapping: Dict,
        tier_mapping: Dict,
        sandbox_constraint: Dict,
        evidence: RemoteTrustEvidence
    ) -> float:
        """
        Calculate final local initial trust score.

        Formula:
            base_trust = verification_score * 0.6
            tier_adjustment = apply tier caps
            sandbox_adjustment = apply sandbox penalties
            final = min(adjusted_trust, tier_max)

        Args:
            state_mapping: State mapping result
            tier_mapping: Tier mapping result
            sandbox_constraint: Sandbox constraint result
            evidence: Remote evidence

        Returns:
            Local initial trust (0-100)
        """
        # Start with verification-based trust
        base_trust = evidence.verification_score * 0.6

        # Apply state modifier
        state_modifier = state_mapping["score_modifier"]
        adjusted_trust = base_trust * state_modifier

        # Apply sandbox adjustment
        if sandbox_constraint["sandbox_downgrade"]:
            adjusted_trust = sandbox_constraint["adjusted_trust"]
        else:
            # Use tier-capped trust
            adjusted_trust = min(adjusted_trust, tier_mapping["capped_trust"])

        # Apply tier-specific caps
        final_tier = sandbox_constraint["enforced_tier"]
        if final_tier == TrustTier.LOW:
            max_trust = self.LOW_TIER_MAX_TRUST
        elif final_tier == TrustTier.MEDIUM:
            max_trust = self.MEDIUM_TIER_MAX_TRUST
        else:  # HIGH (should not happen, but defensive)
            max_trust = self.HIGH_TIER_MAX_TRUST

        final_trust = min(adjusted_trust, max_trust)

        logger.debug(
            f"Trust calculation: base={base_trust:.1f}%, "
            f"state_adj={adjusted_trust:.1f}%, "
            f"final={final_trust:.1f}%"
        )

        return max(0.0, min(100.0, final_trust))

    def _validate_evidence(self, evidence: RemoteTrustEvidence) -> None:
        """
        Validate remote trust evidence.

        Args:
            evidence: Remote evidence to validate

        Raises:
            ValueError: If evidence is invalid
        """
        if not evidence.system_id:
            raise ValueError("system_id is required")

        if not evidence.extension_id:
            raise ValueError("extension_id is required")

        # Validate state
        try:
            TrustState(evidence.trust_state)
        except ValueError:
            raise ValueError(
                f"Invalid trust_state: {evidence.trust_state}. "
                f"Must be one of: {[s.value for s in TrustState]}"
            )

        # Validate tier
        try:
            TrustTier(evidence.trust_tier)
        except ValueError:
            raise ValueError(
                f"Invalid trust_tier: {evidence.trust_tier}. "
                f"Must be one of: {[t.value for t in TrustTier]}"
            )

        # Validate scores
        if not (0 <= evidence.risk_score <= 100):
            raise ValueError(f"risk_score must be in [0, 100], got {evidence.risk_score}")

        if not (0 <= evidence.verification_score <= 100):
            raise ValueError(
                f"verification_score must be in [0, 100], got {evidence.verification_score}"
            )

        # Validate sandbox level
        if not SandboxConstraint.validate_sandbox_level(evidence.sandbox_level):
            logger.warning(
                f"Unknown sandbox level: {evidence.sandbox_level}. "
                "Will treat as 'none'."
            )

    def _generate_explanation(
        self,
        evidence: RemoteTrustEvidence,
        local_state: TrustState,
        local_tier: TrustTier,
        local_initial_trust: float,
        state_mapping: Dict,
        tier_mapping: Dict,
        sandbox_constraint: Dict
    ) -> str:
        """
        Generate human-readable explanation of mapping.

        Args:
            evidence: Remote evidence
            local_state: Mapped local state
            local_tier: Mapped local tier
            local_initial_trust: Calculated initial trust
            state_mapping: State mapping details
            tier_mapping: Tier mapping details
            sandbox_constraint: Sandbox constraint details

        Returns:
            Explanation string
        """
        lines = [
            f"Trust Mapping for {evidence.extension_id}",
            f"Remote System: {evidence.system_id}",
            "",
            "Remote Trust:",
            f"  State: {evidence.trust_state}",
            f"  Tier: {evidence.trust_tier}",
            f"  Risk Score: {evidence.risk_score:.2f}",
            f"  Sandbox: {evidence.sandbox_level if evidence.has_sandbox else 'None'}",
            f"  Verification: {evidence.verification_score:.2f}%",
            "",
            "Local Mapped Trust:",
            f"  State: {local_state.value}",
            f"  Tier: {local_tier.value}",
            f"  Initial Trust: {local_initial_trust:.1f}%",
            f"  Must Evolve: Yes (Phase E required)",
            "",
            "Mapping Rationale:",
            f"  State: {state_mapping['reason']}",
            f"  Tier: {tier_mapping['reason']}",
            f"  Sandbox: {sandbox_constraint['reason']}"
        ]

        if sandbox_constraint["sandbox_downgrade"]:
            lines.append("")
            lines.append("⚠️  Security Downgrade Applied:")
            lines.append(f"    {sandbox_constraint['reason']}")

        if local_tier != TrustTier(evidence.trust_tier):
            lines.append("")
            lines.append(f"⚠️  Tier Downgrade: {evidence.trust_tier} → {local_tier.value}")

        lines.append("")
        lines.append("Next Steps:")
        lines.append("  1. Extension enters local Phase E (EARNING state)")
        lines.append("  2. Trust must be proven through local execution history")
        lines.append("  3. Promotion to STABLE requires meeting Phase E criteria")

        return "\n".join(lines)
