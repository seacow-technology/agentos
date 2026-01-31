"""
Governance Rule Engine - 治理规则引擎

负责：
1. 定义治理规则
2. 评估决策是否触发规则
3. 返回治理动作（ALLOW/WARN/BLOCK/REQUIRE_SIGNOFF）

规则类型：
- Navigation 规则：基于风险等级、盲区数量、置信度
- Compare 规则：基于健康分数变化、实体变化
- Health 规则：基于认知债务、趋势方向
"""

from typing import Dict, Any, List, Tuple
from .decision_record import GovernanceAction, RuleTrigger, DecisionType


class GovernanceRule:
    """治理规则基类"""

    def __init__(self, rule_id: str, rule_name: str, description: str):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.description = description

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        """
        评估规则是否触发

        Returns:
            (is_triggered, action, rationale)
        """
        raise NotImplementedError


# ==================== Navigation 规则 ====================

class HighRiskBlockRule(GovernanceRule):
    """高风险阻止规则：阻止高风险导航"""

    def __init__(self):
        super().__init__(
            rule_id="NAV-001",
            rule_name="High Risk Navigation Block",
            description="Block navigation with HIGH risk level"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.NAVIGATION:
            return False, GovernanceAction.ALLOW, ""

        # 检查是否有路径
        paths_count = outputs.get("paths_count", 0)
        if paths_count == 0:
            return False, GovernanceAction.ALLOW, ""

        # 注意：这里需要从 paths 中检查 risk_level
        # 简化实现：假设 outputs 中包含 max_risk_level
        max_risk = outputs.get("max_risk_level", "LOW")

        if max_risk == "HIGH":
            return True, GovernanceAction.BLOCK, "Navigation contains HIGH risk paths"

        return False, GovernanceAction.ALLOW, ""


class LowConfidenceWarnRule(GovernanceRule):
    """低置信度警告规则：警告低置信度导航"""

    def __init__(self):
        super().__init__(
            rule_id="NAV-002",
            rule_name="Low Confidence Warning",
            description="Warn when navigation confidence is below threshold"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.NAVIGATION:
            return False, GovernanceAction.ALLOW, ""

        # 检查置信度（需要在 decision_recorder 中计算）
        # 这里简化：假设 confidence 在 outputs 中
        avg_confidence = outputs.get("avg_confidence", 1.0)

        if avg_confidence < 0.5:
            return True, GovernanceAction.WARN, f"Average confidence ({avg_confidence:.2f}) below 0.5"

        return False, GovernanceAction.ALLOW, ""


class ManyBlindSpotsSignoffRule(GovernanceRule):
    """多盲区签字规则：盲区数量过多需要签字"""

    def __init__(self):
        super().__init__(
            rule_id="NAV-003",
            rule_name="Many Blind Spots Require Signoff",
            description="Require signoff when navigation crosses many blind spots"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.NAVIGATION:
            return False, GovernanceAction.ALLOW, ""

        # 检查盲区数量（需要从 paths 中统计）
        total_blind_spots = outputs.get("total_blind_spots", 0)

        if total_blind_spots >= 3:
            return True, GovernanceAction.REQUIRE_SIGNOFF, f"Navigation crosses {total_blind_spots} blind spots"

        return False, GovernanceAction.ALLOW, ""


# ==================== Compare 规则 ====================

class HealthScoreDropBlockRule(GovernanceRule):
    """健康分数下降阻止规则：显著下降需要阻止"""

    def __init__(self):
        super().__init__(
            rule_id="CMP-001",
            rule_name="Health Score Drop Block",
            description="Block when health score drops significantly"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.COMPARE:
            return False, GovernanceAction.ALLOW, ""

        health_change = outputs.get("health_score_change", 0.0)

        if health_change < -0.2:  # 下降超过 20%
            return True, GovernanceAction.BLOCK, f"Health score dropped by {abs(health_change):.1%}"

        return False, GovernanceAction.ALLOW, ""


class EntityRemovalWarnRule(GovernanceRule):
    """实体删除警告规则：大量实体被删除需要警告"""

    def __init__(self):
        super().__init__(
            rule_id="CMP-002",
            rule_name="Entity Removal Warning",
            description="Warn when many entities are removed"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.COMPARE:
            return False, GovernanceAction.ALLOW, ""

        entities_removed = outputs.get("entities_removed", 0)

        if entities_removed >= 10:
            return True, GovernanceAction.WARN, f"{entities_removed} entities removed"

        return False, GovernanceAction.ALLOW, ""


# ==================== Health 规则 ====================

class CriticalHealthSignoffRule(GovernanceRule):
    """危急健康签字规则：健康水平危急需要签字"""

    def __init__(self):
        super().__init__(
            rule_id="HLT-001",
            rule_name="Critical Health Requires Signoff",
            description="Require signoff when health level is CRITICAL"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.HEALTH:
            return False, GovernanceAction.ALLOW, ""

        health_level = outputs.get("current_health_level", "HEALTHY")

        if health_level == "CRITICAL":
            return True, GovernanceAction.REQUIRE_SIGNOFF, "System health is CRITICAL"

        return False, GovernanceAction.ALLOW, ""


class HighCognitiveDebtWarnRule(GovernanceRule):
    """高认知债务警告规则：认知债务过高需要警告"""

    def __init__(self):
        super().__init__(
            rule_id="HLT-002",
            rule_name="High Cognitive Debt Warning",
            description="Warn when cognitive debt count is high"
        )

    def evaluate(self, decision_type: DecisionType, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Tuple[bool, GovernanceAction, str]:
        if decision_type != DecisionType.HEALTH:
            return False, GovernanceAction.ALLOW, ""

        debt_count = outputs.get("cognitive_debt_count", 0)

        if debt_count >= 50:
            return True, GovernanceAction.WARN, f"Cognitive debt count is {debt_count}"

        return False, GovernanceAction.ALLOW, ""


# ==================== 规则引擎 ====================

# 全局规则注册表
GOVERNANCE_RULES: List[GovernanceRule] = [
    # Navigation 规则
    HighRiskBlockRule(),
    LowConfidenceWarnRule(),
    ManyBlindSpotsSignoffRule(),

    # Compare 规则
    HealthScoreDropBlockRule(),
    EntityRemovalWarnRule(),

    # Health 规则
    CriticalHealthSignoffRule(),
    HighCognitiveDebtWarnRule(),
]


def apply_governance_rules(
    decision_type: DecisionType,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    use_config_rules: bool = True
) -> Tuple[List[RuleTrigger], GovernanceAction]:
    """
    应用所有治理规则（P4-B: 支持配置规则）

    Args:
        decision_type: 决策类型
        inputs: 决策输入
        outputs: 决策输出
        use_config_rules: 是否使用配置文件规则（默认 True）

    Returns:
        (rules_triggered, final_verdict)
        final_verdict 是所有触发规则中最严格的动作
    """
    triggered_rules = []

    # P4-B: 获取所有规则（内置 + 配置）
    if use_config_rules:
        try:
            from .rule_loader import get_all_rules
            all_rules = get_all_rules()
        except Exception:
            # 配置加载失败，使用内置规则
            all_rules = GOVERNANCE_RULES
    else:
        all_rules = GOVERNANCE_RULES

    for rule in all_rules:
        is_triggered, action, rationale = rule.evaluate(decision_type, inputs, outputs)

        if is_triggered:
            triggered_rules.append(
                RuleTrigger(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    action=action,
                    rationale=rationale
                )
            )

    # 确定最终裁决（最严格的动作）
    final_verdict = GovernanceAction.ALLOW

    action_priority = {
        GovernanceAction.ALLOW: 0,
        GovernanceAction.WARN: 1,
        GovernanceAction.REQUIRE_SIGNOFF: 2,
        GovernanceAction.BLOCK: 3
    }

    for trigger in triggered_rules:
        if action_priority[trigger.action] > action_priority[final_verdict]:
            final_verdict = trigger.action

    return triggered_rules, final_verdict


def get_rule_by_id(rule_id: str) -> GovernanceRule:
    """根据 ID 获取规则"""
    for rule in GOVERNANCE_RULES:
        if rule.rule_id == rule_id:
            return rule
    raise ValueError(f"Rule not found: {rule_id}")


def list_all_rules(use_config_rules: bool = True) -> List[Dict[str, Any]]:
    """
    列出所有规则（P4-B: 支持配置规则）

    Args:
        use_config_rules: 是否包含配置文件规则（默认 True）

    Returns:
        规则列表
    """
    if use_config_rules:
        try:
            from .rule_loader import get_all_rules
            all_rules = get_all_rules()
        except Exception:
            all_rules = GOVERNANCE_RULES
    else:
        all_rules = GOVERNANCE_RULES

    return [
        {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "description": rule.description,
            "priority": getattr(rule, 'priority', 50)
        }
        for rule in all_rules
    ]
