from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class PointerLocator:
    byte_range: Optional[Tuple[int, int]] = None
    line_range: Optional[Tuple[int, int]] = None
    regex: Optional[str] = None
    signature: Optional[str] = None


@dataclass(frozen=True)
class ContextPointer:
    id: str
    source_kind: str  # file|sqlite|artifact|trace
    source_ref: Dict[str, Any]
    locator: Dict[str, Any]  # keep flexible for schema evolution
    preview: str
    estimated_tokens: int
    hash: str  # sha256:...
    signature: Optional[str] = None


@dataclass(frozen=True)
class ContextExcerpt:
    id: str
    pointer_id: str
    excerpt: str
    hash: str  # sha256:...


@dataclass(frozen=True)
class ContextFact:
    id: str
    channel: str  # cli|ui|tool
    severity: str  # error|warn|info
    value_score: float
    signature: str
    data: Dict[str, Any] = field(default_factory=dict)
    evidence_ptrs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextPack:
    version: str  # v2.0
    generated_at_ms: int
    ruleset_version: str
    source: Dict[str, Any]  # {kind, ref, raw_sha256}
    tier_0_tldr: str
    tier_1_facts: List[ContextFact] = field(default_factory=list)
    tier_2_excerpts: List[ContextExcerpt] = field(default_factory=list)
    tier_3_pointers: List[ContextPointer] = field(default_factory=list)


@dataclass(frozen=True)
class ExpansionRequestItem:
    pointer_id: str
    reason: str
    max_tokens: int


@dataclass(frozen=True)
class ExpansionRequest:
    need_more_detail: bool
    requests: List[ExpansionRequestItem] = field(default_factory=list)


@dataclass(frozen=True)
class ExpansionResultItem:
    pointer_id: str
    content_excerpt: str
    content_hash: str
    tokens: int
    signature: Optional[str] = None


@dataclass(frozen=True)
class BudgetState:
    total: int
    base_limit: int
    expand_reserve: int
    requested: int
    used: int
    remaining: int


