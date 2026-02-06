"""
Provenance Validator

验证溯源信息的完整性和一致性。
"""

import logging
from typing import Tuple, Optional

from agentos.core.capabilities.governance_models.provenance import ProvenanceStamp, ExecutionEnv
from agentos.core.capabilities.capability_models import ToolResult

logger = logging.getLogger(__name__)


class ProvenanceValidator:
    """溯源验证器"""

    def validate_completeness(self, provenance: ProvenanceStamp) -> Tuple[bool, Optional[str]]:
        """
        验证溯源信息完整性

        Args:
            provenance: 溯源信息

        Returns:
            (valid, error_message)
        """
        # 检查必填字段
        required_fields = [
            "capability_id",
            "tool_id",
            "capability_type",
            "source_id",
            "execution_env",
            "trust_tier",
            "timestamp",
            "invocation_id"
        ]

        for field in required_fields:
            if not getattr(provenance, field, None):
                return (False, f"Missing required field: {field}")

        # 检查 execution_env 完整性
        env = provenance.execution_env
        if not env.host or not env.pid or not env.python_version:
            return (False, "Incomplete execution environment information")

        return (True, None)

    def validate_consistency(
        self,
        provenance: ProvenanceStamp,
        result: ToolResult
    ) -> Tuple[bool, Optional[str]]:
        """
        验证溯源与结果的一致性

        Args:
            provenance: 溯源信息
            result: 工具结果

        Returns:
            (valid, error_message)
        """
        # invocation_id 必须一致
        if provenance.invocation_id != result.invocation_id:
            return (False, "Invocation ID mismatch between provenance and result")

        # tool_id 应该匹配
        if provenance.capability_id != result.invocation_id.split("_")[0]:
            logger.warning("Tool ID mismatch (non-critical)")

        return (True, None)

    def can_replay(
        self,
        provenance: ProvenanceStamp,
        current_env: ExecutionEnv
    ) -> Tuple[bool, Optional[str]]:
        """
        判断是否可以在当前环境回放

        Args:
            provenance: 原始溯源
            current_env: 当前环境

        Returns:
            (can_replay, reason)
        """
        # 检查关键环境是否一致
        if provenance.execution_env.host != current_env.host:
            return (False, "Different host")

        if provenance.execution_env.python_version != current_env.python_version:
            return (False, "Different Python version")

        if provenance.execution_env.agentos_version != current_env.agentos_version:
            logger.warning("Different AgentOS version, replay may differ")

        return (True, None)
