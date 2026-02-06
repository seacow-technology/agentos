"""
Executor Engine - 执行编排引擎

编排所有组件完成真实执行
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import hashlib
import json

from .allowlist import Allowlist
from .sandbox import Sandbox
from .rollback import RollbackManager
from .lock import ExecutionLock
from .review_gate import ReviewGate
from .audit_logger import AuditLogger
from .sandbox_policy import SandboxPolicyLoader, PolicyDeniedError
from .run_tape import RunTape
from ..infra.git_client import GitClientFactory

# 🔩 M1 绑定点：导入 Mode System（最小化）
from agentos.core.mode import get_mode, ModeViolationError
from agentos.core.mode.mode_alerts import alert_mode_violation, AlertSeverity
# Task 27: Mode Event Listener integration
from agentos.core.mode.mode_event_listener import emit_mode_violation

# Task-Driven: Import TaskManager
from agentos.core.task import TaskManager

# Task #3: Planning Guard - v0.6 Soul
from agentos.core.task.planning_guard import get_planning_guard
from agentos.core.task.errors import PlanningSideEffectForbiddenError
from agentos.core.time import utc_now_iso



class DiffRejected(Exception):
    """
    🔩 H3-2：Diff 验证失败异常
    
    当 DiffVerifier 验证失败时抛出，防止未验证的 diff 被应用。
    """
    def __init__(self, reason: str, validation: Any):
        super().__init__(reason)
        self.reason = reason
        self.validation = validation


class ExecutorEngine:
    """执行引擎 - 编排所有组件"""
    
    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        lock_dir: Optional[Path] = None,
        approval_dir: Optional[Path] = None
    ):
        """
        初始化执行引擎
        
        Args:
            repo_path: Git仓库路径
            output_dir: 输出目录
            lock_dir: 锁目录
            approval_dir: 审批目录
        
        注意: use_sandbox 参数已移除，强制使用 worktree
        """
        self.repo_path = Path(repo_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.allowlist = Allowlist()
        self.sandbox: Optional[Sandbox] = None
        self.rollback_manager = RollbackManager(repo_path)
        self.lock = ExecutionLock(lock_dir or (output_dir / "locks"))
        self.review_gate = ReviewGate(approval_dir or (output_dir / "approvals"))
        self.audit_logger: Optional[AuditLogger] = None
        self.task_manager = TaskManager()  # Task-Driven
        self.planning_guard = get_planning_guard()  # Task #3: Planning Guard
    
    def execute(
        self,
        execution_request: Dict[str, Any],
        sandbox_policy: Dict[str, Any],
        policy_path: Optional[Path] = None,
        caller_source: str = "unknown"
    ) -> Dict[str, Any]:
        """
        执行请求

        Task #1: Chat → Execution Hard Gate
        Added caller_source parameter to enforce source verification.
        Only "task_runner" is allowed to execute. "chat" will be rejected.

        Args:
            execution_request: 执行请求
            sandbox_policy: sandbox策略 (deprecated, use policy_path)
            policy_path: 策略文件路径（新参数）
            caller_source: Source of the call - MUST be "task_runner" for execution
                          Options: "task_runner", "chat", "unknown"

        Returns:
            执行结果

        Raises:
            ChatExecutionForbiddenError: If caller_source is "chat"
        """
        # Task #1: Hard gate - reject chat execution attempts
        # Import here to avoid circular import
        if caller_source == "chat":
            from agentos.core.task.errors import ChatExecutionForbiddenError
            raise ChatExecutionForbiddenError(
                caller_context="ExecutorEngine.execute",
                attempted_operation="execute_task",
                task_id=execution_request.get("task_id"),
                metadata={
                    "execution_request_id": execution_request.get("execution_request_id"),
                    "enforcement": "hard_gate_task_1"
                }
            )

        # Task #1: Enforce that only task_runner can execute
        if caller_source != "task_runner":
            logger.warning(
                f"Execution called with non-task_runner source: {caller_source}. "
                f"This should only be called by task runner."
            )
        exec_req_id = execution_request["execution_request_id"]
        run_dir = self.output_dir / exec_req_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # P0-RT2: RunTape 必须从第一行开始写（最外层初始化）
        audit_dir = run_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        run_tape = RunTape(audit_dir)
        
        # Task-Driven: Extract or create task_id (P0: Orphan 容错)
        task_id = execution_request.get("task_id")
        if not task_id:
            # 🚨 P0 容错：无 task_id 时创建 orphan
            run_tape.audit_logger.log_warning(
                "execution_without_task_id",
                details={
                    "execution_request_id": exec_req_id,
                    "action": "creating_orphan_task",
                    "reason": "execution_request missing task_id"
                }
            )
            task = self.task_manager.create_orphan_task(
                ref_id=exec_req_id,
                created_by="executor_engine"
            )
            task_id = task.task_id
            run_tape.audit_logger.log_event(
                "orphan_task_created",
                details={
                    "task_id": task_id,
                    "orphan_ref": exec_req_id
                }
            )

        # ═══════════════════════════════════════════════════════════════
        # Task #4: EXECUTION FROZEN PLAN VALIDATION (v0.6 Core)
        # ═══════════════════════════════════════════════════════════════
        # Executor only trusts frozen specs. Execution MUST be blocked if
        # spec_frozen = 0. This is a hard gate enforcing v0.6 architecture.
        #
        # Validation:
        #   - Load task from database
        #   - Check task.spec_frozen == 1
        #   - If spec_frozen = 0 → raise SpecNotFrozenError
        #   - Audit rejection reason
        # ═══════════════════════════════════════════════════════════════
        task = self.task_manager.get_task(task_id)
        if not task:
            # Task not found - create error result
            error_msg = f"Task {task_id} not found in database"
            run_tape.audit_logger.log_error(error_msg)
            return self._create_error_result(
                exec_req_id,
                "failed",
                error_msg,
                run_tape,
                run_dir
            )

        # Task #4: Check spec_frozen flag
        if not task.is_spec_frozen():
            from agentos.core.task.errors import SpecNotFrozenError

            # Audit rejection
            run_tape.audit_logger.log_event("execution_blocked_spec_not_frozen", details={
                "task_id": task_id,
                "spec_frozen": task.spec_frozen,
                "reason": "Execution requires frozen specification (spec_frozen = 1)",
                "enforcement": "task_4_frozen_plan_validation",
                "v06_constraint": True
            })

            # Raise error with clear message
            raise SpecNotFrozenError(
                task_id=task_id,
                reason="Execution requires frozen specification. Please freeze spec before executing.",
                metadata={
                    "execution_request_id": exec_req_id,
                    "spec_frozen": task.spec_frozen,
                    "enforcement": "task_4_frozen_plan_validation"
                }
            )

        # Log successful validation
        run_tape.audit_logger.log_event("spec_frozen_validation_passed", details={
            "task_id": task_id,
            "spec_frozen": task.spec_frozen,
            "validation": "passed"
        })
        
        # 保持向后兼容：同时使用 AuditLogger
        self.audit_logger = run_tape.audit_logger
        
        # ═══════════════════════════════════════════════════════════════
        # INTEGRATOR FREEZE (Agent 4): Mode 入口唯一性保证
        # ═══════════════════════════════════════════════════════════════
        # 此处是 Executor 获取 mode 的唯一入口点。
        # 
        # 验收命令:
        #   rg "get_mode\(" agentos/core/executor | wc -l
        #   期望结果: 2（execute + apply_diff_or_raise）
        #
        # 禁止:
        #   - 在其他地方偷偷调用 get_mode()
        #   - 创建默认 silent mode
        #   - 绕过此入口获取 mode
        # ═══════════════════════════════════════════════════════════════
        # 🔩 M1 绑定点：获取 mode_id（默认 implementation）
        mode_id = execution_request.get("mode_id", "implementation")
        mode_defaulted = "mode_id" not in execution_request
        
        try:
            mode = get_mode(mode_id)
        except Exception as e:
            run_tape.audit_logger.log_error(f"Invalid mode_id '{mode_id}': {e}")
            return self._create_error_result(
                exec_req_id,
                "failed",
                f"Invalid mode_id '{mode_id}': {e}",
                run_tape,
                run_dir
            )
        
        # 记录 mode 信息
        run_tape.audit_logger.log_event("mode_resolved", details={
            "mode_id": mode_id,
            "mode_defaulted": mode_defaulted,
            "allows_commit": mode.allows_commit(),
            "allows_diff": mode.allows_diff()
        })
        
        # 保存 mode_id 到实例变量（供 apply_diff_or_raise 使用）
        self._current_mode_id = mode_id
        
        # 记录执行开始
        run_tape.audit_logger.log_event("execution_start", details={
            "execution_request_id": exec_req_id,
            "task_id": task_id,  # Include task_id in audit
            "mode": mode_id,
            "started_at": utc_now_iso()
        })
        
        # Task-Driven: Record execution_request to lineage
        self.task_manager.add_lineage(
            task_id=task_id,
            kind="execution_request",
            ref_id=exec_req_id,
            phase="execution"
        )

        # Task #3: Store task_id for planning guard checks
        self._current_task_id = task_id
        
        # P0-RT1: Policy 在执行前被加载并强制
        policy = None
        if policy_path:
            try:
                policy_loader = SandboxPolicyLoader()
                policy = policy_loader.load(policy_path)
                
                run_tape.audit_logger.log_event("policy_loaded", details={
                    "policy_id": policy.policy_id,
                    "policy_path": str(policy_path),
                    "schema_version": policy.schema_version
                })
            except Exception as e:
                run_tape.audit_logger.log_event("policy_load_failed", details={
                    "error": str(e),
                    "policy_path": str(policy_path)
                })
                return self._create_error_result(
                    exec_req_id,
                    "failed",
                    f"Policy load failed: {str(e)}",
                    run_tape,
                    run_dir
                )
        
        # 记录初始状态
        started_at = utc_now_iso()
        
        try:
            # 1. 检查是否需要审批
            if self.review_gate.requires_review(execution_request):
                approval = self.review_gate.check_approval(exec_req_id)
                if not approval:
                    run_tape.audit_logger.log_error("Execution requires approval but none found")
                    return self._create_error_result(
                        exec_req_id,
                        "blocked",
                        "Requires approval",
                        run_tape,
                        run_dir
                    )
            
            # 2. 获取锁
            repo_hash = hashlib.sha256(str(self.repo_path).encode()).hexdigest()[:16]
            if not self.lock.acquire(exec_req_id, repo_hash):
                run_tape.audit_logger.log_error("Failed to acquire lock - concurrent execution detected")
                return self._create_error_result(
                    exec_req_id,
                    "failed",
                    "Failed to acquire lock",
                    run_tape,
                    run_dir
                )
            
            # P0-RT3: Worktree 必须强制（记录 base_commit）
            main_git = GitClientFactory.get_client(self.repo_path)
            base_commit = main_git.get_head_sha()
            
            # 3. 创建sandbox (worktree) - 强制使用
            self.sandbox = Sandbox(self.repo_path)
            worktree_path = self.sandbox.create_worktree(exec_req_id)
            
            run_tape.audit_logger.log_event("sandbox_created", details={
                "worktree_path": str(worktree_path),
                "mode": "worktree_isolated",
                "base_commit": base_commit[:8]
            })
            
            # 4. 创建回滚点
            rollback_point = self.rollback_manager.create_rollback_point("pre_execution", worktree_path)
            run_tape.audit_logger.log_event("rollback_point_created", details=rollback_point)
            
            # 5. 执行操作（真实执行）- 每个 operation 都要过 policy 检查
            operations_executed = []
            
            # 支持两种格式：
            # 1. execution_request["allowed_operations"] (旧格式)
            # 2. execution_request["patch_plan"]["steps"][]["operations"] (新格式)
            
            if "patch_plan" in execution_request:
                # 新格式：遍历 patch_plan steps
                steps = execution_request["patch_plan"]["steps"]
                for step in steps:
                    for op in step.get("operations", []):
                        # P0-RT1: Policy 检查（deny 直接抛异常）
                        if policy:
                            try:
                                action = op.get("action")
                                params = op.get("params", {})
                                policy.assert_operation_allowed(action, params)
                            except PolicyDeniedError as e:
                                # 记录 policy_denied 事件
                                run_tape.audit_logger.log_event("policy_denied", details={
                                    "operation": e.operation,
                                    "reason": e.reason,
                                    "rule_id": e.rule_id,
                                    "params": params
                                })
                                raise  # 重新抛出，交给外层 except 处理
                        
                        result = self._execute_operation(op, worktree_path)
                        operations_executed.append(result)
            else:
                # 旧格式：直接遍历 allowed_operations
                allowed_ops = execution_request.get("allowed_operations", [])
                for i, op in enumerate(allowed_ops):
                    op_id = f"op_{i+1:03d}"
                    
                    # P0-RT1: Policy 检查
                    if policy:
                        try:
                            action = op.get("action")
                            params = op.get("params", {})
                            policy.assert_operation_allowed(action, params)
                        except PolicyDeniedError as e:
                            run_tape.audit_logger.log_event("policy_denied", details={
                                "operation": e.operation,
                                "reason": e.reason,
                                "rule_id": e.rule_id,
                                "params": params
                            })
                            raise
                    
                    result = self._execute_operation(op, worktree_path, op_id)
                    operations_executed.append(result)
            
            # 6. 完成
            run_tape.audit_logger.log_event("execution_complete")
            
            # 7. P0-RT3: 将 worktree 的 commits 带回主 repo（强制执行）
            commits_brought_back = 0
            patches_generated = 0
            
            if self.sandbox and worktree_path != self.repo_path:
                commits_brought_back, patches_generated = self._bring_back_commits_from_worktree(
                    worktree_path,
                    base_commit,
                    rollback_point,
                    run_dir,
                    exec_req_id,
                    policy  # 🔩 H3-2 收口2：传递 policy 用于 allowed_paths
                )
            
            completed_at = utc_now_iso()
            
            execution_result = {
                "execution_result_id": f"exec_result_{exec_req_id}",
                "schema_version": "0.11.1",
                "execution_request_id": exec_req_id,
                "task_id": task_id,  # Include task_id
                "status": "success",
                "operations_executed": operations_executed,
                "rollback_point": rollback_point,
                "commits_brought_back": commits_brought_back,
                "patches_generated": patches_generated,
                "started_at": started_at,
                "completed_at": completed_at,
                "mode": mode_id,
            }
            
            # Task-Driven: Record commits to lineage
            if commits_brought_back > 0:
                # Extract commit hashes from operations
                for op in operations_executed:
                    if op.get("type") == "git_commit" and op.get("commit_hash"):
                        self.task_manager.add_lineage(
                            task_id=task_id,
                            kind="commit",
                            ref_id=op["commit_hash"],
                            phase="completed"
                        )
            
            # Update task status
            self.task_manager.update_task_status(task_id, "succeeded")
            
            # P0-RT2: 生成 execution_summary.json
            self._generate_execution_summary(
                run_dir,
                exec_req_id,
                "success",
                commits_brought_back,
                patches_generated,
                started_at,
                completed_at
            )
            
            # P0-RT2: 生成 checksums.json
            self._generate_checksums(audit_dir, run_tape)
            
            # 保存结果
            result_file = run_dir / "execution_result.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(execution_result, f, indent=2)
            
            return execution_result
            
        except PolicyDeniedError as e:
            # P0-RT1: Policy 拒绝必须明确记录
            run_tape.audit_logger.log_error(f"Policy denied: {e.reason}")

            completed_at = utc_now_iso()

            # P0-RT2: 生成 execution_summary.json（即使失败）
            self._generate_execution_summary(
                run_dir,
                exec_req_id,
                "denied",
                0,
                0,
                started_at,
                completed_at,
                error=str(e)
            )

            # P0-RT2: 生成 checksums.json（即使失败）
            self._generate_checksums(audit_dir, run_tape)

            # Task-Driven: Update task status
            self.task_manager.update_task_status(task_id, "failed")

            return {
                "execution_result_id": f"exec_result_{exec_req_id}",
                "schema_version": "0.11.1",
                "execution_request_id": exec_req_id,
                "task_id": task_id,
                "status": "denied",
                "error": str(e),
                "policy_denied": {
                    "operation": e.operation,
                    "reason": e.reason,
                    "rule_id": e.rule_id
                },
                "started_at": started_at,
                "completed_at": completed_at
            }

        except Exception as e:
            # Task #4: Check if this is SpecNotFrozenError
            from agentos.core.task.errors import SpecNotFrozenError
            if isinstance(e, SpecNotFrozenError):
                run_tape.audit_logger.log_error(f"Spec not frozen: {e.reason}")

                completed_at = utc_now_iso()

                # Generate execution_summary.json
                self._generate_execution_summary(
                    run_dir,
                    exec_req_id,
                    "blocked",
                    0,
                    0,
                    started_at,
                    completed_at,
                    error=str(e)
                )

                # Generate checksums.json
                self._generate_checksums(audit_dir, run_tape)

                # Task-Driven: Update task status to blocked
                self.task_manager.update_task_status(task_id, "blocked")

                return {
                    "execution_result_id": f"exec_result_{exec_req_id}",
                    "schema_version": "0.11.1",
                    "execution_request_id": exec_req_id,
                    "task_id": task_id,
                    "status": "blocked",
                    "error": str(e),
                    "spec_not_frozen": {
                        "reason": e.reason,
                        "task_id": e.task_id,
                        "enforcement": "task_4_frozen_plan_validation"
                    },
                    "started_at": started_at,
                    "completed_at": completed_at
                }

            # Generic exception handler (original code)
            run_tape.audit_logger.log_error(str(e))
            
        except Exception as e:
            run_tape.audit_logger.log_error(str(e))
            
            # 尝试回滚
            if self.rollback_manager.rollback_points:
                run_tape.audit_logger.log_rollback("execution_failed", self.rollback_manager.rollback_points[-1])
                self.rollback_manager.rollback_to_latest()
            
            completed_at = utc_now_iso()
            
            # P0-RT2: 生成 execution_summary.json（即使失败）
            self._generate_execution_summary(
                run_dir,
                exec_req_id,
                "failed",
                0,
                0,
                started_at,
                completed_at,
                error=str(e)
            )
            
            # P0-RT2: 生成 checksums.json（即使失败）
            self._generate_checksums(audit_dir, run_tape)
            
            # Task-Driven: Update task status
            self.task_manager.update_task_status(task_id, "failed")
            
            return {
                "execution_result_id": f"exec_result_{exec_req_id}",
                "schema_version": "0.11.1",
                "execution_request_id": exec_req_id,
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "started_at": started_at,
                "completed_at": completed_at
            }
            
        finally:
            # 清理（始终执行）
            if self.sandbox:
                self.sandbox.remove_worktree()
            
            self.lock.release()
    
    def _execute_operation(
        self,
        op: Dict[str, Any],
        worktree_path: Path,
        op_id: Optional[str] = None,
        skip_planning_guard: bool = False
    ) -> Dict[str, Any]:
        """
        执行单个操作

        Task #3: Planning Guard integrated here
        Task #10: Added skip_planning_guard parameter with audit logging

        All operations must pass planning guard check before execution.

        Args:
            op: 操作定义
            worktree_path: worktree 路径
            op_id: 操作 ID（可选）
            skip_planning_guard: Skip planning guard check (default False)
                                 WARNING: Bypassing guard will be audited

        Returns:
            操作结果
        """
        if op_id is None:
            op_id = op.get("op_id", "unknown")

        action = op.get("action")
        params = op.get("params", {})

        # Task #10: Audit if planning guard is being skipped
        if skip_planning_guard:
            task_id = getattr(self, '_current_task_id', None)
            self.audit_logger.log_event("planning_guard_skipped", details={
                "task_id": task_id,
                "op_id": op_id,
                "action": action,
                "caller": "executor_engine._execute_operation",
                "reason": "skip_planning_guard=True",
                "warning": "Planning guard bypass detected - this operation is NOT protected",
                "level": "WARN"
            })

        # Task #3: Planning Guard - Check if operation is allowed in current phase
        # Task #10: Skip check if explicitly requested (but already audited above)
        if not skip_planning_guard:
            # Get task if available (from execution_request)
            task_id = getattr(self, '_current_task_id', None)
            task = None
            if task_id:
                task = self.task_manager.get_task(task_id)

            # Determine operation type and name for planning guard
            operation_type, operation_name = self._classify_operation(action)

            # Check with planning guard
            try:
                self.planning_guard.assert_operation_allowed(
                    operation_type=operation_type,
                    operation_name=operation_name,
                    task=task,
                    mode_id=getattr(self, '_current_mode_id', None),
                    metadata={"action": action, "op_id": op_id}
                )
            except PlanningSideEffectForbiddenError as e:
                # Log the violation and return error result
                self.audit_logger.log_error(
                    f"Planning guard blocked operation: {e.message}"
                )
                return {
                    "operation_id": op_id,
                    "action": action,
                    "status": "forbidden",
                    "error": str(e),
                    "error_type": "PlanningSideEffectForbiddenError"
                }

        self.audit_logger.log_operation_start(op_id, action, params)
        
        try:
            # 根据 action 类型执行
            if action == "write_file":
                result = self._execute_write_file(params, worktree_path)
            elif action == "update_file":
                result = self._execute_write_file(params, worktree_path)  # 同样逻辑
            elif action == "git_commit":
                result = self._execute_git_commit(params, worktree_path)
            elif action == "git_add":
                result = self._execute_git_add(params, worktree_path)
            elif action == "mkdir":
                result = self._execute_mkdir(params, worktree_path)
            else:
                raise ValueError(f"Unknown action: {action}")
            
            self.audit_logger.log_operation_end(op_id, "success", result)
            
            return {
                "operation_id": op_id,
                "action": action,
                "status": "success",
                "result": result
            }
        
        except Exception as e:
            self.audit_logger.log_operation_end(op_id, "failed", {"error": str(e)})
            
            return {
                "operation_id": op_id,
                "action": action,
                "status": "failed",
                "error": str(e)
            }
    
    def _execute_write_file(self, params: Dict[str, Any], worktree_path: Path) -> Dict[str, Any]:
        """执行 write_file 操作"""
        path = params["path"]
        content = params["content"]
        
        file_path = worktree_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        return {
            "path": str(path),
            "size": len(content),
            "absolute_path": str(file_path)
        }
    
    def _execute_mkdir(self, params: Dict[str, Any], worktree_path: Path) -> Dict[str, Any]:
        """执行 mkdir 操作"""
        path = params["path"]
        
        dir_path = worktree_path / path
        dir_path.mkdir(parents=True, exist_ok=True)
        
        return {
            "path": str(path),
            "absolute_path": str(dir_path)
        }
    
    def _execute_git_add(self, params: Dict[str, Any], worktree_path: Path) -> Dict[str, Any]:
        """执行 git add 操作"""
        paths = params.get("paths", ["."])
        
        if isinstance(paths, str):
            paths = [paths]
        
        # 使用 GitClient（不用 subprocess）
        git_client = GitClientFactory.get_client(worktree_path)
        git_client.add(paths)
        
        return {
            "paths": paths
        }
    
    def _execute_git_commit(self, params: Dict[str, Any], worktree_path: Path) -> Dict[str, Any]:
        """执行 git commit 操作"""
        message = params["message"]
        
        # 使用 GitClient（不用 subprocess）
        git_client = GitClientFactory.get_client(worktree_path)
        
        # git add -A (添加所有变更)
        git_client.add_all()
        
        # git commit
        commit_hash = git_client.commit(message)
        
        return {
            "commit_hash": commit_hash,
            "message": message,
            "short_hash": commit_hash[:8]
        }
    
    def apply_diff_or_raise(
        self,
        diff: str,
        allowed_paths: List[str],
        forbidden_paths: List[str],
        worktree_path: Path,
        audit_context: Optional[str] = None,
        policy_provided: bool = True,  # 🔩 终审3：记录 policy 是否提供
        mode_id: Optional[str] = None  # 🔩 M3 绑定点：mode 闸门
    ) -> Dict[str, Any]:
        """
        🔩 H3-2：统一的 apply diff 入口（防未来绕过）
        🔩 M3 绑定点：Mode 强制校验（只有 implementation 可 apply diff）
        
        这是 ONLY 合法的 diff 应用入口。
        任何进入 "apply diff" 的路径都必须经过此函数。
        
        硬规则：
        1. 必须先通过 Mode 校验（只有 implementation 允许）
        2. 必须先通过 DiffVerifier.verify()
        3. 如果 is_valid == False，raise DiffRejected（不允许 apply）
        4. 如果 is_valid == True，才调用 GitClient.apply_patch()
        5. 所有操作记录到 audit_logger
        
        Args:
            diff: Unified diff 内容
            allowed_paths: 允许修改的路径（glob 模式）
            forbidden_paths: 禁止修改的路径（glob 模式）
            worktree_path: worktree 路径
            audit_context: 审计上下文（如 tool_run_id）
            policy_provided: 是否提供了 policy
            mode_id: Mode ID（如果为 None，从实例变量读取）
        
        Returns:
            {
                "status": "applied" | "rejected",
                "diff_length": int,
                "files_touched": List[str],
                "validation": DiffValidationResult.to_dict()
            }
        
        Raises:
            DiffRejected: 如果 diff 验证失败
            ModeViolationError: 如果 Mode 不允许 apply diff
        """
        from ...ext.tools import DiffVerifier, ToolResult
        
        # ═══════════════════════════════════════════════════════════════
        # INTEGRATOR FREEZE (Agent 4): Diff 应用唯一闸门
        # ═══════════════════════════════════════════════════════════════
        # 此方法是所有 diff 应用的唯一入口，任何代码变更必须经过此闸门。
        #
        # 验收命令:
        #   rg "apply_diff_or_raise" agentos | wc -l
        #   期望结果: 2（定义 + 调用）
        #
        #   rg "GitClient\.apply_patch\(" agentos | wc -l
        #   期望结果: 2（定义 + 在本方法内调用）
        #
        # Mode 检查硬约束:
        #   - 100% 依赖 mode.allows_commit()
        #   - 非 implementation mode 必须抛出 ModeViolationError
        #   - 无任何特殊路径 / test bypass / legacy hack
        # ═══════════════════════════════════════════════════════════════
        # 🔩 M3 绑定点：Mode 闸门
        if mode_id is None:
            mode_id = getattr(self, '_current_mode_id', 'implementation')
        
        try:
            mode = get_mode(mode_id)
        except Exception as e:
            self.audit_logger.log_error(f"Invalid mode_id '{mode_id}': {e}")
            raise ModeViolationError(
                f"Invalid mode_id '{mode_id}': {e}",
                mode_id=mode_id,
                operation="apply_diff",
                error_category="config"
            )
        
        # 🔩 M3 绑定点：只有 implementation 允许 apply diff
        if not mode.allows_commit():
            self.audit_logger.log_event("mode_diff_denied", details={
                "mode_id": mode_id,
                "operation": "apply_diff",
                "reason": f"Mode '{mode_id}' does not allow commit/diff operations",
                "context": audit_context or "unknown"
            })

            # 🔔 Mode 违规告警 (Task 27: Emit to EventBus)
            emit_mode_violation(
                mode_id=mode_id,
                operation="apply_diff",
                message=f"Mode '{mode_id}' attempted to apply diff (forbidden)",
                context={
                    "audit_context": audit_context or "unknown",
                    "allows_commit": False,
                    "error_category": "config"
                },
                severity=AlertSeverity.ERROR,
                task_id=None  # Will be extracted from context if available
            )

            raise ModeViolationError(
                f"Mode '{mode_id}' does not allow diff operations. Only 'implementation' mode can apply diffs.",
                mode_id=mode_id,
                operation="apply_diff",
                error_category="config"
            )
        
        # 🔩 补强2：记录 diff policy scope（审计证据）+ Mode 信息
        # 🔩 补强2改进：pattern 脱敏截断（防止过长/敏感路径）+ scope_source 改为 policy_provided
        # 🔩 终审3：增加 policy_provided 和 policy_paths_empty 字段（防止误解）
        
        # 脱敏处理：每条 pattern 最多 120 chars
        # 🔩 终审4：防止 None / 非 string pattern（脏数据）
        def sanitize_pattern(pattern: str) -> str:
            if pattern is None:
                return ""
            pattern = str(pattern)  # 强制转为 string
            return pattern[:120] if len(pattern) <= 120 else pattern[:117] + "..."
        
        self.audit_logger.log_event("diff_policy_scope", details={
            "context": audit_context or "unknown",
            "mode_id": mode_id,  # 🔩 M3：记录 mode_id
            "policy_provided": policy_provided,  # 🔩 终审3：明确 policy 是否提供
            "policy_paths_empty": len(allowed_paths) == 0,  # 🔩 终审3：明确 paths 是否为空
            "allowed_paths_count": len(allowed_paths),
            "forbidden_paths_count": len(forbidden_paths),
            "allowed_paths_sample": [sanitize_pattern(p) for p in allowed_paths[:3]] if allowed_paths else [],  # 前3个pattern，脱敏
            "forbidden_paths_sample": [sanitize_pattern(p) for p in forbidden_paths[:3]] if forbidden_paths else [],
            "scope_source": "policy" if policy_provided else "none"  # 🔩 终审3：根据 policy_provided 设置
        })
        
        # 🔩 H3-2：强制验证（不允许绕过）
        # 创建临时 ToolResult 用于验证
        temp_result = ToolResult(
            tool="executor-internal",
            status="success",
            diff=diff,
            files_touched=[],  # DiffVerifier 会从 diff 中提取
            line_count=len(diff.split('\n')),
            tool_run_id=audit_context or "unknown"
        )
        
        diff_verifier = DiffVerifier()
        validation = diff_verifier.verify(temp_result, allowed_paths, forbidden_paths)
        
        # 审计：记录验证结果
        self.audit_logger.log_event("diff_validation", details={
            "context": audit_context or "unknown",
            "is_valid": validation.is_valid,
            "errors_count": len(validation.errors),
            "warnings_count": len(validation.warnings),
            "errors": validation.errors,
            "warnings": validation.warnings
        })
        
        # 🔩 H3-2：如果验证失败，raise（不允许 apply）
        if not validation.is_valid:
            error_msg = f"Diff verification failed: {validation.errors}"
            self.audit_logger.log_error(error_msg)
            
            raise DiffRejected(
                reason=error_msg,
                validation=validation
            )
        
        # 验证通过，apply diff
        # 写入临时 patch 文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
            f.write(diff)
            patch_file = Path(f.name)
        
        try:
            # 使用 GitClient apply_patch
            git_client = GitClientFactory.get_client(worktree_path)
            git_client.apply_patch(patch_file)
            
            # 审计：记录成功
            self.audit_logger.log_event("diff_applied", details={
                "context": audit_context or "unknown",
                "diff_length": len(diff),
                "files_touched": temp_result.files_touched,
                "validation": validation.to_dict()
            })
            
            return {
                "status": "applied",
                "diff_length": len(diff),
                "files_touched": temp_result.files_touched,
                "validation": validation.to_dict()
            }
            
        finally:
            # 清理临时文件
            patch_file.unlink(missing_ok=True)
    
    def _bring_back_commits_from_worktree(
        self,
        worktree_path: Path,
        base_commit: str,
        rollback_point: dict,
        run_dir: Path,
        exec_req_id: str,
        policy: Optional[Any] = None
    ) -> tuple[int, int]:
        """
        P0-RT3 + 钉子2: 将 worktree 的 commits 带回主 repo（强制执行，生成自证证据）
        
        🔩 H3-2 收口2：allowed_paths 从 policy 获取（不用 ["*"]）
        
        使用 format-patch → am 的方式，确保主 repo 获得所有 commits
        
        Args:
            worktree_path: worktree 路径
            base_commit: 基础 commit SHA
            rollback_point: 回滚点（包含 base commit）
            run_dir: 运行目录
            exec_req_id: 执行请求 ID
            policy: SandboxPolicy 对象（用于获取 allowed_paths）
        
        Returns:
            (commits_brought_back, patches_generated)
        """
        try:
            # 1. 在 worktree 收集 commits（钉子2: 需要记录所有 commit SHAs）
            worktree_git = GitClientFactory.get_client(worktree_path)
            head_sha = worktree_git.get_head_sha()
            
            # 获取 worktree 中从 base_commit 到 HEAD 的所有 commits
            worktree_commits = worktree_git.get_commit_range(base_commit, head_sha)
            
            # P0-RT3: 生成独立的 patch 文件（每个 commit 一个）
            patches_dir = run_dir / "patches"
            patches_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用 format-patch 生成多个 patch 文件
            patch_files = worktree_git.format_patch_multiple(base_commit, head_sha, patches_dir)
            
            # 钉子2: 计算每个 patch 的 SHA256
            patch_sha256 = {}
            for patch_file in patch_files:
                with open(patch_file, "rb") as f:
                    patch_sha256[patch_file.name] = hashlib.sha256(f.read()).hexdigest()
            
            self.audit_logger.log_event("patches_generated", details={
                "base_sha": base_commit[:8],
                "head_sha": head_sha[:8],
                "patch_count": len(patch_files),
                "patches_dir": str(patches_dir)
            })
            
            # 2. 回到主 repo 应用所有 patches
            main_git = GitClientFactory.get_client(self.repo_path)
            
            # 记录应用前的 HEAD（用于计算新 commits）
            before_am_head = main_git.get_head_sha()
            
            # 🔩 H3-2：所有 patch apply 必须经过统一入口
            # 🔩 H3-2 收口2：allowed_paths 从 policy 获取（不用 ["*"]）
            # 🔩 补强3：无 policy 时显式拒绝（防止绕过）
            
            # 从 policy 获取允许的路径，如果没有 policy，则拒绝（安全策略）
            if policy:
                # 🔥 大坑修复：policy.allowlist 可能是 pydantic 模型/dataclass，不是 dict
                # 🔩 终审5：增强 dataclass 支持（用 __dict__ 或 vars()）
                allowlist_obj = policy.allowlist
                if hasattr(allowlist_obj, "dict"):
                    # pydantic v1
                    allowlist_dict = allowlist_obj.dict()
                elif hasattr(allowlist_obj, "model_dump"):
                    # pydantic v2
                    allowlist_dict = allowlist_obj.model_dump()
                elif not isinstance(allowlist_obj, dict):
                    # dataclass or other
                    try:
                        # 🔩 终审5：优先用 __dict__（dataclass 友好）
                        if hasattr(allowlist_obj, "__dict__"):
                            allowlist_dict = allowlist_obj.__dict__
                        else:
                            allowlist_dict = dict(allowlist_obj)
                    except (TypeError, ValueError):
                        # 最后防线：当作 schema_mismatch
                        error_msg = f"Policy.allowlist is not a dict-like object: {type(allowlist_obj)}"
                        self.audit_logger.log_event("bring_back_policy_schema_error", details={
                            "error": error_msg,
                            "error_category": "schema",
                            "allowlist_type": str(type(allowlist_obj))
                        })
                        raise PolicyDeniedError(
                            message=error_msg,
                            operation="bring_back_commits",
                            reason="Policy.allowlist schema mismatch (error_category: schema)",
                            rule_id="executor:bring_back_allowlist_schema"
                        )
                else:
                    # 已经是 dict
                    allowlist_dict = allowlist_obj
                
                allowed_paths = allowlist_dict.get("paths", [])
                forbidden_paths = allowlist_dict.get("forbidden_paths", [])
            else:
                # 🔩 补强3：无 policy 时显式 raise（比 allowed_paths=[] 更可运维）
                # 🔩 补强3改进：error_category 明确为 config（不是"拒绝"而是"缺失配置"）
                error_msg = "Policy is required for bring-back commits verification. Cannot apply patches without policy-defined allowlist."
                self.audit_logger.log_event("bring_back_policy_missing", details={
                    "error": error_msg,
                    "error_category": "config",  # 🔩 补强3改进：明确归类为 config
                    "exec_req_id": exec_req_id,
                    "patches_count": len(patch_files)
                })
                raise PolicyDeniedError(
                    message=error_msg,
                    operation="bring_back_commits",
                    reason="Policy missing: bring-back requires policy.allowlist.paths for diff verification (error_category: config)",
                    rule_id="executor:bring_back_requires_policy"
                )
            
            for patch_file in patch_files:
                # 读取 patch 内容并通过 apply_diff_or_raise() 验证
                patch_content = patch_file.read_text()
                self.apply_diff_or_raise(
                    diff=patch_content,
                    allowed_paths=allowed_paths,  # 🔩 H3-2 收口2：从 policy 获取
                    forbidden_paths=forbidden_paths,
                    worktree_path=self.repo_path,
                    audit_context=f"bring_back_patch_{patch_file.name}",
                    policy_provided=True  # 🔩 终审3：policy 已提供
                )
            
            # 3. 验证 commits 数量
            main_head = main_git.get_head_sha()
            
            # 钉子2: 获取主 repo 应用 patch 后新增的 commits
            main_repo_commits_after_am = main_git.get_commit_range(before_am_head, main_head)
            
            self.audit_logger.log_event("commits_brought_back", details={
                "worktree_head": head_sha[:8],
                "main_repo_head": main_head[:8],
                "commits_count": len(patch_files),
                "patches_applied": len(patch_files)
            })
            
            # 4. P0-RT3 + 钉子2: 生成 sandbox_proof.json（自证能力增强）
            sandbox_proof = {
                "worktree_path": str(worktree_path),
                "base_commit": base_commit,
                "worktree_head_sha": head_sha,
                "main_repo_head_sha": main_head,
                "patch_count": len(patch_files),
                "patch_files": [str(p.name) for p in patch_files],
                # 钉子2: 自证字段
                "worktree_commits": worktree_commits,
                "main_repo_commits_after_am": main_repo_commits_after_am,
                "patch_sha256": patch_sha256,
                "brought_back_at": utc_now_iso()
            }
            
            proof_file = run_dir / "audit" / "sandbox_proof.json"
            proof_file.parent.mkdir(parents=True, exist_ok=True)
            with open(proof_file, "w", encoding="utf-8") as f:
                json.dump(sandbox_proof, f, indent=2)
            
            return len(patch_files), len(patch_files)
        
        except Exception as e:
            self.audit_logger.log_error(f"Failed to bring back commits: {str(e)}")
            return 0, 0
    
    def _create_error_result(
        self,
        exec_req_id: str,
        status: str,
        error: str,
        run_tape: RunTape,
        run_dir: Path
    ) -> Dict[str, Any]:
        """
        创建错误结果（统一错误返回格式）
        
        Args:
            exec_req_id: 执行请求 ID
            status: 状态（failed/blocked/denied）
            error: 错误消息
            run_tape: RunTape 实例
            run_dir: 运行目录
        
        Returns:
            执行结果字典
        """
        started_at = utc_now_iso()
        completed_at = started_at
        
        # P0-RT2: 生成 execution_summary.json（即使失败）
        self._generate_execution_summary(
            run_dir,
            exec_req_id,
            status,
            0,
            0,
            started_at,
            completed_at,
            error=error
        )
        
        # P0-RT2: 生成 checksums.json（即使失败）
        audit_dir = run_dir / "audit"
        self._generate_checksums(audit_dir, run_tape)
        
        return {
            "execution_result_id": f"exec_result_{exec_req_id}",
            "schema_version": "0.11.1",
            "execution_request_id": exec_req_id,
            "status": status,
            "error": error,
            "started_at": started_at,
            "completed_at": completed_at
        }
    
    def _generate_execution_summary(
        self,
        run_dir: Path,
        exec_req_id: str,
        status: str,
        commit_count: int,
        patch_count: int,
        started_at: str,
        completed_at: str,
        error: Optional[str] = None
    ) -> None:
        """
        P0-RT2: 生成 execution_summary.json（R3 要求）
        
        Args:
            run_dir: 运行目录
            exec_req_id: 执行请求 ID
            status: 状态
            commit_count: Commit 数量
            patch_count: Patch 数量
            started_at: 开始时间
            completed_at: 完成时间
            error: 错误消息（可选）
        """
        reports_dir = run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        summary = {
            "execution_request_id": exec_req_id,
            "status": status,
            "commit_count": commit_count,
            "patch_count": patch_count,
            "sandbox_used": True,  # 强制使用 worktree
            "started_at": started_at,
            "completed_at": completed_at
        }
        
        if error:
            summary["error"] = error
        
        summary_file = reports_dir / "execution_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    
    def _generate_checksums(
        self,
        audit_dir: Path,
        run_tape: RunTape
    ) -> None:
        """
        P0-RT2: 生成 checksums.json（R3 要求）
        
        Args:
            audit_dir: 审计目录
            run_tape: RunTape 实例
        """
        checksums = {
            "generated_at": utc_now_iso(),
            "files": {}
        }
        
        # 添加 run_tape 自身的 checksum
        if run_tape.run_tape_path.exists():
            content = run_tape.run_tape_path.read_bytes()
            checksums["files"]["run_tape.jsonl"] = hashlib.sha256(content).hexdigest()
        
        # 添加 execution_request.json 的 checksum（如果存在）
        request_file = audit_dir.parent / "execution_request.json"
        if request_file.exists():
            content = request_file.read_bytes()
            checksums["files"]["execution_request.json"] = hashlib.sha256(content).hexdigest()
        
        checksums_file = audit_dir / "checksums.json"
        with open(checksums_file, "w", encoding="utf-8") as f:
            json.dump(checksums, f, indent=2)

    def _classify_operation(self, action: str) -> tuple[str, str]:
        """
        Classify operation into (operation_type, operation_name) for planning guard

        Task #3: Planning Guard operation classification

        Args:
            action: Operation action (write_file, git_commit, etc.)

        Returns:
            Tuple of (operation_type, operation_name)
        """
        # Map executor actions to planning guard operation types
        if action in ["write_file", "update_file"]:
            return ("file_write", "file.write")
        elif action == "mkdir":
            return ("file_write", "Path.mkdir")
        elif action in ["git_commit"]:
            return ("git", "git.commit")
        elif action == "git_add":
            return ("git", "git.add")
        elif action == "git_push":
            return ("git", "git.push")
        elif action in ["run_command", "exec", "shell"]:
            return ("shell", "subprocess.run")
        else:
            # Unknown action, classify as generic
            return ("unknown", action)
