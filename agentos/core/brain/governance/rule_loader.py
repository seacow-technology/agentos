"""
Rule Loader - 从配置文件加载治理规则

P4-B 实现：支持从 YAML 配置文件加载自定义治理规则

Features:
- Load rules from YAML configuration
- Build condition functions from declarative config
- Support multiple operators (==, !=, >, <, >=, <=, in)
- Integrate with existing rule engine
- Enable/disable rules via config
"""

import yaml
from pathlib import Path
from typing import List, Dict, Callable, Any, Optional
from .decision_record import GovernanceAction, DecisionType
from .rule_engine import GovernanceRule


class ConfigurableGovernanceRule(GovernanceRule):
    """
    从配置文件创建的治理规则

    继承 GovernanceRule，但通过配置文件动态生成条件函数
    """

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        description: str,
        applies_to: str,
        condition_fn: Callable[[Dict[str, Any], Dict[str, Any]], bool],
        action: GovernanceAction,
        rationale: str,
        priority: int = 50
    ):
        super().__init__(rule_id, rule_name, description)
        self.applies_to_type = DecisionType[applies_to]
        self.condition_fn = condition_fn
        self.action = action
        self.rationale_template = rationale
        self.priority = priority

    def evaluate(
        self,
        decision_type: DecisionType,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any]
    ) -> tuple[bool, GovernanceAction, str]:
        """
        评估规则是否触发

        Returns:
            (is_triggered, action, rationale)
        """
        # 检查决策类型是否匹配
        if decision_type != self.applies_to_type:
            return False, GovernanceAction.ALLOW, ""

        # 合并 inputs 和 outputs 为 context
        context = {**inputs, **outputs}

        # 评估条件
        try:
            is_triggered = self.condition_fn(context)
        except Exception as e:
            # 条件评估失败，不触发规则
            return False, GovernanceAction.ALLOW, ""

        if is_triggered:
            return True, self.action, self.rationale_template
        else:
            return False, GovernanceAction.ALLOW, ""


def build_condition_function(condition_config: Dict) -> Callable[[Dict], bool]:
    """
    从配置构建条件函数

    支持的操作符：
    - "==": 等于
    - "!=": 不等于
    - ">": 大于
    - "<": 小于
    - ">=": 大于等于
    - "<=": 小于等于
    - "in": 包含（值在列表中）
    - "contains": 包含（列表包含值）

    Args:
        condition_config: 条件配置字典
            - type: 要检查的字段名
            - operator: 比较操作符
            - value: 期望值

    Returns:
        条件函数 (context: Dict) -> bool

    Example:
        config = {
            "type": "coverage_percentage",
            "operator": "<",
            "value": 0.4
        }
        condition_fn = build_condition_function(config)
        result = condition_fn({"coverage_percentage": 0.3})  # True
    """
    cond_type = condition_config['type']
    operator = condition_config['operator']
    expected_value = condition_config['value']

    def condition_fn(context: Dict[str, Any]) -> bool:
        # 从 context 中提取值
        actual_value = context.get(cond_type)

        # 如果字段不存在，条件不成立
        if actual_value is None:
            return False

        # 应用操作符
        try:
            if operator == "==":
                return actual_value == expected_value
            elif operator == "!=":
                return actual_value != expected_value
            elif operator == ">":
                return actual_value > expected_value
            elif operator == "<":
                return actual_value < expected_value
            elif operator == ">=":
                return actual_value >= expected_value
            elif operator == "<=":
                return actual_value <= expected_value
            elif operator == "in":
                # actual_value in expected_value (expected_value should be list)
                return actual_value in expected_value
            elif operator == "contains":
                # expected_value in actual_value (actual_value should be list)
                return expected_value in actual_value
            else:
                # 未知操作符，条件不成立
                return False
        except (TypeError, ValueError):
            # 类型不匹配，条件不成立
            return False

    return condition_fn


