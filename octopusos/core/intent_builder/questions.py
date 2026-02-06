"""Question Generator - Generate QuestionPack based on policy and ambiguities.

RED LINE: full_auto => question_budget=0, no questions.
"""

from typing import List, Dict, Optional


class QuestionGenerator:
    """Generate questions based on ambiguities and execution policy.
    
    RED LINE: full_auto mode must generate ZERO questions.
    """
    
    def __init__(self):
        """Initialize question generator."""
        pass
    
    def generate_questions(
        self,
        ambiguities: List[dict],
        policy: str,
        max_budget: int,
        nl_request: dict,
        parsed_nl: dict
    ) -> Optional[dict]:
        """Generate QuestionPack based on ambiguities and policy.
        
        Args:
            ambiguities: List of detected ambiguities
            policy: Execution policy (full_auto/semi_auto/interactive)
            max_budget: Maximum question budget from policy
            nl_request: Original NL request
            parsed_nl: Parsed NL components
        
        Returns:
            QuestionPack dict or None if no questions needed
        """
        # RED LINE: full_auto => NO questions
        if policy == "full_auto":
            return None
        
        # Filter ambiguities based on policy
        filtered_ambiguities = self._filter_ambiguities_by_policy(ambiguities, policy)
        
        if not filtered_ambiguities:
            return None
        
        # Generate questions
        questions = []
        budget_used = 0
        
        for amb in filtered_ambiguities:
            if budget_used >= max_budget:
                break
            
            question = self._create_question_from_ambiguity(amb, nl_request, parsed_nl)
            if question:
                questions.append(question)
                budget_used += 1
        
        if not questions:
            return None
        
        # Determine question policy
        question_policy = self._determine_question_policy(policy)
        
        return {
            "questions": questions,
            "budget_used": budget_used,
            "policy": question_policy
        }
    
    def _filter_ambiguities_by_policy(
        self,
        ambiguities: List[dict],
        policy: str
    ) -> List[dict]:
        """Filter ambiguities based on execution policy.
        
        Args:
            ambiguities: All detected ambiguities
            policy: Execution policy
        
        Returns:
            Filtered list of ambiguities
        """
        if policy == "full_auto":
            return []
        
        if policy == "semi_auto":
            # Only blockers and high severity
            return [
                amb for amb in ambiguities
                if amb.get("severity") in ["high", "critical"]
            ]
        
        if policy == "interactive":
            # All ambiguities
            return ambiguities
        
        return []
    
    def _create_question_from_ambiguity(
        self,
        ambiguity: dict,
        nl_request: dict,
        parsed_nl: dict
    ) -> Optional[dict]:
        """Create a question from an ambiguity.
        
        Args:
            ambiguity: Ambiguity dict
            nl_request: Original NL request
            parsed_nl: Parsed NL components
        
        Returns:
            Question dict or None
        """
        amb_type = ambiguity.get("type", "unknown")
        amb_desc = ambiguity.get("description", "")
        amb_severity = ambiguity.get("severity", "medium")
        
        # Map severity to blocking level
        blocking_level_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }
        blocking_level = blocking_level_map.get(amb_severity, "medium")
        
        # Generate question based on type
        if amb_type == "missing_actions":
            return {
                "question_id": "q_missing_actions",
                "type": "blocker",
                "blocking_level": "critical",
                "question_text": "No clear actions were detected in your input. Could you clarify what specific tasks or changes should be performed?",
                "context": f"The input text '{nl_request['input_text'][:100]}...' does not contain clear action verbs or task descriptions.",
                "evidence_refs": [f"nl_input:0:{len(nl_request['input_text'])}"],
                "default_strategy": "Generate a minimal documentation-only intent as fallback"
            }
        
        elif amb_type == "vague_specification":
            return {
                "question_id": "q_vague_spec",
                "type": "clarification",
                "blocking_level": blocking_level,
                "question_text": f"Your input contains vague terms ({amb_desc}). Could you provide more specific requirements?",
                "context": f"Ambiguity detected: {amb_desc}",
                "evidence_refs": [f"nl_input:0:100"],
                "default_strategy": "Proceed with best-effort interpretation"
            }
        
        elif amb_type == "too_many_actions":
            actions = parsed_nl.get("actions", [])
            return {
                "question_id": "q_too_many_actions",
                "type": "optimization",
                "blocking_level": "medium",
                "question_text": f"Your input specifies {len(actions)} actions. Should these be prioritized or split into multiple phases?",
                "context": f"Large number of actions detected: {len(actions)}",
                "evidence_refs": [f"nl_input:0:{len(nl_request['input_text'])}"],
                "default_strategy": "Process all actions in a single phase",
                "suggested_answers": [
                    {
                        "answer_text": "Process all in one phase",
                        "rationale": "Complete all actions together"
                    },
                    {
                        "answer_text": "Split into multiple phases",
                        "rationale": "Break down into manageable chunks"
                    }
                ]
            }
        
        # Default question for unknown types
        return {
            "question_id": f"q_{amb_type}",
            "type": "clarification",
            "blocking_level": blocking_level,
            "question_text": f"Clarification needed: {amb_desc}",
            "context": f"Ambiguity type: {amb_type}",
            "evidence_refs": [f"nl_input:0:100"]
        }
    
    def _determine_question_policy(self, policy: str) -> str:
        """Determine question policy string.
        
        Args:
            policy: Execution policy
        
        Returns:
            Question policy string
        """
        policy_map = {
            "full_auto": "never",
            "semi_auto": "blockers_only",
            "interactive": "conceptual_only"
        }
        return policy_map.get(policy, "blockers_only")
    
    def validate_question_pack(self, question_pack: Optional[dict], policy: str) -> bool:
        """Validate question pack against policy.
        
        RED LINE: full_auto must have zero questions.
        
        Args:
            question_pack: QuestionPack dict
            policy: Execution policy
        
        Returns:
            True if valid, False otherwise
        """
        if policy == "full_auto":
            # Must be None or empty
            if question_pack is None:
                return True
            if question_pack.get("questions") == []:
                return True
            return False
        
        if question_pack is None:
            return True
        
        # Check budget
        budget_used = question_pack.get("budget_used", 0)
        questions_count = len(question_pack.get("questions", []))
        
        if budget_used != questions_count:
            return False
        
        # Check policy
        q_policy = question_pack.get("policy", "")
        if not q_policy:
            return False
        
        return True
