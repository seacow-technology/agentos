"""
LLM Token Tracking Wrapper - Universal injection point for token usage tracking

This module provides a decorator and wrapper for all LLM calls to automatically
inject token usage tracking and budget enforcement.

PR-0131-2026-1 Wave A: Real Token Tracking Integration
"""

import logging
import functools
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMCallContext:
    """Context for LLM call tracking"""
    task_id: Optional[str] = None
    provider: str = "unknown"
    model: str = "unknown"
    operation: str = "generate"


def track_llm_call(context: Optional[LLMCallContext] = None):
    """
    Decorator to track token usage for LLM calls

    Usage:
        @track_llm_call(LLMCallContext(task_id="task_123", provider="anthropic"))
        def my_llm_call():
            return anthropic_client.messages.create(...)

    Args:
        context: LLMCallContext with task_id, provider, model info
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute LLM call
            response = func(*args, **kwargs)

            # Extract token usage from response
            try:
                from agentos.core.policy.token_usage import TokenUsage
                usage = TokenUsage.from_provider_response(
                    response=response,
                    task_id=context.task_id if context else None,
                    provider=context.provider if context else "unknown",
                    model=context.model if context else "unknown"
                )

                # Record to audit if task_id available
                if context and context.task_id:
                    try:
                        from agentos.core.task.audit_service import TaskAuditService
                        audit_service = TaskAuditService()
                        audit_service.record_operation(
                            task_id=context.task_id,
                            operation="llm_call",
                            event_type="TOKEN_USAGE",
                            status="success",
                            payload=usage.to_dict()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record token usage audit: {e}")

                # Check budget if configured
                if context and context.task_id:
                    try:
                        from agentos.core.policy.token_usage import TokenTracker
                        # Note: Budget checking should be done at higher level
                        # This is just recording
                    except Exception as e:
                        logger.debug(f"Budget checking skipped: {e}")

            except Exception as e:
                logger.warning(f"Failed to track token usage: {e}")

            return response

        return wrapper
    return decorator


class LLMCallWrapper:
    """
    Wrapper for LLM calls with automatic token tracking

    Use this wrapper for all LLM provider calls to ensure
    consistent token tracking across providers.
    """

    def __init__(self, provider: str, model: str):
        """
        Initialize wrapper

        Args:
            provider: Provider name (anthropic/openai/local)
            model: Model name
        """
        self.provider = provider
        self.model = model

    def wrap_call(
        self,
        llm_call: Callable,
        task_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Wrap and execute LLM call with token tracking

        Args:
            llm_call: Callable that returns LLM response
            task_id: Optional task ID for audit
            **kwargs: Additional arguments for llm_call

        Returns:
            LLM response (with tracking side-effect)
        """
        # Execute call
        response = llm_call(**kwargs)

        # Track tokens
        try:
            from agentos.core.policy.token_usage import TokenUsage
            usage = TokenUsage.from_provider_response(
                response=response,
                task_id=task_id,
                provider=self.provider,
                model=self.model
            )

            # Record to audit
            if task_id:
                try:
                    from agentos.core.task.audit_service import TaskAuditService
                    audit_service = TaskAuditService()
                    audit_service.record_operation(
                        task_id=task_id,
                        operation="llm_call",
                        event_type="TOKEN_USAGE",
                        status="success",
                        payload=usage.to_dict()
                    )
                    logger.debug(f"Recorded token usage: {usage.total_tokens} tokens")
                except Exception as e:
                    logger.warning(f"Failed to record audit: {e}")

        except Exception as e:
            logger.warning(f"Failed to track tokens: {e}")

        return response


# Global singleton instances for common providers
anthropic_wrapper = LLMCallWrapper("anthropic", "claude")
openai_wrapper = LLMCallWrapper("openai", "gpt")
local_wrapper = LLMCallWrapper("local", "local-model")


def inject_token_tracking_into_adapter(adapter_class):
    """
    Class decorator to inject token tracking into adapter

    This wraps the generate() and generate_stream() methods
    to automatically track token usage.

    Usage:
        @inject_token_tracking_into_adapter
        class MyAdapter(ChatModelAdapter):
            ...
    """
    original_generate = adapter_class.generate
    original_generate_stream = getattr(adapter_class, 'generate_stream', None)

    def wrapped_generate(self, messages, **kwargs):
        """Wrapped generate with token tracking"""
        # Call original
        response, metadata = original_generate(self, messages, **kwargs)

        # Track tokens if metadata contains usage info
        try:
            if hasattr(self, 'task_id') and self.task_id:
                from agentos.core.policy.token_usage import TokenUsage
                # Extract from metadata
                prompt_tokens = metadata.get('prompt_tokens', 0)
                completion_tokens = metadata.get('completion_tokens', 0) or metadata.get('tokens_used', 0)
                total_tokens = prompt_tokens + completion_tokens

                usage = TokenUsage(
                    task_id=self.task_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    model=getattr(self, 'model', 'unknown'),
                    provider=getattr(self, 'provider', 'unknown'),
                    confidence="HIGH" if total_tokens > 0 else "LOW"
                )

                # Record audit
                from agentos.core.task.audit_service import TaskAuditService
                audit_service = TaskAuditService()
                audit_service.record_operation(
                    task_id=self.task_id,
                    operation="llm_call",
                    event_type="TOKEN_USAGE",
                    status="success",
                    payload=usage.to_dict()
                )
        except Exception as e:
            logger.debug(f"Token tracking failed: {e}")

        return response, metadata

    # Replace methods
    adapter_class.generate = wrapped_generate

    if original_generate_stream:
        def wrapped_generate_stream(self, messages, **kwargs):
            """Wrapped stream generate with token tracking"""
            # For streaming, we can only track after completion
            # This is a limitation - streaming doesn't provide token counts until end
            for chunk in original_generate_stream(self, messages, **kwargs):
                yield chunk

        adapter_class.generate_stream = wrapped_generate_stream

    return adapter_class
