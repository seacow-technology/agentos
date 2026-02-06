"""
BrainOS Graph Version Management

管理知识图谱的版本。

版本策略：
1. 每个图谱版本对应一个 commit hash
2. 版本号格式：v{commit_hash[:8]}_{timestamp}
3. 存储版本元数据（构建时间、抽取器版本、统计信息）

幂等性保证：
- 同一 commit hash 的多次构建应使用相同版本号
- 版本比较基于 commit hash，不是时间戳

增量构建：
- 记录上一版本的 commit hash
- 仅处理两个版本之间的差异

TODO v0.2:
- 图谱版本 diff（节点/边的增删改）
- 版本回滚（恢复到历史版本）
- 版本分支（支持多个 repo 分支）
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
from agentos.core.time import utc_now, utc_now_iso



@dataclass
class GraphVersion:
    """
    知识图谱版本

    Attributes:
        version_id: 版本唯一标识符（如 v_{commit_hash[:8]}_{timestamp}）
        commit_hash: 对应的 Git commit hash
        created_at: 创建时间（ISO 8601）
        stats: 图谱统计信息（节点数、边数等）
        extractor_versions: 抽取器版本信息
        metadata: 其他元数据

    Contract:
        - 同一 commit_hash 应产生同一 version_id（幂等性）
        - version_id 必须全局唯一
    """
    version_id: str
    commit_hash: str
    created_at: str
    stats: Dict[str, Any] = field(default_factory=dict)
    extractor_versions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_version_id(commit_hash: str, timestamp: Optional[str] = None) -> str:
        """
        生成版本 ID

        格式：v_{commit_hash[:8]}_{timestamp}

        Args:
            commit_hash: Git commit hash
            timestamp: 时间戳（可选，默认当前时间）

        Returns:
            str: 版本 ID
        """
        if not timestamp:
            timestamp = utc_now().strftime("%Y%m%d%H%M%S")
        return f"v_{commit_hash[:8]}_{timestamp}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version_id": self.version_id,
            "commit_hash": self.commit_hash,
            "created_at": self.created_at,
            "stats": self.stats,
            "extractor_versions": self.extractor_versions,
            "metadata": self.metadata,
        }


class VersionManager:
    """
    图谱版本管理器

    负责创建、查询、比较图谱版本。

    Example:
        >>> manager = VersionManager()
        >>> version = manager.create_version(
        ...     commit_hash="abc123...",
        ...     stats={"nodes": 100, "edges": 200}
        ... )
        >>> print(version.version_id)
    """

    def __init__(self):
        self.versions: Dict[str, GraphVersion] = {}

    def create_version(
        self,
        commit_hash: str,
        stats: Optional[Dict[str, Any]] = None,
        extractor_versions: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphVersion:
        """
        创建新版本

        Args:
            commit_hash: Git commit hash
            stats: 图谱统计信息
            extractor_versions: 抽取器版本信息
            metadata: 其他元数据

        Returns:
            GraphVersion 对象

        Contract:
            - 同一 commit_hash 应返回相同的 version_id（幂等性）
        """
        version_id = GraphVersion.generate_version_id(commit_hash)
        created_at = utc_now_iso()

        version = GraphVersion(
            version_id=version_id,
            commit_hash=commit_hash,
            created_at=created_at,
            stats=stats or {},
            extractor_versions=extractor_versions or {},
            metadata=metadata or {},
        )

        self.versions[version_id] = version
        return version

    def get_version(self, version_id: str) -> Optional[GraphVersion]:
        """
        获取版本

        Args:
            version_id: 版本 ID

        Returns:
            GraphVersion 或 None
        """
        return self.versions.get(version_id)

    def get_latest_version(self) -> Optional[GraphVersion]:
        """
        获取最新版本

        Returns:
            GraphVersion 或 None（如果没有版本）
        """
        if not self.versions:
            return None
        # 按 created_at 排序，返回最新
        sorted_versions = sorted(
            self.versions.values(),
            key=lambda v: v.created_at,
            reverse=True
        )
        return sorted_versions[0]

    def list_versions(self) -> list:
        """
        列出所有版本

        Returns:
            List[GraphVersion]，按创建时间倒序
        """
        return sorted(
            self.versions.values(),
            key=lambda v: v.created_at,
            reverse=True
        )
