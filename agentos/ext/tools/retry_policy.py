"""Retry policy for tool adapters with exponential backoff."""

import time
import random
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF


class RetryPolicy:
    """
    Retry policy with exponential backoff and jitter.
    
    Features:
    - Configurable retry strategies
    - Exponential backoff with jitter
    - Retry count tracking
    - Audit logging integration
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry policy.
        
        Args:
            config: Retry configuration (default: 3 retries with exponential backoff)
        """
        self.config = config or RetryConfig()
        self.retry_count = 0
        self.total_delay = 0.0
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result if successful
        
        Raises:
            Exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # Success - record metrics
                if attempt > 0:
                    self.retry_count += attempt
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    
                    print(f"Attempt {attempt + 1} failed: {e}. "
                          f"Retrying in {delay:.2f}s...")
                    
                    time.sleep(delay)
                    self.total_delay += delay
        
        # All retries exhausted
        self.retry_count += self.config.max_retries
        raise Exception(
            f"All {self.config.max_retries} retries exhausted"
        ) from last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = min(
                self.config.initial_delay * (self.config.exponential_base ** attempt),
                self.config.max_delay
            )
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = min(
                self.config.initial_delay * (attempt + 1),
                self.config.max_delay
            )
        else:  # FIXED_DELAY
            delay = self.config.initial_delay
        
        # Add jitter to avoid thundering herd
        if self.config.jitter:
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        return {
            "retry_count": self.retry_count,
            "total_delay_seconds": self.total_delay,
            "max_retries": self.config.max_retries,
            "strategy": self.config.strategy.value
        }
    
    def reset(self) -> None:
        """Reset retry metrics."""
        self.retry_count = 0
        self.total_delay = 0.0


class RetryableAdapter:
    """Mixin class to add retry capability to adapters."""
    
    def __init__(self, *args, retry_config: Optional[RetryConfig] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_policy = RetryPolicy(retry_config)
    
    def dispatch_with_retry(self, *args, **kwargs):
        """Dispatch with automatic retry."""
        return self.retry_policy.execute_with_retry(
            self.dispatch,
            *args,
            **kwargs
        )
    
    def collect_with_retry(self, *args, **kwargs):
        """Collect with automatic retry."""
        return self.retry_policy.execute_with_retry(
            self.collect,
            *args,
            **kwargs
        )
    
    def get_retry_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        return self.retry_policy.get_metrics()


def create_retry_policy(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    strategy: str = "exponential_backoff"
) -> RetryPolicy:
    """
    Create a retry policy with given parameters.
    
    Args:
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        strategy: Retry strategy name
    
    Returns:
        Configured RetryPolicy
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        strategy=RetryStrategy(strategy)
    )
    return RetryPolicy(config)
