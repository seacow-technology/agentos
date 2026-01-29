"""Tool Dispatch - 工具调度执行

生成命令、运行工具、收集输出。
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from agentos.core.infra.tool_executor import ToolExecutor


class ToolDispatcher:
    """工具调度器"""
    
    def __init__(self, output_dir: Path):
        """
        初始化调度器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def dispatch(
        self,
        task_pack: Dict[str, Any],
        tool_adapter: Any
    ) -> Dict[str, Any]:
        """
        调度工具执行
        
        Args:
            task_pack: Tool task pack
            tool_adapter: Tool adapter 实例
        
        Returns:
            调度结果
        """
        task_pack_id = task_pack["tool_task_pack_id"]
        tool_type = task_pack["tool_type"]
        
        # 创建运行目录
        run_dir = self.output_dir / task_pack_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 task pack
        task_pack_file = run_dir / "task_pack.json"
        with open(task_pack_file, "w", encoding="utf-8") as f:
            json.dump(task_pack, f, indent=2)
        
        # 生成调度命令
        command = tool_adapter.dispatch(task_pack, run_dir)
        
        # 保存命令
        command_file = run_dir / "dispatch_command.sh"
        with open(command_file, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"# Task Pack: {task_pack_id}\n")
            f.write(f"# Tool: {tool_type}\n\n")
            f.write(command)
            f.write("\n")
        
        command_file.chmod(0o755)
        
        return {
            "status": "dispatched",
            "task_pack_id": task_pack_id,
            "run_dir": str(run_dir),
            "command_file": str(command_file),
            "command": command
        }
    
    def execute(
        self,
        task_pack: Dict[str, Any],
        tool_adapter: Any,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行工具（实际调用工具 CLI）
        
        Args:
            task_pack: Tool task pack
            tool_adapter: Tool adapter 实例
            timeout: 超时时间（秒）
        
        Returns:
            执行结果
        """
        # 先 dispatch
        dispatch_result = self.dispatch(task_pack, tool_adapter)
        run_dir = Path(dispatch_result["run_dir"])
        
        # 记录开始时间
        started_at = datetime.now(timezone.utc)
        
        # 这里简化实现：生成命令文件
        # 实际执行需要用户手动运行或通过外部调度
        # 因为工具（claude CLI, codex）可能需要交互或特殊环境
        
        result = {
            "status": "pending_execution",
            "task_pack_id": task_pack["tool_task_pack_id"],
            "run_dir": str(run_dir),
            "dispatch_command": dispatch_result["command"],
            "message": "Command generated. Run manually or use external scheduler.",
            "started_at": started_at.isoformat()
        }
        
        # 保存结果
        result_file = run_dir / "dispatch_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        return result


def dispatch_tool(
    task_pack: Dict[str, Any],
    tool_adapter: Any,
    output_dir: Path
) -> Dict[str, Any]:
    """
    调度工具执行（便捷函数）
    
    Args:
        task_pack: Tool task pack
        tool_adapter: Tool adapter 实例
        output_dir: 输出目录
    
    Returns:
        调度结果
    """
    dispatcher = ToolDispatcher(output_dir)
    return dispatcher.dispatch(task_pack, tool_adapter)
