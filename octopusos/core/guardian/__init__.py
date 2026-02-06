"""
Guardian 模块

Guardian = 验收事实记录器（Verification / Acceptance Authority）

核心原则：
- Guardian 记录验收事实，不控制流程
- Guardian 是叠加层（Overlay），不是 Gate
- 不修改 task 状态机，不引入强制卡死流程

导出的核心类型：
- GuardianReview: 验收审查记录数据模型
- GuardianService: 服务层（CRUD 操作）
- GuardianStorage: 存储适配器（数据库访问）
- GuardianPolicy: 规则集快照
- PolicyRegistry: 规则集注册表
"""

from agentos.core.guardian.models import GuardianReview
from agentos.core.guardian.service import GuardianService
from agentos.core.guardian.storage import GuardianStorage
from agentos.core.guardian.policies import GuardianPolicy, PolicyRegistry, get_policy_registry

__all__ = [
    "GuardianReview",
    "GuardianService",
    "GuardianStorage",
    "GuardianPolicy",
    "PolicyRegistry",
    "get_policy_registry",
]
