"""Tool Executor - 外部工具执行适配层

封装外部工具（Claude CLI, Codex, OpenCode）的执行。
这是系统边界：允许调用外部工具 CLI。
"""

from pathlib import Path
from typing import Optional, Tuple, List
import subprocess


class ToolExecutor:
    """外部工具执行器"""
    
    @staticmethod
    def execute_command(
        command: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """
        执行外部命令
        
        Args:
            command: 命令列表
            cwd: 工作目录
            timeout: 超时时间（秒）
            capture_output: 是否捕获输出
        
        Returns:
            (returncode, stdout, stderr)
        
        Raises:
            subprocess.TimeoutExpired: 超时
        """
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=capture_output,
            text=True
        )
        
        return result.returncode, result.stdout, result.stderr
    
    @staticmethod
    def check_tool_available(tool_name: str) -> bool:
        """
        检查工具是否Available
        
        Args:
            tool_name: 工具名称（如 "claude", "codex"）
        
        Returns:
            是否Available
        """
        try:
            result = subprocess.run(
                [tool_name, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
