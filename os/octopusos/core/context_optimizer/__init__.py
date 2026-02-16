"""
Context Optimizer Pipeline

This package provides deterministic, auditable context reduction:
- preserves raw inputs (hashable)
- produces structured summaries (traceable)
- measures real token deltas via tiktoken (no estimation)
"""

from .metrics import count_tokens, compute_reduction
from .pipeline import (
    optimize_cli_text,
    optimize_ui_text,
    optimize_tool_trace_text,
    generate_all_reports,
)
from .schema import OptimizerResult, TokenMetrics, TokenOptimizationReport

__all__ = [
    "OptimizerResult",
    "TokenMetrics",
    "TokenOptimizationReport",
    "count_tokens",
    "compute_reduction",
    "optimize_cli_text",
    "optimize_ui_text",
    "optimize_tool_trace_text",
    "generate_all_reports",
]

