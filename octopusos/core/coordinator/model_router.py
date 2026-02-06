"""Model Router - Route tasks to appropriate models (v0.9.2)"""


class ModelRouter:
    """Select models for reasoning tasks and record decisions"""
    
    def __init__(self, policy: dict):
        self.policy = policy
        self.budget_used = 0.0
        self.max_budget = policy.get("budgets", {}).get("max_cost_usd", 10.0)
    
    def select_model(self, task_type: str, context: dict) -> dict:
        """
        Select model for a task
        
        Returns:
            ModelDecision
        """
        # Simplified selection logic
        data_sensitivity = context.get("data_sensitivity", "internal")
        
        if data_sensitivity == "confidential":
            model = "local_model"
            cost = 0.0
        else:
            model = "claude-3-sonnet"
            cost = 1.0
        
        return {
            "decision_id": f"model_decision_{task_type}",
            "task_type": task_type,
            "model_selected": model,
            "timestamp": "2026-01-25T00:00:00Z",
            "reason": f"Selected {model} for {task_type}",
            "cost_estimate": cost,
            "budget_remaining": self.max_budget - self.budget_used - cost,
            "data_sensitivity": data_sensitivity,
            "fallback_available": True
        }
    
    def check_budget(self, estimated_cost: float) -> bool:
        """Check if within budget"""
        return (self.budget_used + estimated_cost) <= self.max_budget
