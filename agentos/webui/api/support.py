"""
Support API - Diagnostic and troubleshooting endpoints

v0.3.2 Closeout #5: Diagnostic bundle for support and debugging
"""

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel

from agentos.providers.registry import ProviderRegistry
from agentos.core.status_store import StatusStore
from agentos.selfcheck import SelfCheckRunner
from agentos.webui.middleware import sanitize_response


from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

router = APIRouter()


class DiagnosticBundleResponse(BaseModel):
    """Diagnostic bundle response"""
    ts: str
    version: str
    system: Dict[str, Any]
    providers: List[Dict[str, Any]]
    selfcheck: Dict[str, Any]
    cache_stats: Dict[str, Any]


@router.get("/diagnostic-bundle")
async def get_diagnostic_bundle() -> DiagnosticBundleResponse:
    """
    Generate diagnostic bundle for support and debugging

    Collects comprehensive system state including:
    - System information (Python, OS, platform)
    - Provider status (all providers)
    - Self-check results (no network calls)
    - Cache statistics

    All sensitive data (API keys, tokens) are automatically masked.

    Use this endpoint to:
    - Troubleshoot issues
    - Generate support tickets
    - Verify system configuration

    Returns:
        Complete diagnostic bundle with sanitized data
    """
    # System info
    system_info = {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "architecture": platform.architecture()[0],
        "hostname": platform.node(),
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
    }

    # Get provider status from StatusStore
    store = StatusStore.get_instance()
    provider_status_list, ttl = await store.get_all_provider_status(ttl_ms=5000)

    providers_info = []
    for status in provider_status_list:
        providers_info.append({
            "id": status.id,
            "type": status.type.value,
            "state": status.state.value,
            "endpoint": status.endpoint,
            "latency_ms": status.latency_ms,
            "last_ok_at": status.last_ok_at,
            "last_error": status.last_error,
            "reason_code": status.reason_code,
            "hint": status.hint,
        })

    # Run self-check (no network calls)
    runner = SelfCheckRunner()
    selfcheck_result = await runner.run(
        session_id=None,
        include_network=False,  # Use cached status only
        include_context=True,
    )

    selfcheck_info = {
        "summary": selfcheck_result.summary,
        "ts": selfcheck_result.ts,
        "items": [
            {
                "id": item.id,
                "group": item.group,
                "name": item.name,
                "status": item.status,
                "detail": item.detail,
                "hint": item.hint,
            }
            for item in selfcheck_result.items
        ],
    }

    # Cache statistics
    cache_stats = store.get_stats()

    # Get version
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).parent.parent.parent,
        )
        if result.returncode == 0:
            version = f"0.3.2 (git {result.stdout.strip()})"
        else:
            version = "0.3.2"
    except Exception:
        version = "0.3.2"

    # Build response
    response = DiagnosticBundleResponse(
        ts=iso_z(utc_now()),
        version=version,
        system=system_info,
        providers=providers_info,
        selfcheck=selfcheck_info,
        cache_stats=cache_stats,
    )

    # Apply sanitization to mask any sensitive data
    return sanitize_response(response.model_dump())
