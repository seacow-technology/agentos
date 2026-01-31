"""
Metrics API - Prometheus-compatible metrics endpoint

GET /api/metrics - Get system metrics in Prometheus format
GET /api/metrics/json - Get system metrics in JSON format
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime, timezone
import time

from agentos.store import get_writer
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


router = APIRouter()


class MetricsSnapshot(BaseModel):
    """Metrics snapshot in JSON format"""
    timestamp: str
    metrics: Dict[str, Any]


# Global metrics storage
class MetricsCollector:
    """Simple in-memory metrics collector"""

    def __init__(self):
        self.start_time = time.time()
        self.http_requests_total = 0
        self.http_requests_by_method = {}
        self.http_requests_by_status = {}
        self.http_request_durations = []
        self.active_sessions = 0
        self.errors_total = 0

    def record_request(self, method: str, status: int, duration_ms: float):
        """Record an HTTP request"""
        self.http_requests_total += 1
        self.http_requests_by_method[method] = self.http_requests_by_method.get(method, 0) + 1
        self.http_requests_by_status[status] = self.http_requests_by_status.get(status, 0) + 1
        self.http_request_durations.append(duration_ms)

        # Keep only last 1000 durations
        if len(self.http_request_durations) > 1000:
            self.http_request_durations = self.http_request_durations[-1000:]

        # Track errors (4xx and 5xx)
        if status >= 400:
            self.errors_total += 1

    def get_percentile(self, percentile: float) -> float:
        """Get percentile of request durations"""
        if not self.http_request_durations:
            return 0.0
        sorted_durations = sorted(self.http_request_durations)
        index = int(len(sorted_durations) * percentile / 100)
        return sorted_durations[index]

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        uptime = time.time() - self.start_time

        # Get queue metrics
        queue_size = 0
        db_connections = 0
        try:
            writer = get_writer()
            if writer:
                queue_size = writer.queue_size
                db_connections = 1  # SQLiteWriter uses single connection
        except:
            pass

        # Calculate request rate
        requests_per_second = self.http_requests_total / uptime if uptime > 0 else 0

        # Calculate error rate
        error_rate = (self.errors_total / self.http_requests_total) if self.http_requests_total > 0 else 0

        return {
            "http_requests_total": self.http_requests_total,
            "http_requests_by_method": self.http_requests_by_method,
            "http_requests_by_status": self.http_requests_by_status,
            "http_request_duration_p50_ms": self.get_percentile(50),
            "http_request_duration_p95_ms": self.get_percentile(95),
            "http_request_duration_p99_ms": self.get_percentile(99),
            "active_sessions": self.active_sessions,
            "queue_size": queue_size,
            "db_connections": db_connections,
            "errors_total": self.errors_total,
            "error_rate": round(error_rate, 4),
            "requests_per_second": round(requests_per_second, 2),
            "uptime_seconds": round(uptime, 2),
        }

    def to_prometheus_format(self, metrics: Dict[str, Any]) -> str:
        """Convert metrics to Prometheus text format"""
        lines = []

        # Simple gauge metrics
        lines.append(f"# HELP http_requests_total Total number of HTTP requests")
        lines.append(f"# TYPE http_requests_total counter")
        lines.append(f"http_requests_total {metrics['http_requests_total']}")
        lines.append("")

        # Requests by method
        lines.append(f"# HELP http_requests_by_method_total HTTP requests by method")
        lines.append(f"# TYPE http_requests_by_method_total counter")
        for method, count in metrics['http_requests_by_method'].items():
            lines.append(f'http_requests_by_method_total{{method="{method}"}} {count}')
        lines.append("")

        # Requests by status code
        lines.append(f"# HELP http_requests_by_status_total HTTP requests by status code")
        lines.append(f"# TYPE http_requests_by_status_total counter")
        for status, count in metrics['http_requests_by_status'].items():
            lines.append(f'http_requests_by_status_total{{status="{status}"}} {count}')
        lines.append("")

        # Request duration percentiles (in milliseconds)
        lines.append(f"# HELP http_request_duration_milliseconds HTTP request duration")
        lines.append(f"# TYPE http_request_duration_milliseconds summary")
        lines.append(f'http_request_duration_milliseconds{{quantile="0.5"}} {metrics["http_request_duration_p50_ms"]}')
        lines.append(f'http_request_duration_milliseconds{{quantile="0.95"}} {metrics["http_request_duration_p95_ms"]}')
        lines.append(f'http_request_duration_milliseconds{{quantile="0.99"}} {metrics["http_request_duration_p99_ms"]}')
        lines.append("")

        # Active sessions
        lines.append(f"# HELP active_sessions Number of active sessions")
        lines.append(f"# TYPE active_sessions gauge")
        lines.append(f"active_sessions {metrics['active_sessions']}")
        lines.append("")

        # Queue size
        lines.append(f"# HELP queue_size Current queue size")
        lines.append(f"# TYPE queue_size gauge")
        lines.append(f"queue_size {metrics['queue_size']}")
        lines.append("")

        # DB connections
        lines.append(f"# HELP db_connections Number of database connections")
        lines.append(f"# TYPE db_connections gauge")
        lines.append(f"db_connections {metrics['db_connections']}")
        lines.append("")

        # Error metrics
        lines.append(f"# HELP errors_total Total number of errors")
        lines.append(f"# TYPE errors_total counter")
        lines.append(f"errors_total {metrics['errors_total']}")
        lines.append("")

        lines.append(f"# HELP error_rate Error rate (errors/requests)")
        lines.append(f"# TYPE error_rate gauge")
        lines.append(f"error_rate {metrics['error_rate']}")
        lines.append("")

        # Throughput
        lines.append(f"# HELP requests_per_second Request throughput")
        lines.append(f"# TYPE requests_per_second gauge")
        lines.append(f"requests_per_second {metrics['requests_per_second']}")
        lines.append("")

        # Uptime
        lines.append(f"# HELP uptime_seconds System uptime in seconds")
        lines.append(f"# TYPE uptime_seconds counter")
        lines.append(f"uptime_seconds {metrics['uptime_seconds']}")
        lines.append("")

        return "\n".join(lines)


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _metrics_collector


@router.get("")
async def get_metrics() -> Response:
    """
    Get system metrics in Prometheus text format

    This endpoint is compatible with Prometheus scrapers.

    Returns:
        Metrics in Prometheus exposition format
    """
    collector = get_metrics_collector()
    metrics = collector.get_metrics()
    prometheus_text = collector.to_prometheus_format(metrics)

    return Response(
        content=prometheus_text,
        media_type="text/plain; version=0.0.4"
    )


@router.get("/json")
async def get_metrics_json() -> MetricsSnapshot:
    """
    Get system metrics in JSON format

    Returns:
        MetricsSnapshot with current metrics
    """
    collector = get_metrics_collector()
    metrics = collector.get_metrics()

    return MetricsSnapshot(
        timestamp=iso_z(utc_now()),
        metrics=metrics
    )
