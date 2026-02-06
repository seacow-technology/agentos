"""
Token Usage Tracking and Budget Management

Provides comprehensive token usage tracking for all LLM calls,
enabling cost control and audit trail for token consumption.

PR-0131-2026-1: Token Budget & Cost Governance (v0.6 → PASS)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
from agentos.core.time import utc_now_iso



@dataclass(frozen=True)
class TokenUsage:
    """
    Immutable token usage record for a single LLM call

    Tracks token consumption with provider-agnostic format.
    All LLM calls must produce a TokenUsage record.
    """
    usage_id: str = field(default_factory=lambda: f"token_{uuid.uuid4().hex[:12]}")
    task_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    provider: str = ""  # "anthropic", "openai", "local", etc.
    timestamp: str = field(default_factory=lambda: utc_now_iso())
    confidence: str = "HIGH"  # HIGH | LOW | ESTIMATED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for audit storage"""
        return {
            "usage_id": self.usage_id,
            "task_id": self.task_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "provider": self.provider,
            "timestamp": self.timestamp,
            "confidence": self.confidence
        }

    @classmethod
    def from_provider_response(
        cls,
        response: Any,
        task_id: Optional[str] = None,
        provider: str = "unknown",
        model: str = "unknown"
    ) -> "TokenUsage":
        """
        Extract token usage from provider response

        Handles various provider response formats:
        - Anthropic: response.usage.{input_tokens, output_tokens}
        - OpenAI: response.usage.{prompt_tokens, completion_tokens, total_tokens}
        - Local: May lack usage data

        Args:
            response: Provider API response object
            task_id: Optional task ID
            provider: Provider name
            model: Model name

        Returns:
            TokenUsage instance with HIGH or LOW confidence
        """
        confidence = "HIGH"
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        try:
            # Anthropic format
            if hasattr(response, 'usage'):
                usage = response.usage
                if hasattr(usage, 'input_tokens'):
                    prompt_tokens = usage.input_tokens
                    completion_tokens = usage.output_tokens
                    total_tokens = prompt_tokens + completion_tokens
                # OpenAI format
                elif hasattr(usage, 'prompt_tokens'):
                    prompt_tokens = usage.prompt_tokens
                    completion_tokens = usage.completion_tokens
                    total_tokens = usage.total_tokens
        except (AttributeError, TypeError):
            # Provider doesn't provide usage data
            confidence = "LOW"
            # Use heuristic estimation if needed
            if hasattr(response, 'content'):
                estimated_tokens = len(str(response.content)) // 4
                completion_tokens = estimated_tokens
                total_tokens = estimated_tokens

        return cls(
            task_id=task_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model,
            provider=provider,
            timestamp=utc_now_iso(),
            confidence=confidence
        )


@dataclass
class TokenBudget:
    """
    Token budget configuration for a task or execution

    Enforces hard limits on token consumption to prevent runaway costs.
    """
    max_total_tokens: int
    max_prompt_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None

    def validate_usage(self, cumulative: TokenUsage) -> tuple[bool, str]:
        """
        Validate if cumulative usage exceeds budget

        Args:
            cumulative: Cumulative token usage

        Returns:
            (is_valid, reason) - False if budget exceeded
        """
        if cumulative.total_tokens > self.max_total_tokens:
            return False, f"Total tokens {cumulative.total_tokens} exceeds budget {self.max_total_tokens}"

        if self.max_prompt_tokens and cumulative.prompt_tokens > self.max_prompt_tokens:
            return False, f"Prompt tokens {cumulative.prompt_tokens} exceeds budget {self.max_prompt_tokens}"

        if self.max_completion_tokens and cumulative.completion_tokens > self.max_completion_tokens:
            return False, f"Completion tokens {cumulative.completion_tokens} exceeds budget {self.max_completion_tokens}"

        return True, "OK"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "max_total_tokens": self.max_total_tokens,
            "max_prompt_tokens": self.max_prompt_tokens,
            "max_completion_tokens": self.max_completion_tokens
        }


class TokenTracker:
    """
    Token usage tracker for a task

    Maintains cumulative token usage and enforces budget limits.
    Thread-safe for concurrent LLM calls.
    """
    def __init__(self, task_id: str, budget: Optional[TokenBudget] = None):
        """
        Initialize token tracker

        Args:
            task_id: Task ID
            budget: Optional token budget
        """
        self.task_id = task_id
        self.budget = budget
        self.usages: list[TokenUsage] = []
        self._lock = None  # Use threading.Lock if concurrency needed

    def record(self, usage: TokenUsage) -> None:
        """
        Record a token usage

        Args:
            usage: Token usage record

        Raises:
            BudgetExceededError: If budget is exceeded after this usage
        """
        self.usages.append(usage)

        # Check budget if configured
        if self.budget:
            cumulative = self.get_cumulative()
            is_valid, reason = self.budget.validate_usage(cumulative)
            if not is_valid:
                from agentos.core.task.errors import BudgetExceededError
                raise BudgetExceededError(
                    task_id=self.task_id,
                    budget=self.budget.to_dict(),
                    cumulative_usage=cumulative.to_dict(),
                    reason=reason
                )

    def get_cumulative(self) -> TokenUsage:
        """
        Get cumulative token usage across all recorded usages

        Returns:
            TokenUsage with summed totals
        """
        total_prompt = sum(u.prompt_tokens for u in self.usages)
        total_completion = sum(u.completion_tokens for u in self.usages)
        total = sum(u.total_tokens for u in self.usages)

        # Determine confidence: LOW if any usage has LOW confidence
        confidence = "HIGH"
        if any(u.confidence == "LOW" for u in self.usages):
            confidence = "LOW"

        return TokenUsage(
            usage_id=f"cumulative_{self.task_id}",
            task_id=self.task_id,
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total,
            model="aggregate",
            provider="aggregate",
            timestamp=utc_now_iso(),
            confidence=confidence
        )

    def to_audit_dict(self) -> Dict[str, Any]:
        """
        Convert to audit dictionary

        Returns:
            Dictionary suitable for task_audits.payload
        """
        cumulative = self.get_cumulative()
        return {
            "task_id": self.task_id,
            "cumulative_usage": cumulative.to_dict(),
            "budget": self.budget.to_dict() if self.budget else None,
            "usage_count": len(self.usages),
            "individual_usages": [u.to_dict() for u in self.usages]
        }
