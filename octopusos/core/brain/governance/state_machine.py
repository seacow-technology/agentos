"""
Decision State Machine - 决策状态机（P4-D）

状态转换规则（冻结）：

PENDING → APPROVED (if final_verdict = ALLOW)
PENDING → BLOCKED (if final_verdict = BLOCK)
PENDING → SIGNED (if final_verdict = REQUIRE_SIGNOFF and signoff completed)
PENDING → FAILED (if error occurs)

不允许的转换：
- PENDING → APPROVED (when final_verdict = REQUIRE_SIGNOFF)
- SIGNED → PENDING
- BLOCKED → APPROVED
- APPROVED → BLOCKED
- Any transition from terminal states (APPROVED, BLOCKED, SIGNED, FAILED)

核心原则：
1. 状态机保证决策流程的确定性
2. 终态不可逆转
3. REQUIRE_SIGNOFF 必须经过签字才能完成
4. Red Line 4: REQUIRE_SIGNOFF 状态阻止操作继续
"""

from enum import Enum
from typing import List, Optional
from .decision_record import DecisionStatus, GovernanceAction


class StateTransition(Enum):
    """状态转换类型"""
    APPROVE = "APPROVE"          # 批准（允许操作）
    BLOCK = "BLOCK"              # 阻止（拒绝操作）
    SIGNOFF = "SIGNOFF"          # 签字（完成审批）
    FAIL = "FAIL"                # 失败（错误）


class StateTransitionError(Exception):
    """非法状态转换异常"""
    pass


def validate_state_transition(
    current_status: DecisionStatus,
    target_status: DecisionStatus,
    final_verdict: GovernanceAction
) -> bool:
    """
    验证状态转换是否合法

    Args:
        current_status: 当前状态
        target_status: 目标状态
        final_verdict: 最终裁决

    Returns:
        True if valid, False otherwise

    Rules:
        1. PENDING → APPROVED: only if final_verdict = ALLOW
        2. PENDING → BLOCKED: only if final_verdict = BLOCK
        3. PENDING → SIGNED: only if final_verdict = REQUIRE_SIGNOFF
        4. PENDING → FAILED: always allowed (error handling)
        5. Terminal states (APPROVED, BLOCKED, SIGNED, FAILED) → any: FORBIDDEN
    """
    # 终态不允许转换
    terminal_states = [
        DecisionStatus.APPROVED,
        DecisionStatus.BLOCKED,
        DecisionStatus.SIGNED,
        DecisionStatus.FAILED
    ]

    if current_status in terminal_states:
        return False

    # PENDING → APPROVED（只有 final_verdict = ALLOW 时）
    if current_status == DecisionStatus.PENDING and target_status == DecisionStatus.APPROVED:
        return final_verdict == GovernanceAction.ALLOW

    # PENDING → BLOCKED（只有 final_verdict = BLOCK 时）
    if current_status == DecisionStatus.PENDING and target_status == DecisionStatus.BLOCKED:
        return final_verdict == GovernanceAction.BLOCK

    # PENDING → SIGNED（只有 final_verdict = REQUIRE_SIGNOFF 时）
    if current_status == DecisionStatus.PENDING and target_status == DecisionStatus.SIGNED:
        return final_verdict == GovernanceAction.REQUIRE_SIGNOFF

    # PENDING → FAILED（总是允许，用于错误处理）
    if current_status == DecisionStatus.PENDING and target_status == DecisionStatus.FAILED:
        return True

    # 其他转换：禁止
    return False


def get_allowed_transitions(
    current_status: DecisionStatus,
    final_verdict: GovernanceAction
) -> List[DecisionStatus]:
    """
    获取当前状态下允许的转换

    Args:
        current_status: 当前状态
        final_verdict: 最终裁决

    Returns:
        允许的目标状态列表

    Example:
        >>> get_allowed_transitions(DecisionStatus.PENDING, GovernanceAction.ALLOW)
        [DecisionStatus.APPROVED, DecisionStatus.FAILED]
    """
    allowed = []

    if current_status == DecisionStatus.PENDING:
        # 基于 final_verdict 确定允许的转换
        if final_verdict == GovernanceAction.ALLOW:
            allowed.append(DecisionStatus.APPROVED)
        elif final_verdict == GovernanceAction.BLOCK:
            allowed.append(DecisionStatus.BLOCKED)
        elif final_verdict == GovernanceAction.REQUIRE_SIGNOFF:
            allowed.append(DecisionStatus.SIGNED)
        elif final_verdict == GovernanceAction.WARN:
            # WARN 视为 ALLOW（带警告）
            allowed.append(DecisionStatus.APPROVED)

        # 失败总是允许
        allowed.append(DecisionStatus.FAILED)

    # 终态：不允许转换
    # （列表为空）

    return allowed


