"""
Metrics Tracking Middleware

Automatically tracks metrics for all HTTP requests including:
- Request counts by method and status
- Request duration
- Error rates
- Active session counts

Integrates with the metrics API endpoint for reporting.
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics"""

    async def dispatch(self, request: Request, call_next):
        """Track request metrics"""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Record metrics
        try:
            from agentos.webui.api.metrics import get_metrics_collector
            collector = get_metrics_collector()
            collector.record_request(
                method=request.method,
                status=response.status_code,
                duration_ms=duration_ms
            )
        except Exception as e:
            logger.warning(f"Failed to record metrics: {e}")

        # Add response header with duration
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response


def add_metrics_middleware(app: FastAPI):
    """
    Add metrics tracking middleware to FastAPI app

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(MetricsMiddleware)
    logger.info("Metrics tracking middleware enabled")
