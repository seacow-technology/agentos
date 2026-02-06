"""
MCP Health Checker - Monitor MCP server health

This module provides health monitoring for MCP servers, including:
- Connection status checks
- Periodic health monitoring
- Graceful degradation on failures

Health Status:
- HEALTHY: Server is responsive and functioning
- DEGRADED: Server is responsive but experiencing issues
- UNHEALTHY: Server is not responsive or has failed
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from agentos.core.mcp.client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    """
    Result of a health check

    Attributes:
        status: Current health status
        timestamp: When the check was performed
        message: Human-readable status message
        response_time_ms: Response time in milliseconds
        consecutive_failures: Number of consecutive failures
    """

    def __init__(
        self,
        status: HealthStatus,
        message: str,
        response_time_ms: Optional[int] = None,
        consecutive_failures: int = 0
    ):
        self.status = status
        self.timestamp = datetime.now()
        self.message = message
        self.response_time_ms = response_time_ms
        self.consecutive_failures = consecutive_failures

    def __repr__(self):
        return (
            f"HealthCheckResult(status={self.status}, message={self.message}, "
            f"response_time_ms={self.response_time_ms})"
        )


class MCPHealthChecker:
    """
    Health checker for MCP servers

    Performs periodic health checks and tracks server status.
    Can run in background to continuously monitor server health.

    Example:
        checker = MCPHealthChecker(client)
        result = await checker.check_health()
        if result.status == HealthStatus.HEALTHY:
            print("Server is healthy")

        # Start continuous monitoring
        await checker.start_monitoring(interval_seconds=60)
    """

    def __init__(
        self,
        client: MCPClient,
        failure_threshold: int = 3,
        degraded_threshold_ms: int = 5000
    ):
        """
        Initialize health checker

        Args:
            client: MCP client to monitor
            failure_threshold: Number of consecutive failures before marking UNHEALTHY
            degraded_threshold_ms: Response time threshold for DEGRADED status
        """
        self.client = client
        self.failure_threshold = failure_threshold
        self.degraded_threshold_ms = degraded_threshold_ms

        self._consecutive_failures = 0
        self._last_check: Optional[HealthCheckResult] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 60  # seconds

    async def check_health(self) -> HealthCheckResult:
        """
        Perform a health check

        Checks if the server is alive and responsive by attempting
        to list tools.

        Returns:
            HealthCheckResult
        """
        start_time = datetime.now()

        try:
            # Check if client is alive
            if not self.client.is_alive():
                self._consecutive_failures += 1
                logger.warning(
                    f"MCP server not alive: {self.client.config.id} "
                    f"(failures: {self._consecutive_failures})"
                )

                status = (
                    HealthStatus.UNHEALTHY
                    if self._consecutive_failures >= self.failure_threshold
                    else HealthStatus.DEGRADED
                )

                result = HealthCheckResult(
                    status=status,
                    message="Server process not running",
                    consecutive_failures=self._consecutive_failures
                )
                self._last_check = result
                return result

            # Try to list tools as a health check
            await self.client.list_tools()

            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            response_time_ms = int(response_time)

            # Reset failure count on success
            self._consecutive_failures = 0

            # Determine status based on response time
            if response_time_ms > self.degraded_threshold_ms:
                status = HealthStatus.DEGRADED
                message = f"Server responding slowly ({response_time_ms}ms)"
                logger.warning(f"MCP server degraded: {self.client.config.id} - {message}")
            else:
                status = HealthStatus.HEALTHY
                message = "Server healthy"
                logger.debug(f"MCP server healthy: {self.client.config.id} ({response_time_ms}ms)")

            result = HealthCheckResult(
                status=status,
                message=message,
                response_time_ms=response_time_ms,
                consecutive_failures=0
            )

            self._last_check = result
            return result

        except MCPClientError as e:
            self._consecutive_failures += 1
            logger.error(
                f"Health check failed for MCP server {self.client.config.id}: {e} "
                f"(failures: {self._consecutive_failures})"
            )

            status = (
                HealthStatus.UNHEALTHY
                if self._consecutive_failures >= self.failure_threshold
                else HealthStatus.DEGRADED
            )

            result = HealthCheckResult(
                status=status,
                message=f"Health check error: {e}",
                consecutive_failures=self._consecutive_failures
            )

            self._last_check = result
            return result

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(
                f"Unexpected error in health check for {self.client.config.id}: {e}",
                exc_info=True
            )

            status = (
                HealthStatus.UNHEALTHY
                if self._consecutive_failures >= self.failure_threshold
                else HealthStatus.DEGRADED
            )

            result = HealthCheckResult(
                status=status,
                message=f"Unexpected error: {e}",
                consecutive_failures=self._consecutive_failures
            )

            self._last_check = result
            return result

    async def start_monitoring(self, interval_seconds: int = 60):
        """
        Start periodic health monitoring

        Runs health checks in the background at the specified interval.

        Args:
            interval_seconds: Time between health checks in seconds
        """
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning(
                f"Health monitoring already running for {self.client.config.id}"
            )
            return

        self._monitoring_interval = interval_seconds
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info(
            f"Started health monitoring for MCP server {self.client.config.id} "
            f"(interval: {interval_seconds}s)"
        )

    async def stop_monitoring(self):
        """
        Stop periodic health monitoring
        """
        if not self._monitoring_task or self._monitoring_task.done():
            logger.debug(f"No active monitoring for {self.client.config.id}")
            return

        self._monitoring_task.cancel()
        try:
            await self._monitoring_task
        except asyncio.CancelledError:
            pass

        self._monitoring_task = None
        logger.info(f"Stopped health monitoring for MCP server {self.client.config.id}")

    async def _monitoring_loop(self):
        """
        Background monitoring loop

        Continuously performs health checks at the configured interval.
        """
        logger.debug(f"Health monitoring loop started for {self.client.config.id}")

        try:
            while True:
                # Perform health check
                result = await self.check_health()

                # Log status changes
                if self._last_check and result.status != self._last_check.status:
                    logger.info(
                        f"MCP server {self.client.config.id} status changed: "
                        f"{self._last_check.status} -> {result.status}"
                    )

                # Wait for next check
                await asyncio.sleep(self._monitoring_interval)

        except asyncio.CancelledError:
            logger.debug(f"Health monitoring cancelled for {self.client.config.id}")
            raise

        except Exception as e:
            logger.error(
                f"Error in health monitoring loop for {self.client.config.id}: {e}",
                exc_info=True
            )

    def get_last_check(self) -> Optional[HealthCheckResult]:
        """
        Get result of last health check

        Returns:
            Last HealthCheckResult or None if no checks performed
        """
        return self._last_check

    def is_healthy(self) -> bool:
        """
        Check if server is currently healthy

        Returns:
            True if last check was HEALTHY, False otherwise
        """
        if not self._last_check:
            return False

        return self._last_check.status == HealthStatus.HEALTHY

    def is_available(self) -> bool:
        """
        Check if server is available (HEALTHY or DEGRADED)

        Returns:
            True if server is available for use, False if UNHEALTHY
        """
        if not self._last_check:
            # No check performed yet, assume available
            return True

        return self._last_check.status != HealthStatus.UNHEALTHY

    def reset_failures(self):
        """
        Reset consecutive failure count

        Useful for manual recovery after resolving issues.
        """
        logger.info(f"Resetting failure count for MCP server {self.client.config.id}")
        self._consecutive_failures = 0
