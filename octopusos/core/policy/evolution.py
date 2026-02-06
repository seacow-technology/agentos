"""Policy evolution engine."""

from __future__ import annotations

class PolicyEvolutionEngine:
    """Manage policy evolution with safety constraints."""
    
    ALLOWED_PARAMS = {
        "max_files_per_commit": (3, 20),
        "retry_budget": (1, 5),
        "question_budget": (1, 5)
    }
    
    def evolve_policy(
        self,
        base_policy: dict,
        learning_pack: dict
    ) -> dict:
        """Evolve policy based on learning."""
        # Evolution logic with constraints
        return {
            "policy_id": "pol-v2-abc123",
            "parent_policy_id": base_policy.get("policy_id"),
            "diff": {},
            "status": "canary"
        }
    
    def validate_evolution(self, policy_diff: dict) -> tuple[bool, str]:
        """Validate policy evolution is within allowed range."""
        for param, value in policy_diff.items():
            if param not in self.ALLOWED_PARAMS:
                return False, f"Parameter {param} not allowed to evolve"
            
            min_val, max_val = self.ALLOWED_PARAMS[param]
            if not (min_val <= value <= max_val):
                return False, f"{param} out of range [{min_val}, {max_val}]"
        
        return True, "OK"
