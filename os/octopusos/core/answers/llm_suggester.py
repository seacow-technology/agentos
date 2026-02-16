"""LLM-powered answer suggestion engine supporting OpenAI and Anthropic."""

import os
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from octopusos.core.time import utc_now_iso


try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


class LLMSuggester:
    """Generate answer suggestions using LLM (OpenAI or Anthropic)."""
    
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_suggestions: int = 3
    ):
        """
        Initialize LLM suggester.
        
        Args:
            provider: "openai" or "anthropic"
            model: Model name (defaults to gpt-4 or claude-3-sonnet)
            api_key: API key (falls back to environment variables)
            temperature: Sampling temperature (0-1)
            max_suggestions: Maximum number of suggestions per question
        """
        self.provider = provider.lower()
        self.temperature = temperature
        self.max_suggestions = max_suggestions
        
        # Initialize client based on provider
        if self.provider == "openai":
            if OpenAI is None:
                raise ImportError("OpenAI package not installed: pip install openai")
            
            self.model = model or "gpt-4-turbo-preview"
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key not found")
            
            self.client = OpenAI(api_key=self.api_key)
            
        elif self.provider == "anthropic":
            if Anthropic is None:
                raise ImportError("Anthropic package not installed: pip install anthropic")
            
            self.model = model or "claude-3-sonnet-20240229"
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("Anthropic API key not found")
            
            self.client = Anthropic(api_key=self.api_key)
            
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def suggest_answers(
        self,
        question: Dict,
        question_pack: Dict,
        context: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Generate answer suggestions for a question.
        
        Args:
            question: Question dictionary from QuestionPack
            question_pack: Full QuestionPack for additional context
            context: Optional additional context (factpack, memory, etc.)
        
        Returns:
            List of suggestion dictionaries with keys:
            - answer_text: Suggested answer
            - rationale: Why this answer is appropriate
            - evidence_refs: Suggested evidence references
            - source: LLM provider and model
            - prompt_hash: Hash of the prompt used
            - confidence: Estimated confidence (0-1)
            - generated_at: Timestamp
        """
        # Build prompt
        prompt = self._build_prompt(question, question_pack, context)
        prompt_hash = self._hash_prompt(prompt)
        
        # Generate suggestions
        if self.provider == "openai":
            suggestions = self._suggest_openai(prompt)
        elif self.provider == "anthropic":
            suggestions = self._suggest_anthropic(prompt)
        else:
            suggestions = []
        
        # Enrich with metadata
        for sugg in suggestions:
            sugg["source"] = f"{self.provider}/{self.model}"
            sugg["prompt_hash"] = prompt_hash
            sugg["generated_at"] = utc_now_iso()
        
        return suggestions
    
    def _build_prompt(
        self,
        question: Dict,
        question_pack: Dict,
        context: Optional[Dict] = None
    ) -> str:
        """Build prompt for LLM."""
        question_text = question.get("question_text", "")
        question_context = question.get("context", "")
        question_type = question.get("type", "")
        blocking_level = question.get("blocking_level", "")
        evidence_refs = question.get("evidence_refs", [])
        
        # Start with base prompt
        prompt = f"""You are helping a human answer questions for an AI agent orchestration system.

Question Type: {question_type}
Blocking Level: {blocking_level}

Question:
{question_text}

Context:
{question_context}

Evidence that triggered this question:
{', '.join(evidence_refs)}
"""
        
        # Add suggested answers if available
        suggested_answers = question.get("suggested_answers", [])
        if suggested_answers:
            prompt += "\n\nExisting suggested answers:\n"
            for i, sugg in enumerate(suggested_answers, 1):
                prompt += f"{i}. {sugg.get('answer_text')}\n"
                prompt += f"   Rationale: {sugg.get('rationale')}\n"
        
        # Add additional context if provided
        if context:
            if "factpack" in context:
                prompt += f"\n\nProject Facts:\n{context['factpack']}"
            if "memory" in context:
                prompt += f"\n\nRelevant Memories:\n{context['memory']}"
        
        # Add execution mode context
        policy = question_pack.get("policy_constraints", {})
        execution_mode = policy.get("execution_mode", "unknown")
        question_budget = policy.get("question_budget", 0)
        
        prompt += f"""

Execution Mode: {execution_mode}
Question Budget Remaining: {policy.get('budget_remaining', 0)} / {question_budget}

Please provide {self.max_suggestions} high-quality answer suggestions. For each suggestion:
1. Provide a clear, actionable answer
2. Explain the rationale for this answer
3. Suggest evidence references that support the answer
4. Estimate confidence level (0-1)

Format your response as JSON array:
[
  {{
    "answer_text": "...",
    "rationale": "...",
    "evidence_refs": ["ref1", "ref2"],
    "confidence": 0.8
  }},
  ...
]
"""
        
        return prompt
    
    def _suggest_openai(self, prompt: str) -> List[Dict]:
        """Generate suggestions using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at helping humans make informed decisions "
                                   "for AI agent orchestration systems. Provide thoughtful, "
                                   "evidence-based suggestions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
                max_tokens=2000
            )

            # Best-effort usage tracking
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                usage = getattr(response, "usage", None)
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="openai",
                        model=self.model,
                        operation="answers.suggest",
                        prompt_tokens=getattr(usage, "prompt_tokens", None),
                        completion_tokens=getattr(usage, "completion_tokens", None),
                        total_tokens=getattr(usage, "total_tokens", None),
                        confidence="HIGH" if usage is not None else "LOW",
                        usage_raw={
                            "finish_reason": getattr(getattr(response, "choices", [None])[0], "finish_reason", None),
                        },
                        metadata={"max_suggestions": self.max_suggestions},
                    )
                )
            except Exception:
                pass
            
            import json
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Handle both array and object with "suggestions" key
            if isinstance(result, list):
                return result[:self.max_suggestions]
            elif "suggestions" in result:
                return result["suggestions"][:self.max_suggestions]
            else:
                return []
            
        except Exception as e:
            print(f"OpenAI error: {e}")
            return []
    
    def _suggest_anthropic(self, prompt: str) -> List[Dict]:
        """Generate suggestions using Anthropic Claude."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=self.temperature,
                system="You are an expert at helping humans make informed decisions "
                       "for AI agent orchestration systems. Provide thoughtful, "
                       "evidence-based suggestions. Always respond with valid JSON.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Best-effort usage tracking
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                usage = getattr(response, "usage", None)
                prompt_tokens = getattr(usage, "input_tokens", None)
                completion_tokens = getattr(usage, "output_tokens", None)
                total_tokens = None
                try:
                    if prompt_tokens is not None and completion_tokens is not None:
                        total_tokens = int(prompt_tokens) + int(completion_tokens)
                except Exception:
                    total_tokens = None
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="anthropic",
                        model=self.model,
                        operation="answers.suggest",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        confidence="HIGH" if usage is not None else "LOW",
                        metadata={"max_suggestions": self.max_suggestions},
                    )
                )
            except Exception:
                pass
            
            import json
            content = response.content[0].text
            
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Handle both array and object with "suggestions" key
            if isinstance(result, list):
                return result[:self.max_suggestions]
            elif "suggestions" in result:
                return result["suggestions"][:self.max_suggestions]
            else:
                return []
            
        except Exception as e:
            print(f"Anthropic error: {e}")
            return []
    
    def _hash_prompt(self, prompt: str) -> str:
        """Compute SHA-256 hash of prompt for traceability."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def suggest_all_answers(
    question_pack: Dict,
    provider: str = "openai",
    model: Optional[str] = None,
    context: Optional[Dict] = None,
    fallback_provider: Optional[str] = "anthropic"
) -> Tuple[List[List[Dict]], List[str]]:
    """
    Generate suggestions for all questions in a QuestionPack.
    
    Args:
        question_pack: QuestionPack dictionary
        provider: Primary LLM provider ("openai" or "anthropic")
        model: Model name (optional)
        context: Additional context dictionary
        fallback_provider: Fallback provider if primary fails
    
    Returns:
        Tuple of (suggestions_list, errors)
        - suggestions_list: List of suggestion lists, one per question
        - errors: List of error messages for questions that failed
    """
    suggestions_list = []
    errors = []
    
    # Try primary provider
    try:
        suggester = LLMSuggester(provider=provider, model=model)
        
        for i, question in enumerate(question_pack.get("questions", [])):
            try:
                suggestions = suggester.suggest_answers(
                    question=question,
                    question_pack=question_pack,
                    context=context
                )
                suggestions_list.append(suggestions)
            except Exception as e:
                errors.append(f"Question {i+1}: {str(e)}")
                suggestions_list.append([])
        
        return suggestions_list, errors
        
    except Exception as primary_error:
        # Try fallback provider if available
        if fallback_provider and fallback_provider != provider:
            try:
                suggester = LLMSuggester(provider=fallback_provider)
                
                for i, question in enumerate(question_pack.get("questions", [])):
                    try:
                        suggestions = suggester.suggest_answers(
                            question=question,
                            question_pack=question_pack,
                            context=context
                        )
                        suggestions_list.append(suggestions)
                    except Exception as e:
                        errors.append(f"Question {i+1}: {str(e)}")
                        suggestions_list.append([])
                
                errors.insert(0, f"Primary provider failed: {primary_error}, used fallback")
                return suggestions_list, errors
                
            except Exception as fallback_error:
                errors.append(f"Primary error: {primary_error}")
                errors.append(f"Fallback error: {fallback_error}")
                return [], errors
        else:
            errors.append(f"LLM error: {primary_error}")
            return [], errors


def create_suggestions_cache_key(question_pack: Dict) -> str:
    """Create cache key for question pack suggestions."""
    pack_id = question_pack.get("pack_id", "")
    question_ids = [q.get("question_id", "") for q in question_pack.get("questions", [])]
    key_str = f"{pack_id}:{':'.join(question_ids)}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()
