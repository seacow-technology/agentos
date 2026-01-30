"""
BrainOS: Read-only Reasoning Layer for AgentOS

BrainOS 提供只读推理能力，通过索引、构图、查询来支持：
- Why：追溯代码/能力的依据（ADR/Doc/Commit）
- Impact：分析变更影响范围
- Trace：追踪概念/能力的演进历史
- Map：输出知识子图谱

核心原则：
- 只读：不修改代码、不触发执行
- 可追溯：每条结论带证据链（provenance）
- 可重复：同一 commit 构建结果一致

边界约束：
- ✅ 可做：索引、构图、查询、追溯
- ❌ 不可做：修改代码、触发执行、写入业务状态（除 BrainOS 自己的索引库）

Version History:
- 0.1.0-alpha: Initial skeleton with frozen contracts
"""

__version__ = "0.1.0-alpha"

# 冻结契约 (Frozen Contracts)
READONLY_PRINCIPLE = "BrainOS MUST NOT modify any repo content"
PROVENANCE_PRINCIPLE = "Every conclusion MUST have traceable evidence"
IDEMPOTENCE_PRINCIPLE = "Same commit MUST produce identical graph"

# 验证函数
def validate_readonly_compliance(operation: str) -> bool:
    """
    验证操作是否符合只读原则

    Args:
        operation: 操作描述

    Returns:
        bool: True if compliant, False otherwise

    Raises:
        ValueError: If operation violates READONLY_PRINCIPLE
    """
    forbidden_keywords = ["write", "modify", "delete", "execute", "commit", "push"]
    if any(keyword in operation.lower() for keyword in forbidden_keywords):
        raise ValueError(f"Operation '{operation}' violates {READONLY_PRINCIPLE}")
    return True
