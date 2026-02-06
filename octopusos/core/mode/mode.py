"""Mode 数据类 - 最小可签版本

只保留核心：
- mode_id
- allows_commit()
- allows_diff()
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from .mode_policy import get_global_policy


class ModeViolationError(Exception):
    """
    Mode 约束违反异常（系统级，不可绕过）
    
    error_category: config（策略违反）
    """
    
    def __init__(self, message: str, mode_id: str, operation: str, error_category: str = "config"):
        super().__init__(message)
        self.mode_id = mode_id
        self.operation = operation
        self.error_category = error_category


@dataclass
class Mode:
    """
    Mode = 运行约束集合
    
    最小可签版本：只保留 3 个核心方法
    """
    mode_id: str
    metadata: Dict[str, Any]
    
    def allows_commit(self) -> bool:
        """
        是否允许 commit/diff 操作

        🔩 M1/M3 绑定点：现在由 ModePolicy 决定
        """
        policy = get_global_policy()
        return policy.check_permission(self.mode_id, "commit")
    
    def allows_diff(self) -> bool:
        """
        是否允许产生 diff (output_kind == "diff")

        🔩 M2 绑定点：现在由 ModePolicy 决定
        """
        policy = get_global_policy()
        return policy.check_permission(self.mode_id, "diff")
    
    def get_required_output_kind(self) -> str:
        """
        获取必须的 output_kind
        
        返回:
            "diff": 必须产生 diff
            "": 禁止 diff
        """
        if self.allows_diff():
            return "diff"  # 使用既有枚举值
        return ""


# 简化的 Mode Registry（内存中，无 JSON 加载）
_BUILTIN_MODES: Dict[str, Mode] = {
    "implementation": Mode(
        mode_id="implementation",
        metadata={"description": "实施模式：允许产生 diff 和 commit"}
    ),
    "design": Mode(
        mode_id="design",
        metadata={"description": "设计模式：禁止 diff"}
    ),
    "chat": Mode(
        mode_id="chat",
        metadata={"description": "聊天模式：禁止 diff"}
    ),
    "ops": Mode(
        mode_id="ops",
        metadata={"description": "运维模式：禁止 diff"}
    ),
    "test": Mode(
        mode_id="test",
        metadata={"description": "测试模式：禁止 diff"}
    ),
    "planning": Mode(
        mode_id="planning",
        metadata={"description": "规划模式：禁止 diff"}
    ),
    "debug": Mode(
        mode_id="debug",
        metadata={"description": "调试模式：禁止 diff"}
    ),
    "release": Mode(
        mode_id="release",
        metadata={"description": "发布模式：禁止 diff"}
    ),
    "experimental_open_plan": Mode(
        mode_id="experimental_open_plan",
        metadata={
            "description": "实验性开放计划模式: AI自由拆解步骤,系统验证边界",
            "experimental": True,
            "inherits_from": "planning"
        }
    ),
}


def get_mode(mode_id: str) -> Mode:
    """
    获取 Mode 实例
    
    简化版：直接从内存字典读取（避免 JSON 加载卡死）
    """
    if mode_id not in _BUILTIN_MODES:
        raise ValueError(f"Unknown mode_id: {mode_id}")
    return _BUILTIN_MODES[mode_id]
