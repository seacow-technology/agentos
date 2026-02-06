"""
Base Tool Adapter - 基础接口

所有外部工具适配器的基类

Step 3 Runtime 核心：
- health_check(): 健康检查（四态模型）
- run(): 执行外包（产出 diff）
- supports(): 声明能力（local/cloud）
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

from .types import ToolHealth, ToolTask, ToolResult, ToolCapabilities


class BaseToolAdapter(ABC):
    """外部工具适配器基类"""
    
    def __init__(self, tool_name: str):
        """
        初始化适配器
        
        Args:
            tool_name: 工具名称
        """
        self.tool_name = tool_name
    
    # ========== Step 3 Runtime 核心方法 ==========
    
    @abstractmethod
    def health_check(self) -> ToolHealth:
        """
        健康检查（Runtime 必须）
        
        四态模型：
        - connected: 工具Available
        - not_configured: CLI 不存在
        - invalid_token: 认证失败
        - unreachable: 超时/不可达
        
        Returns:
            ToolHealth
        """
        pass
    
    @abstractmethod
    def run(self, task: ToolTask, allow_mock: bool = False) -> ToolResult:
        """
        执行外包任务（Runtime 核心）
        
        权力边界红线：
        - Tool 只能产出 diff
        - Tool 不能直接写 repo
        - Tool 不能直接 commit
        
        🔩 钉子 A：Mock 模式限定
        - allow_mock 只能由 Gate 明确传入
        - 或通过 AGENTOS_GATE_MODE=1 环境变量
        
        Args:
            task: 任务描述
            allow_mock: 是否允许 Mock 模式（仅 Gate 可传入）
        
        Returns:
            ToolResult（必须包含 diff）
        """
        pass
    
    @abstractmethod
    def supports(self) -> ToolCapabilities:
        """
        声明工具能力
        
        Returns:
            ToolCapabilities
        """
        pass
    
    # ========== 原有 Pack/Dispatch/Collect 方法 ==========
    
    @abstractmethod
    def pack(self, execution_request: Dict[str, Any], repo_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将执行请求打包成工具任务包
        
        Args:
            execution_request: 执行请求
            repo_state: 仓库状态
        
        Returns:
            ToolTaskPack
        """
        pass
    
    @abstractmethod
    def dispatch(self, task_pack: Dict[str, Any], output_dir: Path) -> str:
        """
        调度工具执行任务
        
        Args:
            task_pack: 工具任务包
            output_dir: 输出目录
        
        Returns:
            调度命令（用户可手动执行或自动执行）
        """
        pass
    
    @abstractmethod
    def collect(self, task_pack_id: str, output_dir: Path) -> Dict[str, Any]:
        """
        收集工具执行结果
        
        Args:
            task_pack_id: 任务包ID
            output_dir: 工具输出目录
        
        Returns:
            ToolResultPack
        """
        pass
    
    @abstractmethod
    def verify(self, result_pack: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        验证工具执行结果
        
        Args:
            result_pack: 结果包
        
        Returns:
            (is_valid, errors)
        """
        pass
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "tool_name": self.tool_name,
            "adapter_version": "0.11.2"
        }
