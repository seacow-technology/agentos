"""
Extension Execution API

Provides endpoints for executing extension capabilities and tracking run progress.

Part of PR-E1: Runner Infrastructure
"""

import logging
import threading
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from agentos.core.capabilities.runner_base import Invocation, get_runner
from agentos.core.runs import RunStore, RunStatus
from agentos.webui.api.contracts import ReasonCode

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (initialized on startup)
_run_store: Optional[RunStore] = None
_builtin_runner = None


def get_run_store() -> RunStore:
    """Get run store instance"""
    global _run_store
    if _run_store is None:
        _run_store = RunStore(retention_hours=1)
    return _run_store


def get_builtin_runner():
    """Get builtin runner instance"""
    global _builtin_runner
    if _builtin_runner is None:
        _builtin_runner = get_runner("builtin", default_timeout=30)
    return _builtin_runner


# ============================================
# Request/Response Models
# ============================================

class ExecuteRequest(BaseModel):
    """Execute extension capability request"""
    session_id: str = Field(description="Chat session ID")
    command: str = Field(description="Slash command to execute (e.g., '/test hello')")
    dry_run: bool = Field(default=False, description="Dry run mode (validate only)")


class ExecuteResponse(BaseModel):
    """Execute response with run ID"""
    run_id: str = Field(description="Run identifier for tracking progress")
    status: str = Field(description="Initial status (PENDING)")


class RunStatusResponse(BaseModel):
    """Run status and progress response"""
    run_id: str
    extension_id: str
    action_id: str
    status: str
    progress_pct: int = Field(ge=0, le=100)
    current_stage: Optional[str] = None
    stages: list = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================
# API Endpoints
# ============================================

