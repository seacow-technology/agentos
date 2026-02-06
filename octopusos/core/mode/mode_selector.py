"""ModeSelector - Intent to Mode mapping

规则驱动的自然语言意图识别，将用户输入映射到合适的 Mode Pipeline
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List
import re


@dataclass
class ModeSelection:
    """Mode 选择结果
    
    Attributes:
        primary_mode: 主要模式 ID
        pipeline: 模式执行序列（按顺序）
        reason: 选择此 pipeline 的原因（用于审计）
    """
    primary_mode: str
    pipeline: List[str]
    reason: str


class ModeSelector:
    """Intent → Mode 映射器
    
    基于规则的简单意图识别：
    - 开发类需求 → planning + implementation
    - 只读需求 → chat
    - 修复类需求 → debug + implementation
    """
    
    # 规则定义：关键词模式 → (primary_mode, pipeline, reason)
    RULES = [
        # 开发类需求（创建新东西）
        {
            "patterns": [
                r"(需要|想要|创建|实现|开发|构建|生成).*(页面|网站|应用|app|site|page|landing|dashboard)",
                r"(build|create|implement|develop|generate).*(page|site|app|landing|website|dashboard)",
                r"I need.*(page|site|app|landing|dashboard)",
            ],
            "primary_mode": "planning",
            "pipeline": ["planning", "implementation"],
            "reason": "Development task detected: creating new page/site/app"
        },
        # 修复类需求（调试 bug）
        {
            "patterns": [
                r"(修复|调试|解决).*(bug|问题|错误|异常)",
                r"(fix|debug|resolve|solve).*(bug|issue|error|problem)",
            ],
            "primary_mode": "debug",
            "pipeline": ["debug", "implementation"],
            "reason": "Fix task detected: debugging and fixing issues"
        },
        # 分析/查看类需求（只读）
        {
            "patterns": [
                r"(分析|查看|解释|说明|展示|显示)",
                r"(analyze|explain|show|display|view|what is|how does)",
            ],
            "primary_mode": "chat",
            "pipeline": ["chat"],
            "reason": "Read-only task detected: analysis or explanation"
        },
        # 运维类需求
        {
            "patterns": [
                r"(部署|发布|上线|回滚|监控)",
                r"(deploy|release|rollback|monitor)",
            ],
            "primary_mode": "ops",
            "pipeline": ["ops"],
            "reason": "Operations task detected"
        },
        # 测试类需求
        {
            "patterns": [
                r"(测试|验证|检查).*(功能|代码|单元|集成)",
                r"(test|verify|check).*(function|code|unit|integration)",
            ],
            "primary_mode": "test",
            "pipeline": ["test", "implementation"],
            "reason": "Testing task detected"
        },
    ]
    
    # 默认规则（匹配不到任何规则时使用）
    DEFAULT_SELECTION = ModeSelection(
        primary_mode="chat",
        pipeline=["chat"],
        reason="No specific pattern matched, defaulting to chat mode"
    )
    
    def select_mode(self, nl_input: str) -> ModeSelection:
        """根据自然语言输入选择 Mode Pipeline
        
        Args:
            nl_input: 用户的自然语言输入
            
        Returns:
            ModeSelection: 包含 primary_mode, pipeline, reason
            
        Example:
            >>> selector = ModeSelector()
            >>> result = selector.select_mode("I need a demo landing page")
            >>> result.pipeline
            ['planning', 'implementation']
        """
        nl_lower = nl_input.lower().strip()
        
        # 遍历规则，找到第一个匹配的
        for rule in self.RULES:
            for pattern in rule["patterns"]:
                if re.search(pattern, nl_lower, re.IGNORECASE):
                    return ModeSelection(
                        primary_mode=rule["primary_mode"],
                        pipeline=rule["pipeline"],
                        reason=rule["reason"]
                    )
        
        # 没有匹配到任何规则，返回默认
        return self.DEFAULT_SELECTION
    
    def get_supported_patterns(self) -> List[str]:
        """获取所有支持的模式类型（用于文档生成）
        
        Returns:
            List[str]: 模式类型列表
        """
        patterns = []
        for rule in self.RULES:
            patterns.append(f"{rule['primary_mode']}: {rule['reason']}")
        return patterns
