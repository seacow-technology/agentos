"""
Guardian Policy 管理

提供规则快照管理功能，用于审计追溯。

核心概念：
- GuardianPolicy: 规则集快照（包含规则定义、版本、校验和）
- PolicyRegistry: 规则集注册表（管理所有规则快照）

设计原则：
1. 规则快照是不可变的（immutable）
2. 每个规则集版本都有唯一的 snapshot_id
3. 使用 SHA256 校验和确保规则完整性
4. 支持规则演化追踪（对比不同版本）

Created for Task #2: Guardian Service 和 API 端点
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from agentos.store import get_db_path
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class GuardianPolicy:
    """
    Guardian 规则集快照

    代表某个规则集在特定时刻的状态（不可变）。
    用于审计追溯：可以查看历史审查使用的是哪个版本的规则。

    Attributes:
        policy_id: 规则集 ID（如：guardian.task.state_machine）
        name: 规则集名称（可读）
        version: 版本号（如：v1.0.0）
        rules: 规则集定义（JSON 结构）
        checksum: SHA256 校验和（基于 rules 内容）
        created_at: 创建时间
        metadata: 额外元数据
    """
    policy_id: str
    name: str
    version: str
    rules: Dict[str, Any]
    checksum: str
    created_at: str = field(
        default_factory=lambda: utc_now_iso()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def snapshot_id(self) -> str:
        """
        快照 ID（唯一标识）

        格式：{policy_id}:{version}@sha256:{checksum[:12]}

        Example:
            guardian.task.state_machine:v1.0.0@sha256:abc123def456
        """
        return f"{self.policy_id}:{self.version}@sha256:{self.checksum[:12]}"

    @staticmethod
    def compute_checksum(rules: Dict[str, Any]) -> str:
        """
        计算规则集的 SHA256 校验和

        Args:
            rules: 规则集定义

        Returns:
            SHA256 校验和（十六进制字符串）

        Example:
            ```python
            rules = {"rule1": {"check": "state_machine_valid"}}
            checksum = GuardianPolicy.compute_checksum(rules)
            ```
        """
        # 规范化 JSON（排序键，无空格）
        canonical_json = json.dumps(rules, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "version": self.version,
            "rules": self.rules,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "snapshot_id": self.snapshot_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuardianPolicy":
        """从字典反序列化"""
        return cls(
            policy_id=data["policy_id"],
            name=data["name"],
            version=data["version"],
            rules=data["rules"],
            checksum=data["checksum"],
            created_at=data.get("created_at", utc_now_iso()),
            metadata=data.get("metadata", {})
        )


class PolicyRegistry:
    """
    规则集注册表

    管理所有 Guardian 规则集的快照，支持版本追踪和审计。

    数据存储：
    - 内存缓存：快速访问当前活跃规则
    - 数据库持久化：长期存储历史快照（未来扩展）

    当前实现：内存缓存（简单有效）
    未来扩展：可选数据库持久化（用于历史审计）
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化规则集注册表

        Args:
            db_path: 数据库路径（可选，当前实现使用内存缓存）
        """
        if db_path is None:
            db_path = get_db_path()

        self.db_path = db_path
        self._cache: Dict[str, GuardianPolicy] = {}  # snapshot_id -> policy

        logger.info(f"PolicyRegistry initialized with db_path={db_path}")

    def register(self, policy: GuardianPolicy) -> str:
        """
        注册规则集快照

        Args:
            policy: GuardianPolicy 实例

        Returns:
            snapshot_id（快照唯一标识）

        Raises:
            ValueError: 如果规则集校验和不匹配

        Example:
            ```python
            registry = PolicyRegistry()

            policy = GuardianPolicy(
                policy_id="guardian.task.state_machine",
                name="Task State Machine Validator",
                version="v1.0.0",
                rules={"check_transitions": True},
                checksum=GuardianPolicy.compute_checksum({"check_transitions": True})
            )

            snapshot_id = registry.register(policy)
            print(f"Registered: {snapshot_id}")
            ```
        """
        # 验证校验和
        expected_checksum = GuardianPolicy.compute_checksum(policy.rules)
        if policy.checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for policy {policy.policy_id}:{policy.version}. "
                f"Expected: {expected_checksum}, Got: {policy.checksum}"
            )

        snapshot_id = policy.snapshot_id

        # 检查是否已注册
        if snapshot_id in self._cache:
            logger.debug(f"Policy already registered: {snapshot_id}")
            return snapshot_id

        # 注册到缓存
        self._cache[snapshot_id] = policy

        logger.info(
            f"Registered policy: {snapshot_id} "
            f"(name: {policy.name}, version: {policy.version})"
        )

        return snapshot_id

    def get(self, snapshot_id: str) -> Optional[GuardianPolicy]:
        """
        根据 snapshot_id 获取规则集

        Args:
            snapshot_id: 快照 ID

        Returns:
            GuardianPolicy 实例或 None

        Example:
            ```python
            registry = PolicyRegistry()
            policy = registry.get("guardian.task.state_machine:v1.0.0@sha256:abc123")
            if policy:
                print(f"Rules: {policy.rules}")
            ```
        """
        return self._cache.get(snapshot_id)

    def list_versions(self, policy_id: str) -> List[GuardianPolicy]:
        """
        列出某个规则集的所有版本

        Args:
            policy_id: 规则集 ID

        Returns:
            GuardianPolicy 列表（按版本号排序）

        Example:
            ```python
            registry = PolicyRegistry()
            versions = registry.list_versions("guardian.task.state_machine")
            for policy in versions:
                print(f"Version {policy.version}: {policy.snapshot_id}")
            ```
        """
        policies = [
            policy for policy in self._cache.values()
            if policy.policy_id == policy_id
        ]

        # 按版本号排序（字符串排序，简单实现）
        policies.sort(key=lambda p: p.version, reverse=True)

        return policies

    def list_all(self) -> List[GuardianPolicy]:
        """
        列出所有已注册的规则集

        Returns:
            GuardianPolicy 列表（按创建时间倒序）

        Example:
            ```python
            registry = PolicyRegistry()
            all_policies = registry.list_all()
            for policy in all_policies:
                print(f"{policy.name} ({policy.version})")
            ```
        """
        policies = list(self._cache.values())
        policies.sort(key=lambda p: p.created_at, reverse=True)
        return policies

    def get_latest(self, policy_id: str) -> Optional[GuardianPolicy]:
        """
        获取某个规则集的最新版本

        Args:
            policy_id: 规则集 ID

        Returns:
            GuardianPolicy 实例或 None

        Example:
            ```python
            registry = PolicyRegistry()
            latest = registry.get_latest("guardian.task.state_machine")
            if latest:
                print(f"Latest version: {latest.version}")
            ```
        """
        versions = self.list_versions(policy_id)
        return versions[0] if versions else None

    def create_and_register(
        self,
        policy_id: str,
        name: str,
        version: str,
        rules: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建并注册规则集快照（便捷方法）

        自动计算校验和并创建 GuardianPolicy 实例。

        Args:
            policy_id: 规则集 ID
            name: 规则集名称
            version: 版本号
            rules: 规则集定义
            metadata: 额外元数据（可选）

        Returns:
            snapshot_id（快照唯一标识）

        Example:
            ```python
            registry = PolicyRegistry()

            snapshot_id = registry.create_and_register(
                policy_id="guardian.task.state_machine",
                name="Task State Machine Validator",
                version="v1.0.0",
                rules={"check_transitions": True},
                metadata={"author": "system"}
            )
            ```
        """
        checksum = GuardianPolicy.compute_checksum(rules)

        policy = GuardianPolicy(
            policy_id=policy_id,
            name=name,
            version=version,
            rules=rules,
            checksum=checksum,
            metadata=metadata or {}
        )

        return self.register(policy)


# Global registry instance (singleton pattern)
_global_registry: Optional[PolicyRegistry] = None


def get_policy_registry(db_path: Optional[Path] = None) -> PolicyRegistry:
    """
    获取全局 PolicyRegistry 实例（单例模式）

    Args:
        db_path: 数据库路径（可选）

    Returns:
        PolicyRegistry 实例

    Example:
        ```python
        # 获取全局注册表
        registry = get_policy_registry()

        # 注册规则
        registry.create_and_register(
            policy_id="guardian.example",
            name="Example Guardian",
            version="v1.0.0",
            rules={"check": "example"}
        )
        ```
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = PolicyRegistry(db_path=db_path)

    return _global_registry
