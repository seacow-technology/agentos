"""
配置加载器

支持从 YAML 配置文件加载 Lead Agent 规则阈值，
并允许通过环境变量或命令行参数 override。
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RuleThresholds:
    """规则阈值配置"""
    spike_threshold: int = 5
    pause_count_threshold: int = 2
    retry_threshold: int = 1
    decision_lag_threshold_ms: int = 5000
    redline_ratio_increase_threshold: float = 0.10
    redline_ratio_min_baseline: float = 0.05
    high_risk_allow_threshold: int = 1


@dataclass
class AlertThresholds:
    """告警阈值配置"""
    min_blocked_for_alert: int = 5
    min_high_risk_for_alert: int = 1


@dataclass
class LeadConfig:
    """Lead Agent 配置"""
    version: str
    rule_thresholds: RuleThresholds
    alert_thresholds: AlertThresholds
    print_summary: bool = True
    log_level: str = "INFO"


def load_shadow_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load shadow classifier configuration from YAML file.

    Args:
        config_path: Path to shadow config file (default: agentos/config/shadow_classifiers.yaml)

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "shadow_classifiers.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Shadow config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    return config_data or {}


def save_shadow_config(config: Dict[str, Any], config_path: Optional[Path] = None) -> None:
    """
    Save shadow classifier configuration to YAML file.

    Args:
        config: Configuration dictionary to save
        config_path: Path to shadow config file (default: agentos/config/shadow_classifiers.yaml)
    """
    if config_path is None:
        config_path = Path(__file__).parent / "shadow_classifiers.yaml"

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def load_lead_config(config_path: Optional[Path] = None) -> LeadConfig:
    """
    加载 Lead Agent 配置

    优先级（从高到低）：
    1. 环境变量 LEAD_CONFIG（路径）
    2. 参数 config_path
    3. 默认路径 agentos/config/lead_rules.yaml
    4. 硬编码默认值

    Args:
        config_path: 配置文件路径（可选）

    Returns:
        LeadConfig: 配置对象
    """
    # 1. 尝试环境变量
    env_config_path = os.getenv("LEAD_CONFIG")
    if env_config_path:
        config_path = Path(env_config_path)

    # 2. 尝试参数
    if config_path is None:
        # 3. 默认路径
        default_path = Path(__file__).parent / "lead_rules.yaml"
        if default_path.exists():
            config_path = default_path

    # 4. 加载 YAML（如果存在）
    if config_path and config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # 处理空文件或 None 的情况
        if config_data is None:
            config_data = {}

        # 解析规则阈值
        rules = config_data.get("rules", {})
        rule_thresholds = RuleThresholds(
            spike_threshold=rules.get("blocked_reason_spike", {}).get("threshold", 5),
            pause_count_threshold=rules.get("pause_block_churn", {}).get("pause_count_threshold", 2),
            retry_threshold=rules.get("retry_then_fail", {}).get("threshold", 1),
            decision_lag_threshold_ms=rules.get("decision_lag", {}).get("p95_threshold_ms", 5000),
            redline_ratio_increase_threshold=rules.get("redline_ratio", {}).get("increase_threshold", 0.10),
            redline_ratio_min_baseline=rules.get("redline_ratio", {}).get("min_baseline", 0.05),
            high_risk_allow_threshold=rules.get("high_risk_allow", {}).get("threshold", 1)
        )

        # 解析告警阈值
        alert_cfg = config_data.get("alert_thresholds", {})
        alert_thresholds = AlertThresholds(
            min_blocked_for_alert=alert_cfg.get("min_blocked_for_alert", 5),
            min_high_risk_for_alert=alert_cfg.get("min_high_risk_for_alert", 1)
        )

        # 解析日志配置
        logging_cfg = config_data.get("logging", {})

        return LeadConfig(
            version=config_data.get("version", "1.0.0"),
            rule_thresholds=rule_thresholds,
            alert_thresholds=alert_thresholds,
            print_summary=logging_cfg.get("print_threshold_summary", True),
            log_level=logging_cfg.get("log_level", "INFO")
        )

    else:
        # 硬编码默认值（fallback）
        return LeadConfig(
            version="1.0.0",
            rule_thresholds=RuleThresholds(),
            alert_thresholds=AlertThresholds()
        )
