"""Multi-round question-answer coordinator for dynamic questioning."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import hashlib

from octopusos.core.answers.llm_suggester import LLMSuggester
from octopusos.core.time import utc_now_iso



class MultiRoundCoordinator:
    """
    Coordinator for multi-round AnswerPack creation.
    
    Supports:
    - Dynamic question generation based on previous answers
    - Depth tracking (prevent infinite loops)
    - Dependency tracking between rounds
    """
    
    MAX_DEPTH = 3  # Red line: prevent infinite loops
    
    def __init__(
        self,
        initial_question_pack: Dict,
        llm_suggester: Optional[LLMSuggester] = None,
        max_depth: int = MAX_DEPTH
    ):
        """
        Initialize multi-round coordinator.
        
        Args:
            initial_question_pack: Initial QuestionPack
            llm_suggester: LLM suggester for generating follow-up questions
            max_depth: Maximum depth of question rounds (default 3)
        """
        self.initial_question_pack = initial_question_pack
        self.llm_suggester = llm_suggester
        self.max_depth = min(max_depth, self.MAX_DEPTH)
        
        # Track rounds
        self.rounds: List[Dict] = []
        self.current_depth = 0
        
        # Track dependencies
        self.question_dependencies: Dict[str, List[str]] = {}
    
    def start_round(self, question_pack: Dict) -> str:
        """
        Start a new round with a QuestionPack.
        
        Args:
            question_pack: QuestionPack for this round
        
        Returns:
            round_id
        """
        if self.current_depth >= self.max_depth:
            raise ValueError(
                f"Maximum depth ({self.max_depth}) reached. "
                "Cannot start new round to prevent infinite loops."
            )
        
        round_id = self._generate_round_id(question_pack)
        
        round_data = {
            "round_id": round_id,
            "depth": self.current_depth,
            "question_pack": question_pack,
            "answer_pack": None,
            "started_at": utc_now_iso(),
            "completed_at": None,
            "triggered_by": None  # question_id that triggered this round
        }
        
        self.rounds.append(round_data)
        self.current_depth += 1
        
        return round_id
    
    def complete_round(self, round_id: str, answer_pack: Dict) -> None:
        """
        Complete a round with an AnswerPack.
        
        Args:
            round_id: Round identifier
            answer_pack: AnswerPack for this round
        """
        round_data = self._get_round(round_id)
        if not round_data:
            raise ValueError(f"Round not found: {round_id}")
        
        round_data["answer_pack"] = answer_pack
        round_data["completed_at"] = utc_now_iso()
    
    def should_generate_followup(self, answer_pack: Dict) -> Tuple[bool, str]:
        """
        Determine if follow-up questions should be generated.
        
        Args:
            answer_pack: Completed AnswerPack
        
        Returns:
            Tuple of (should_generate, reason)
        """
        # Check depth limit
        if self.current_depth >= self.max_depth:
            return False, f"Maximum depth ({self.max_depth}) reached"
        
        # Check execution mode
        question_pack = self.rounds[-1]["question_pack"] if self.rounds else {}
        policy = question_pack.get("policy_constraints", {})
        execution_mode = policy.get("execution_mode", "")
        
        if execution_mode == "full_auto":
            return False, "full_auto mode does not allow follow-up questions"
        
        # Check question budget
        budget_remaining = policy.get("budget_remaining", 0)
        if budget_remaining <= 0:
            return False, "Question budget exhausted"
        
        # Check if any answers indicate need for clarification
        for answer in answer_pack.get("answers", []):
            answer_text = answer.get("answer_text", "").lower()
            
            # Look for uncertainty indicators
            if any(phrase in answer_text for phrase in [
                "not sure",
                "unclear",
                "need clarification",
                "depends on",
                "could be",
                "either"
            ]):
                return True, "Uncertainty detected in answers"
        
        return False, "No follow-up needed"
    
    def generate_followup_questions(
        self,
        answer_pack: Dict,
        triggered_by_question_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Generate follow-up questions based on previous answers.
        
        Args:
            answer_pack: Completed AnswerPack
            triggered_by_question_id: Question that triggered follow-up
        
        Returns:
            New QuestionPack if follow-up needed, None otherwise
        """
        if not self.llm_suggester:
            return None
        
        should_generate, reason = self.should_generate_followup(answer_pack)
        if not should_generate:
            return None
        
        # Build context from previous rounds
        context = self._build_context()
        
        # Generate follow-up questions using LLM
        followup_pack = self._llm_generate_followup(
            answer_pack=answer_pack,
            context=context,
            triggered_by=triggered_by_question_id
        )
        
        if followup_pack:
            # Track dependency
            if triggered_by_question_id:
                followup_questions = [
                    q["question_id"] 
                    for q in followup_pack.get("questions", [])
                ]
                self.question_dependencies[triggered_by_question_id] = followup_questions
        
        return followup_pack
    
    def get_full_context(self) -> Dict:
        """
        Get full context from all rounds.
        
        Returns:
            Dictionary with all questions and answers
        """
        context = {
            "total_rounds": len(self.rounds),
            "current_depth": self.current_depth,
            "max_depth": self.max_depth,
            "rounds": []
        }
        
        for round_data in self.rounds:
            context["rounds"].append({
                "round_id": round_data["round_id"],
                "depth": round_data["depth"],
                "questions": round_data["question_pack"].get("questions", []),
                "answers": round_data["answer_pack"].get("answers", []) 
                    if round_data["answer_pack"] else [],
                "triggered_by": round_data["triggered_by"]
            })
        
        return context
    
    def get_final_answer_pack(self) -> Dict:
        """
        Merge all rounds into a single consolidated AnswerPack.
        
        Returns:
            Consolidated AnswerPack with all answers
        """
        if not self.rounds or not self.rounds[0].get("answer_pack"):
            raise ValueError("No completed rounds")
        
        # Start with first round's answer pack
        base_pack = self.rounds[0]["answer_pack"]
        
        consolidated = {
            "answer_pack_id": f"multi_{base_pack.get('answer_pack_id', 'unknown')}",
            "schema_version": "0.12.0",  # Upgraded for multi-round
            "question_pack_id": self.initial_question_pack.get("pack_id"),
            "intent_id": self.initial_question_pack.get("intent_id"),
            "answers": [],
            "provided_at": utc_now_iso(),
            "lineage": base_pack.get("lineage", {}),
            "metadata": {
                "multi_round": True,
                "total_rounds": len(self.rounds),
                "max_depth_reached": self.current_depth >= self.max_depth,
                "question_dependencies": self.question_dependencies
            }
        }
        
        # Collect all answers
        for round_data in self.rounds:
            if round_data["answer_pack"]:
                consolidated["answers"].extend(
                    round_data["answer_pack"].get("answers", [])
                )
        
        # Add completeness
        consolidated["completeness"] = {
            "total_questions": sum(
                len(r["question_pack"].get("questions", [])) 
                for r in self.rounds
            ),
            "answered": len(consolidated["answers"]),
            "unanswered_question_ids": [],
            "fallback_used": False
        }
        
        # Compute checksum
        from octopusos.core.answers import AnswerStore
        store = AnswerStore()
        consolidated["checksum"] = store.compute_checksum(consolidated)
        
        return consolidated
    
    def _generate_round_id(self, question_pack: Dict) -> str:
        """Generate unique round ID."""
        pack_id = question_pack.get("pack_id", "unknown")
        timestamp = datetime.now().isoformat()
        hash_input = f"{pack_id}:{self.current_depth}:{timestamp}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"round_{self.current_depth}_{hash_val}"
    
    def _get_round(self, round_id: str) -> Optional[Dict]:
        """Get round data by ID."""
        for round_data in self.rounds:
            if round_data["round_id"] == round_id:
                return round_data
        return None
    
    def _build_context(self) -> Dict:
        """Build context from previous rounds."""
        context = {
            "previous_questions": [],
            "previous_answers": [],
            "execution_mode": None,
            "question_budget_remaining": 0
        }
        
        for round_data in self.rounds:
            qpack = round_data["question_pack"]
            apack = round_data["answer_pack"]
            
            context["previous_questions"].extend(
                qpack.get("questions", [])
            )
            
            if apack:
                context["previous_answers"].extend(
                    apack.get("answers", [])
                )
            
            # Get latest policy
            policy = qpack.get("policy_constraints", {})
            if not context["execution_mode"]:
                context["execution_mode"] = policy.get("execution_mode")
            context["question_budget_remaining"] = policy.get("budget_remaining", 0)
        
        return context
    
    def _llm_generate_followup(
        self,
        answer_pack: Dict,
        context: Dict,
        triggered_by: Optional[str] = None
    ) -> Optional[Dict]:
        """Use LLM to generate follow-up questions."""
        if not self.llm_suggester:
            return None
        
        # Build prompt for follow-up generation
        prompt = self._build_followup_prompt(answer_pack, context, triggered_by)
        
        try:
            # Use LLM to generate questions
            # Note: This is a simplified version - real implementation would use
            # structured output or function calling
            response = self._llm_call_followup(prompt)
            
            if not response or not response.get("questions"):
                return None
            
            # Build new QuestionPack
            followup_pack = {
                "pack_id": f"qpack_followup_{self.current_depth}_{hashlib.sha256(str(response).encode()).hexdigest()[:8]}",
                "schema_version": "0.9.2",
                "coordinator_run_id": self.initial_question_pack.get("coordinator_run_id"),
                "intent_id": self.initial_question_pack.get("intent_id"),
                "questions": response["questions"],
                "policy_constraints": context.get("policy_constraints", {}),
                "created_at": utc_now_iso(),
                "metadata": {
                    "generated_by": "multi_round_coordinator",
                    "triggered_by": triggered_by,
                    "depth": self.current_depth
                }
            }
            
            return followup_pack
            
        except Exception as e:
            print(f"Follow-up generation error: {e}")
            return None
    
    def _build_followup_prompt(
        self,
        answer_pack: Dict,
        context: Dict,
        triggered_by: Optional[str] = None
    ) -> str:
        """Build prompt for LLM follow-up generation."""
        prompt = """Based on the previous questions and answers, generate follow-up questions that:
1. Clarify unclear or uncertain answers
2. Explore dependencies or implications
3. Resolve conflicts or inconsistencies

Previous questions and answers:
"""
        
        for i, prev_answer in enumerate(context.get("previous_answers", []), 1):
            q_id = prev_answer.get("question_id")
            # Find matching question
            prev_q = next(
                (q for q in context.get("previous_questions", [])
                 if q.get("question_id") == q_id),
                None
            )
            
            if prev_q:
                prompt += f"\n{i}. Q: {prev_q.get('question_text')}\n"
                prompt += f"   A: {prev_answer.get('answer_text')}\n"
        
        prompt += f"""

Current depth: {self.current_depth}
Max depth: {self.max_depth}
Budget remaining: {context.get('question_budget_remaining', 0)}

Generate 1-3 follow-up questions in JSON format:
{{
  "questions": [
    {{
      "question_id": "q_followup_1",
      "type": "clarification",
      "blocking_level": "medium",
      "question_text": "...",
      "context": "...",
      "evidence_refs": ["previous_answer_ref"],
      "impact": {{
        "scope": "single_action",
        "description": "..."
      }}
    }}
  ]
}}
"""
        
        return prompt
    
    def _llm_call_followup(self, prompt: str) -> Optional[Dict]:
        """Call LLM to generate follow-up questions."""
        try:
            import json
            # Use OpenAI client from suggester
            if hasattr(self.llm_suggester, 'client') and hasattr(self.llm_suggester.client, 'chat'):
                response = self.llm_suggester.client.chat.completions.create(
                    model=self.llm_suggester.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at generating clarifying questions "
                                       "for AI agent orchestration. Generate thoughtful follow-up "
                                       "questions based on previous answers."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )

                # Best-effort usage tracking
                try:
                    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                    usage = getattr(response, "usage", None)
                    record_llm_usage_event_best_effort(
                        LLMUsageEvent(
                            provider="openai",
                            model=getattr(self.llm_suggester, "model", None),
                            operation="answers.followup_questions",
                            prompt_tokens=getattr(usage, "prompt_tokens", None),
                            completion_tokens=getattr(usage, "completion_tokens", None),
                            total_tokens=getattr(usage, "total_tokens", None),
                            confidence="HIGH" if usage is not None else "LOW",
                        )
                    )
                except Exception:
                    pass
                
                content = response.choices[0].message.content
                return json.loads(content)
            else:
                return None
            
        except Exception as e:
            print(f"LLM follow-up call error: {e}")
            return None
