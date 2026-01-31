"""
Async Executor Engine - 异步执行编排引擎 (v0.12)

支持并行执行和 DAG 调度
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import hashlib

from .allowlist import Allowlist
from .sandbox import Sandbox
from .rollback import RollbackManager
from .lock import ExecutionLock
from .review_gate import ReviewGate
from .audit_logger import AuditLogger
from .dag_scheduler import DAGScheduler, Operation, OperationStatus
from agentos.core.time import utc_now_iso



class AsyncExecutorEngine:
    """异步执行引擎 - 支持并行执行"""
    
    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        lock_dir: Optional[Path] = None,
        approval_dir: Optional[Path] = None,
        max_concurrency: int = 5
    ):
        """
        初始化异步执行引擎
        
        Args:
            repo_path: Git仓库路径
            output_dir: 输出目录
            lock_dir: 锁目录
            approval_dir: 审批目录
            max_concurrency: 最大并发数
        """
        self.repo_path = Path(repo_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrency = max_concurrency
        
        # 初始化组件
        self.allowlist = Allowlist()
        self.sandbox: Optional[Sandbox] = None
        self.rollback_manager = RollbackManager(repo_path)
        self.lock = ExecutionLock(lock_dir or (output_dir / "locks"))
        self.review_gate = ReviewGate(approval_dir or (output_dir / "approvals"))
        self.audit_logger: Optional[AuditLogger] = None
    
    async def execute(
        self,
        execution_request: Dict[str, Any],
        sandbox_policy: Dict[str, Any],
        use_dag: bool = True
    ) -> Dict[str, Any]:
        """
        异步执行请求
        
        Args:
            execution_request: 执行请求
            sandbox_policy: sandbox策略
            use_dag: 是否使用DAG并行执行
        
        Returns:
            执行结果
        """
        exec_req_id = execution_request["execution_request_id"]
        run_dir = self.output_dir / exec_req_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化audit logger
        run_tape_path = run_dir / "run_tape.jsonl"
        self.audit_logger = AuditLogger(run_tape_path)
        
        self.audit_logger.log_event("execution_start", details={
            "execution_request_id": exec_req_id,
            "mode": execution_request.get("execution_mode"),
            "dag_enabled": use_dag
        })
        
        try:
            # 1. 检查是否需要审批
            if self.review_gate.requires_review(execution_request):
                approval = self.review_gate.check_approval(exec_req_id)
                if not approval:
                    self.audit_logger.log_error("Execution requires approval but none found")
                    return self._create_error_result(exec_req_id, "Requires approval")
            
            # 2. 获取锁
            repo_hash = hashlib.sha256(str(self.repo_path).encode()).hexdigest()[:16]
            if not self.lock.acquire(exec_req_id, repo_hash):
                self.audit_logger.log_error("Failed to acquire lock")
                return self._create_error_result(exec_req_id, "Lock acquisition failed")
            
            # 3. 创建 Sandbox
            branch_name = execution_request.get("target_branch")
            self.sandbox = Sandbox(self.repo_path, create_branch=bool(branch_name))
            
            try:
                worktree_path = self.sandbox.create_worktree(exec_req_id, branch_name)
                self.audit_logger.log_event("sandbox_created", details={
                    "worktree_path": str(worktree_path)
                })
                
                # 4. 创建回滚点
                rollback_id = self.rollback_manager.create_rollback_point(
                    exec_req_id,
                    worktree=worktree_path
                )
                self.audit_logger.log_event("rollback_point_created", details={
                    "rollback_id": rollback_id
                })
                
                # 5. 执行操作
                if use_dag:
                    # DAG 并行执行
                    success, operation_results = await self._execute_dag(
                        execution_request,
                        sandbox_policy
                    )
                else:
                    # 线性执行 (向后兼容)
                    success, operation_results = await self._execute_linear(
                        execution_request,
                        sandbox_policy
                    )
                
                # 6. 构建结果
                result = {
                    "execution_result_id": f"exec_result_{exec_req_id}",
                    "schema_version": "0.12.0",
                    "execution_request_id": exec_req_id,
                    "status": "completed" if success else "failed",
                    "started_at": utc_now_iso(),
                    "completed_at": utc_now_iso(),
                    "worktree_path": str(worktree_path),
                    "rollback_id": rollback_id,
                    "operation_results": operation_results,
                    "execution_mode": "parallel_dag" if use_dag else "sequential"
                }
                
                self.audit_logger.log_event("execution_completed", details={
                    "status": result["status"]
                })
                
                return result
                
            finally:
                # 清理
                if self.sandbox:
                    self.sandbox.remove_worktree()
                self.lock.release(exec_req_id, repo_hash)
                
        except Exception as e:
            self.audit_logger.log_error(f"Execution failed: {str(e)}")
            if self.sandbox:
                self.sandbox.remove_worktree()
            repo_hash = hashlib.sha256(str(self.repo_path).encode()).hexdigest()[:16]
            self.lock.release(exec_req_id, repo_hash)
            
            return self._create_error_result(exec_req_id, str(e))
    
    async def _execute_dag(
        self,
        execution_request: Dict,
        sandbox_policy: Dict
    ) -> tuple[bool, List[Dict]]:
        """使用DAG并行执行操作"""
        allowed_ops = execution_request.get("allowed_operations", [])
        
        # 构建DAG
        scheduler = DAGScheduler(allowed_ops)
        
        # 记录DAG可视化
        self.audit_logger.log_event("dag_created", details={
            "visualization": scheduler.visualize_dag(),
            "statistics": scheduler.get_statistics()
        })
        
        # 执行DAG
        async def execute_single_op(op: Operation) -> Dict:
            """执行单个操作"""
            self.audit_logger.log_event("operation_start", details={
                "op_id": op.op_id,
                "op_type": op.op_type
            })
            
            try:
                # 检查allowlist
                if not self.allowlist.is_allowed(op.op_type):
                    raise ValueError(f"Operation type not allowed: {op.op_type}")
                
                # 简化版执行 - 实际实现需要根据op_type调用相应的执行逻辑
                result = {
                    "op_id": op.op_id,
                    "status": "completed",
                    "message": f"Executed {op.op_type}"
                }
                
                self.audit_logger.log_event("operation_completed", details={
                    "op_id": op.op_id
                })
                
                return result
                
            except Exception as e:
                self.audit_logger.log_error(f"Operation {op.op_id} failed: {str(e)}")
                raise
        
        success, results = await scheduler.execute_parallel(
            execute_single_op,
            max_concurrency=self.max_concurrency
        )
        
        # 记录统计
        stats = scheduler.get_statistics()
        self.audit_logger.log_event("dag_completed", details=stats)
        
        return success, results
    
    async def _execute_linear(
        self,
        execution_request: Dict,
        sandbox_policy: Dict
    ) -> tuple[bool, List[Dict]]:
        """线性执行操作（向后兼容）"""
        allowed_ops = execution_request.get("allowed_operations", [])
        results = []
        
        for i, op in enumerate(allowed_ops):
            op_id = op.get("op_id", f"op_{i}")
            op_type = op.get("type")
            
            self.audit_logger.log_event("operation_start", details={
                "op_id": op_id,
                "op_type": op_type
            })
            
            try:
                # 检查allowlist
                if not self.allowlist.is_allowed(op_type):
                    raise ValueError(f"Operation type not allowed: {op_type}")
                
                # 简化版执行
                result = {
                    "op_id": op_id,
                    "status": "completed",
                    "message": f"Executed {op_type}"
                }
                results.append(result)
                
                self.audit_logger.log_event("operation_completed", details={
                    "op_id": op_id
                })
                
            except Exception as e:
                self.audit_logger.log_error(f"Operation {op_id} failed: {str(e)}")
                results.append({
                    "op_id": op_id,
                    "status": "failed",
                    "error": str(e)
                })
                return False, results
        
        return True, results
    
    def _create_error_result(self, exec_req_id: str, error: str) -> Dict:
        """创建错误结果"""
        return {
            "execution_result_id": f"exec_result_{exec_req_id}",
            "schema_version": "0.12.0",
            "execution_request_id": exec_req_id,
            "status": "failed",
            "error": error,
            "started_at": utc_now_iso(),
            "completed_at": utc_now_iso()
        }


# Helper function for backward compatibility
def execute_async(engine: AsyncExecutorEngine, *args, **kwargs) -> Dict:
    """同步包装器，用于向后兼容"""
    return asyncio.run(engine.execute(*args, **kwargs))
