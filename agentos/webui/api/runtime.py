"""
Runtime API - System runtime management

Endpoints for managing runtime state, permissions, and system health.

v0.3.2 Closeout - Security hardening
"""

import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class RuntimeModeResponse(BaseModel):
    """Response for runtime mode detection"""
    mode: str  # "local" or "cloud"


class PermissionsFixResponse(BaseModel):
    """Response for permissions fix operation"""
    ok: bool
    message: str
    fixed_files: list[str] = []


@router.get("/mode")
async def get_runtime_mode() -> RuntimeModeResponse:
    """
    Get current runtime mode

    Returns "local" for local development, "cloud" for hosted environments.
    Currently always returns "local" as the system runs locally.

    Returns:
        RuntimeModeResponse with mode field
    """
    # For now, always local mode
    # In future, could detect based on environment variables or deployment context
    return RuntimeModeResponse(mode="local")


@router.post("/fix-permissions")
async def fix_permissions() -> PermissionsFixResponse:
    """
    Fix file permissions for sensitive files

    Sets secrets file to chmod 600 (owner read/write only).

    This is a safe operation that only modifies permissions on:
    - ~/.agentos/secrets/providers.json

    Returns:
        - ok: True if successful
        - message: Status message
        - fixed_files: List of files that were fixed
    """
    secrets_file = Path.home() / ".agentos" / "secrets" / "providers.json"
    fixed_files = []

    try:
        if not secrets_file.exists():
            return PermissionsFixResponse(
                ok=True,
                message="No secrets file exists yet",
                fixed_files=[],
            )

        # Windows 兼容: 跳过权限检查
        import platform
        if platform.system() == "Windows":
            return PermissionsFixResponse(
                ok=True,
                message="Permission checks skipped on Windows (uses ACL)",
                fixed_files=[],
            )

        # Check current permissions
        stat_info = secrets_file.stat()
        current_mode = stat_info.st_mode & 0o777

        if current_mode == 0o600:
            return PermissionsFixResponse(
                ok=True,
                message="Permissions already correct (600)",
                fixed_files=[],
            )

        # Fix permissions
        os.chmod(secrets_file, 0o600)
        fixed_files.append(str(secrets_file))

        logger.info(f"Fixed permissions on {secrets_file}: {oct(current_mode)[2:]} -> 600")

        return PermissionsFixResponse(
            ok=True,
            message=f"Fixed permissions: {oct(current_mode)[2:]} -> 600",
            fixed_files=fixed_files,
        )

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Permission denied. Cannot modify file permissions.",
        )
    except Exception as e:
        logger.error(f"Failed to fix permissions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix permissions: {str(e)}",
        )
