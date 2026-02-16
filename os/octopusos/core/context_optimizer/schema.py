from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TokenMetrics:
    model: str
    raw_tokens: int
    optimized_tokens: int
    reduction_rate: float  # 0..1
    reduction_percent: float  # 0..100
    raw_bytes: int
    optimized_bytes: int
    bytes_removed: int


@dataclass(frozen=True)
class OptimizerResult:
    """
    Optimizer output contract:
    - summary_text: the optimized text (what will be injected as context)
    - structured: machine readable info extracted from raw
    - metadata: includes traceability fields like raw_sha256 and counters
    """

    summary_text: str
    structured: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_text: Optional[str] = None


@dataclass(frozen=True)
class TokenOptimizationReport:
    kind: str  # cli|ui|tool|aggregate
    metrics: TokenMetrics
    structured: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_sha256: Optional[str] = None
    optimized_sha256: Optional[str] = None
    raw_preview: Optional[str] = None
    optimized_preview: Optional[str] = None

