"""
Health API - System health status

GET /api/health - Get system health
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import psutil
import os
import shutil

from agentos.store import get_db, get_writer
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


router = APIRouter()

# Global counters for metrics
_request_count = 0
_error_count = 0
_start_time = utc_now()


class HealthStatus(BaseModel):
    """Health status response"""
    status: str  # "ok" | "warn" | "down"
    timestamp: str
    uptime_seconds: Optional[float] = None
    components: Dict[str, Any]
    metrics: Dict[str, Any]


def check_db_health() -> Dict[str, Any]:
    """Check database health"""
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        # Do NOT close: get_db() returns shared thread-local connection
        return {"status": "ok", "message": "Database operational"}
    except Exception as e:
        return {"status": "down", "message": f"Database error: {str(e)}"}


def check_extensions_health() -> Dict[str, Any]:
    """Check extensions health"""
    try:
        from agentos.core.extensions.registry import ExtensionRegistry
        registry = ExtensionRegistry()

        # Count installed extensions
        # Note: registry._get_connection() creates a NEW connection, so closing is correct
        conn = registry._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM extensions WHERE status = 'installed'")
        installed_count = cursor.fetchone()[0]
        conn.close()  # OK: This is a new connection, not from get_db()

        return {
            "status": "ok",
            "installed_count": installed_count,
            "message": f"{installed_count} extensions installed"
        }
    except Exception as e:
        return {"status": "warn", "message": f"Extensions check failed: {str(e)}"}


def check_mcp_health() -> Dict[str, Any]:
    """Check MCP servers health"""
    try:
        from agentos.core.mcp.marketplace_registry import MCPMarketplaceRegistry
        registry = MCPMarketplaceRegistry()

        # Count installed MCP servers
        installed = registry.list_installed()
        active_count = len([s for s in installed if s.get("status") == "running"])

        return {
            "status": "ok" if active_count > 0 else "warn",
            "installed_count": len(installed),
            "active_count": active_count,
            "message": f"{active_count}/{len(installed)} MCP servers active"
        }
    except Exception as e:
        return {"status": "warn", "message": f"MCP check failed: {str(e)}"}


def check_queue_health() -> Dict[str, Any]:
    """Check SQLiteWriter queue health"""
    try:
        writer = get_writer()
        if not writer:
            return {"status": "unknown", "message": "Writer not initialized"}

        queue_size = writer.queue_size
        high_water = writer.queue_high_water_mark

        status = "ok"
        if queue_size > 100:
            status = "critical"
        elif queue_size > 50:
            status = "warn"

        return {
            "status": status,
            "queue_size": queue_size,
            "high_water_mark": high_water,
            "message": f"Queue size: {queue_size} (high water: {high_water})"
        }
    except Exception as e:
        return {"status": "warn", "message": f"Queue check failed: {str(e)}"}


def check_networkos_health() -> Dict[str, Any]:
    """Check NetworkOS database health"""
    try:
        from agentos.networkos.health import NetworkOSHealthCheck

        checker = NetworkOSHealthCheck()
        all_passed, results = checker.run_all_checks()

        status = "ok" if all_passed else "error"

        # If DB doesn't exist, downgrade to warning (will be created on first use)
        if not all_passed and 'check_db_exists' in results.get('summary', {}).get('checks_failed', []):
            status = "warn"

        return {
            "status": status,
            "all_passed": all_passed,
            "passed_count": results.get('summary', {}).get('passed_count', 0),
            "failed_count": results.get('summary', {}).get('failed_count', 0),
            "checks_failed": results.get('summary', {}).get('checks_failed', []),
            "message": f"NetworkOS health: {status}"
        }
    except Exception as e:
        return {"status": "warn", "message": f"NetworkOS check failed: {str(e)}"}


def check_disk_space() -> Dict[str, Any]:
    """Check disk space"""
    try:
        # Check disk space for the store directory
        from agentos.store import get_db_path
        db_path = get_db_path()
        usage = shutil.disk_usage(db_path.parent)

        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        percent_used = (usage.used / usage.total) * 100

        status = "ok"
        if percent_used > 95:
            status = "critical"
        elif percent_used > 90:
            status = "warn"

        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent_used": round(percent_used, 2),
            "message": f"{round(free_gb, 1)}GB free ({100 - round(percent_used, 1)}%)"
        }
    except Exception as e:
        return {"status": "warn", "message": f"Disk check failed: {str(e)}"}


def get_uptime() -> float:
    """Get system uptime in seconds"""
    return (utc_now() - _start_time).total_seconds()


def get_request_count() -> int:
    """Get total request count"""
    return _request_count


def get_error_count() -> int:
    """Get error count in the last hour"""
    # This is a simple counter, in production should be time-windowed
    return _error_count


@router.get("/health")
async def get_health() -> HealthStatus:
    """
    Get comprehensive system health status

    Returns:
        HealthStatus with overall status and component details
    """
    try:
        # Check all components
        db_health = check_db_health()
        extensions_health = check_extensions_health()
        mcp_health = check_mcp_health()
        queue_health = check_queue_health()
        disk_health = check_disk_space()
        networkos_health = check_networkos_health()

        # Get process metrics
        process = psutil.Process(os.getpid())
        uptime = utc_now().timestamp() - process.create_time()

        # Determine overall status
        overall_status = "ok"
        if db_health["status"] == "down":
            overall_status = "down"
        elif any(c.get("status") == "critical" for c in [queue_health, disk_health]):
            overall_status = "critical"
        elif any(c.get("status") == "warn" for c in [extensions_health, mcp_health, queue_health, disk_health, networkos_health]):
            overall_status = "warn"

        components = {
            "database": db_health,
            "extensions": extensions_health,
            "mcp_servers": mcp_health,
            "queue": queue_health,
            "disk": disk_health,
            "networkos": networkos_health,
        }

        metrics = {
            "uptime_seconds": round(get_uptime(), 2),
            "requests_total": get_request_count(),
            "errors_last_hour": get_error_count(),
            "cpu_percent": process.cpu_percent(),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "pid": os.getpid(),
        }

        return HealthStatus(
            status=overall_status,
            timestamp=iso_z(utc_now()),
            uptime_seconds=uptime,
            components=components,
            metrics=metrics,
        )

    except Exception as e:
        return HealthStatus(
            status="down",
            timestamp=iso_z(utc_now()),
            components={"error": str(e)},
            metrics={},
        )


@router.get("/autocomm")
async def get_autocomm_health() -> Dict[str, Any]:
    """
    Check AutoComm subsystem health

    Tests the availability and health of AutoComm components:
    - CommunicationAdapter
    - AutoCommPolicy

    Returns:
        Dict with status and component health information
    """
    try:
        # Try instantiating the components
        from agentos.core.chat.communication_adapter import CommunicationAdapter
        from agentos.core.chat.auto_comm_policy import AutoCommPolicy

        # Test adapter
        adapter_status = "ok"
        adapter_message = "CommunicationAdapter initialized successfully"
        try:
            adapter = CommunicationAdapter()
        except Exception as e:
            adapter_status = "error"
            adapter_message = f"Failed to initialize: {str(e)}"

        # Test policy
        policy_status = "ok"
        policy_message = "AutoCommPolicy initialized successfully"
        policy_enabled = None
        try:
            policy = AutoCommPolicy()
            policy_enabled = policy.enabled
            policy_message = f"AutoCommPolicy initialized (enabled={policy_enabled})"
        except Exception as e:
            policy_status = "error"
            policy_message = f"Failed to initialize: {str(e)}"

        # Determine overall status
        if adapter_status == "error" or policy_status == "error":
            overall_status = "unhealthy"
        elif policy_enabled is False:
            overall_status = "disabled"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": iso_z(utc_now()),
            "components": {
                "adapter": {
                    "status": adapter_status,
                    "message": adapter_message
                },
                "policy": {
                    "status": policy_status,
                    "enabled": policy_enabled,
                    "message": policy_message
                }
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": iso_z(utc_now()),
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/writer-stats")
async def get_writer_stats() -> Dict[str, Any]:
    """
    Get SQLiteWriter monitoring statistics

    Returns real-time metrics for the database writer including:
    - Queue status and backlog
    - Write performance metrics
    - Retry and failure counts
    - Throughput and latency statistics

    Returns:
        Dict containing all writer monitoring metrics
        Returns error dict if writer not initialized
    """
    try:
        # Get the global writer instance
        writer = get_writer()

        if writer:
            stats = writer.get_stats()

            # Add health status based on metrics
            status = "ok"
            warnings = []

            if stats["queue_size"] > 100:
                status = "critical"
                warnings.append("Queue backlog critical - immediate action required")
            elif stats["queue_size"] > 50:
                status = "warning"
                warnings.append("Queue backlog detected - consider optimization")

            if stats["failed_writes"] > 0:
                failure_rate = stats["failed_writes"] / max(stats["total_writes"], 1)
                if failure_rate > 0.01:  # >1% failure rate
                    status = "warning"
                    warnings.append(f"High failure rate: {failure_rate*100:.1f}%")

            stats["status"] = status
            if warnings:
                stats["warnings"] = warnings

            return stats
        else:
            return {
                "error": "Writer not initialized",
                "status": "unavailable",
                "message": "SQLiteWriter has not been initialized yet"
            }

    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "message": "Failed to retrieve writer statistics"
        }
