"""
Task Router - Capability-driven routing system for AgentOS

Provides intelligent instance selection based on task requirements,
with full auditability and explainability.

PR-1: Core router implementation with requirements extraction,
instance profiling, scoring, and routing decisions.
"""

from agentos.router.router import Router
from agentos.router.models import (
    RoutePlan,
    TaskRequirements,
    InstanceProfile,
    RerouteReason,
    RerouteEvent,
    RouteDecision,
)
from agentos.router.requirements_extractor import RequirementsExtractor
from agentos.router.instance_profiles import InstanceProfileBuilder
from agentos.router.scorer import RouteScorer, RouteScore
from agentos.router.persistence import RouterPersistence
from agentos.router import events as router_events

__all__ = [
    "Router",
    "RoutePlan",
    "TaskRequirements",
    "InstanceProfile",
    "RerouteReason",
    "RerouteEvent",
    "RouteDecision",
    "RequirementsExtractor",
    "InstanceProfileBuilder",
    "RouteScorer",
    "RouteScore",
    "RouterPersistence",
    "router_events",
]
