"""
Provenance Models

能力溯源数据模型，提供"法庭级别"的可追溯性。
"""

import os
import platform
import sys
from datetime import datetime
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field


class TrustTier(str, Enum):
    """
    Trust Tier for capability sources

    信任层级，从高到低：
    - T0: 系统内置能力（最高信任）
    - T1: 经过审核的扩展（高信任）
    - T2: 用户安装的扩展（中信任）
    - T3: 外部 MCP 服务器（需谨慎）
    """
    T0 = "T0"  # System built-in (highest trust)
    T1 = "T1"  # Vetted extensions (high trust)
    T2 = "T2"  # User-installed extensions (medium trust)
    T3 = "T3"  # External MCP servers (needs caution)


class ExecutionEnv(BaseModel):
    """执行环境信息"""
    host: str = Field(description="主机名")
    pid: int = Field(description="进程 ID")
    container_id: Optional[str] = Field(None, description="容器 ID（如果在容器中）")
    python_version: str = Field(description="Python 版本")
    agentos_version: str = Field(description="AgentOS 版本")
    platform: str = Field(description="平台信息")
    cwd: str = Field(description="当前工作目录")


class ProvenanceStamp(BaseModel):
    """
    溯源戳

    记录能力调用的完整溯源信息，确保结果可追溯。
    """
    capability_id: str = Field(description="能力 ID")
    tool_id: str = Field(description="工具 ID")
    capability_type: Literal["extension", "mcp"] = Field(
        description="能力类型"
    )
    source_id: str = Field(description="来源 ID（extension_id 或 mcp_server_id）")
    source_version: Optional[str] = Field(None, description="来源版本")
    execution_env: ExecutionEnv = Field(description="执行环境")
    trust_tier: str = Field(description="信任层级")
    timestamp: datetime = Field(description="时间戳")
    invocation_id: str = Field(description="调用 ID")

    # Optional: 额外的上下文
    task_id: Optional[str] = Field(None, description="任务 ID")
    project_id: Optional[str] = Field(None, description="项目 ID")
    spec_hash: Optional[str] = Field(None, description="规范哈希")


def get_current_env() -> ExecutionEnv:
    """
    获取当前执行环境信息

    Returns:
        ExecutionEnv: 当前环境
    """
    # 尝试获取容器 ID
    container_id = None
    try:
        with open('/proc/self/cgroup', 'r') as f:
            for line in f:
                if 'docker' in line or 'containerd' in line:
                    # 简化的容器 ID 提取
                    parts = line.strip().split('/')
                    if len(parts) > 2:
                        container_id = parts[-1][:12]
                        break
    except:
        pass

    # 获取 AgentOS 版本
    agentos_version = "unknown"
    try:
        from agentos import __version__
        agentos_version = __version__
    except:
        pass

    return ExecutionEnv(
        host=platform.node(),
        pid=os.getpid(),
        container_id=container_id,
        python_version=sys.version.split()[0],
        agentos_version=agentos_version,
        platform=platform.platform(),
        cwd=os.getcwd()
    )
