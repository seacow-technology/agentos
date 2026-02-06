"""Policy engine for voice communication security and governance.

This module implements policy-based access control for voice sessions,
including risk assessment, rate limiting, and authorization gates.

Audit Requirements:
-------------------
When creating VoiceSession audit logs, ensure the following metadata is captured:

For Twilio sessions (provider=TWILIO):
- call_sid: Twilio call SID (unique call identifier)
- stream_sid: Twilio Media Stream SID (unique stream identifier)
- from_number: Caller phone number (E.164 format, e.g., +1234567890)
- to_number: Recipient phone number (E.164 format)
- provider: "twilio"
- risk_tier: "MEDIUM" (from PROVIDER_RISK_TIERS)
- policy_verdict: Policy evaluation result (APPROVED, DENIED, RATE_LIMITED, etc.)
- rate_limit_status: Rate limiting check result
- admin_token_required: Whether admin token was required
- admin_token_verified: Whether admin token verification passed

For LOCAL sessions (provider=LOCAL):
- provider: "local"
- risk_tier: "LOW"
- policy_verdict: Policy evaluation result
- websocket_id: WebSocket connection identifier (if applicable)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from agentos.core.communication.models import RiskLevel, RequestStatus, PolicyVerdict
from agentos.core.communication.rate_limit import RateLimiter
from agentos.core.communication.voice.models import VoiceProvider, STTProvider

logger = logging.getLogger(__name__)


class VoicePolicy:
    """Policy engine for voice communication operations.

    The VoicePolicy engine evaluates voice session requests, performs
    risk assessment, and determines authorization requirements.

    Default behavior:
    - Voice operations default to LOW risk tier
    - No admin token required by default (for usability)
    - High-risk operations can escalate to require admin token
    - All operations are audited via evidence chain
    """

    # Default risk tier for voice operations
    DEFAULT_RISK_TIER = RiskLevel.LOW

    # Risk tier mapping for different voice providers
    PROVIDER_RISK_TIERS: Dict[VoiceProvider, RiskLevel] = {
        VoiceProvider.LOCAL: RiskLevel.LOW,     # Local WebSocket = low risk
        VoiceProvider.TWILIO: RiskLevel.MEDIUM, # External PSTN = medium risk
    }

    def __init__(self, rate_limiter: Optional[RateLimiter] = None):
        """Initialize voice policy engine.

        Args:
            rate_limiter: Optional rate limiter instance. If None, creates a new one.
        """
        self.enabled = True
        self.rate_limit_per_minute = 10  # Max 10 voice sessions per minute
        self.max_session_duration_seconds = 3600  # 1 hour max session
        self.require_admin_token_for_high_risk = True

        # Rate limiting
        self.rate_limiter = rate_limiter or RateLimiter()

        # Twilio-specific rate limiting: track calls per phone number
        # Key format: "twilio:from_number:{phone_number}"
        self.call_history: Dict[str, List[float]] = {}  # from_number -> [timestamps]
        self.calls_per_hour_limit = 10  # Max 10 calls per hour per phone number

    def evaluate_session_request(
        self,
        project_id: str,
        provider: VoiceProvider,
        stt_provider: STTProvider,
        metadata: Optional[Dict] = None,
    ) -> PolicyVerdict:
        """Evaluate a voice session creation request.

        Args:
            project_id: Project ID requesting the session
            provider: Voice provider type
            stt_provider: STT provider type
            metadata: Additional request metadata (may include from_number, admin_token)

        Returns:
            PolicyVerdict with status, reason_code, and hint
        """
        if not self.enabled:
            return PolicyVerdict(
                status=RequestStatus.DENIED,
                reason_code="VOICE_DISABLED",
                hint="Voice communication is disabled",
            )

        metadata = metadata or {}

        # Twilio-specific policy checks
        if provider == VoiceProvider.TWILIO:
            # Check rate limiting for incoming phone number
            from_number = metadata.get("from_number")
            if from_number:
                rate_limit_verdict = self._check_twilio_rate_limit(from_number)
                if rate_limit_verdict.status != RequestStatus.APPROVED:
                    return rate_limit_verdict

            # Check if high-risk operation requires admin token
            requires_data_access = metadata.get("requires_data_access", False)
            if requires_data_access:
                admin_token = metadata.get("admin_token")
                if not self._verify_admin_token(admin_token):
                    logger.warning(
                        f"Admin token verification failed for Twilio session: "
                        f"from_number={from_number}"
                    )
                    return PolicyVerdict(
                        status=RequestStatus.REQUIRE_ADMIN,
                        reason_code="ADMIN_TOKEN_REQUIRED",
                        hint="This operation requires admin approval via valid admin token",
                        metadata={
                            "requires_admin_token": True,
                            "provider": provider.value,
                        },
                    )

        # Assess risk level based on provider
        risk_level = self.assess_risk_level(provider, metadata)

        # Check if admin token is required for high-risk operations
        if self.require_admin_token_for_high_risk and risk_level >= RiskLevel.HIGH:
            # For high-risk operations, require explicit approval
            # However, this is a soft gate - the service can override if needed
            logger.warning(
                f"High-risk voice session requested: provider={provider}, "
                f"risk_level={risk_level}"
            )

        # Default: approve with risk assessment
        return PolicyVerdict(
            status=RequestStatus.APPROVED,
            reason_code="VOICE_SESSION_APPROVED",
            hint=f"Voice session approved with {risk_level.value} risk tier",
            metadata={
                "risk_level": risk_level.value,
                "provider": provider.value,
                "stt_provider": stt_provider.value,
            },
        )

    def assess_risk_level(
        self,
        provider: VoiceProvider,
        metadata: Dict,
    ) -> RiskLevel:
        """Assess risk level for a voice session.

        Risk factors:
        - Provider type (LOCAL < TWILIO)
        - External connectivity (none < PSTN < international)
        - Data sensitivity flags in metadata

        Args:
            provider: Voice provider type
            metadata: Request metadata

        Returns:
            Assessed risk level
        """
        # Start with provider base risk
        base_risk = self.PROVIDER_RISK_TIERS.get(provider, self.DEFAULT_RISK_TIER)

        # Check metadata for risk escalation factors
        risk_score = self._risk_level_to_score(base_risk)

        # Escalate if handling sensitive data
        if metadata.get("sensitive_data"):
            risk_score += 1

        # Escalate if international calling
        if metadata.get("international_call"):
            risk_score += 1

        # Escalate if recording enabled
        if metadata.get("recording_enabled"):
            risk_score += 1

        return self._score_to_risk_level(risk_score)

    def require_admin_token(self) -> bool:
        """Check if operations require admin token.

        This method provides a hook for high-risk operations to
        require explicit human authorization via admin token.

        Returns:
            True if admin token is required
        """
        return self.require_admin_token_for_high_risk

    def validate_session_params(
        self,
        project_id: str,
        provider: VoiceProvider,
        stt_provider: STTProvider,
    ) -> tuple[bool, str]:
        """Validate voice session parameters.

        Args:
            project_id: Project ID
            provider: Voice provider
            stt_provider: STT provider

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate project_id
        if not project_id or not isinstance(project_id, str):
            return False, "project_id is required and must be a string"

        # Validate provider
        if not isinstance(provider, VoiceProvider):
            return False, f"Invalid provider type: {provider}"

        # Validate STT provider
        if not isinstance(stt_provider, STTProvider):
            return False, f"Invalid STT provider type: {stt_provider}"

        return True, "Parameters valid"

    def _check_twilio_rate_limit(self, from_number: str) -> PolicyVerdict:
        """Check rate limit for Twilio phone number.

        Twilio-specific rate limiting: max 10 calls per hour per phone number.

        Args:
            from_number: Incoming phone number (E.164 format)

        Returns:
            PolicyVerdict indicating if call is allowed
        """
        if not from_number:
            # If no from_number provided, allow (will be rejected elsewhere)
            return PolicyVerdict(
                status=RequestStatus.APPROVED,
                reason_code="RATE_LIMIT_CHECK_SKIPPED",
                hint="No from_number provided for rate limit check",
            )

        # Get call count in the last hour
        call_count = self._get_call_count_last_hour(from_number)

        if call_count >= self.calls_per_hour_limit:
            logger.warning(
                f"Rate limit exceeded for Twilio number {from_number}: "
                f"{call_count}/{self.calls_per_hour_limit} calls in last hour"
            )
            return PolicyVerdict(
                status=RequestStatus.RATE_LIMITED,
                reason_code="RATE_LIMIT_EXCEEDED",
                hint=f"Phone number {from_number} exceeded {self.calls_per_hour_limit} calls/hour limit",
                metadata={
                    "from_number": from_number,
                    "call_count": call_count,
                    "limit": self.calls_per_hour_limit,
                },
            )

        # Rate limit check passed
        logger.info(
            f"Rate limit check passed for {from_number}: "
            f"{call_count}/{self.calls_per_hour_limit} calls in last hour"
        )
        return PolicyVerdict(
            status=RequestStatus.APPROVED,
            reason_code="RATE_LIMIT_OK",
            hint=f"Rate limit check passed ({call_count}/{self.calls_per_hour_limit})",
        )

    def _get_call_count_last_hour(self, from_number: str) -> int:
        """Get the number of calls from a phone number in the last hour.

        Args:
            from_number: Phone number (E.164 format)

        Returns:
            Number of calls in the last hour
        """
        if from_number not in self.call_history:
            return 0

        now = time.time()
        one_hour_ago = now - 3600  # 3600 seconds = 1 hour

        # Clean up expired timestamps
        self.call_history[from_number] = [
            ts for ts in self.call_history[from_number] if ts > one_hour_ago
        ]

        return len(self.call_history[from_number])

    def record_call(self, from_number: str) -> None:
        """Record a call from a phone number for rate limiting.

        Args:
            from_number: Phone number (E.164 format)
        """
        if not from_number:
            return

        if from_number not in self.call_history:
            self.call_history[from_number] = []

        self.call_history[from_number].append(time.time())
        logger.debug(f"Recorded call from {from_number}, total in history: {len(self.call_history[from_number])}")

    def _verify_admin_token(self, token: Optional[str]) -> bool:
        """Verify admin token for high-risk operations.

        Admin tokens are required for operations that access sensitive data
        or perform privileged actions via voice interface.

        Token format: "admin-{random_string}" with minimum length 20 characters
        Note: This is a simplified verification. In production, tokens should
        be validated against a secure token store or database.

        Args:
            token: Admin token to verify

        Returns:
            True if token is valid, False otherwise
        """
        if not token:
            logger.debug("Admin token verification failed: no token provided")
            return False

        # Basic format validation
        if not isinstance(token, str) or not token.startswith("admin-"):
            logger.debug(f"Admin token verification failed: invalid format")
            return False

        # Minimum length check (admin- + at least 14 characters = 20 total)
        if len(token) < 20:
            logger.debug(f"Admin token verification failed: token too short (length={len(token)})")
            return False

        # In production, validate against database or key vault
        # For now, accept any token matching the format
        logger.info("Admin token verification passed")
        return True

    @staticmethod
    def _risk_level_to_score(risk: RiskLevel) -> int:
        """Convert risk level to numeric score."""
        mapping = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        return mapping.get(risk, 0)

    @staticmethod
    def _score_to_risk_level(score: int) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score <= 0:
            return RiskLevel.LOW
        elif score == 1:
            return RiskLevel.MEDIUM
        elif score == 2:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
