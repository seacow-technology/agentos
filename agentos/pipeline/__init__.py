"""Pipeline Resume - BLOCKED → RESUMED 工作流

当 pipeline 因 question_pack 被 BLOCKED 后，支持应用 answer_pack 并继续执行。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import hashlib


class PipelineResumer:
    """Pipeline Resume 管理器"""
    
    def __init__(self, run_dir: Path):
        """
        初始化 Resume 管理器
        
        Args:
            run_dir: Pipeline run 目录
        """
        self.run_dir = Path(run_dir)
        self.intent_dir = self.run_dir / "01_intent"
        self.audit_file = self.run_dir / "resume_audit.jsonl"
    
    def is_blocked(self) -> bool:
        """
        检查 pipeline 是否处于 BLOCKED 状态
        
        Returns:
            是否 BLOCKED
        """
        status_file = self.intent_dir / "status.json"
        if not status_file.exists():
            return False
        
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        
        return status.get("status") == "BLOCKED"
    
    def get_question_pack(self) -> Optional[Dict[str, Any]]:
        """
        获取 question pack
        
        Returns:
            question_pack 或 None
        """
        qpack_file = self.intent_dir / "question_pack.json"
        if not qpack_file.exists():
            return None
        
        with open(qpack_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def validate_answer_pack(
        self,
        answer_pack: Dict[str, Any],
        question_pack: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        验证 answer_pack 与 question_pack 匹配
        
        Args:
            answer_pack: Answer pack
            question_pack: Question pack
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # 检查 pack ID 匹配
        if answer_pack.get("question_pack_id") != question_pack.get("question_pack_id"):
            errors.append("question_pack_id mismatch")
        
        # 检查所有 question 都有 answer
        questions = question_pack.get("questions", [])
        answers = {a["question_id"]: a for a in answer_pack.get("answers", [])}
        
        for question in questions:
            q_id = question["question_id"]
            if q_id not in answers:
                errors.append(f"Missing answer for question: {q_id}")
            else:
                # 检查 evidence_refs
                answer = answers[q_id]
                if not answer.get("evidence_refs"):
                    errors.append(f"Missing evidence_refs for question: {q_id}")
        
        return len(errors) == 0, errors
    
    def apply_answer_pack(self, answer_pack: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用 answer_pack 到 pipeline
        
        Args:
            answer_pack: Answer pack
        
        Returns:
            Resume context（包含 resume 信息）
        """
        # 记录 resume 事件
        self._log_audit({
            "event": "RESUME_START",
            "answer_pack_id": answer_pack["answer_pack_id"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 保存 answer_pack 到 run_dir
        answer_pack_file = self.intent_dir / "answer_pack.json"
        with open(answer_pack_file, "w", encoding="utf-8") as f:
            json.dump(answer_pack, f, indent=2)
        
        # 更新状态为 RESUMED
        status_file = self.intent_dir / "status.json"
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        
        status["status"] = "RESUMED"
        status["resumed_at"] = datetime.now(timezone.utc).isoformat()
        status["answer_pack_id"] = answer_pack["answer_pack_id"]
        
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        
        resume_context = {
            "resume_from_step": "02_dryrun",  # 从 dryrun 继续
            "answer_pack_id": answer_pack["answer_pack_id"],
            "resumed_at": status["resumed_at"]
        }
        
        self._log_audit({
            "event": "RESUME_APPLIED",
            "context": resume_context,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return resume_context
    
    def _log_audit(self, event: Dict[str, Any]) -> None:
        """记录审计日志"""
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def resume_pipeline_run(
    run_dir: Path,
    answer_pack_path: Path
) -> Dict[str, Any]:
    """
    Resume 一个 BLOCKED 的 pipeline run
    
    Args:
        run_dir: Pipeline run 目录
        answer_pack_path: Answer pack 文件路径
    
    Returns:
        Resume 结果
    
    Raises:
        ValueError: 如果 pipeline 不是 BLOCKED 状态或验证失败
    """
    resumer = PipelineResumer(run_dir)
    
    # 检查状态
    if not resumer.is_blocked():
        raise ValueError(f"Pipeline is not BLOCKED: {run_dir}")
    
    # 获取 question pack
    question_pack = resumer.get_question_pack()
    if not question_pack:
        raise ValueError(f"No question_pack.json found in {run_dir}")
    
    # 加载 answer pack
    with open(answer_pack_path, "r", encoding="utf-8") as f:
        answer_pack = json.load(f)
    
    # 验证
    is_valid, errors = resumer.validate_answer_pack(answer_pack, question_pack)
    if not is_valid:
        raise ValueError(f"Answer pack validation failed: {errors}")
    
    # 应用
    resume_context = resumer.apply_answer_pack(answer_pack)
    
    return {
        "status": "SUCCESS",
        "resume_context": resume_context,
        "run_dir": str(run_dir)
    }
