"""
Gate Adapter

统一封装对 gates 系统的调用（pause/enforcer/redlines）。
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from ...gates.pause_gate import PauseState, PauseCheckpoint, PauseMetadata, can_pause_at
from ...gates.runtime_enforcer import GateEnforcer
from ...gates.validate_agent_redlines import AgentRedlineValidator
from ...gates.validate_command_redlines import CommandRedlineValidator
from ...gates.validate_rule_redlines import RuleRedlineValidator

logger = logging.getLogger(__name__)


class GateAdapter:
    """
    Gate Adapter

    职责：
    - 封装 pause gate 调用
    - 封装 runtime enforcer 调用
    - 封装 redline validator 调用
    - 提供统一接口供 Supervisor policies 使用
    """

    def __init__(self, db_path: Path):
        """
        初始化 Gate Adapter

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.agent_validator = AgentRedlineValidator()
        self.command_validator = CommandRedlineValidator()
        self.rule_validator = RuleRedlineValidator()

        logger.info("GateAdapter initialized")

    def trigger_pause(
        self,
        task_id: str,
        checkpoint: str,
        reason: str,
        cursor: Optional[sqlite3.Cursor] = None,
    ) -> bool:
        """
        触发 pause gate

        Args:
            task_id: 任务 ID
            checkpoint: 暂停检查点
            reason: 暂停原因
            cursor: 数据库游标

        Returns:
            是否成功触发暂停
        """
        try:
            # 创建暂停元数据
            metadata = PauseMetadata(
                pause_state=PauseState.AWAITING_APPROVAL,
                pause_reason=reason,
                pause_checkpoint=checkpoint,
            )

            # 这里应该更新 task 的 metadata
            # 由于当前没有直接的 Task 管理接口，我们先写审计日志
            logger.info(
                f"Pause gate triggered: task={task_id}, checkpoint={checkpoint}, reason={reason}"
            )

            # TODO: 更新 task metadata 中的 pause_state
            # 这需要访问 task store

            return True

        except Exception as e:
            logger.error(f"Failed to trigger pause gate: {e}", exc_info=True)
            return False

    def check_can_pause(self, checkpoint: str, run_mode: str) -> bool:
        """
        检查是否可以在特定检查点暂停

        Args:
            checkpoint: 检查点
            run_mode: 运行模式（interactive/assisted/autonomous）

        Returns:
            是否可以暂停
        """
        return can_pause_at(checkpoint, run_mode)

    def validate_agent_redlines(self, agent_spec: Dict[str, Any]) -> tuple[bool, list]:
        """
        验证 agent 红线

        Args:
            agent_spec: Agent 规范

        Returns:
            (是否通过, 错误列表)
        """
        try:
            return self.agent_validator.validate_all(agent_spec)
        except Exception as e:
            logger.error(f"Agent redline validation error: {e}", exc_info=True)
            return False, [str(e)]

    def validate_command_redlines(self, command_spec: Dict[str, Any]) -> tuple[bool, list]:
        """
        验证 command 红线

        Args:
            command_spec: Command 规范

        Returns:
            (是否通过, 错误列表)
        """
        try:
            return self.command_validator.validate_all(command_spec)
        except Exception as e:
            logger.error(f"Command redline validation error: {e}", exc_info=True)
            return False, [str(e)]

    def validate_rule_redlines(self, rule_spec: Dict[str, Any]) -> tuple[bool, list]:
        """
        验证 rule 红线

        Args:
            rule_spec: Rule 规范

        Returns:
            (是否通过, 错误列表)
        """
        try:
            return self.rule_validator.validate_all(rule_spec)
        except Exception as e:
            logger.error(f"Rule redline validation error: {e}", exc_info=True)
            return False, [str(e)]

    def enforce_runtime_gates(
        self,
        run_id: str,
        execution_mode: str,
        commit_sha: Optional[str] = None,
        memory_pack: Optional[Dict] = None,
        artifacts_dir: Optional[Path] = None,
        question_attempts: int = 0,
        cursor: Optional[sqlite3.Cursor] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        执行运行时 gates 检查

        Args:
            run_id: 运行 ID
            execution_mode: 执行模式
            commit_sha: Commit SHA
            memory_pack: Memory pack
            artifacts_dir: Artifacts 目录
            question_attempts: 问题尝试次数
            cursor: 数据库游标

        Returns:
            (是否通过, 违规原因)
        """
        try:
            # 使用 GateEnforcer 进行检查
            GateEnforcer.pre_publish_gate_check(
                run_id=run_id,
                execution_mode=execution_mode,
                commit_sha=commit_sha,
                memory_pack=memory_pack,
                artifacts_dir=artifacts_dir,
                db_cursor=cursor,
                question_attempts=question_attempts,
            )

            logger.info(f"Runtime gates passed for run_id={run_id}")
            return True, None

        except Exception as e:
            logger.warning(f"Runtime gate violation: {e}")
            return False, str(e)

    def check_redline_violation(
        self,
        entity_type: str,
        entity_spec: Dict[str, Any],
    ) -> tuple[bool, list]:
        """
        统一红线检查接口

        Args:
            entity_type: 实体类型（agent/command/rule）
            entity_spec: 实体规范

        Returns:
            (是否违规, 错误列表)
        """
        if entity_type == "agent":
            is_valid, errors = self.validate_agent_redlines(entity_spec)
        elif entity_type == "command":
            is_valid, errors = self.validate_command_redlines(entity_spec)
        elif entity_type == "rule":
            is_valid, errors = self.validate_rule_redlines(entity_spec)
        else:
            logger.error(f"Unknown entity_type: {entity_type}")
            return True, [f"Unknown entity type: {entity_type}"]

        # 返回值反转：is_valid=True -> violation=False
        return not is_valid, errors
