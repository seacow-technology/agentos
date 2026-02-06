"""Question Governor - Govern question emission and answer processing (v0.9.2)"""


class QuestionGovernor:
    """Manage question emission and answer integration"""
    
    def __init__(self, policy: dict):
        self.policy = policy
        self.question_budget = policy.get("question_budget", 0)
        self.question_policy = policy.get("question_policy", "never")
    
    def should_ask(self, uncertainty: dict, context: dict) -> bool:
        """Decide if a question should be asked"""
        mode = self.policy.get("mode", "interactive")
        
        # RED LINE: full_auto never asks questions
        if mode == "full_auto":
            return False
        
        # Check budget
        if self.question_budget <= 0:
            return False
        
        # semi_auto: only blockers
        if mode == "semi_auto" and uncertainty.get("type") != "blocker":
            return False
        
        return True
    
    def generate_question_pack(self, uncertainties: list, graph: dict, context: dict) -> dict:
        """
        Generate QuestionPack from uncertainties
        
        Returns:
            QuestionPack
        """
        questions = []
        budget_consumed = 0
        
        for uncertainty in uncertainties:
            if self.should_ask(uncertainty, context):
                questions.append({
                    "question_id": f"q_{len(questions):03d}",
                    "type": uncertainty.get("type", "clarification"),
                    "blocking_level": uncertainty.get("blocking_level", "medium"),
                    "question_text": uncertainty.get("question_text"),
                    "context": uncertainty.get("context"),
                    "evidence_refs": uncertainty.get("evidence_refs", []),
                    "impact": {"scope": "single_action", "description": ""}
                })
                budget_consumed += 1
                
                if budget_consumed >= self.question_budget:
                    break
        
        return {
            "pack_id": f"qpack_{context['intent']['id']}",
            "schema_version": "0.9.2",
            "coordinator_run_id": context["run_id"],
            "intent_id": context["intent"]["id"],
            "questions": questions,
            "policy_constraints": {
                "execution_mode": self.policy.get("mode"),
                "question_budget": self.question_budget,
                "question_policy": self.question_policy,
                "budget_consumed": budget_consumed,
                "budget_remaining": self.question_budget - budget_consumed
            },
            "created_at": "2026-01-25T00:00:00Z"
        }
    
    def process_answer_pack(self, answers: dict, graph: dict) -> dict:
        """Integrate answers into graph"""
        # Simplified: just return graph unchanged
        return graph
