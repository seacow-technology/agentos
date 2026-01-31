"""
Audit Logger - 审计日志

记录所有执行事件到run_tape
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
from agentos.core.time import utc_now_iso



class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, run_tape_path: Path):
        """初始化审计日志"""
        self.run_tape_path = Path(run_tape_path)
        self.run_tape_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果文件不存在，创建它
        if not self.run_tape_path.exists():
            self.run_tape_path.touch()
        
        self.event_counter = 0
    
    def log_event(
        self,
        event_type: str,
        operation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        stdout_summary: Optional[str] = None,
        stderr_summary: Optional[str] = None
    ):
        """
        记录事件到run_tape
        
        Args:
            event_type: 事件类型 (operation_start, operation_end, error, rollback)
            operation_id: 操作ID
            details: 详细信息
            stdout_summary: stdout摘要（最多1000字符）
            stderr_summary: stderr摘要（最多1000字符）
        """
        self.event_counter += 1
        
        event = {
            "event_id": f"event_{self.event_counter:06d}",
            "timestamp": utc_now_iso(),
            "event_type": event_type
        }
        
        if operation_id:
            event["operation_id"] = operation_id
        
        if details:
            event["details"] = details
        
        if stdout_summary:
            event["stdout_summary"] = stdout_summary[:1000]
        
        if stderr_summary:
            event["stderr_summary"] = stderr_summary[:1000]
        
        # Append to JSONL
        with open(self.run_tape_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def log_operation_start(self, operation_id: str, operation_type: str, params: Dict[str, Any]):
        """记录操作开始"""
        self.log_event(
            event_type="operation_start",
            operation_id=operation_id,
            details={
                "operation_type": operation_type,
                "params": params
            }
        )
    
    def log_operation_end(
        self,
        operation_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None
    ):
        """记录操作结束"""
        details = {"status": status}
        if result:
            details["result"] = result
        
        self.log_event(
            event_type="operation_end",
            operation_id=operation_id,
            details=details,
            stdout_summary=stdout[:1000] if stdout else None,
            stderr_summary=stderr[:1000] if stderr else None
        )
    
    def log_error(self, error_message: str, operation_id: Optional[str] = None):
        """记录错误"""
        self.log_event(
            event_type="error",
            operation_id=operation_id,
            details={"error": error_message}
        )
    
    def log_rollback(self, reason: str, rollback_point: Dict[str, Any]):
        """记录回滚"""
        self.log_event(
            event_type="rollback",
            details={
                "reason": reason,
                "rollback_point": rollback_point
            }
        )
    
    def get_all_events(self) -> list:
        """读取所有事件"""
        events = []
        
        if not self.run_tape_path.exists():
            return events
        
        with open(self.run_tape_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        
        return events
    
    def compute_tape_checksum(self) -> str:
        """计算run_tape的checksum"""
        if not self.run_tape_path.exists():
            return hashlib.sha256(b"").hexdigest()
        
        with open(self.run_tape_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
