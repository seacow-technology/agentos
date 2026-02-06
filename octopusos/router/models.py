"""
Router Data Models

Defines the data structures for routing decisions and instance profiles.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, timezone


class RerouteReason(str, Enum):
    """Reasons for rerouting a task"""
    CONN_REFUSED = "CONN_REFUSED"  # Connection refused
    TIMEOUT = "TIMEOUT"  # Request timeout
    PROCESS_EXITED = "PROCESS_EXITED"  # Process died/exited
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"  # Service fingerprint mismatch
    INSTANCE_NOT_READY = "INSTANCE_NOT_READY"  # Instance not in READY state
    NO_AVAILABLE_INSTANCE = "NO_AVAILABLE_INSTANCE"  # No available instances


@dataclass
class InstanceProfile:
    """
    Instance capability profile

    Aggregates provider metadata, runtime state, and capability tags
    for routing decisions.
    """
    instance_id: str  # e.g., "llamacpp:qwen3-coder-30b"
    provider_type: str  # e.g., "llamacpp", "ollama", "openai"
    base_url: str  # Endpoint URL
    state: str  # READY, ERROR, DISCONNECTED, DEGRADED
    latency_ms: Optional[float] = None  # Last probe latency
    fingerprint: Optional[str] = None  # Detected fingerprint
    tags: List[str] = field(default_factory=list)  # Capability tags: coding, fast, big_ctx, etc.
    ctx: Optional[int] = None  # Context window size
    cost_category: str = "local"  # local, cloud, paid
    model: Optional[str] = None  # Model name/identifier
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_provider_status(
        cls,
        status: "ProviderStatus",
        tags: Optional[List[str]] = None,
        ctx: Optional[int] = None,
        model: Optional[str] = None,
    ) -> "InstanceProfile":
        """
        Create InstanceProfile from ProviderStatus

        Args:
            status: ProviderStatus object
            tags: Optional capability tags (from config)
            ctx: Optional context window size (from config)
            model: Optional model name (from config)

        Returns:
            InstanceProfile
        """
        # Determine cost category
        provider_id = status.id.split(":")[0] if ":" in status.id else status.id
        cost_category = "cloud" if provider_id in ["openai", "anthropic"] else "local"

        return cls(
            instance_id=status.id,
            provider_type=provider_id,
            base_url=status.endpoint or "",
            state=status.state.value,
            latency_ms=status.latency_ms,
            fingerprint=None,  # TODO: Extract from metadata if available
            tags=tags or [],
            ctx=ctx,
            cost_category=cost_category,
            model=model,
            metadata={},
        )


@dataclass
class TaskRequirements:
    """
    Task capability requirements

    Extracted from task spec/metadata to guide routing decisions.
    """
    needs: List[str] = field(default_factory=list)  # Required capabilities: coding, frontend, etc.
    prefer: List[str] = field(default_factory=list)  # Preferences: local, fast, cheap
    min_ctx: int = 4096  # Minimum context window
    latency_class: str = "normal"  # normal, fast, batch

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class RouteDecision:
    """
    A single routing decision with score and reasoning
    """
    instance_id: str
    score: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class RoutePlan:
    """
    Complete routing plan for a task

    Contains selected instance, fallback chain, scores, and reasoning.
    All routing decisions are explainable and auditable.
    """
    task_id: str
    selected: str  # Selected instance ID
    fallback: List[str] = field(default_factory=list)  # Fallback chain
    scores: Dict[str, float] = field(default_factory=dict)  # All scores
    reasons: List[str] = field(default_factory=list)  # Reasons for selection
    router_version: str = "v1"
    timestamp: Optional[str] = None
    requirements: Optional[TaskRequirements] = None

    def __post_init__(self):
        """Set timestamp if not provided"""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)

        # Handle requirements (can be TaskRequirements, dict, or None)
        req = self.requirements
        if req:
            if hasattr(req, "to_dict"):
                result["requirements"] = req.to_dict()  # TaskRequirements
            elif isinstance(req, dict):
                result["requirements"] = req  # Already dict
            else:
                # Fallback: try asdict for dataclass
                try:
                    result["requirements"] = asdict(req)  # type: ignore[arg-type]
                except Exception:
                    result["requirements"] = {"value": str(req)}

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutePlan":
        """Create from dictionary"""
        # Extract requirements if present
        requirements = None
        if "requirements" in data and data["requirements"]:
            req_data = data["requirements"]
            if isinstance(req_data, dict):
                requirements = TaskRequirements(**req_data)

        return cls(
            task_id=data["task_id"],
            selected=data["selected"],
            fallback=data.get("fallback", []),
            scores=data.get("scores", {}),
            reasons=data.get("reasons", []),
            router_version=data.get("router_version", "v1"),
            timestamp=data.get("timestamp"),
            requirements=requirements,
        )


@dataclass
class RerouteEvent:
    """
    Reroute event details

    Records why and how a task was rerouted.
    """
    task_id: str
    from_instance: str
    to_instance: str
    reason_code: RerouteReason
    reason_detail: str
    timestamp: str
    fallback_chain: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Set timestamp if not provided"""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["reason_code"] = self.reason_code.value
        return result
