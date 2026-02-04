"""
System Actions - MEDIUM/HIGH Risk Operations

These operations require policy evaluation and may be denied.
They demonstrate the "controlled path" through governance.

Expected behavior:
- MEDIUM risk: Policy evaluated, may require approval
- HIGH risk: Often denied with clear explanation
- Trust Tier: MEDIUM to HIGH

KEY PRINCIPLE: Ops Assistant can only REQUEST, never EXECUTE directly.
"""

import logging
from typing import Dict, Any, Optional

from agentos.core.capabilities.execution_policy.models import PolicyDecision
from .client import GovernanceAPIClient

logger = logging.getLogger(__name__)


class SystemActions:
    """
    System Operations (MEDIUM/HIGH Risk)

    These operations demonstrate governance in action.
    They may be denied, and when denied, they explain WHY.

    Design Principle:
    - Never execute without policy approval
    - Never cache authorization
    - Never bypass policy rules
    - Always explain denials clearly

    THIS IS THE KEY: Ops Assistant must "fail gracefully and often"
    """

    def __init__(self, db_path: str):
        """
        Initialize system actions

        Args:
            db_path: Path to AgentOS database
        """
        self.client = GovernanceAPIClient(db_path)

    def request_context_refresh(
        self,
        session_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request Context Refresh (MEDIUM Risk)

        This operation modifies system state, so it requires policy evaluation.

        Expected outcomes:
        - ALLOW: Proceed with refresh
        - REQUIRE_APPROVAL: Wait for human approval
        - DENY: Blocked with explanation

        Args:
            session_id: Session identifier
            reason: Reason for refresh (optional)

        Returns:
            Result with status and explanation
        """
        logger.info(
            f"[SystemActions] Requesting context refresh for session {session_id}"
        )

        # Step 1: Evaluate policy
        policy_result = self.client.evaluate_policy(
            extension_id="system.context_refresh",
            action_id="refresh",
            session_id=session_id,
            metadata={"reason": reason or "Manual refresh request"}
        )

        # Step 2: Handle decision
        if policy_result.decision == PolicyDecision.DENY:
            logger.warning(
                f"[SystemActions] Context refresh DENIED: {policy_result.reason}"
            )

            return {
                "status": "blocked",
                "decision": "DENY",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "context": {
                    "tier": policy_result.context.tier,
                    "risk_score": policy_result.context.risk_score,
                    "session_id": session_id
                },
                "message": (
                    f"Context refresh was DENIED by policy. "
                    f"Reason: {policy_result.reason}"
                )
            }

        elif policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
            logger.info(
                f"[SystemActions] Context refresh REQUIRES APPROVAL: {policy_result.reason}"
            )

            return {
                "status": "pending_approval",
                "decision": "REQUIRE_APPROVAL",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "context": {
                    "tier": policy_result.context.tier,
                    "risk_score": policy_result.context.risk_score,
                    "session_id": session_id
                },
                "message": (
                    f"Context refresh requires human approval. "
                    f"Reason: {policy_result.reason}"
                )
            }

        else:  # ALLOW
            logger.info(
                f"[SystemActions] Context refresh ALLOWED: {policy_result.reason}"
            )

            # In MVP, simulate the refresh
            # In production, this would call actual context service
            refresh_result = self._execute_context_refresh(session_id)

            return {
                "status": "success",
                "decision": "ALLOW",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "result": refresh_result,
                "message": "Context refresh completed successfully"
            }

    def request_extension_execution(
        self,
        extension_id: str,
        action_id: str,
        args: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request Extension Execution (HIGH Risk)

        This is a HIGH risk operation that will often be denied.
        This demonstrates that governance is real and active.

        Expected outcomes:
        - ALLOW: Very rare for unknown extensions
        - REQUIRE_APPROVAL: Common for HIGH tier
        - DENY: Most common outcome (THIS IS GOOD!)

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            args: Action arguments
            session_id: Session identifier (optional)

        Returns:
            Result with status and explanation
        """
        logger.info(
            f"[SystemActions] Requesting execution of {extension_id}/{action_id}"
        )

        # Step 1: Evaluate policy
        policy_result = self.client.evaluate_policy(
            extension_id=extension_id,
            action_id=action_id,
            session_id=session_id,
            metadata={"args": args}
        )

        # Step 2: Handle decision
        if policy_result.decision == PolicyDecision.DENY:
            logger.warning(
                f"[SystemActions] Extension execution DENIED: {policy_result.reason}"
            )

            return {
                "status": "denied",
                "decision": "DENY",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "context": {
                    "extension_id": extension_id,
                    "action_id": action_id,
                    "tier": policy_result.context.tier,
                    "risk_score": policy_result.context.risk_score,
                    "auth_status": policy_result.context.auth_status,
                    "sandbox_available": policy_result.context.sandbox_available
                },
                "message": (
                    f"Extension execution was DENIED by policy.\n"
                    f"Reason: {policy_result.reason}\n"
                    f"Trust Tier: {policy_result.context.tier}\n"
                    f"Risk Score: {policy_result.context.risk_score:.1f}"
                ),
                "explanation": self._explain_denial(policy_result)
            }

        elif policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
            logger.info(
                f"[SystemActions] Extension execution REQUIRES APPROVAL: {policy_result.reason}"
            )

            return {
                "status": "pending_approval",
                "decision": "REQUIRE_APPROVAL",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "context": {
                    "extension_id": extension_id,
                    "action_id": action_id,
                    "tier": policy_result.context.tier,
                    "risk_score": policy_result.context.risk_score
                },
                "message": (
                    f"Extension execution requires human approval.\n"
                    f"Reason: {policy_result.reason}\n"
                    f"Trust Tier: {policy_result.context.tier}\n"
                    f"Risk Score: {policy_result.context.risk_score:.1f}"
                ),
                "approval_required": True
            }

        else:  # ALLOW
            logger.info(
                f"[SystemActions] Extension execution ALLOWED: {policy_result.reason}"
            )

            # In MVP, simulate the execution
            # In production, this would call actual execution service
            exec_result = self._execute_extension(extension_id, action_id, args)

            return {
                "status": "success",
                "decision": "ALLOW",
                "reason": policy_result.reason,
                "rules_applied": policy_result.rules_applied,
                "result": exec_result,
                "message": "Extension execution completed successfully"
            }

    def demonstrate_denial(self) -> Dict[str, Any]:
        """
        Demonstrate that HIGH risk operations are often denied

        This is a key test: Can we prove governance works by
        showing that dangerous operations are blocked?

        Returns:
            Demonstration results showing denials
        """
        logger.info("[SystemActions] Demonstrating HIGH risk denials")

        results = {
            "test": "HIGH_RISK_DENIALS",
            "expected": "Most requests should be DENIED or REQUIRE_APPROVAL",
            "results": []
        }

        # Test 1: Try to execute unknown extension
        test_cases = [
            {
                "extension_id": "dangerous_extension",
                "action_id": "dangerous_action",
                "args": {},
                "expected": "DENY or REQUIRE_APPROVAL"
            },
            {
                "extension_id": "system.shell",
                "action_id": "execute",
                "args": {"command": "rm -rf /"},
                "expected": "DENY"
            },
            {
                "extension_id": "file.operations",
                "action_id": "delete_all",
                "args": {},
                "expected": "DENY"
            }
        ]

        for test_case in test_cases:
            result = self.request_extension_execution(
                extension_id=test_case["extension_id"],
                action_id=test_case["action_id"],
                args=test_case["args"]
            )

            results["results"].append({
                "extension_id": test_case["extension_id"],
                "action_id": test_case["action_id"],
                "decision": result["decision"],
                "status": result["status"],
                "reason": result["reason"],
                "expected": test_case["expected"],
                "passed": result["status"] in ["denied", "pending_approval"]
            })

        # Calculate pass rate
        passed_count = sum(1 for r in results["results"] if r["passed"])
        total_count = len(results["results"])
        results["pass_rate"] = f"{passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)"

        logger.info(
            f"[SystemActions] HIGH risk demonstration: {results['pass_rate']} "
            f"correctly denied or required approval"
        )

        return results

    def _execute_context_refresh(self, session_id: str) -> Dict[str, Any]:
        """
        Execute context refresh (internal, after policy approval)

        Args:
            session_id: Session identifier

        Returns:
            Refresh result
        """
        # In MVP, return mock result
        return {
            "session_id": session_id,
            "refreshed_at": "2026-02-02T00:00:00Z",
            "status": "completed",
            "message": "Context refresh simulated (MVP)"
        }

    def _execute_extension(
        self,
        extension_id: str,
        action_id: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute extension (internal, after policy approval)

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            args: Action arguments

        Returns:
            Execution result
        """
        # In MVP, return mock result
        return {
            "extension_id": extension_id,
            "action_id": action_id,
            "executed_at": "2026-02-02T00:00:00Z",
            "status": "completed",
            "message": "Extension execution simulated (MVP)"
        }

    def _explain_denial(self, policy_result) -> str:
        """
        Generate clear explanation for denial

        This is crucial: When denied, users need to understand WHY.

        Args:
            policy_result: Policy decision result

        Returns:
            Human-readable explanation
        """
        explanation = [
            "Your request was denied by the governance system.",
            "",
            f"Reason: {policy_result.reason}",
            "",
            "Context:",
            f"- Trust Tier: {policy_result.context.tier}",
            f"- Risk Score: {policy_result.context.risk_score:.1f}",
            f"- Authorization Status: {policy_result.context.auth_status}",
            f"- Sandbox Available: {policy_result.context.sandbox_available}",
            "",
            "Rules Applied:",
        ]

        for rule in policy_result.rules_applied:
            explanation.append(f"- {rule}")

        explanation.extend([
            "",
            "What this means:",
            "Governance is protecting the system from potentially dangerous operations.",
            "This is by design - Ops Assistant cannot bypass these protections.",
            "",
            "Next steps:",
            "1. Review the risk factors above",
            "2. Consider if the operation is truly necessary",
            "3. If needed, contact an administrator for review"
        ])

        return "\n".join(explanation)
