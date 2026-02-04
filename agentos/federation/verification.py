"""
Federation Verifier for Remote Trust Evidence.

Phase G2 - Federation Verification

Core Principle: "互信不是相信" (Trust is not belief, it's verification)
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from .verification_result import (
    VerificationResult,
    VerificationStatus,
    DimensionResult
)


class FederationVerifier:
    """
    Federation Verifier for validating remote AgentOS trust evidence.

    Verification Dimensions:
    1. Policy Engine - Is policy enforced?
    2. Sandbox - Is sandbox truly enabled?
    3. Audit Trail - Is audit history complete?
    4. Execution Transparency - Are denials recorded?
    """

    # Dimension weights for score calculation
    DIMENSION_WEIGHTS = {
        "policy_engine": 0.4,  # Most important
        "sandbox": 0.3,
        "audit_trail": 0.2,
        "execution_transparency": 0.1
    }

    # Verification thresholds
    ACCEPT_THRESHOLD = 90  # >= 90 points = ACCEPT
    LIMITED_TRUST_THRESHOLD = 50  # 50-89 points = LIMITED_TRUST
    # < 50 points = REJECT

    # Evidence validity period (24 hours)
    EVIDENCE_VALIDITY_HOURS = 24

    def __init__(self):
        """Initialize the verifier."""
        self.verification_time = datetime.now(timezone.utc)

    def verify_evidence(self, evidence: Dict[str, Any]) -> VerificationResult:
        """
        Verify complete trust evidence from remote AgentOS.

        Args:
            evidence: Trust evidence dictionary

        Returns:
            VerificationResult with verification status and details
        """
        # First check evidence validity and signature
        if not self._validate_evidence_format(evidence):
            return self._create_reject_result(
                "INVALID_FORMAT",
                "Evidence format is invalid or incomplete",
                evidence
            )

        if not self._verify_evidence_freshness(evidence):
            return self._create_reject_result(
                "EXPIRED",
                "Evidence has expired (older than 24 hours)",
                evidence
            )

        if not self._verify_signature(evidence):
            return self._create_reject_result(
                "INVALID_SIGNATURE",
                "Evidence signature verification failed",
                evidence
            )

        # Verify each dimension
        dimensions = {}

        # 1. Policy Engine Verification
        dimensions["policy_engine"] = self.verify_policy_engine(evidence)

        # 2. Sandbox Verification
        dimensions["sandbox"] = self.verify_sandbox(evidence)

        # 3. Audit Trail Verification
        dimensions["audit_trail"] = self.verify_audit_trail(evidence)

        # 4. Execution Transparency Verification
        dimensions["execution_transparency"] = self.verify_execution_transparency(
            evidence
        )

        # Calculate overall score
        overall_score = self.calculate_verification_score(dimensions)

        # Determine status based on critical failures and score
        status = self._determine_verification_status(dimensions, overall_score)

        # Calculate recommended initial trust
        initial_trust = self._calculate_initial_trust(status, overall_score)

        # Generate summary
        summary = self._generate_summary(status, dimensions)

        return VerificationResult(
            status=status,
            dimensions=dimensions,
            recommended_initial_trust=initial_trust,
            overall_score=overall_score,
            summary=summary,
            evidence_id=evidence.get("system_id")
        )

    def verify_policy_engine(self, evidence: Dict[str, Any]) -> DimensionResult:
        """
        Verify Policy Engine existence and enforcement.

        Criteria:
        - Policy Engine must exist
        - Enforcement must be 'mandatory'
        - At least 3 policy rules must be defined

        Args:
            evidence: Trust evidence

        Returns:
            DimensionResult for policy engine
        """
        governance = evidence.get("governance_capabilities", {})
        policy_engine = governance.get("policy_engine", {})

        # Check existence
        if not policy_engine.get("exists", False):
            return DimensionResult(
                dimension="policy_engine",
                passed=False,
                reason="Policy Engine not declared",
                score=0.0,
                details={"exists": False}
            )

        # Check enforcement level
        enforcement = policy_engine.get("enforcement", "")
        if enforcement != "mandatory":
            return DimensionResult(
                dimension="policy_engine",
                passed=False,
                reason=f"Policy not enforced (enforcement={enforcement})",
                score=20.0,
                details={"enforcement": enforcement}
            )

        # Check policy rules count
        rules = policy_engine.get("rules", [])
        rule_count = len(rules)
        if rule_count < 3:
            return DimensionResult(
                dimension="policy_engine",
                passed=False,
                reason=f"Too few policy rules (count={rule_count}, minimum=3)",
                score=50.0,
                details={"rule_count": rule_count, "minimum_required": 3}
            )

        # All checks passed
        return DimensionResult(
            dimension="policy_engine",
            passed=True,
            reason="Policy Engine verified",
            score=100.0,
            details={
                "exists": True,
                "enforcement": enforcement,
                "rule_count": rule_count
            }
        )

    def verify_sandbox(self, evidence: Dict[str, Any]) -> DimensionResult:
        """
        Verify Sandbox availability and isolation level.

        Criteria:
        - Sandbox must be available
        - Isolation level must not be 'none'

        Args:
            evidence: Trust evidence

        Returns:
            DimensionResult for sandbox
        """
        governance = evidence.get("governance_capabilities", {})
        sandbox = governance.get("sandbox", {})

        # Check availability
        if not sandbox.get("available", False):
            return DimensionResult(
                dimension="sandbox",
                passed=False,
                reason="Sandbox not available",
                score=30.0,  # Partial score for LIMITED_TRUST
                details={"available": False}
            )

        # Check isolation level
        isolation_level = sandbox.get("isolation_level", "none")
        if isolation_level == "none":
            return DimensionResult(
                dimension="sandbox",
                passed=False,
                reason="No isolation (isolation_level=none)",
                score=0.0,
                details={"isolation_level": isolation_level}
            )

        # Calculate score based on isolation level
        isolation_scores = {
            "low": 60.0,
            "medium": 80.0,
            "high": 100.0
        }
        score = isolation_scores.get(isolation_level, 50.0)

        return DimensionResult(
            dimension="sandbox",
            passed=True,
            reason=f"Sandbox verified (isolation={isolation_level})",
            score=score,
            details={
                "available": True,
                "isolation_level": isolation_level
            }
        )

    def verify_audit_trail(self, evidence: Dict[str, Any]) -> DimensionResult:
        """
        Verify Audit Trail completeness and integrity.

        Criteria:
        - Audit log count must be > 0
        - Audit log hash must be verifiable

        Args:
            evidence: Trust evidence

        Returns:
            DimensionResult for audit trail
        """
        audit_integrity = evidence.get("audit_integrity", {})

        # Check audit log count
        audit_log_count = audit_integrity.get("audit_log_count", 0)
        if audit_log_count == 0:
            return DimensionResult(
                dimension="audit_trail",
                passed=False,
                reason="No audit history",
                score=0.0,
                details={"audit_log_count": 0}
            )

        # Verify hash integrity
        audit_log_hash = audit_integrity.get("audit_log_hash", "")
        if not self._verify_audit_hash(audit_integrity):
            return DimensionResult(
                dimension="audit_trail",
                passed=False,
                reason="Audit integrity compromised",
                score=0.0,
                details={
                    "audit_log_count": audit_log_count,
                    "hash_valid": False
                }
            )

        return DimensionResult(
            dimension="audit_trail",
            passed=True,
            reason=f"Audit trail verified (count={audit_log_count})",
            score=100.0,
            details={
                "audit_log_count": audit_log_count,
                "hash_valid": True
            }
        )

    def verify_execution_transparency(
        self, evidence: Dict[str, Any]
    ) -> DimensionResult:
        """
        Verify Execution Transparency (denial records present).

        Criteria:
        - If many executions exist, some denials should be present
        - No denial records in large samples is suspicious

        Args:
            evidence: Trust evidence

        Returns:
            DimensionResult for execution transparency
        """
        execution_samples = evidence.get("execution_samples", [])
        sample_count = len(execution_samples)

        if sample_count == 0:
            return DimensionResult(
                dimension="execution_transparency",
                passed=False,
                reason="No execution samples provided",
                score=30.0,
                details={"sample_count": 0}
            )

        # Count denials
        denials = [
            s for s in execution_samples
            if s.get("policy_decision") == "DENY"
        ]
        denial_count = len(denials)

        # Suspicious: too many samples with zero denials
        if sample_count > 10 and denial_count == 0:
            return DimensionResult(
                dimension="execution_transparency",
                passed=False,
                reason="No denial records (suspicious - possible hiding)",
                score=0.0,
                details={
                    "sample_count": sample_count,
                    "denial_count": denial_count,
                    "suspicious": True
                }
            )

        # Calculate transparency score
        if sample_count < 10:
            # Too few samples, give benefit of doubt
            score = 80.0
        else:
            # Expect at least 5% denials in large samples
            denial_ratio = denial_count / sample_count
            if denial_ratio >= 0.05:
                score = 100.0
            else:
                score = 60.0 + (denial_ratio / 0.05) * 40.0

        return DimensionResult(
            dimension="execution_transparency",
            passed=True,
            reason=f"Execution transparency verified (samples={sample_count}, denials={denial_count})",
            score=score,
            details={
                "sample_count": sample_count,
                "denial_count": denial_count,
                "denial_ratio": denial_count / sample_count if sample_count > 0 else 0
            }
        )

    def calculate_verification_score(
        self, dimensions: Dict[str, DimensionResult]
    ) -> float:
        """
        Calculate overall verification score based on dimension results.

        Score calculation:
        - policy_engine: 40%
        - sandbox: 30%
        - audit_trail: 20%
        - execution_transparency: 10%

        Args:
            dimensions: Dictionary of dimension results

        Returns:
            Overall score (0-100)
        """
        total_score = 0.0

        for dimension_name, weight in self.DIMENSION_WEIGHTS.items():
            dimension_result = dimensions.get(dimension_name)
            if dimension_result:
                total_score += dimension_result.score * weight

        return round(total_score, 2)

    # Private helper methods

    def _validate_evidence_format(self, evidence: Dict[str, Any]) -> bool:
        """Validate evidence has required structure."""
        required_keys = [
            "evidence_version",
            "system_id",
            "generated_at",
            "validity_period",
            "governance_capabilities",
            "audit_integrity",
            "execution_samples",
            "signature"
        ]

        for key in required_keys:
            if key not in evidence:
                return False

        return True

    def _verify_evidence_freshness(self, evidence: Dict[str, Any]) -> bool:
        """Verify evidence is not expired (within 24 hours)."""
        try:
            timestamp_str = evidence["generated_at"]
            # Handle Z suffix and ensure timezone aware
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            evidence_timestamp = datetime.fromisoformat(timestamp_str)

            # Ensure both timestamps are timezone-aware
            if evidence_timestamp.tzinfo is None:
                evidence_timestamp = evidence_timestamp.replace(tzinfo=timezone.utc)

            age = self.verification_time - evidence_timestamp
            return age <= timedelta(hours=self.EVIDENCE_VALIDITY_HOURS)
        except (ValueError, KeyError):
            return False

    def _verify_signature(self, evidence: Dict[str, Any]) -> bool:
        """
        Verify evidence signature.

        Note: In production, this should use proper cryptographic verification.
        For now, we do a basic hash check.
        """
        signature = evidence.get("signature", "")
        if not signature:
            return False

        # Create a copy without signature for hashing
        evidence_copy = evidence.copy()
        evidence_copy.pop("signature", None)

        # Calculate hash
        evidence_json = json.dumps(evidence_copy, sort_keys=True)
        calculated_hash = hashlib.sha256(evidence_json.encode()).hexdigest()

        # In production, verify signature using public key
        # For now, just check that signature exists and is not empty
        return len(signature) >= 32

    def _verify_audit_hash(self, audit_integrity: Dict[str, Any]) -> bool:
        """
        Verify audit log hash integrity.

        Note: In production, this should verify against actual audit logs.
        """
        audit_hash = audit_integrity.get("audit_log_hash", "")
        # Remove prefix if present (e.g., "sha256:...")
        if ":" in audit_hash:
            audit_hash = audit_hash.split(":", 1)[1]
        return len(audit_hash) == 64  # SHA-256 hash length

    def _determine_verification_status(
        self,
        dimensions: Dict[str, DimensionResult],
        overall_score: float
    ) -> VerificationStatus:
        """
        Determine verification status based on dimensions and score.

        Rules:
        - Policy Engine failure = REJECT (critical)
        - Score >= 90 = ACCEPT
        - Score 50-89 = LIMITED_TRUST
        - Score < 50 = REJECT
        """
        # Policy Engine is critical - failure = REJECT
        policy_result = dimensions.get("policy_engine")
        if policy_result and not policy_result.passed:
            return VerificationStatus.REJECT

        # Audit Trail is critical - failure = REJECT
        audit_result = dimensions.get("audit_trail")
        if audit_result and not audit_result.passed:
            return VerificationStatus.REJECT

        # Execution Transparency failure = REJECT (hiding denials)
        transparency_result = dimensions.get("execution_transparency")
        if transparency_result and not transparency_result.passed:
            if "suspicious" in transparency_result.details:
                return VerificationStatus.REJECT

        # Score-based determination
        if overall_score >= self.ACCEPT_THRESHOLD:
            return VerificationStatus.ACCEPT
        elif overall_score >= self.LIMITED_TRUST_THRESHOLD:
            return VerificationStatus.LIMITED_TRUST
        else:
            return VerificationStatus.REJECT

    def _calculate_initial_trust(
        self,
        status: VerificationStatus,
        overall_score: float
    ) -> int:
        """
        Calculate recommended initial trust level (0-100).

        Mapping:
        - ACCEPT: 50-70% (based on score)
        - LIMITED_TRUST: 20-40% (based on score)
        - REJECT: 0%
        """
        if status == VerificationStatus.REJECT:
            return 0

        if status == VerificationStatus.ACCEPT:
            # Map 90-100 score to 50-70 trust
            return min(70, int(50 + (overall_score - 90) * 2))

        if status == VerificationStatus.LIMITED_TRUST:
            # Map 50-89 score to 20-40 trust
            return min(40, int(20 + (overall_score - 50) * 0.5))

        return 0

    def _generate_summary(
        self,
        status: VerificationStatus,
        dimensions: Dict[str, DimensionResult]
    ) -> str:
        """Generate human-readable summary of verification."""
        passed = [d.dimension for d in dimensions.values() if d.passed]
        failed = [d.dimension for d in dimensions.values() if not d.passed]

        if status == VerificationStatus.ACCEPT:
            return f"All verification dimensions passed: {', '.join(passed)}"

        if status == VerificationStatus.LIMITED_TRUST:
            return f"Partial trust: Passed={len(passed)}, Failed={len(failed)}"

        if status == VerificationStatus.REJECT:
            reasons = [d.reason for d in dimensions.values() if not d.passed]
            return f"Verification rejected: {'; '.join(reasons)}"

        return "Unknown verification status"

    def _create_reject_result(
        self,
        reason_code: str,
        reason: str,
        evidence: Dict[str, Any]
    ) -> VerificationResult:
        """Create a rejection result for invalid evidence."""
        dimension_result = DimensionResult(
            dimension="evidence_validation",
            passed=False,
            reason=reason,
            score=0.0,
            details={"reason_code": reason_code}
        )

        return VerificationResult(
            status=VerificationStatus.REJECT,
            dimensions={"evidence_validation": dimension_result},
            recommended_initial_trust=0,
            overall_score=0.0,
            summary=f"Evidence validation failed: {reason}",
            evidence_id=evidence.get("system_id")
        )
