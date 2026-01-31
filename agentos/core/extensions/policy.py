"""Policy checker for extension runtime enforcement"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PolicyCheckResult:
    """Result of a policy check operation"""
    allowed: bool
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    hint: Optional[str] = None


class PolicyChecker:
    """
    PolicyChecker enforces AgentOS governance policies for extensions.

    Currently enforces Python-only runtime policy to prevent external binary
    execution for security and portability reasons.
    """

    @staticmethod
    def check_runtime_policy(manifest: dict) -> PolicyCheckResult:
        """
        Check if the extension complies with Python-only runtime policy.

        Validates that:
        1. The manifest specifies "python" as the runtime
        2. The manifest has an empty external_bins array

        Args:
            manifest: Extension manifest dictionary

        Returns:
            PolicyCheckResult indicating whether the extension is allowed
            and providing detailed reason/hint if not allowed
        """
        # Check if runtime field exists
        runtime = manifest.get("runtime")
        if runtime is None:
            return PolicyCheckResult(
                allowed=False,
                reason="Extension manifest missing required 'runtime' field. Only Python runtime extensions are currently supported.",
                reason_code="POLICY_RUNTIME_FIELD_MISSING",
                hint="Please add 'runtime: python' to your manifest.json file."
            )

        # Check if runtime is "python"
        if runtime != "python":
            return PolicyCheckResult(
                allowed=False,
                reason="Extension requires external binary runtime which violates AgentOS governance policy. Only Python runtime extensions are currently supported.",
                reason_code="POLICY_EXTERNAL_BINARY_FORBIDDEN",
                hint="Please convert this extension to use pure Python implementation, or contact admin for Tier 2 exception approval."
            )

        # Check if external_bins field exists
        if "external_bins" not in manifest:
            return PolicyCheckResult(
                allowed=False,
                reason="Extension manifest missing required 'external_bins' field. This field must be an empty array for Python-only extensions.",
                reason_code="POLICY_EXTERNAL_BINS_FIELD_MISSING",
                hint="Please add 'external_bins: []' to your manifest.json file."
            )

        # Check if external_bins is an array
        external_bins = manifest.get("external_bins")
        if not isinstance(external_bins, list):
            return PolicyCheckResult(
                allowed=False,
                reason="Extension manifest 'external_bins' field must be an array. Found type: " + type(external_bins).__name__,
                reason_code="POLICY_EXTERNAL_BINS_INVALID_TYPE",
                hint="Please ensure 'external_bins' is an array (e.g., 'external_bins: []')."
            )

        # Check if external_bins is empty
        if len(external_bins) > 0:
            return PolicyCheckResult(
                allowed=False,
                reason="Extension requires external binary runtime which violates AgentOS governance policy. Only Python runtime extensions are currently supported.",
                reason_code="POLICY_EXTERNAL_BINARY_FORBIDDEN",
                hint="Please convert this extension to use pure Python implementation, or contact admin for Tier 2 exception approval."
            )

        # All checks passed
        return PolicyCheckResult(
            allowed=True,
            reason="Extension complies with Python-only runtime policy",
            reason_code="POLICY_COMPLIANT"
        )
