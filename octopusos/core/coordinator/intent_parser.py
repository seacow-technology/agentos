"""Intent Parser - Parse and validate ExecutionIntent (v0.9.2)"""


class IntentParser:
    """Parse ExecutionIntent and validate registry references"""
    
    def __init__(self, registry):
        self.registry = registry
    
    def parse(self, intent: dict) -> dict:
        """
        Parse Intent and extract structured information
        
        Returns:
            ParsedIntent with workflows, agents, commands, constraints
        """
        return {
            "intent_id": intent["id"],
            "workflows": self.extract_workflows(intent),
            "agents": self.extract_agents(intent),
            "commands": self.extract_commands(intent),
            "constraints": self.extract_constraints(intent),
            "risk": intent.get("risk", {}),
            "budgets": intent.get("budgets", {})
        }
    
    def validate_registry_refs(self, intent: dict) -> tuple[bool, list]:
        """Validate all references exist in registry"""
        missing = []
        
        for workflow in intent.get("selected_workflows", []):
            if not self._check_registry("workflow", workflow["workflow_id"]):
                missing.append(f"workflow:{workflow['workflow_id']}")
        
        for agent in intent.get("selected_agents", []):
            if not self._check_registry("agent", agent["agent_id"]):
                missing.append(f"agent:{agent['agent_id']}")
        
        return len(missing) == 0, missing
    
    def _check_registry(self, content_type: str, content_id: str) -> bool:
        """Check if content exists in registry"""
        # Placeholder - would query registry
        return True
    
    def extract_workflows(self, intent: dict) -> list:
        return intent.get("selected_workflows", [])
    
    def extract_agents(self, intent: dict) -> list:
        return intent.get("selected_agents", [])
    
    def extract_commands(self, intent: dict) -> list:
        return intent.get("planned_commands", [])
    
    def extract_constraints(self, intent: dict) -> dict:
        return intent.get("constraints", {})
