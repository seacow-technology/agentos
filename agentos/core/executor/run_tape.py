"""Run Tape - 扩展审计日志，支持 snapshot 和 checksum

基于 audit_logger，增加：
- Step-level snapshots（每步保存状态）
- File checksums（文件校验和）
- Snapshot 查询功能
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .audit_logger import AuditLogger


class RunTape:
    """Run Tape - 增强的审计日志"""
    
    def __init__(self, run_dir: Path):
        """
        初始化 Run Tape
        
        Args:
            run_dir: 执行目录
        """
        self.run_dir = Path(run_dir)
        self.run_tape_path = self.run_dir / "run_tape.jsonl"
        self.snapshots_dir = self.run_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用 AuditLogger 作为基础
        self.audit_logger = AuditLogger(self.run_tape_path)
        
        self.current_step = None
    
    def start_step(self, step_id: str, step_type: str, params: Dict[str, Any]) -> None:
        """
        开始一个 step
        
        Args:
            step_id: Step ID
            step_type: Step 类型
            params: 参数
        """
        self.current_step = step_id
        
        self.audit_logger.log_event(
            event_type="step_start",
            operation_id=step_id,
            details={
                "step_type": step_type,
                "params": params,
                "started_at": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def end_step(
        self,
        step_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        create_snapshot: bool = True
    ) -> None:
        """
        结束一个 step
        
        Args:
            step_id: Step ID
            status: 状态（success/failed）
            result: 结果数据
            create_snapshot: 是否创建 snapshot
        """
        # 计算 checksums
        checksums = self._compute_checksums() if create_snapshot else {}
        
        self.audit_logger.log_event(
            event_type="step_end",
            operation_id=step_id,
            details={
                "status": status,
                "result": result,
                "checksums": checksums,
                "ended_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # 保存 snapshot
        if create_snapshot:
            self._save_snapshot(step_id, checksums)
        
        self.current_step = None
    
    def log_operation(
        self,
        operation_id: str,
        operation_type: str,
        params: Dict[str, Any]
    ) -> None:
        """记录操作（兼容旧接口）"""
        self.audit_logger.log_operation_start(operation_id, operation_type, params)
    
    def log_error(self, error_type: str, message: str, details: Optional[Dict] = None) -> None:
        """记录错误"""
        self.audit_logger.log_error(error_type, message, details)
    
    def _compute_checksums(self) -> Dict[str, str]:
        """
        计算当前工作目录的文件 checksums
        
        Returns:
            {file_path: sha256_checksum}
        """
        checksums = {}
        
        # 只计算特定目录的文件
        target_dirs = ["docs", "examples", "agentos", "tests", "scripts"]
        
        for dir_name in target_dirs:
            dir_path = self.run_dir / dir_name
            if not dir_path.exists():
                continue
            
            for file_path in dir_path.rglob("*.py"):
                if file_path.is_file():
                    try:
                        content = file_path.read_bytes()
                        checksum = hashlib.sha256(content).hexdigest()
                        rel_path = str(file_path.relative_to(self.run_dir))
                        checksums[rel_path] = checksum
                    except Exception:
                        pass
        
        return checksums
    
    def _save_snapshot(self, step_id: str, checksums: Dict[str, str]) -> None:
        """
        保存 snapshot
        
        Args:
            step_id: Step ID
            checksums: File checksums
        """
        snapshot_file = self.snapshots_dir / f"{step_id}.json"
        
        snapshot = {
            "step_id": step_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checksums": checksums,
            "file_count": len(checksums)
        }
        
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    
    def get_snapshot(self, step_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定 step 的 snapshot
        
        Args:
            step_id: Step ID
        
        Returns:
            Snapshot 数据或 None
        """
        snapshot_file = self.snapshots_dir / f"{step_id}.json"
        
        if not snapshot_file.exists():
            return None
        
        with open(snapshot_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_all_snapshots(self) -> List[Dict[str, Any]]:
        """获取所有 snapshots"""
        snapshots = []
        
        for snapshot_file in sorted(self.snapshots_dir.glob("*.json")):
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshots.append(json.load(f))
        
        return snapshots
    
    def get_events(self) -> List[Dict[str, Any]]:
        """
        获取所有事件
        
        Returns:
            事件列表
        """
        if not self.run_tape_path.exists():
            return []
        
        events = []
        with open(self.run_tape_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        return events
    
    def get_step_events(self, step_id: str) -> List[Dict[str, Any]]:
        """
        获取指定 step 的所有事件
        
        Args:
            step_id: Step ID
        
        Returns:
            事件列表
        """
        all_events = self.get_events()
        return [e for e in all_events if e.get("operation_id") == step_id]


def create_run_tape(run_dir: Path) -> RunTape:
    """
    创建 Run Tape（便捷函数）
    
    Args:
        run_dir: 执行目录
    
    Returns:
        RunTape 实例
    """
    return RunTape(run_dir)
