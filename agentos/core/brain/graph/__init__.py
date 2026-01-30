"""
BrainOS Graph Module

负责构建和管理知识图谱。

核心功能：
1. GraphBuilder: 从抽取结果构建图谱
2. VersionManager: 管理图谱版本（基于 commit）
3. Graph 合并和去重

契约：
- 幂等性：同一 commit 的多次构建产生同一图谱
- 版本化：每个图谱版本对应一个 commit hash
- 增量构建：支持基于上一版本的增量更新

v0.1 实现：
- 基础图构建（添加节点和边）
- 简单去重（基于 key）
- 版本标记（metadata）

TODO v0.2:
- 图谱 diff 和 merge
- 子图抽取（基于查询种子）
- 图谱统计和质量评估
"""

from .builder import GraphBuilder
from .version import GraphVersion, VersionManager

__all__ = [
    "GraphBuilder",
    "GraphVersion",
    "VersionManager",
]