def load_rules_from_config(config_path: str) -> List[ConfigurableGovernanceRule]:
    """
    从 YAML 配置加载规则

    Args:
        config_path: rules_config.yaml 路径

    Returns:
        List[ConfigurableGovernanceRule]: 规则列表

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 格式错误
        KeyError: 配置缺少必需字段

    Example:
        rules = load_rules_from_config("rules_config.yaml")
        for rule in rules:
            print(f"Loaded rule: {rule.rule_id}")
    """
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Rules config not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not config or 'rules' not in config:
        raise ValueError("Invalid rules config: missing 'rules' key")

    rules = []

    for rule_config in config.get('rules', []):
        # 跳过禁用的规则
        if not rule_config.get('enabled', True):
            continue

        # 验证必需字段
        required_fields = ['id', 'name', 'applies_to', 'condition', 'action', 'rationale']
        for field in required_fields:
            if field not in rule_config:
                raise KeyError(f"Rule config missing required field: {field}")

        # 构建条件函数
        try:
            condition_fn = build_condition_function(rule_config['condition'])
        except Exception as e:
            raise ValueError(f"Failed to build condition for rule {rule_config['id']}: {e}")

        # 验证 action 是有效的 GovernanceAction
        try:
            action = GovernanceAction[rule_config['action']]
        except KeyError:
            raise ValueError(f"Invalid action for rule {rule_config['id']}: {rule_config['action']}")

        # 验证 applies_to 是有效的 DecisionType
        try:
            DecisionType[rule_config['applies_to']]
        except KeyError:
            raise ValueError(f"Invalid applies_to for rule {rule_config['id']}: {rule_config['applies_to']}")

        # 创建规则
        rule = ConfigurableGovernanceRule(
            rule_id=rule_config['id'],
            rule_name=rule_config['name'],
            description=rule_config.get('description', ''),
            applies_to=rule_config['applies_to'],
            condition_fn=condition_fn,
            action=action,
            rationale=rule_config['rationale'],
            priority=rule_config.get('priority', 50)
        )

        rules.append(rule)

    return rules


def get_default_config_path() -> Path:
    """
    获取默认配置文件路径

    Returns:
        Path: 默认配置文件路径（当前模块目录下的 rules_config.yaml）
    """
    return Path(__file__).parent / "rules_config.yaml"


def load_default_rules() -> List[ConfigurableGovernanceRule]:
    """
    加载默认规则配置

    Returns:
        List[ConfigurableGovernanceRule]: 默认规则列表

    Raises:
        FileNotFoundError: 默认配置文件不存在
    """
    default_config = get_default_config_path()
    return load_rules_from_config(str(default_config))


def merge_rules(
    builtin_rules: List[GovernanceRule],
    config_rules: List[ConfigurableGovernanceRule]
) -> List[GovernanceRule]:
    """
    合并内置规则和配置规则

    规则合并策略：
    1. 配置规则优先（如果 rule_id 相同，配置规则覆盖内置规则）
    2. 按 priority 排序（高优先级在前）

    Args:
        builtin_rules: 内置规则列表
        config_rules: 配置规则列表

    Returns:
        合并后的规则列表（按优先级排序）
    """
    # 创建 rule_id -> rule 映射
    rule_map = {}

    # 先添加内置规则
    for rule in builtin_rules:
        rule_map[rule.rule_id] = rule

    # 配置规则覆盖内置规则
    for rule in config_rules:
        rule_map[rule.rule_id] = rule

    # 转为列表
    merged_rules = list(rule_map.values())

    # 按优先级排序（ConfigurableGovernanceRule 有 priority，内置规则默认 50）
    def get_priority(rule):
        return getattr(rule, 'priority', 50)

    merged_rules.sort(key=get_priority, reverse=True)

    return merged_rules


# 模块级别函数：方便使用
_cached_rules: Optional[List[ConfigurableGovernanceRule]] = None


def get_all_rules(reload: bool = False) -> List[GovernanceRule]:
    """
    获取所有规则（内置 + 配置）

    Args:
        reload: 是否重新加载配置文件（默认 False，使用缓存）

    Returns:
        所有规则列表
    """
    global _cached_rules

    if _cached_rules is None or reload:
        try:
            _cached_rules = load_default_rules()
        except Exception as e:
            # 加载配置失败，返回空列表（使用内置规则）
            _cached_rules = []

    from .rule_engine import GOVERNANCE_RULES
    return merge_rules(GOVERNANCE_RULES, _cached_rules)
