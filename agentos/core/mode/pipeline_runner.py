"""ModePipelineRunner - 多阶段 Mode 执行编排

按顺序执行 Mode Pipeline，支持 planning → implementation 等多阶段流水线
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import json

from .mode_selector import ModeSelection
from ..executor.executor_engine import ExecutorEngine
from ..task import TaskManager, TaskContext


@dataclass
class StageResult:
    """单个阶段的执行结果
    
    Attributes:
        mode_id: 执行的 mode ID
        status: 执行状态（success/failed/blocked）
        output: 执行输出
        started_at: 开始时间
        finished_at: 结束时间
        error: 错误信息（如果失败）
    """
    mode_id: str
    status: str
    output: Dict[str, Any]
    started_at: str
    finished_at: str
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Pipeline 整体执行结果
    
    Attributes:
        pipeline_id: Pipeline 唯一标识
        mode_selection: 原始的 mode 选择结果
        stages: 各个阶段的执行结果
        overall_status: 整体状态（success/failed/partial）
        started_at: 开始时间
        finished_at: 结束时间
    """
    pipeline_id: str
    mode_selection: ModeSelection
    stages: List[StageResult]
    overall_status: str
    started_at: str
    finished_at: str
    task_id: Optional[str] = None  # Task ID for traceability
    
    @property
    def summary(self) -> str:
        """生成简要总结"""
        success_count = sum(1 for s in self.stages if s.status == "success")
        total_count = len(self.stages)
        return f"{success_count}/{total_count} stages succeeded, overall: {self.overall_status}"


