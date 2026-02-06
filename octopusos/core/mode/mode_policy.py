"""Mode Policy Engine - 策略驱动的权限管理系统

本模块实现了基于策略的 Mode 权限控制引擎：
- 支持 JSON 策略文件加载
- 提供安全的默认策略
- 支持权限查询和验证
- 全局策略实例管理

设计原则：
1. 安全默认值：未知 mode 禁止所有危险操作
2. 策略分离：权限配置与代码逻辑分离
3. 可扩展性：支持自定义策略文件
4. Schema 验证：确保策略文件格式正确
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Set, Optional, Any
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class ModePermissions:
    """
    Mode 权限配置

    定义了某个 mode 允许执行的操作和风险等级。

    Attributes:
        mode_id: Mode 唯一标识符
        allows_commit: 是否允许 git commit 操作
        allows_diff: 是否允许生成代码 diff
        allowed_operations: 允许的操作集合（扩展点）
        risk_level: 风险等级 (low/medium/high/critical)
    """
    mode_id: str
    allows_commit: bool = False
    allows_diff: bool = False
    allowed_operations: Set[str] = field(default_factory=set)
    risk_level: str = "low"

    def __post_init__(self):
        """验证风险等级合法性"""
        valid_risk_levels = {"low", "medium", "high", "critical"}
        if self.risk_level not in valid_risk_levels:
            logger.warning(
                f"Invalid risk_level '{self.risk_level}' for mode '{self.mode_id}', "
                f"defaulting to 'low'"
            )
            self.risk_level = "low"


# ==============================================================================
# Policy Engine
# ==============================================================================

class ModePolicy:
    """
    Mode 策略引擎

    负责加载、验证和查询 Mode 权限策略。
    支持从 JSON 文件加载策略，或使用内置的默认策略。

    策略文件格式示例:
    {
        "version": "1.0",
        "modes": {
            "implementation": {
                "allows_commit": true,
                "allows_diff": true,
                "allowed_operations": ["read", "write", "execute"],
                "risk_level": "high"
            },
            "design": {
                "allows_commit": false,
                "allows_diff": false,
                "allowed_operations": ["read"],
                "risk_level": "low"
            }
        }
    }
    """

    def __init__(self, policy_path: Optional[Path] = None):
        """
        初始化策略引擎

        Args:
            policy_path: 策略文件路径。如果为 None，使用默认策略。
        """
        self._permissions: Dict[str, ModePermissions] = {}
        self._policy_version: str = "1.0"

        if policy_path:
            self._load_policy(policy_path)
        else:
            self._load_default_policy()

    def _load_policy(self, policy_path: Path) -> None:
        """
        从文件加载策略

        Args:
            policy_path: 策略文件路径

        Raises:
            FileNotFoundError: 策略文件不存在
            ValueError: 策略文件格式错误
        """
        try:
            with open(policy_path, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)

            self._validate_and_load(policy_data)
            logger.info(f"Policy loaded from {policy_path}")

        except FileNotFoundError:
            logger.error(f"Policy file not found: {policy_path}")
            logger.info("Falling back to default policy")
            self._load_default_policy()

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in policy file: {e}")
            logger.info("Falling back to default policy")
            self._load_default_policy()

        except Exception as e:
            logger.error(f"Error loading policy: {e}")
            logger.info("Falling back to default policy")
            self._load_default_policy()

    def _load_default_policy(self) -> None:
        """
        加载默认策略

        默认策略规则：
        - implementation: 允许 commit 和 diff（高风险）
        - 其他所有 mode: 禁止 commit 和 diff（低风险）

        这是一个保守的安全策略，只有明确用于实施的 mode 才能修改代码。
        """
        # implementation mode - 唯一允许修改代码的 mode
        self._permissions["implementation"] = ModePermissions(
            mode_id="implementation",
            allows_commit=True,
            allows_diff=True,
            allowed_operations={"read", "write", "execute", "commit", "diff"},
            risk_level="high"
        )

        # 其他 modes - 只读或受限操作
        restricted_modes = [
            "design",      # 设计模式：纯规划，不修改代码
            "chat",        # 聊天模式：交互式对话
            "planning",    # 规划模式：制定计划
            "debug",       # 调试模式：分析问题
            "ops",         # 运维模式：系统操作
            "test",        # 测试模式：执行测试
            "release",     # 发布模式：发布流程
        ]

        for mode_id in restricted_modes:
            self._permissions[mode_id] = ModePermissions(
                mode_id=mode_id,
                allows_commit=False,
                allows_diff=False,
                allowed_operations={"read"},
                risk_level="low"
            )

        self._policy_version = "1.0-default"
        logger.info("Default policy loaded")

    def _validate_and_load(self, policy_data: Dict[str, Any]) -> None:
        """
        验证策略数据并加载

        简化的 JSON Schema 验证：
        - 必须包含 "version" 和 "modes" 字段
        - modes 必须是字典，key 为 mode_id
        - 每个 mode 必须包含权限配置

        Args:
            policy_data: 解析后的策略数据

        Raises:
            ValueError: 策略数据格式错误
        """
        # 验证顶层结构
        if not isinstance(policy_data, dict):
            raise ValueError("Policy data must be a dictionary")

        if "version" not in policy_data:
            raise ValueError("Policy must contain 'version' field")

        if "modes" not in policy_data:
            raise ValueError("Policy must contain 'modes' field")

        modes_data = policy_data["modes"]
        if not isinstance(modes_data, dict):
            raise ValueError("'modes' must be a dictionary")

        # 解析每个 mode 的权限
        for mode_id, mode_config in modes_data.items():
            if not isinstance(mode_config, dict):
                logger.warning(f"Invalid config for mode '{mode_id}', skipping")
                continue

            try:
                # 提取权限配置
                allows_commit = mode_config.get("allows_commit", False)
                allows_diff = mode_config.get("allows_diff", False)
                allowed_operations = set(mode_config.get("allowed_operations", []))
                risk_level = mode_config.get("risk_level", "low")

                # 创建权限对象
                self._permissions[mode_id] = ModePermissions(
                    mode_id=mode_id,
                    allows_commit=allows_commit,
                    allows_diff=allows_diff,
                    allowed_operations=allowed_operations,
                    risk_level=risk_level
                )

            except Exception as e:
                logger.error(f"Error parsing permissions for mode '{mode_id}': {e}")
                continue

        self._policy_version = policy_data["version"]
        logger.info(f"Policy version {self._policy_version} validated and loaded")

    def get_permissions(self, mode_id: str) -> ModePermissions:
        """
        获取指定 mode 的权限配置

        Args:
            mode_id: Mode 标识符

        Returns:
            ModePermissions: 权限配置对象

        Note:
            如果 mode_id 未定义，返回安全默认值（禁止所有危险操作）
        """
        if mode_id in self._permissions:
            return self._permissions[mode_id]

        # 安全默认值：未知 mode 禁止所有危险操作
        logger.warning(
            f"Unknown mode_id '{mode_id}', returning safe default permissions"
        )
        return ModePermissions(
            mode_id=mode_id,
            allows_commit=False,
            allows_diff=False,
            allowed_operations={"read"},
            risk_level="low"
        )

    def check_permission(self, mode_id: str, permission: str) -> bool:
        """
        检查 mode 是否具有指定权限

        Args:
            mode_id: Mode 标识符
            permission: 权限名称 (如 "commit", "diff", "read", "write")

        Returns:
            bool: True 表示有权限，False 表示无权限

        Examples:
            >>> policy = ModePolicy()
            >>> policy.check_permission("implementation", "commit")
            True
            >>> policy.check_permission("design", "commit")
            False
        """
        perms = self.get_permissions(mode_id)

        # 检查特殊权限
        if permission == "commit":
            return perms.allows_commit
        elif permission == "diff":
            return perms.allows_diff

        # 检查通用权限
        return permission in perms.allowed_operations

    def get_all_modes(self) -> Set[str]:
        """
        获取所有已定义的 mode_id

        Returns:
            Set[str]: mode_id 集合
        """
        return set(self._permissions.keys())

    def get_policy_version(self) -> str:
        """
        获取策略版本

        Returns:
            str: 策略版本号
        """
        return self._policy_version


# ==============================================================================
# Global Policy Management
# ==============================================================================

# 全局策略实例
_global_policy: Optional[ModePolicy] = None


def set_global_policy(policy: ModePolicy) -> None:
    """
    设置全局策略实例

    Args:
        policy: ModePolicy 实例
    """
    global _global_policy
    _global_policy = policy
    logger.info("Global policy updated")


def get_global_policy() -> ModePolicy:
    """
    获取全局策略实例

    如果全局策略未初始化，自动创建默认策略。

    Returns:
        ModePolicy: 全局策略实例
    """
    global _global_policy
    if _global_policy is None:
        _global_policy = ModePolicy()
        logger.info("Global policy auto-initialized with default policy")
    return _global_policy


def load_policy_from_file(policy_path: Path) -> ModePolicy:
    """
    从文件加载策略并设置为全局策略

    Args:
        policy_path: 策略文件路径

    Returns:
        ModePolicy: 加载的策略实例
    """
    policy = ModePolicy(policy_path)
    set_global_policy(policy)
    logger.info(f"Global policy loaded from {policy_path}")
    return policy


# ==============================================================================
# Convenience Functions
# ==============================================================================

def check_mode_permission(mode_id: str, permission: str) -> bool:
    """
    使用全局策略检查权限（便捷函数）

    Args:
        mode_id: Mode 标识符
        permission: 权限名称

    Returns:
        bool: True 表示有权限，False 表示无权限
    """
    return get_global_policy().check_permission(mode_id, permission)


def get_mode_permissions(mode_id: str) -> ModePermissions:
    """
    使用全局策略获取权限配置（便捷函数）

    Args:
        mode_id: Mode 标识符

    Returns:
        ModePermissions: 权限配置对象
    """
    return get_global_policy().get_permissions(mode_id)
