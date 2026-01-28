"""Cost optimizer for tool selection based on task size and budget."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ToolPriority(Enum):
    """Tool selection priority."""
    COST = "cost"  # Minimize cost
    SPEED = "speed"  # Minimize latency
    ACCURACY = "accuracy"  # Maximize quality
    BALANCED = "balanced"  # Balance all factors


@dataclass
class ToolCostProfile:
    """Cost profile for a tool."""
    tool_type: str
    cost_per_1k_lines: float  # USD
    avg_latency_seconds: float
    quality_score: float  # 0-1
    max_task_size: Optional[int] = None  # lines of code


class CostOptimizer:
    """
    Cost optimizer for tool selection.
    
    Features:
    - Task size-based selection
    - Budget-aware selection
    - Multi-factor optimization (cost, speed, quality)
    - Dynamic fallback
    """
    
    # Default cost profiles
    DEFAULT_PROFILES = {
        "claude_cli": ToolCostProfile(
            tool_type="claude_cli",
            cost_per_1k_lines=0.50,
            avg_latency_seconds=15.0,
            quality_score=0.95
        ),
        "opencode": ToolCostProfile(
            tool_type="opencode",
            cost_per_1k_lines=0.10,
            avg_latency_seconds=30.0,
            quality_score=0.85
        ),
        "codex": ToolCostProfile(
            tool_type="codex",
            cost_per_1k_lines=1.00,
            avg_latency_seconds=10.0,
            quality_score=0.98
        )
    }
    
    def __init__(
        self,
        tool_profiles: Optional[Dict[str, ToolCostProfile]] = None,
        budget_usd: float = 10.0
    ):
        """
        Initialize cost optimizer.
        
        Args:
            tool_profiles: Tool cost profiles (default: use defaults)
            budget_usd: Budget in USD
        """
        self.tool_profiles = tool_profiles or self.DEFAULT_PROFILES
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
    
    def select_tool(
        self,
        task_size: int,
        urgency: str = "normal",
        priority: ToolPriority = ToolPriority.BALANCED
    ) -> Optional[str]:
        """
        Select best tool for task.
        
        Args:
            task_size: Task size in lines of code
            urgency: Task urgency ("low", "normal", "high")
            priority: Selection priority
        
        Returns:
            Selected tool type or None if over budget
        """
        budget_remaining = self.budget_usd - self.spent_usd
        
        if budget_remaining <= 0:
            return None
        
        # Calculate estimated cost for each tool
        candidates = []
        
        for tool_type, profile in self.tool_profiles.items():
            # Check task size limit
            if profile.max_task_size and task_size > profile.max_task_size:
                continue
            
            # Calculate cost
            estimated_cost = (task_size / 1000) * profile.cost_per_1k_lines
            
            # Skip if over budget
            if estimated_cost > budget_remaining:
                continue
            
            # Calculate score based on priority
            score = self._calculate_score(
                profile,
                task_size,
                urgency,
                priority
            )
            
            candidates.append((tool_type, score, estimated_cost))
        
        if not candidates:
            return None
        
        # Sort by score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[0][0]
    
    def _calculate_score(
        self,
        profile: ToolCostProfile,
        task_size: int,
        urgency: str,
        priority: ToolPriority
    ) -> float:
        """Calculate tool selection score."""
        estimated_cost = (task_size / 1000) * profile.cost_per_1k_lines
        
        # Normalize factors (0-1)
        cost_factor = 1.0 - min(estimated_cost / 5.0, 1.0)  # Lower cost = higher score
        speed_factor = 1.0 - min(profile.avg_latency_seconds / 60.0, 1.0)  # Lower latency = higher score
        quality_factor = profile.quality_score
        
        # Adjust weights based on urgency
        if urgency == "high":
            speed_weight = 0.5
            cost_weight = 0.2
            quality_weight = 0.3
        elif urgency == "low":
            speed_weight = 0.1
            cost_weight = 0.6
            quality_weight = 0.3
        else:  # normal
            speed_weight = 0.3
            cost_weight = 0.4
            quality_weight = 0.3
        
        # Override weights based on priority
        if priority == ToolPriority.COST:
            cost_weight, speed_weight, quality_weight = 0.7, 0.1, 0.2
        elif priority == ToolPriority.SPEED:
            cost_weight, speed_weight, quality_weight = 0.2, 0.7, 0.1
        elif priority == ToolPriority.ACCURACY:
            cost_weight, speed_weight, quality_weight = 0.2, 0.1, 0.7
        
        # Calculate weighted score
        score = (
            cost_factor * cost_weight +
            speed_factor * speed_weight +
            quality_factor * quality_weight
        )
        
        return score
    
    def estimate_cost(
        self,
        tool_type: str,
        task_size: int
    ) -> float:
        """
        Estimate cost for a tool and task size.
        
        Args:
            tool_type: Tool type identifier
            task_size: Task size in lines of code
        
        Returns:
            Estimated cost in USD
        """
        if tool_type not in self.tool_profiles:
            raise ValueError(f"Unknown tool type: {tool_type}")
        
        profile = self.tool_profiles[tool_type]
        return (task_size / 1000) * profile.cost_per_1k_lines
    
    def record_execution(
        self,
        tool_type: str,
        actual_cost: float
    ) -> None:
        """
        Record actual execution cost.
        
        Args:
            tool_type: Tool type used
            actual_cost: Actual cost incurred
        """
        self.spent_usd += actual_cost
    
    def get_budget_status(self) -> Dict:
        """Get budget status."""
        return {
            "budget_usd": self.budget_usd,
            "spent_usd": self.spent_usd,
            "remaining_usd": self.budget_usd - self.spent_usd,
            "utilization_percent": (self.spent_usd / self.budget_usd * 100)
                if self.budget_usd > 0 else 0
        }
    
    def get_recommendations(
        self,
        task_sizes: List[int]
    ) -> List[Tuple[int, str, float]]:
        """
        Get tool recommendations for multiple tasks.
        
        Args:
            task_sizes: List of task sizes
        
        Returns:
            List of (task_size, tool_type, estimated_cost) tuples
        """
        recommendations = []
        
        for task_size in task_sizes:
            tool_type = self.select_tool(task_size)
            if tool_type:
                cost = self.estimate_cost(tool_type, task_size)
                recommendations.append((task_size, tool_type, cost))
        
        return recommendations
