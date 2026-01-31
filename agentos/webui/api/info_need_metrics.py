"""
InfoNeed Metrics API - WebUI Integration

Provides REST API endpoints for InfoNeed classification quality metrics.

Endpoints:
- GET /api/info-need-metrics/summary - Get metrics summary for a time range
- GET /api/info-need-metrics/history - Get historical trend data
- GET /api/info-need-metrics/export - Export metrics data

Constraints:
- Read-only metrics, no semantic analysis
- Pure statistical data from InfoNeedMetrics calculator
- No LLM calls, can run offline
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agentos.metrics.info_need_metrics import InfoNeedMetrics
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class TimeRange:
    """Time range presets for metric queries"""
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

@router.get("/summary")
async def get_metrics_summary(
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)")
) -> Dict[str, Any]:
    """
    Get InfoNeed metrics summary for a time period

    Returns:
        {
            "ok": true,
            "data": {
                "time_range": "24h",
                "period": {
                    "start": "2026-01-30T10:30:00Z",
                    "end": "2026-01-31T10:30:00Z"
                },
                "last_updated": "2026-01-31T10:30:00Z",
                "metrics": {
                    "comm_trigger_rate": 0.234,
                    "false_positive_rate": 0.087,
                    "false_negative_rate": 0.142,
                    "ambient_hit_rate": 0.956,
                    "decision_latency": {
                        "p50": 145.3,
                        "p95": 234.2,
                        "p99": 345.1,
                        "avg": 165.4,
                        "count": 450
                    },
                    "decision_stability": 0.892
                },
                "counts": {
                    "total_classifications": 450,
                    "comm_triggered": 105,
                    "ambient_queries": 90,
                    "false_positives": 12,
                    "false_negatives": 18
                }
            },
            "error": null
        }
    """
    try:
        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Calculate metrics
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics(start_time=start_dt, end_time=end_dt)

        # Extract core metrics for summary
        comm_triggered = sum(
            1 for item in calculator._load_classifications(start_dt, end_dt)
            if item.get("decision") == "REQUIRE_COMM"
        )

        classifications = calculator._load_classifications(start_dt, end_dt)
        outcomes = calculator._load_outcomes(start_dt, end_dt)
        enriched = calculator._enrich_with_outcomes(classifications, outcomes)

        # Count false positives
        false_positive_count = sum(
            1 for item in enriched
            if item.get("decision") == "REQUIRE_COMM" and
               item.get("outcome") and
               item["outcome"].get("outcome") == "unnecessary_comm"
        )

        # Count false negatives
        false_negative_count = sum(
            1 for item in enriched
            if item.get("decision") != "REQUIRE_COMM" and
               item.get("outcome") and
               item["outcome"].get("outcome") == "user_corrected"
        )

        # Count ambient queries
        ambient_count = sum(
            1 for item in enriched
            if item.get("classified_type") == "AMBIENT_STATE"
        )

        summary = {
            "time_range": time_range,
            "period": metrics["period"],
            "last_updated": iso_z(utc_now()),
            "metrics": {
                "comm_trigger_rate": metrics["comm_trigger_rate"],
                "false_positive_rate": metrics["false_positive_rate"],
                "false_negative_rate": metrics["false_negative_rate"],
                "ambient_hit_rate": metrics["ambient_hit_rate"],
                "decision_latency": metrics["decision_latency"],
                "decision_stability": metrics["decision_stability"],
            },
            "counts": {
                "total_classifications": metrics["total_classifications"],
                "comm_triggered": comm_triggered,
                "ambient_queries": ambient_count,
                "false_positives": false_positive_count,
                "false_negatives": false_negative_count,
            }
        }

        return {
            "ok": True,
            "data": summary,
            "error": None
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }


@router.get("/history")
async def get_metrics_history(
    time_range: str = Query("7d", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)"),
    granularity: str = Query("hour", description="Data granularity: hour, day")
) -> Dict[str, Any]:
    """
    Get historical trend data for metrics

    Returns time-series data points for trend visualization

    Returns:
        {
            "ok": true,
            "data": {
                "time_range": "7d",
                "granularity": "hour",
                "data_points": [
                    {
                        "timestamp": "2026-01-30T10:00:00Z",
                        "comm_trigger_rate": 0.234,
                        "false_positive_rate": 0.087,
                        "false_negative_rate": 0.142,
                        "ambient_hit_rate": 0.956,
                        "decision_latency_avg": 145.3,
                        "decision_stability": 0.892,
                        "sample_count": 45
                    },
                    ...
                ]
            },
            "error": null
        }
    """
    try:
        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Determine time bucket size based on granularity
        if granularity == "hour":
            bucket_size = timedelta(hours=1)
        elif granularity == "day":
            bucket_size = timedelta(days=1)
        else:
            raise ValueError(f"Invalid granularity: {granularity}. Must be 'hour' or 'day'")

        # Generate time buckets
        data_points = []
        current_time = start_dt
        calculator = InfoNeedMetrics()

        while current_time < end_dt:
            bucket_end = min(current_time + bucket_size, end_dt)

            # Calculate metrics for this bucket
            try:
                metrics = calculator.calculate_metrics(
                    start_time=current_time,
                    end_time=bucket_end
                )

                data_points.append({
                    "timestamp": iso_z(current_time),
                    "comm_trigger_rate": metrics["comm_trigger_rate"],
                    "false_positive_rate": metrics["false_positive_rate"],
                    "false_negative_rate": metrics["false_negative_rate"],
                    "ambient_hit_rate": metrics["ambient_hit_rate"],
                    "decision_latency_avg": metrics["decision_latency"]["avg"],
                    "decision_stability": metrics["decision_stability"],
                    "sample_count": metrics["total_classifications"]
                })
            except Exception as e:
                logger.warning(f"Failed to calculate metrics for bucket {current_time}: {e}")
                # Add empty data point to maintain continuity
                data_points.append({
                    "timestamp": iso_z(current_time),
                    "comm_trigger_rate": 0.0,
                    "false_positive_rate": 0.0,
                    "false_negative_rate": 0.0,
                    "ambient_hit_rate": 0.0,
                    "decision_latency_avg": 0.0,
                    "decision_stability": 0.0,
                    "sample_count": 0
                })

            current_time = bucket_end

        return {
            "ok": True,
            "data": {
                "time_range": time_range,
                "granularity": granularity,
                "data_points": data_points
            },
            "error": None
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }


@router.get("/export")
async def export_metrics(
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, custom"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format, for custom range)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format, for custom range)"),
    format: str = Query("json", description="Export format: json")
) -> Dict[str, Any]:
    """
    Export metrics data in specified format

    Currently only JSON format is supported

    Returns:
        {
            "ok": true,
            "data": {
                "full_metrics": {...},  // Complete metrics object from calculator
                "export_time": "2026-01-31T10:30:00Z",
                "format": "json"
            },
            "error": null
        }
    """
    try:
        if format != "json":
            raise ValueError(f"Unsupported export format: {format}. Only 'json' is supported.")

        # Parse time range
        start_dt, end_dt = parse_time_range(time_range, start_time, end_time)

        # Calculate full metrics
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics(start_time=start_dt, end_time=end_dt)

        return {
            "ok": True,
            "data": {
                "full_metrics": metrics,
                "export_time": iso_z(utc_now()),
                "format": format
            },
            "error": None
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}", exc_info=True)
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }
