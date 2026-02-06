"""Rules Adjudicator - Adjudicate rules against planned actions (v0.9.2)"""


class RulesAdjudicator:
    """Adjudicate rules against planned actions"""
    
    def __init__(self, registry):
        self.registry = registry
    
    def adjudicate_all(self, commands: list, context: dict) -> list:
        """
        Adjudicate all planned commands
        
        Returns:
            List of RuleDecisions
        """
        decisions = []
        
        for command in commands:
            decision = self.adjudicate(command, [], context)
            decisions.append(decision)
        
        return decisions
    
    def adjudicate(self, command: dict, rules: list, evidence: dict) -> dict:
        """
        Adjudicate a single command against rules
        
        Returns:
            RuleDecision (allow/deny/warn/require_review)
        """
        # Default: allow low-risk read operations
        effects = command.get("effects", [])
        risk_level = command.get("risk_level", "low")
        
        if "write" in effects or "deploy" in effects:
            decision = "require_review" if risk_level in ["high", "critical"] else "allow"
        else:
            decision = "allow"
        
        return {
            "command_id": command.get("command_id"),
            "decision": decision,
            "evidence_refs": command.get("evidence_refs", []),
            "reason": f"Risk level: {risk_level}, Effects: {effects}"
        }
    
    def assess_risk(self, decisions: list) -> dict:
        """
        Aggregate rule decisions into risk assessment
        
        Returns:
            RiskAssessment
        """
        # Count require_review decisions
        review_count = sum(1 for d in decisions if d.get("decision") == "require_review")
        
        if review_count > 3:
            overall_risk = "high"
        elif review_count > 0:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        return {
            "overall_risk": overall_risk,
            "factors": [f"{review_count} actions require review"]
        }
