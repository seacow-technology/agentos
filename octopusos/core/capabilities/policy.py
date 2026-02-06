"""
Tool Policy Engine - Access control and gating for tool invocations

This module provides the policy engine that controls whether tool invocations
are allowed based on risk level, side effects, and other criteria.

7-Layer Security Gate System:
1. Mode Gate: Planning mode blocks side effects
2. Spec Frozen Gate: Execution requires frozen specs
3. Project Binding Gate: Requires project_id
4. Quota Gate: Resource quota checks (calls, concurrency, runtime, cost)
5. Policy Gate: Risk level and side effect policies
6. Admin Token Gate: High-risk operations require admin approval
7. Audit Gate: Complete audit trail

Example:
    from agentos.core.capabilities.policy import ToolPolicyEngine
    from agentos.core.capabilities.capability_models import (
        ToolDescriptor,
        ToolInvocation,
        RiskLevel
    )

    engine = ToolPolicyEngine()

    # Check if invocation is allowed
    allowed, reason, decision = engine.check_allowed(tool, invocation, admin_token)
    if not allowed:
        print(f"Denied: {reason}")
"""

import logging
import sqlite3
from pathlib import Path
from typing import Tuple, Optional, Callable

from agentos.core.capabilities.capability_models import (
    ToolDescriptor,
    ToolInvocation,
    PolicyDecision,
    RiskLevel,
    ExecutionMode,
    TrustTier,
)
from agentos.core.capabilities.trust_tier_defaults import (
    get_default_risk_level,
    should_require_admin_token,
    get_side_effects_policy,
)

logger = logging.getLogger(__name__)