class ModePipelineRunner:
    """Mode Pipeline 执行器
    
    按顺序执行多个 mode，每个 mode 的输出可以作为下一个 mode 的输入
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """初始化 Pipeline Runner
        
        Args:
            output_dir: 输出目录（默认为 outputs/pipeline）
        """
        self.output_dir = Path(output_dir or "outputs/pipeline")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.task_manager = TaskManager()
    
    def run_pipeline(
        self,
        mode_selection: ModeSelection,
        nl_input: str,
        repo_path: Path,
        policy_path: Optional[Path] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> PipelineResult:
        """执行 Mode Pipeline
        
        Args:
            mode_selection: Mode 选择结果
            nl_input: 原始自然语言输入
            repo_path: 目标仓库路径
            policy_path: Sandbox 策略路径
            task_id: 可选的已存在 task_id
            session_id: 可选的 session_id
            
        Returns:
            PipelineResult: Pipeline 执行结果
            
        Example:
            >>> runner = ModePipelineRunner()
            >>> selection = ModeSelection(
            ...     primary_mode="planning",
            ...     pipeline=["planning", "implementation"],
            ...     reason="Development task"
            ... )
            >>> result = runner.run_pipeline(
            ...     selection, "I need a landing page", 
            ...     Path("."), Path("policies/sandbox_policy.json")
            ... )
        """
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).isoformat()
        
        # Task-Driven: Create or resolve task
        if not task_id:
            task = self.task_manager.create_task(
                title=f"Pipeline: {nl_input[:50]}...",
                session_id=session_id,
                created_by="pipeline_runner"
            )
            task_id = task.task_id
        
        # Create task context
        task_context = TaskContext(task_id=task_id, session_id=session_id)
        
        # Record pipeline_id to lineage
        self.task_manager.add_lineage(
            task_id=task_id,
            kind="pipeline",
            ref_id=pipeline_id,
            phase="started"
        )
        
        # 创建 pipeline 输出目录
        pipeline_dir = self.output_dir / pipeline_id
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 pipeline 元数据
        metadata = {
            "pipeline_id": pipeline_id,
            "task_id": task_id,  # Include task_id in metadata
            "session_id": session_id,
            "mode_selection": {
                "primary_mode": mode_selection.primary_mode,
                "pipeline": mode_selection.pipeline,
                "reason": mode_selection.reason
            },
            "nl_input": nl_input,
            "repo_path": str(repo_path),
            "started_at": started_at
        }
        
        metadata_file = pipeline_dir / "pipeline_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # 执行各个阶段
        stages: List[StageResult] = []
        context = {"original_input": nl_input}
        overall_status = "success"
        
        for stage_idx, mode_id in enumerate(mode_selection.pipeline):
            stage_result = self._run_stage(
                mode_id=mode_id,
                stage_idx=stage_idx,
                context=context,
                repo_path=repo_path,
                policy_path=policy_path,
                pipeline_dir=pipeline_dir,
                task_context=task_context
            )
            
            stages.append(stage_result)
            
            # 如果当前阶段失败，停止后续执行
            if stage_result.status != "success":
                overall_status = "failed"
                break
            
            # 将当前阶段的输出添加到上下文，供下一阶段使用
            context[f"{mode_id}_output"] = stage_result.output
        
        # 如果部分成功
        if overall_status == "success" and len(stages) < len(mode_selection.pipeline):
            overall_status = "partial"
        
        finished_at = datetime.now(timezone.utc).isoformat()
        
        # Update task status
        self.task_manager.update_task_status(task_id, overall_status)
        self.task_manager.add_lineage(
            task_id=task_id,
            kind="pipeline",
            ref_id=pipeline_id,
            phase="completed"
        )
        
        # 保存完整结果
        result = PipelineResult(
            pipeline_id=pipeline_id,
            mode_selection=mode_selection,
            stages=stages,
            overall_status=overall_status,
            started_at=started_at,
            finished_at=finished_at
        )
        result.task_id = task_id  # Attach task_id to result
        
        result_file = pipeline_dir / "pipeline_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "pipeline_id": result.pipeline_id,
                "overall_status": result.overall_status,
                "stages": [
                    {
                        "mode_id": s.mode_id,
                        "status": s.status,
                        "started_at": s.started_at,
                        "finished_at": s.finished_at,
                        "error": s.error
                    }
                    for s in result.stages
                ],
                "started_at": result.started_at,
                "finished_at": result.finished_at
            }, f, indent=2, ensure_ascii=False)
        
        return result
    
    def _run_stage(
        self,
        mode_id: str,
        stage_idx: int,
        context: Dict[str, Any],
        repo_path: Path,
        policy_path: Optional[Path],
        pipeline_dir: Path,
        task_context: TaskContext
    ) -> StageResult:
        """执行单个阶段
        
        Args:
            mode_id: Mode ID
            stage_idx: 阶段索引
            context: 上下文（包含之前阶段的输出）
            repo_path: 仓库路径
            policy_path: 策略路径
            pipeline_dir: Pipeline 输出目录
            
        Returns:
            StageResult: 阶段执行结果
        """
        started_at = datetime.now(timezone.utc).isoformat()
        
        # 构造 execution_request
        exec_req_id = f"stage_{stage_idx}_{mode_id}_{uuid.uuid4().hex[:8]}"
        execution_request = self._build_execution_request(
            exec_req_id=exec_req_id,
            mode_id=mode_id,
            context=context,
            repo_path=repo_path,
            task_context=task_context
        )
        
        # Record execution_request to lineage
        self.task_manager.add_lineage(
            task_id=task_context.task_id,
            kind="execution_request",
            ref_id=exec_req_id,
            phase=mode_id
        )
        
        # 创建阶段输出目录
        stage_dir = pipeline_dir / f"stage_{stage_idx}_{mode_id}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 调用 ExecutorEngine
            executor = ExecutorEngine(
                repo_path=repo_path,
                output_dir=stage_dir,
                lock_dir=stage_dir / "locks",
                approval_dir=stage_dir / "approvals"
            )
            
            # Task #1: Pass caller_source to enforce chat → execution hard gate
            result = executor.execute(
                execution_request=execution_request,
                sandbox_policy={},  # deprecated parameter
                policy_path=policy_path,
                caller_source="task_runner"  # Pipeline runner is always called by task runner
            )
            
            finished_at = datetime.now(timezone.utc).isoformat()
            
            # 判断执行状态
            status = result.get("status", "unknown")
            error = result.get("error") if status != "success" else None
            
            return StageResult(
                mode_id=mode_id,
                status=status,
                output=result,
                started_at=started_at,
                finished_at=finished_at,
                error=error
            )
            
        except Exception as e:
            finished_at = datetime.now(timezone.utc).isoformat()
            return StageResult(
                mode_id=mode_id,
                status="failed",
                output={"error": str(e)},
                started_at=started_at,
                finished_at=finished_at,
                error=str(e)
            )
    
    def _build_execution_request(
        self,
        exec_req_id: str,
        mode_id: str,
        context: Dict[str, Any],
        repo_path: Path,
        task_context: TaskContext
    ) -> Dict[str, Any]:
        """构造 execution_request
        
        Args:
            exec_req_id: 执行请求 ID
            mode_id: Mode ID
            context: 上下文
            repo_path: 仓库路径
            
        Returns:
            Dict[str, Any]: execution_request
        """
        # 基础结构
        execution_request = {
            "execution_request_id": exec_req_id,
            "task_id": task_context.task_id,  # Include task_id
            "session_id": task_context.session_id,
            "mode_id": mode_id,  # 🔩 关键：明确设置 mode_id
            "context": context,
            "repo_path": str(repo_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "steps": []  # 简化版：步骤由 Executor 内部决定
        }
        
        return execution_request
