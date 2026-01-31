"""
Decision Comparison API - WebUI Integration for v3 Shadow Classifier System

Provides REST API endpoints for comparing active vs shadow classifier decisions.
This API enables humans to evaluate shadow versions and make informed migration decisions.

Endpoints:
- GET /api/v3/decision-comparison/list - Get paginated list of decision comparisons
- GET /api/v3/decision-comparison/{decision_set_id} - Get detailed comparison for a decision set
- GET /api/v3/decision-comparison/summary - Get summary statistics for multiple shadow versions

Design Philosophy:
- Read-only API, no modifications
- Data-driven comparison metrics
- Support flexible filtering (session, time range, info_need_type)
- Clear distinction between active (executed) and shadow (hypothetical) decisions
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agentos.core.time import utc_now
from agentos.core.audit import (
    get_decision_sets,
    get_decision_set_by_id,
    get_shadow_evaluations_for_decision_set,
)
from agentos.core.chat.decision_comparator import get_comparator
from agentos.core.chat.shadow_registry import get_shadow_registry
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class TimeRange:
    """Time range presets for decision queries"""
    HOUR_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    CUSTOM = "custom"


def parse_time_range(
    time_range: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> tuple[datetime, datetime]:
    """
    Parse time range string and return start/end datetime objects

    Args:
        time_range: Preset time range (24h, 7d, 30d, custom)
        start_time: Optional custom start time (ISO format)
        end_time: Optional custom end time (ISO format)

    Returns:
        (start_datetime, end_datetime)

    Raises:
        ValueError: If time range is invalid or custom times are missing
    """
    now = utc_now()

    if time_range == TimeRange.HOUR_24:
        return now - timedelta(hours=24), now
    elif time_range == TimeRange.DAYS_7:
        return now - timedelta(days=7), now
    elif time_range == TimeRange.DAYS_30:
        return now - timedelta(days=30), now
    elif time_range == TimeRange.CUSTOM:
        if not start_time or not end_time:
            raise ValueError("Custom time range requires both start_time and end_time")

        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

            # Ensure timezone awareness
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            return start_dt, end_dt
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid datetime format: {e}")
    else:
        raise ValueError(f"Invalid time_range: {time_range}. Must be one of: 24h, 7d, 30d, custom")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/list")
async def list_decision_comparisons(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    active_version: str = Query("v1", description="Active classifier version"),
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)"),
    info_need_type: Optional[str] = Query(None, description="Filter by info_need_type"),
    limit: int = Query(100, description="Maximum results", ge=1, le=1000),
    offset: int = Query(0, description="Offset for pagination", ge=0),
) -> Dict[str, Any]:
    """
    Get paginated list of decision comparisons

    Returns a list of decision sets where active and shadow decisions can be compared.
    Each item includes basic information about the decision and available shadow versions.

    Returns:
        {
            "ok": true,
            "data": {
                "items": [
                    {
                        "decision_set_id": "abc123",
                        "message_id": "msg_456",
                        "session_id": "session_789",
                        "question_text": "What is the status of PR #123?",
                        "timestamp": "2026-01-31T10:00:00Z",
                        "active_decision": {
                            "version": "v1",
                            "decision_action": "REQUIRE_COMM",
                            "info_need_type": "EXTERNAL_FACT_UNCERTAIN",
                            "confidence_level": "medium"
                        },
                        "shadow_versions": ["v2-shadow-a", "v2-shadow-b"],
                        "shadow_count": 2,
                        "has_evaluation": true
                    },
                    ...
                ],
                "total_count": 312,
                "limit": 100,
                "offset": 0,
                "filters": {
                    "session_id": "session_789",
                    "active_version": "v1",
                    "time_range": "24h",
                    "info_need_type": null
                }
            },
            "error": null
        }
    """
    try:
        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Fetch decision sets from audit logs
        decision_sets = get_decision_sets(
            session_id=session_id,
            active_version=active_version,
            has_shadow=True,
            limit=limit + offset,  # Fetch more to handle offset
        )

        # Filter by time range
        filtered_sets = []
        for ds in decision_sets:
            ds_time = datetime.fromtimestamp(ds["created_at"], tz=timezone.utc)
            if start_dt <= ds_time <= end_dt:
                payload = ds["payload"]

                # Apply info_need_type filter if specified
                if info_need_type:
                    active_decision = payload.get("active_decision", {})
                    if active_decision.get("info_need_type") != info_need_type:
                        continue

                filtered_sets.append(ds)

        # Apply pagination
        total_count = len(filtered_sets)
        paginated_sets = filtered_sets[offset:offset + limit]

        # Transform to response format
        items = []
        for ds in paginated_sets:
            payload = ds["payload"]
            active_decision = payload.get("active_decision", {})
            shadow_versions = payload.get("shadow_versions", [])

            # Check if evaluation exists
            decision_set_id = payload.get("decision_set_id", "")
            has_evaluation = False
            if decision_set_id:
                evaluations = get_shadow_evaluations_for_decision_set(decision_set_id)
                has_evaluation = len(evaluations) > 0

            items.append({
                "decision_set_id": payload.get("decision_set_id", ""),
                "message_id": payload.get("message_id", ""),
                "session_id": payload.get("session_id", ""),
                "question_text": payload.get("question_text", ""),
                "timestamp": iso_z(datetime.fromtimestamp(ds["created_at"], tz=timezone.utc)),
                "active_decision": {
                    "version": active_decision.get("classifier_version", {}).get("version_id", active_version),
                    "decision_action": active_decision.get("decision_action", ""),
                    "info_need_type": active_decision.get("info_need_type", ""),
                    "confidence_level": active_decision.get("confidence_level", ""),
                },
                "shadow_versions": shadow_versions,
                "shadow_count": len(shadow_versions),
                "has_evaluation": has_evaluation,
            })

        return {
            "ok": True,
            "data": {
                "items": items,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "session_id": session_id,
                    "active_version": active_version,
                    "time_range": time_range,
                    "info_need_type": info_need_type,
                },
            },
            "error": None,
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list decision comparisons: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.get("/{decision_set_id}")
async def get_decision_comparison(
    decision_set_id: str,
) -> Dict[str, Any]:
    """
    Get detailed comparison for a specific decision set

    Shows side-by-side comparison of active decision and all shadow decisions,
    including scores and outcome signals.

    Returns:
        {
            "ok": true,
            "data": {
                "decision_set_id": "abc123",
                "message_id": "msg_456",
                "session_id": "session_789",
                "question_text": "What is the status of PR #123?",
                "timestamp": "2026-01-31T10:00:00Z",
                "context_snapshot": {...},
                "active_decision": {
                    "candidate_id": "candidate_001",
                    "version": "v1",
                    "version_type": "active",
                    "decision_action": "REQUIRE_COMM",
                    "info_need_type": "EXTERNAL_FACT_UNCERTAIN",
                    "confidence_level": "medium",
                    "reason_codes": ["uncertain_info", "external_state"],
                    "outcome": {
                        "executed": true,
                        "result": "user_satisfied",
                        "signals": ["smooth_completion"]
                    },
                    "score": 0.8,
                    "score_details": {
                        "base_score": 1.0,
                        "raw_score": 0.8,
                        "signal_contributions": [...]
                    }
                },
                "shadow_decisions": [
                    {
                        "candidate_id": "candidate_002",
                        "version": "v2-shadow-a",
                        "version_type": "shadow",
                        "version_description": "Expanded keyword matching for EXTERNAL_FACT",
                        "decision_action": "DIRECT_ANSWER",
                        "info_need_type": "LOCAL_KNOWLEDGE",
                        "confidence_level": "high",
                        "reason_codes": ["cached_info", "high_confidence"],
                        "outcome": {
                            "executed": false,
                            "hypothetical_result": "would_trigger_comm",
                            "signals": []
                        },
                        "score": 0.3,
                        "score_details": {...},
                        "shadow_metadata": {
                            "warning": "NOT EXECUTED - Hypothetical evaluation only"
                        }
                    },
                    ...
                ],
                "comparison": {
                    "best_shadow_version": "v2-shadow-b",
                    "best_shadow_score": 0.9,
                    "active_score": 0.8,
                    "score_delta": 0.1,
                    "would_change_decision": true
                }
            },
            "error": null
        }
    """
    try:
        # Fetch decision set from audit logs
        decision_set_event = get_decision_set_by_id(decision_set_id)

        if not decision_set_event:
            raise HTTPException(
                status_code=404,
                detail=f"Decision set {decision_set_id} not found"
            )

        payload = decision_set_event["payload"]

        # Extract basic information
        message_id = payload.get("message_id", "")
        session_id = payload.get("session_id", "")
        question_text = payload.get("question_text", "")
        timestamp = iso_z(datetime.fromtimestamp(decision_set_event["created_at"], tz=timezone.utc))
        context_snapshot = payload.get("context_snapshot", {})

        # Get active decision
        active_decision_data = payload.get("active_decision", {})
        active_classifier_version = active_decision_data.get("classifier_version", {})

        # Get shadow decisions
        shadow_decisions_data = payload.get("shadow_decisions", [])
        shadow_versions = payload.get("shadow_versions", [])

        # Fetch evaluation scores if available
        evaluation = None
        evaluations = get_shadow_evaluations_for_decision_set(decision_set_id)
        if evaluations:
            evaluation = evaluations[0]["payload"]  # Get most recent evaluation

        # Build active decision response
        active_decision = {
            "candidate_id": active_decision_data.get("candidate_id", ""),
            "version": active_classifier_version.get("version_id", ""),
            "version_type": "active",
            "decision_action": active_decision_data.get("decision_action", ""),
            "info_need_type": active_decision_data.get("info_need_type", ""),
            "confidence_level": active_decision_data.get("confidence_level", ""),
            "reason_codes": active_decision_data.get("reason_codes", []),
            "rule_signals": active_decision_data.get("rule_signals", {}),
            "outcome": {
                "executed": True,
                "result": "completed",  # Could be enhanced with actual outcome data
                "signals": []
            },
            "score": None,
            "score_details": None,
        }

        # Add score if evaluation exists
        if evaluation:
            active_score = evaluation.get("active_score")
            if active_score is not None:
                active_decision["score"] = active_score
                active_decision["score_details"] = evaluation.get("active_score_details", {})

        # Build shadow decisions response
        shadow_decisions = []
        for i, shadow_data in enumerate(shadow_decisions_data):
            shadow_version = shadow_versions[i] if i < len(shadow_versions) else "unknown"
            shadow_classifier_version = shadow_data.get("classifier_version", {})

            shadow_decision = {
                "candidate_id": shadow_data.get("candidate_id", ""),
                "version": shadow_version,
                "version_type": "shadow",
                "version_description": shadow_classifier_version.get("change_description", ""),
                "decision_action": shadow_data.get("decision_action", ""),
                "info_need_type": shadow_data.get("info_need_type", ""),
                "confidence_level": shadow_data.get("confidence_level", ""),
                "reason_codes": shadow_data.get("reason_codes", []),
                "rule_signals": shadow_data.get("rule_signals", {}),
                "outcome": {
                    "executed": False,
                    "hypothetical_result": "not_executed",
                    "signals": []
                },
                "score": None,
                "score_details": None,
                "shadow_metadata": {
                    "warning": "NOT EXECUTED - Hypothetical evaluation only"
                }
            }

            # Add score if evaluation exists
            if evaluation:
                shadow_scores = evaluation.get("shadow_scores", {})
                shadow_score = shadow_scores.get(shadow_version)
                if shadow_score is not None:
                    shadow_decision["score"] = shadow_score
                    shadow_score_details = evaluation.get("shadow_score_details", {})
                    shadow_decision["score_details"] = shadow_score_details.get(shadow_version, {})

            shadow_decisions.append(shadow_decision)

        # Calculate comparison metrics
        comparison = {
            "best_shadow_version": None,
            "best_shadow_score": None,
            "active_score": active_decision.get("score"),
            "score_delta": None,
            "would_change_decision": False,
        }

        if shadow_decisions and active_decision.get("score") is not None:
            # Find best shadow version
            best_shadow = max(
                shadow_decisions,
                key=lambda s: s.get("score") if s.get("score") is not None else -float("inf")
            )

            if best_shadow.get("score") is not None:
                comparison["best_shadow_version"] = best_shadow["version"]
                comparison["best_shadow_score"] = best_shadow["score"]
                comparison["score_delta"] = best_shadow["score"] - active_decision["score"]

                # Check if decision would change
                active_action = active_decision.get("decision_action")
                best_shadow_action = best_shadow.get("decision_action")
                comparison["would_change_decision"] = (active_action != best_shadow_action)

        return {
            "ok": True,
            "data": {
                "decision_set_id": decision_set_id,
                "message_id": message_id,
                "session_id": session_id,
                "question_text": question_text,
                "timestamp": timestamp,
                "context_snapshot": context_snapshot,
                "active_decision": active_decision,
                "shadow_decisions": shadow_decisions,
                "comparison": comparison,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision comparison: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }


@router.get("/summary")
async def get_comparison_summary(
    active_version: str = Query("v1", description="Active classifier version"),
    shadow_versions: str = Query(..., description="Comma-separated shadow version IDs"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    info_need_type: Optional[str] = Query(None, description="Filter by info_need_type"),
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)"),
) -> Dict[str, Any]:
    """
    Get summary statistics comparing active to multiple shadow versions

    Returns aggregated metrics showing how each shadow version performs compared to active.
    Helps identify the best shadow version to migrate to production.

    Returns:
        {
            "ok": true,
            "data": {
                "active_version": "v1",
                "shadow_comparisons": [
                    {
                        "shadow_version": "v2-shadow-b",
                        "sample_count": 312,
                        "divergence_rate": 0.48,
                        "improvement_rate": 0.15,
                        "better_count": 220,
                        "worse_count": 50,
                        "neutral_count": 42,
                        "recommendation": "CONSIDER_MIGRATION"
                    },
                    {
                        "shadow_version": "v2-shadow-a",
                        "sample_count": 312,
                        "divergence_rate": 0.35,
                        "improvement_rate": -0.05,
                        "better_count": 100,
                        "worse_count": 180,
                        "neutral_count": 32,
                        "recommendation": "DO_NOT_MIGRATE"
                    }
                ],
                "filters": {...}
            },
            "error": null
        }
    """
    try:
        # Parse shadow versions
        shadow_version_list = [v.strip() for v in shadow_versions.split(",") if v.strip()]
        if not shadow_version_list:
            raise ValueError("At least one shadow version is required")

        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Get comparator
        comparator = get_comparator()

        # Get summary statistics
        summary = comparator.get_summary_statistics(
            active_version=active_version,
            shadow_versions=shadow_version_list,
            session_id=session_id,
            time_range=(start_dt, end_dt),
            limit=1000,
        )

        # Add recommendations
        for shadow_comparison in summary["shadow_comparisons"]:
            improvement_rate = shadow_comparison.get("improvement_rate")
            better_count = shadow_comparison.get("better_count", 0)
            worse_count = shadow_comparison.get("worse_count", 0)
            sample_count = shadow_comparison.get("sample_count", 0)

            # Calculate recommendation
            recommendation = "INSUFFICIENT_DATA"
            if sample_count >= 50:  # Need at least 50 samples
                if improvement_rate and improvement_rate > 0.1:
                    if better_count > worse_count * 2:
                        recommendation = "STRONGLY_RECOMMEND_MIGRATION"
                    else:
                        recommendation = "CONSIDER_MIGRATION"
                elif improvement_rate and improvement_rate > 0:
                    recommendation = "MARGINAL_IMPROVEMENT"
                elif improvement_rate and improvement_rate < -0.05:
                    recommendation = "DO_NOT_MIGRATE"
                else:
                    recommendation = "NO_CLEAR_WINNER"

            shadow_comparison["recommendation"] = recommendation

        return {
            "ok": True,
            "data": summary,
            "error": None,
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get comparison summary: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e),
        }
