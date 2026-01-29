"""
Runtime Gate Enforcement (v0.3)

运行时强制执行 Gate 规则，防止绕过静态测试。
这是最后一道防线，确保即使有人不跑 tests 也无法违反核心不变量。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from agentos.core.policy.execution_policy import PolicyViolation


class GateEnforcer:
    """运行时 Gate 强制执行器"""

    @staticmethod
    def enforce_traceability_for_commit(
        run_id: int, 
        commit_sha: Optional[str],
        artifacts_dir: Path,
        db_cursor
    ) -> None:
        """
        强制执行 Gate 5: Traceability 三件套
        
        规则：如果有 commit，必须有 review_pack
        
        Args:
            run_id: Run ID
            commit_sha: Commit SHA (如果有)
            artifacts_dir: Artifacts 目录
            db_cursor: Database cursor
            
        Raises:
            PolicyViolation: 如果违反 Traceability 规则
        """
        if not commit_sha:
            # 没有 commit，不需要检查
            return
        
        # 检查是否有 review_pack
        review_pack_path = artifacts_dir / f"review_pack_run_{run_id}.json"
        if not review_pack_path.exists():
            raise PolicyViolation(
                f"Gate 5 violation: Run {run_id} has commit {commit_sha} but no review_pack. "
                f"This is a critical traceability violation (Invariant #6). "
                f"Expected: {review_pack_path}"
            )
        
        # 检查 review_pack 是否有效
        try:
            with open(review_pack_path, encoding="utf-8") as f:
                review_pack = json.load(f)
            
            # 验证必需字段
            required_fields = ["run_id", "task_id", "commits", "patches"]
            missing = [f for f in required_fields if f not in review_pack]
            if missing:
                raise PolicyViolation(
                    f"Gate 5 violation: review_pack for run {run_id} missing required fields: {missing}"
                )
            
            # 验证 commit SHA 匹配
            commits = review_pack.get("commits", [])
            if not any(c.get("sha") == commit_sha for c in commits):
                raise PolicyViolation(
                    f"Gate 5 violation: review_pack for run {run_id} doesn't contain commit {commit_sha}"
                )
        
        except (json.JSONDecodeError, FileNotFoundError) as e:
            raise PolicyViolation(
                f"Gate 5 violation: review_pack for run {run_id} is invalid: {e}"
            )
    
    @staticmethod
    def enforce_full_auto_question_budget(
        execution_mode: str,
        question_attempts: int = 0
    ) -> None:
        """
        强制执行 Gate 4.2: full_auto question_budget = 0
        
        规则：full_auto 模式下，question attempt = PolicyViolation
        
        Args:
            execution_mode: 执行模式
            question_attempts: 问题尝试次数
            
        Raises:
            PolicyViolation: 如果 full_auto 模式下尝试提问
        """
        if execution_mode == "full_auto" and question_attempts > 0:
            raise PolicyViolation(
                f"Gate 4.2 violation: full_auto mode attempted {question_attempts} questions. "
                f"full_auto question_budget MUST be 0 (Invariant #2). "
                f"This is a critical policy violation."
            )
    
    @staticmethod
    def enforce_memory_pack_requirement(
        memory_pack: Optional[dict],
        execution_mode: str
    ) -> None:
        """
        强制执行 Gate 4.1: 无 MemoryPack 不允许执行
        
        规则：除了特殊模式，必须有 memory_pack
        
        Args:
            memory_pack: Memory pack (可为 None)
            execution_mode: 执行模式
            
        Raises:
            PolicyViolation: 如果缺少 memory_pack
        """
        # 允许空 memory_pack（但必须存在）
        if memory_pack is None and execution_mode not in ["init", "scan_only"]:
            raise PolicyViolation(
                f"Gate 4.1 violation: No memory_pack provided for mode {execution_mode}. "
                f"Memory pack is required for execution (Invariant #1). "
                f"Use empty pack {{}} if no context needed."
            )
    
    @staticmethod
    def pre_publish_gate_check(
        run_id: int,
        execution_mode: str,
        commit_sha: Optional[str],
        memory_pack: Optional[dict],
        artifacts_dir: Path,
        db_cursor,
        question_attempts: int = 0
    ) -> None:
        """
        发布前 Gate 综合检查（运行时最后防线）
        
        在任何 publish/apply 操作前调用，防止绕过静态测试。
        
        Args:
            run_id: Run ID
            execution_mode: 执行模式
            commit_sha: Commit SHA (如果有)
            memory_pack: Memory pack
            artifacts_dir: Artifacts 目录
            db_cursor: Database cursor
            question_attempts: 问题尝试次数
            
        Raises:
            PolicyViolation: 如果违反任何 Gate 规则
        """
        # Gate 4.1: Memory Pack Requirement
        GateEnforcer.enforce_memory_pack_requirement(memory_pack, execution_mode)
        
        # Gate 4.2: full_auto Question Budget
        GateEnforcer.enforce_full_auto_question_budget(execution_mode, question_attempts)
        
        # Gate 5: Traceability
        GateEnforcer.enforce_traceability_for_commit(
            run_id, commit_sha, artifacts_dir, db_cursor
        )
    
    @staticmethod
    def create_audit_event(
        gate_name: str,
        run_id: int,
        status: str,
        violation_reason: Optional[str] = None
    ) -> dict:
        """
        创建 Gate 审计事件
        
        Args:
            gate_name: Gate 名称 (如 "Gate 5: Traceability")
            run_id: Run ID
            status: "passed" | "failed"
            violation_reason: 违规原因（如果 failed）
            
        Returns:
            Audit event dict
        """
        import time
        
        return {
            "ts": time.time(),
            "gate": gate_name,
            "run_id": run_id,
            "status": status,
            "violation_reason": violation_reason,
            "enforcement_layer": "runtime",
        }
