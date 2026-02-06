"""Rule engine for validation"""

import json
from pathlib import Path
from typing import Any


class RuleEngine:
    """Rule engine for validating AgentSpec against FactPack"""
    
    def __init__(self):
        self.system_rules = self._load_system_rules()
    
    def _load_system_rules(self) -> list[dict[str, Any]]:
        """Load system-level rules"""
        rules = []
        rules_dir = Path("rules/system")
        
        if not rules_dir.exists():
            return rules
        
        for rule_file in rules_dir.glob("*.json"):
            try:
                with open(rule_file, encoding="utf-8") as f:
                    rule = json.load(f)
                    rules.append(rule)
            except Exception:
                pass
        
        return rules
    
    def validate(
        self,
        agent_spec: dict[str, Any],
        factpack: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Validate AgentSpec against FactPack using rules
        
        Returns:
            (is_valid, errors): Tuple of validation result and error messages
        """
        errors = []
        
        for rule in self.system_rules:
            rule_errors = self._check_rule(rule, agent_spec, factpack)
            errors.extend(rule_errors)
        
        return len(errors) == 0, errors
    
    def _check_rule(
        self,
        rule: dict[str, Any],
        agent_spec: dict[str, Any],
        factpack: dict[str, Any]
    ) -> list[str]:
        """Check a single rule"""
        check_type = rule.get("check_type")
        
        if check_type == "command_existence":
            return self._check_command_existence(rule, agent_spec, factpack)
        elif check_type == "path_validation":
            return self._check_path_validation(rule, agent_spec, factpack)
        
        return []
    
    def _check_command_existence(
        self,
        rule: dict[str, Any],
        agent_spec: dict[str, Any],
        factpack: dict[str, Any]
    ) -> list[str]:
        """Check that all commands exist in FactPack"""
        errors = []
        
        spec_commands = set(agent_spec.get("commands", {}).keys())
        factpack_commands = set(factpack.get("commands", {}).keys())
        
        fabricated = spec_commands - factpack_commands
        if fabricated:
            severity = rule.get("severity", "error")
            errors.append(
                f"[{severity}] {rule['rule_id']}: "
                f"Commands not in FactPack: {fabricated}"
            )
        
        return errors
    
    def _check_path_validation(
        self,
        rule: dict[str, Any],
        agent_spec: dict[str, Any],
        factpack: dict[str, Any]
    ) -> list[str]:
        """Check that paths are reasonable"""
        # Simplified: just warn if paths look suspicious
        errors = []
        allowed_paths = agent_spec.get("allowed_paths", [])
        
        suspicious = [
            path for path in allowed_paths
            if ".." in path or path.startswith("/")
        ]
        
        if suspicious:
            severity = rule.get("severity", "warning")
            errors.append(
                f"[{severity}] {rule['rule_id']}: "
                f"Suspicious paths: {suspicious}"
            )
        
        return errors