class ToolPolicyEngine:
    """
    Tool policy engine for access control with 7-layer security gates

    Gates:
    1. Mode Gate: Planning mode blocks side effects
    2. Spec Frozen Gate: Execution requires frozen specs
    3. Project Binding Gate: Requires project_id
    4. Quota Gate: Resource quota checks (calls, concurrency, runtime, cost)
    5. Policy Gate: Risk level and side effect policies
    6. Admin Token Gate: High-risk operations require admin approval
    7. Audit Gate: Complete audit trail (handled by caller)
    """

    def __init__(
        self,
        task_db_path: Optional[Path] = None,
        admin_token_validator: Optional[Callable[[str], bool]] = None,
        quota_manager: Optional['QuotaManager'] = None
    ):
        """
        Initialize policy engine

        Args:
            task_db_path: Path to TaskDB (for spec_frozen verification)
            admin_token_validator: Function to validate admin tokens
            quota_manager: QuotaManager for quota gate checks (optional)
        """
        self.task_db_path = task_db_path
        self.admin_token_validator = admin_token_validator
        self.quota_manager = quota_manager

        # Default blacklisted side effects
        self.blacklisted_effects = ["payments", "cloud.key_delete"]

    def check_allowed(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation,
        admin_token: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[PolicyDecision]]:
        """
        Check if tool invocation is allowed through 7-layer gates

        Args:
            tool: ToolDescriptor for the tool being invoked
            invocation: ToolInvocation request
            admin_token: Admin token for high-risk operations (optional)

        Returns:
            (allowed, denial_reason, decision)
            - allowed: True if all gates pass
            - denial_reason: Reason for denial if not allowed
            - decision: PolicyDecision object with full context
        """
        # Gate 0: Check if tool is enabled
        if not tool.enabled:
            reason = f"Tool '{tool.name}' is disabled"
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 1: Mode Gate
        allowed, reason = self._check_mode_gate(tool, invocation)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 2: Spec Frozen Gate
        allowed, reason = self._check_spec_frozen_gate(invocation)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 3: Project Binding Gate
        allowed, reason = self._check_project_binding_gate(invocation)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 4: Quota Gate
        allowed, reason = self._check_quota_gate(tool, invocation)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 5: Policy Gate (blacklist, risk policies)
        allowed, reason = self._check_policy_gate(tool, invocation)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=False
            )
            return (False, reason, decision)

        # Gate 6: Admin Token Gate
        allowed, reason = self._check_admin_token_gate(tool, admin_token)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason=reason,
                requires_approval=True,
                approval_context=self.get_approval_context(tool, invocation)
            )
            return (False, reason, decision)

        # All gates passed
        logger.debug(f"Policy check for {tool.tool_id}: ALLOWED (all gates passed)")
        decision = PolicyDecision(
            allowed=True,
            reason=None,
            requires_approval=False,
            approval_context=None
        )
        return (True, None, decision)

    def _check_mode_gate(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 1: Mode Gate - Planning mode blocks side effects

        Rules:
        - mode == "planning" + side_effects non-empty → DENY
        - mode == "execution" → ALLOW (continue to next gate)

        Args:
            tool: ToolDescriptor
            invocation: ToolInvocation

        Returns:
            (allowed, reason)
        """
        if invocation.mode == ExecutionMode.PLANNING:
            if tool.side_effect_tags:
                return (
                    False,
                    f"Tool '{tool.name}' has side effects {tool.side_effect_tags} "
                    f"and cannot be executed in planning mode"
                )

        return (True, None)

    def _check_spec_frozen_gate(
        self,
        invocation: ToolInvocation
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 2: Spec Frozen Gate - Execution requires frozen spec

        Rules:
        - mode == "execution" + spec_frozen == False → DENY
        - mode == "execution" + spec_hash empty → DENY
        - task_id exists → verify TaskDB spec_frozen

        Args:
            invocation: ToolInvocation

        Returns:
            (allowed, reason)
        """
        if invocation.mode == ExecutionMode.EXECUTION:
            if not invocation.spec_frozen:
                return (
                    False,
                    "Execution mode requires spec_frozen=True"
                )

            if not invocation.spec_hash:
                return (
                    False,
                    "Execution mode requires spec_hash"
                )

            # If task_id exists, verify TaskDB
            if invocation.task_id and self.task_db_path:
                if not self._verify_task_spec_frozen(invocation.task_id):
                    return (
                        False,
                        f"Task {invocation.task_id} spec is not frozen in TaskDB"
                    )

        return (True, None)

    def _verify_task_spec_frozen(self, task_id: str) -> bool:
        """
        Query TaskDB to verify task's spec_frozen status

        Args:
            task_id: Task identifier

        Returns:
            True if task spec is frozen, False otherwise
        """
        try:
            from agentos.store import get_db_path

            db_path = self.task_db_path or get_db_path()
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT spec_frozen FROM tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                logger.warning(f"Task {task_id} not found in TaskDB")
                return False

            return bool(row[0])
        except Exception as e:
            logger.error(f"Failed to verify task spec_frozen: {e}", exc_info=True)
            return False

    def _check_project_binding_gate(
        self,
        invocation: ToolInvocation
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 3: Project Binding Gate - Require project_id

        Rules:
        - project_id empty → DENY

        Args:
            invocation: ToolInvocation

        Returns:
            (allowed, reason)
        """
        if not invocation.project_id:
            return (
                False,
                "Tool invocation must be bound to a project_id"
            )

        return (True, None)

    def _check_quota_gate(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 4: Quota Gate - 检查配额限制

        规则:
        - 超限 → DENY
        - 临界 → WARN(允许但记录)
        - 正常 → ALLOW

        Args:
            tool: ToolDescriptor
            invocation: ToolInvocation

        Returns:
            (allowed, reason)
        """
        if not self.quota_manager:
            # 无配额管理器,默认允许
            return (True, None)

        # 构造 quota_id(可以基于 tool_id, source_id 等)
        quota_id = f"tool:{tool.tool_id}"

        # 检查配额
        result = self.quota_manager.check_quota(quota_id)

        if not result.allowed:
            # 超限,拒绝
            logger.warning(
                f"Quota exceeded for {tool.tool_id}: {result.reason}"
            )
            # 发送超限审计事件
            from agentos.core.capabilities.audit import emit_quota_exceeded
            emit_quota_exceeded(invocation, tool, result.reason)
            return (False, f"Quota exceeded: {result.reason}")

        if result.warning:
            # 临界,警告
            logger.info(
                f"Quota warning for {tool.tool_id}: approaching limit"
            )
            # 发送警告审计事件
            from agentos.core.capabilities.audit import emit_quota_warning
            emit_quota_warning(invocation, tool, result.state.model_dump())

        return (True, None)

    def _check_policy_gate(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 5: Policy Gate - Risk and side effect policies

        Rules (configurable):
        - Blacklisted side effects (e.g., payments) → DENY
        - Trust tier-based side effects policy
        - Can add more policies (per-project, per-user, time-based, etc.)

        Args:
            tool: ToolDescriptor
            invocation: ToolInvocation

        Returns:
            (allowed, reason)
        """
        # Get trust tier-based side effects policy
        se_policy = get_side_effects_policy(tool.trust_tier)

        # Check trust tier blacklist
        for effect in tool.side_effect_tags:
            if effect in se_policy["blacklisted_effects"]:
                return (
                    False,
                    f"Side effect '{effect}' is blacklisted for trust tier {tool.trust_tier.value}"
                )

        # T3 (Cloud MCP) 默认不允许副作用
        if tool.trust_tier == TrustTier.T3:
            if not se_policy["allow_side_effects"] and tool.side_effect_tags:
                return (
                    False,
                    f"Cloud MCP (T3) tools with side effects require explicit approval"
                )

        # Check global blacklisted side effects
        for effect in tool.side_effect_tags:
            if effect in self.blacklisted_effects:
                return (
                    False,
                    f"Side effect '{effect}' is blacklisted by global policy"
                )

        # Future: Add more policy rules
        # - Per-project access control
        # - Per-user permissions
        # - Time-based restrictions
        # - Rate limiting

        return (True, None)

    def _check_admin_token_gate(
        self,
        tool: ToolDescriptor,
        admin_token: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate 6: Admin Token Gate - High-risk operations require approval

        Rules:
        - requires_admin_token == True + admin_token empty → DENY
        - requires_admin_token == True + token invalid → DENY
        - risk_level == CRITICAL + admin_token empty → DENY
        - Trust tier-based admin token requirement

        Args:
            tool: ToolDescriptor
            admin_token: Admin token (optional)

        Returns:
            (allowed, reason)
        """
        # Check trust tier-based admin token requirement
        trust_tier_needs_admin = should_require_admin_token(
            tool.trust_tier,
            has_side_effects=bool(tool.side_effect_tags)
        )

        needs_admin = (
            tool.requires_admin_token or
            tool.risk_level == RiskLevel.CRITICAL or
            trust_tier_needs_admin
        )

        if needs_admin:
            if not admin_token:
                return (
                    False,
                    f"Tool '{tool.name}' (risk={tool.risk_level.value}, "
                    f"trust_tier={tool.trust_tier.value}) "
                    f"requires admin_token for approval"
                )

            # Validate token if validator is provided
            if self.admin_token_validator:
                if not self.admin_token_validator(admin_token):
                    return (False, "Invalid admin_token")

        return (True, None)

    def check_side_effects_allowed(
        self,
        side_effects: list[str],
        invocation: ToolInvocation
    ) -> PolicyDecision:
        """
        Check if specific side effects are allowed

        Args:
            side_effects: List of side effect tags
            invocation: ToolInvocation request

        Returns:
            PolicyDecision
        """
        # Check against blacklist
        for effect in side_effects:
            if effect in self.blacklisted_effects:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Side effect '{effect}' is blacklisted by policy",
                    requires_approval=False,
                    approval_context=None
                )

        return PolicyDecision(
            allowed=True,
            reason=None,
            requires_approval=False,
            approval_context=None
        )

    def requires_spec_freezing(self, tool: ToolDescriptor) -> bool:
        """
        Check if tool requires spec freezing

        Spec freezing means the task plan must be immutable before execution.
        This prevents malicious modifications during execution.

        Args:
            tool: ToolDescriptor

        Returns:
            True if spec freezing is required
        """
        # High-risk and critical tools require spec freezing
        return tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def requires_admin_approval(self, tool: ToolDescriptor) -> bool:
        """
        Check if tool requires admin approval

        Args:
            tool: ToolDescriptor

        Returns:
            True if admin approval is required
        """
        # Critical operations or explicitly marked tools
        return (
            tool.risk_level == RiskLevel.CRITICAL or
            tool.requires_admin_token or
            "payments" in tool.side_effect_tags
        )

    def get_approval_context(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation
    ) -> dict:
        """
        Get context for approval request

        Args:
            tool: ToolDescriptor
            invocation: ToolInvocation request

        Returns:
            Dict with approval context information

        For PR-3: Will provide rich context for approval UI
        """
        return {
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "risk_level": tool.risk_level.value,
            "side_effects": tool.side_effect_tags,
            "actor": invocation.actor,
            "timestamp": invocation.timestamp.isoformat(),
            "inputs": invocation.inputs,
        }