@router.post("/api/extensions/execute", response_model=ExecuteResponse)
async def execute_extension(req: ExecuteRequest = Body(...)):
    """
    Execute an extension capability

    Body:
    {
        "session_id": "sess_abc123",
        "command": "/test hello world",
        "dry_run": false
    }

    Returns:
    {
        "run_id": "run_abc123def456",
        "status": "PENDING"
    }

    The execution runs asynchronously. Use GET /api/runs/{run_id} to track progress.
    """
    try:
        # Import SlashCommandRouter
        from agentos.core.chat.slash_command_router import SlashCommandRouter
        from agentos.core.extensions.registry import ExtensionRegistry

        # Validate command format
        if not req.command.strip().startswith('/'):
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Invalid command format",
                    "hint": "Command must start with '/' (e.g., '/test hello')",
                    "reason_code": ReasonCode.INVALID_INPUT
                }
            )

        # Route command using SlashCommandRouter
        registry = ExtensionRegistry()
        router_instance = SlashCommandRouter(registry)
        route = router_instance.route(req.command)

        if not route:
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Command not found: {req.command.split()[0]}",
                    "hint": "Check available extensions and commands",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        # Check if extension is enabled
        if not route.extension_enabled:
            raise HTTPException(
                status_code=403,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Extension '{route.extension_name}' is disabled",
                    "hint": f"Enable the extension to use {route.command_name}",
                    "reason_code": ReasonCode.PERMISSION_DENIED
                }
            )

        # Create run record
        run_store = get_run_store()
        run = run_store.create_run(
            extension_id=route.extension_id,
            action_id=route.action_id or "default",
            metadata={
                "session_id": req.session_id,
                "command": req.command,
                "command_name": route.command_name,
                "runner": route.runner,
                "dry_run": req.dry_run
            }
        )

        # Create invocation
        invocation = Invocation(
            extension_id=route.extension_id,
            action_id=route.action_id or "default",
            session_id=req.session_id,
            args=route.args,
            flags={"dry_run": req.dry_run},
            metadata={
                "command_name": route.command_name,
                "runner": route.runner
            }
        )

        # Execute in background thread
        def run_execution():
            try:
                # Select runner based on route.runner field
                runner_type = route.runner

                # Map runner types
                if runner_type in ("exec.python_handler", "builtin", "default"):
                    runner = get_builtin_runner()
                elif runner_type == "shell" or runner_type.startswith("exec.shell"):
                    # Shell runner not yet implemented
                    run_store.complete_run(
                        run_id=run.run_id,
                        status=RunStatus.FAILED,
                        error=f"ShellRunner not yet implemented (runner={runner_type})"
                    )
                    return
                else:
                    # Default to builtin runner
                    logger.warning(f"Unknown runner type '{runner_type}', using builtin")
                    runner = get_builtin_runner()

                # Progress callback
                def progress_cb(stage: str, pct: int, message: str):
                    run_store.update_progress(
                        run_id=run.run_id,
                        stage=stage,
                        progress_pct=pct,
                        message=message
                    )

                # Execute
                result = runner.run(invocation, progress_cb=progress_cb)

                # Update run with result
                if result.success:
                    run_store.complete_run(
                        run_id=run.run_id,
                        status=RunStatus.SUCCEEDED,
                        stdout=result.output,
                        error=None
                    )
                else:
                    run_store.complete_run(
                        run_id=run.run_id,
                        status=RunStatus.FAILED,
                        stdout=result.output,
                        stderr=result.error or "",
                        error=result.error
                    )

            except Exception as e:
                logger.error(f"Execution failed: {e}", exc_info=True)
                run_store.complete_run(
                    run_id=run.run_id,
                    status=RunStatus.FAILED,
                    error=str(e)
                )

        # Start execution thread
        thread = threading.Thread(target=run_execution, daemon=True)
        thread.start()

        return ExecuteResponse(
            run_id=run.run_id,
            status=run.status.value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Failed to start execution: {str(e)}",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """
    Get run status and progress

    Returns:
    {
        "run_id": "run_abc123def456",
        "extension_id": "test.hello",
        "action_id": "execute",
        "status": "RUNNING",
        "progress_pct": 60,
        "current_stage": "EXECUTING",
        "stages": [
            {
                "stage": "VALIDATING",
                "progress_pct": 5,
                "message": "Validating invocation parameters",
                "timestamp": "2024-01-30T10:00:00Z"
            },
            ...
        ],
        "stdout": "Mock execution output...",
        "stderr": "",
        "error": null,
        "started_at": "2024-01-30T10:00:00Z",
        "ended_at": null,
        "duration_seconds": null,
        "metadata": {...}
    }
    """
    try:
        run_store = get_run_store()
        run = run_store.get_run(run_id)

        if run is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Run not found: {run_id}",
                    "hint": "Check the run ID and try again",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        return RunStatusResponse(
            run_id=run.run_id,
            extension_id=run.extension_id,
            action_id=run.action_id,
            status=run.status.value,
            progress_pct=run.progress_pct,
            current_stage=run.current_stage,
            stages=run.stages,
            stdout=run.stdout,
            stderr=run.stderr,
            error=run.error,
            started_at=run.started_at.isoformat() if run.started_at else None,
            ended_at=run.ended_at.isoformat() if run.ended_at else None,
            duration_seconds=run.duration_seconds,
            metadata=run.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get run status",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/runs", response_model=Dict[str, Any])
async def list_runs(
    extension_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """
    List runs with optional filtering

    Query params:
    - extension_id: Filter by extension
    - status: Filter by status (PENDING, RUNNING, SUCCEEDED, FAILED, etc.)
    - limit: Maximum number of runs to return (default: 100)

    Returns:
    {
        "runs": [...],
        "total": 10
    }
    """
    try:
        run_store = get_run_store()

        # Parse status filter
        status_enum = None
        if status:
            try:
                status_enum = RunStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "ok": False,
                        "data": None,
                        "error": f"Invalid status: {status}",
                        "hint": f"Valid statuses: {[s.value for s in RunStatus]}",
                        "reason_code": ReasonCode.INVALID_INPUT
                    }
                )

        # List runs
        runs = run_store.list_runs(
            extension_id=extension_id,
            status=status_enum,
            limit=limit
        )

        # Convert to dict
        runs_data = [run.to_dict() for run in runs]

        return {
            "runs": runs_data,
            "total": len(runs_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list runs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to list runs",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )
