"""Response Guardian - Enforces capability declarations in Execution Phase

This module prevents the system from returning "I cannot access..." fallback
responses when in Execution Phase and AutoComm is available. It ensures the
system always declares and uses its capabilities rather than reverting to
traditional LLM "I don't know" patterns.

CRITICAL BEHAVIOR:
- In Execution Phase: BLOCK any "I cannot access..." responses
- Force the system to declare external info needs via proper channels
- Prevent confusion between "system has no capability" vs "needs user approval"
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GuardianDecision:
    """Decision from Response Guardian"""
    allowed: bool  # Whether response can pass through
    reason: str    # Reason for block/allow
    replacement_response: Optional[str] = None  # Suggested replacement if blocked
    metadata: Dict[str, Any] = None


class ResponseGuardian:
    """Guardian that enforces capability declarations in Execution Phase

    This prevents the system from falling back to "I cannot access real-time data"
    responses when it actually HAS the capability through AutoComm.

    Behavior:
    - Planning Phase: Allow all responses (including "I cannot access...")
    - Execution Phase: BLOCK "I cannot access..." and force proper declaration
    """

    # Patterns that indicate capability denial
    CAPABILITY_DENIAL_PATTERNS = [
        # Chinese patterns
        r'我无法.*访问.*实时',
        r'我无法.*直接.*获取',
        r'我无法.*查询.*当前',
        r'我不能.*访问.*实时',
        r'我不能.*查询.*当前',
        r'我不能.*获取.*实时',
        r'抱歉.*我.*无法.*访问',
        r'作为.*AI.*我无法',

        # English patterns
        r'I cannot.*access.*real-time',
        r'I cannot.*directly.*access',
        r'I don\'?t have.*access to.*current',
        r'I am unable to.*access',
        r'As an AI.*I cannot',
        r'Sorry.*I cannot.*access',

        # Suggestion patterns (these are OK if followed by proper action)
        # But NOT ok if they're the only response
        r'建议.*查看.*weather\.com',
        r'建议.*使用.*手机.*天气',
        r'you.*should.*check.*weather',
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Response Guardian

        Args:
            config: Configuration dict with guardian settings
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.strict_mode = self.config.get('strict_mode', True)

        logger.info(
            f"ResponseGuardian initialized: "
            f"enabled={self.enabled}, strict_mode={self.strict_mode}"
        )

    def check_response(
        self,
        response_content: str,
        session_metadata: Dict[str, Any],
        classification: Optional[Any] = None
    ) -> GuardianDecision:
        """Check if response is allowed based on execution phase and content

        Args:
            response_content: The LLM's response text
            session_metadata: Session metadata including execution_phase
            classification: Optional InfoNeed classification result

        Returns:
            GuardianDecision with allow/block decision and replacement if needed
        """
        try:
            # Check if guardian is enabled
            if not self.enabled:
                return GuardianDecision(
                    allowed=True,
                    reason="Guardian disabled",
                    metadata={"guardian_enabled": False}
                )

            # Get execution phase
            execution_phase = session_metadata.get('execution_phase', 'planning')
            auto_comm_enabled = session_metadata.get('auto_comm_enabled', True)

            # Planning phase: allow all responses
            if execution_phase == 'planning':
                return GuardianDecision(
                    allowed=True,
                    reason="Planning phase allows all responses",
                    metadata={
                        "execution_phase": execution_phase,
                        "check_performed": False
                    }
                )

            # Execution phase: check for capability denial patterns
            if execution_phase == 'execution':
                denial_found, matched_pattern = self._detect_capability_denial(
                    response_content
                )

                if denial_found:
                    # Check if AutoComm is available
                    if auto_comm_enabled:
                        # BLOCK: System has capability but is denying it
                        logger.warning(
                            "Response Guardian BLOCKED capability denial in Execution Phase",
                            extra={
                                "event": "RESPONSE_GUARDIAN_BLOCK",
                                "execution_phase": execution_phase,
                                "matched_pattern": matched_pattern,
                                "response_preview": response_content[:200]
                            }
                        )

                        # Generate replacement response
                        replacement = self._generate_replacement_response(
                            original_response=response_content,
                            classification=classification
                        )

                        return GuardianDecision(
                            allowed=False,
                            reason=f"Capability denial blocked in execution phase (pattern: {matched_pattern})",
                            replacement_response=replacement,
                            metadata={
                                "execution_phase": execution_phase,
                                "auto_comm_enabled": auto_comm_enabled,
                                "matched_pattern": matched_pattern,
                                "guardian_action": "blocked"
                            }
                        )
                    else:
                        # AutoComm disabled - allow the denial
                        return GuardianDecision(
                            allowed=True,
                            reason="AutoComm disabled, denial allowed",
                            metadata={
                                "execution_phase": execution_phase,
                                "auto_comm_enabled": False
                            }
                        )

                # No denial pattern found - allow
                return GuardianDecision(
                    allowed=True,
                    reason="No capability denial detected",
                    metadata={
                        "execution_phase": execution_phase,
                        "auto_comm_enabled": auto_comm_enabled,
                        "guardian_check": "passed"
                    }
                )

            # Unknown phase - allow with warning
            logger.warning(f"Unknown execution phase: {execution_phase}")
            return GuardianDecision(
                allowed=True,
                reason=f"Unknown execution phase: {execution_phase}",
                metadata={"execution_phase": execution_phase}
            )

        except Exception as e:
            logger.error(f"Response Guardian check failed: {e}", exc_info=True)
            # Fail open - allow response
            return GuardianDecision(
                allowed=True,
                reason=f"Guardian error: {str(e)}",
                metadata={"error": str(e)}
            )

    def _detect_capability_denial(
        self,
        response_content: str
    ) -> Tuple[bool, Optional[str]]:
        """Detect if response contains capability denial patterns

        Args:
            response_content: Response text to check

        Returns:
            Tuple of (denial_found, matched_pattern)
        """
        content_lower = response_content.lower()

        for pattern in self.CAPABILITY_DENIAL_PATTERNS:
            if re.search(pattern, response_content, re.IGNORECASE):
                logger.debug(f"Matched denial pattern: {pattern}")
                return True, pattern

        return False, None

    def _generate_replacement_response(
        self,
        original_response: str,
        classification: Optional[Any]
    ) -> str:
        """Generate replacement response when denial is blocked

        Args:
            original_response: Original response that was blocked
            classification: Optional classification result

        Returns:
            Replacement response text
        """
        # Build replacement that declares capability correctly
        replacement_parts = [
            "⚠️ **System Capability Enforcement**\n",
            "The system attempted to return a 'cannot access' response, "
            "but this is Execution Phase and external capabilities are available.\n\n",
        ]

        if classification:
            from agentos.core.chat.models.info_need import DecisionAction

            if hasattr(classification, 'decision_action'):
                action = classification.decision_action

                if action == DecisionAction.REQUIRE_COMM:
                    replacement_parts.append(
                        "**Correct behavior**: This question requires external information "
                        "and should be handled via AutoComm or `/comm` command.\n\n"
                    )
                elif action == DecisionAction.SUGGEST_COMM:
                    replacement_parts.append(
                        "**Correct behavior**: This question can be answered from existing "
                        "knowledge with a suggestion to verify via `/comm`.\n\n"
                    )

        replacement_parts.extend([
            "**What happened**: The LLM generated a 'cannot access real-time data' response, ",
            "which conflicts with the system's declared AutoComm capabilities.\n\n",
            "**Next steps**:\n",
            "1. Use `/comm search <query>` to get external information\n",
            "2. Or ask your question again - the system will attempt AutoComm\n",
            "3. If this persists, check session metadata: `auto_comm_enabled=true`\n\n",
            "---\n",
            "_This message was generated by Response Guardian to prevent capability denial "
            "when capabilities are available._"
        ])

        return "".join(replacement_parts)


# Global instance (can be configured per project)
_guardian_instance: Optional[ResponseGuardian] = None


def get_response_guardian() -> ResponseGuardian:
    """Get or create global Response Guardian instance

    Returns:
        ResponseGuardian instance
    """
    global _guardian_instance

    if _guardian_instance is None:
        _guardian_instance = ResponseGuardian(config={
            'enabled': True,
            'strict_mode': True
        })

    return _guardian_instance


def check_response_with_guardian(
    response_content: str,
    session_metadata: Dict[str, Any],
    classification: Optional[Any] = None
) -> Tuple[str, Dict[str, Any]]:
    """Convenience function to check response and return final content

    Args:
        response_content: Original response from LLM
        session_metadata: Session metadata
        classification: Optional classification result

    Returns:
        Tuple of (final_response_content, guardian_metadata)
    """
    guardian = get_response_guardian()

    decision = guardian.check_response(
        response_content=response_content,
        session_metadata=session_metadata,
        classification=classification
    )

    if decision.allowed:
        return response_content, decision.metadata or {}
    else:
        # Response was blocked - use replacement
        logger.warning(
            f"Response Guardian blocked response: {decision.reason}",
            extra={
                "guardian_decision": {
                    "allowed": False,
                    "reason": decision.reason,
                    "metadata": decision.metadata
                }
            }
        )

        return decision.replacement_response, decision.metadata or {}