def apply_transition(
    current_status: DecisionStatus,
    transition: StateTransition,
    final_verdict: GovernanceAction
) -> DecisionStatus:
    """
    应用状态转换

    Args:
        current_status: 当前状态
        transition: 转换类型
        final_verdict: 最终裁决

    Returns:
        新状态

    Raises:
        StateTransitionError: 非法转换

    Example:
        >>> apply_transition(DecisionStatus.PENDING, StateTransition.APPROVE, GovernanceAction.ALLOW)
        DecisionStatus.APPROVED
    """
    # 确定目标状态
    target_status = None

    if transition == StateTransition.APPROVE:
        target_status = DecisionStatus.APPROVED
    elif transition == StateTransition.BLOCK:
        target_status = DecisionStatus.BLOCKED
    elif transition == StateTransition.SIGNOFF:
        target_status = DecisionStatus.SIGNED
    elif transition == StateTransition.FAIL:
        target_status = DecisionStatus.FAILED

    if target_status is None:
        raise StateTransitionError(f"Unknown transition: {transition}")

    # 验证转换合法性
    if not validate_state_transition(current_status, target_status, final_verdict):
        raise StateTransitionError(
            f"Invalid state transition: {current_status.value} → {target_status.value} "
            f"(final_verdict={final_verdict.value})"
        )

    return target_status


def can_proceed_with_verdict(
    status: DecisionStatus,
    final_verdict: GovernanceAction
) -> tuple[bool, Optional[str]]:
    """
    判断决策是否允许操作继续（Red Line 4）

    Args:
        status: 决策状态
        final_verdict: 最终裁决

    Returns:
        (can_proceed, blocking_reason)
        - can_proceed: True if operation can proceed
        - blocking_reason: 阻止原因（如果被阻止）

    Red Line 4 规则：
    - BLOCK: 总是阻止
    - REQUIRE_SIGNOFF + PENDING: 阻止（需要签字）
    - REQUIRE_SIGNOFF + SIGNED: 允许
    - WARN: 允许（带警告）
    - ALLOW: 允许

    Example:
        >>> can_proceed_with_verdict(DecisionStatus.PENDING, GovernanceAction.BLOCK)
        (False, "Decision is blocked by governance rules")

        >>> can_proceed_with_verdict(DecisionStatus.PENDING, GovernanceAction.REQUIRE_SIGNOFF)
        (False, "Decision requires human signoff before proceeding")

        >>> can_proceed_with_verdict(DecisionStatus.SIGNED, GovernanceAction.REQUIRE_SIGNOFF)
        (True, None)
    """
    # BLOCK: 总是阻止
    if final_verdict == GovernanceAction.BLOCK:
        return False, "Decision is blocked by governance rules"

    # REQUIRE_SIGNOFF: 只有 SIGNED 状态才允许
    if final_verdict == GovernanceAction.REQUIRE_SIGNOFF:
        if status == DecisionStatus.SIGNED:
            return True, None
        elif status == DecisionStatus.PENDING:
            return False, "Decision requires human signoff before proceeding"
        else:
            return False, f"Decision in unexpected state: {status.value}"

    # ALLOW 或 WARN: 允许（APPROVED 或 PENDING 状态）
    if final_verdict in [GovernanceAction.ALLOW, GovernanceAction.WARN]:
        if status in [DecisionStatus.APPROVED, DecisionStatus.PENDING]:
            return True, None
        else:
            return False, f"Decision in unexpected state: {status.value}"

    # 其他情况：阻止
    return False, f"Unknown final verdict: {final_verdict.value}"


def get_state_diagram() -> str:
    """
    返回状态机图示（用于文档）

    Returns:
        ASCII 状态机图
    """
    return """
Decision State Machine (P4-D)
==============================

┌─────────┐
│ PENDING │ (initial state)
└────┬────┘
     │
     ├───[final_verdict = ALLOW]─────────────> APPROVED (terminal)
     │
     ├───[final_verdict = BLOCK]─────────────> BLOCKED (terminal)
     │
     ├───[final_verdict = REQUIRE_SIGNOFF]──> SIGNED (terminal, after human signoff)
     │
     └───[error]─────────────────────────────> FAILED (terminal)


Terminal States: APPROVED, BLOCKED, SIGNED, FAILED
- No transitions allowed from terminal states
- Terminal states are immutable

Red Line 4 Enforcement:
- BLOCK: Operation rejected immediately
- REQUIRE_SIGNOFF + PENDING: Operation blocked until signoff
- REQUIRE_SIGNOFF + SIGNED: Operation allowed
- WARN/ALLOW: Operation allowed (may log warning)
"""


# 状态机验证函数（用于测试）
def verify_state_machine_integrity() -> List[str]:
    """
    验证状态机完整性

    Returns:
        错误列表（空列表表示通过）

    验证项：
    1. 所有 PENDING → X 转换必须有对应的 final_verdict
    2. 终态不允许任何转换
    3. REQUIRE_SIGNOFF 只能转换为 SIGNED
    """
    errors = []

    # 测试 1: PENDING → APPROVED 需要 ALLOW
    if validate_state_transition(
        DecisionStatus.PENDING,
        DecisionStatus.APPROVED,
        GovernanceAction.BLOCK  # 错误的 verdict
    ):
        errors.append("PENDING → APPROVED should require ALLOW verdict")

    # 测试 2: 终态不允许转换
    for terminal_state in [DecisionStatus.APPROVED, DecisionStatus.BLOCKED, DecisionStatus.SIGNED]:
        if validate_state_transition(
            terminal_state,
            DecisionStatus.PENDING,
            GovernanceAction.ALLOW
        ):
            errors.append(f"{terminal_state.value} should not allow transition to PENDING")

    # 测试 3: REQUIRE_SIGNOFF 只能转换为 SIGNED
    if validate_state_transition(
        DecisionStatus.PENDING,
        DecisionStatus.APPROVED,
        GovernanceAction.REQUIRE_SIGNOFF
    ):
        errors.append("PENDING with REQUIRE_SIGNOFF should not allow APPROVED")

    return errors
