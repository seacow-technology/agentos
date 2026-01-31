"""Tasks API v0.31 Extensions - Project-Aware Task Operations

Extends tasks.py with v0.4 project-aware endpoints for spec freezing, binding, and artifacts.

New Endpoints:
- POST /api/tasks/{task_id}/spec/freeze - Freeze task spec
- POST /api/tasks/{task_id}/bind - Create/update task binding
- POST /api/tasks/{task_id}/ready - Mark task as ready
- GET /api/tasks/{task_id}/artifacts - List task artifacts
- POST /api/tasks/{task_id}/artifacts - Register task artifact

Created for Task #4 Phase 3: RESTful API Implementation
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentos.core.task.spec_service import TaskSpecService
from agentos.core.task.binding_service import BindingService
from agentos.core.task.artifact_service_v31 import ArtifactService
from agentos.core.task.service import TaskService
from agentos.core.project.errors import (
    SpecNotFoundError,
    SpecAlreadyFrozenError,
    SpecIncompleteError,
    BindingNotFoundError,
    BindingValidationError,
    InvalidWorkdirError,
    ArtifactNotFoundError,
    InvalidKindError,
    UnsafePathError,
    ProjectNotFoundError,
    RepoNotFoundError,
    RepoNotInProjectError,
)
from agentos.core.task.errors import TaskNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class FreezeSpecRequest(BaseModel):
    """Request to freeze task spec (optional, can be empty)"""
    pass


class BindTaskRequest(BaseModel):
    """Request to bind task to project/repo"""
    project_id: str = Field(..., description="Project ID (required)")
    repo_id: Optional[str] = Field(None, description="Repository ID (optional)")
    workdir: Optional[str] = Field(None, description="Working directory (relative path)")


class MarkReadyRequest(BaseModel):
    """Request to mark task as ready (optional, can be empty)"""
    pass


class RegisterArtifactRequest(BaseModel):
    """Request to register task artifact"""
    kind: str = Field(..., description="Artifact kind (file/dir/url/log/report)")
    path: str = Field(..., description="Artifact path or URL")
    display_name: Optional[str] = Field(None, description="Optional display name")
    hash: Optional[str] = Field(None, description="Optional hash (sha256:...)")
    size_bytes: Optional[int] = Field(None, description="Optional size in bytes")


# ============================================================================
# Spec Management Endpoints
# ============================================================================


@router.post("/tasks/{task_id}/spec/freeze")
async def freeze_task_spec(task_id: str) -> Dict[str, Any]:
    """Freeze task spec (DRAFT → PLANNED)

    Process:
        1. Verify spec completeness (title, acceptance_criteria)
        2. Create new spec version (version++)
        3. Set task.spec_frozen = 1
        4. Update task.status = "planned"
        5. Write audit event: TASK_SPEC_FROZEN

    Returns:
        {
            "success": true,
            "task": {...},
            "spec": {...}
        }

    Errors:
        404 - TASK_NOT_FOUND
        400 - SPEC_ALREADY_FROZEN
        400 - SPEC_INCOMPLETE: Missing required fields

    Example:
        POST /api/tasks/task_01HY6XA.../spec/freeze
    """
    try:
        spec_service = TaskSpecService()
        task_service = TaskService()

        # Freeze the spec
        spec = spec_service.freeze_spec(task_id)

        # Get updated task
        task = task_service.get_task(task_id)

        return {
            "success": True,
            "task": task.to_dict() if hasattr(task, 'to_dict') else task.__dict__,
            "spec": spec.to_dict(),
        }

    except (
        TaskNotFoundError,
        SpecAlreadyFrozenError,
        SpecIncompleteError,
        SpecNotFoundError,
    ) as e:
        status_code = 404 if isinstance(e, (TaskNotFoundError, SpecNotFoundError)) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify task exists and spec is complete with title and acceptance_criteria"
            }
        )

    except Exception as e:
        logger.error(f"Failed to freeze spec: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to freeze spec: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


# ============================================================================
# Binding Endpoints
# ============================================================================


@router.post("/tasks/{task_id}/bind")
async def bind_task(
    task_id: str,
    request: BindTaskRequest
) -> Dict[str, Any]:
    """Create or update task binding

    Body:
        {
            "project_id": "proj_xxx",
            "repo_id": "repo_xxx",       # optional
            "workdir": "src/api"         # optional
        }

    Returns:
        {
            "success": true,
            "binding": {...}
        }

    Errors:
        404 - TASK_NOT_FOUND
        404 - PROJECT_NOT_FOUND
        404 - REPO_NOT_FOUND
        400 - REPO_NOT_IN_PROJECT
        400 - INVALID_WORKDIR: Unsafe path

    Example:
        POST /api/tasks/task_01HY6XA.../bind
        {"project_id": "proj_01HY6X9...", "workdir": "backend/api"}
    """
    try:
        binding_service = BindingService()

        # Create or update binding
        binding = binding_service.create_binding(
            task_id=task_id,
            project_id=request.project_id,
            repo_id=request.repo_id,
            workdir=request.workdir,
        )

        return {
            "success": True,
            "binding": binding.to_dict(),
        }

    except (
        TaskNotFoundError,
        ProjectNotFoundError,
        RepoNotFoundError,
        RepoNotInProjectError,
        InvalidWorkdirError,
    ) as e:
        status_code = 404 if isinstance(e, (TaskNotFoundError, ProjectNotFoundError, RepoNotFoundError)) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify task, project, and repo exist, and workdir is a safe relative path"
            }
        )

    except Exception as e:
        logger.error(f"Failed to bind task: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to bind task: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.post("/tasks/{task_id}/ready")
async def mark_task_ready(task_id: str) -> Dict[str, Any]:
    """Mark task as ready (PLANNED → READY)

    Validation:
        - spec_frozen = 1
        - binding.project_id is not null
        - dependencies satisfied

    Process:
        1. Verify binding
        2. Verify spec frozen
        3. Update task.status = "ready"
        4. Write audit event: TASK_READY

    Returns:
        {
            "success": true,
            "task": {...}
        }

    Errors:
        404 - TASK_NOT_FOUND
        400 - SPEC_NOT_FROZEN
        400 - BINDING_INCOMPLETE

    Example:
        POST /api/tasks/task_01HY6XA.../ready
    """
    try:
        binding_service = BindingService()
        task_service = TaskService()

        # Validate binding
        binding_service.validate_binding(task_id)

        # Transition to READY state
        from agentos.core.task.state_machine import TaskStateMachine
        from agentos.core.task.states import TaskState

        state_machine = TaskStateMachine()
        updated_task = state_machine.transition(
            task_id,
            to=TaskState.READY.value,
            actor="api_user",
            reason="Manual transition to READY via API"
        )

        return {
            "success": True,
            "task": updated_task.to_dict() if hasattr(updated_task, 'to_dict') else updated_task.__dict__,
        }

    except (
        TaskNotFoundError,
        BindingNotFoundError,
        BindingValidationError,
    ) as e:
        status_code = 404 if isinstance(e, (TaskNotFoundError, BindingNotFoundError)) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify task exists, spec is frozen, and binding is complete"
            }
        )

    except Exception as e:
        logger.error(f"Failed to mark task ready: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to mark task ready: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


# ============================================================================
# Artifact Endpoints
# ============================================================================


@router.get("/tasks/{task_id}/artifacts")
async def list_task_artifacts(task_id: str) -> Dict[str, Any]:
    """List artifacts for a task

    Returns:
        {
            "success": true,
            "artifacts": [...]
        }

    Errors:
        404 - TASK_NOT_FOUND

    Example:
        GET /api/tasks/task_01HY6XA.../artifacts
    """
    try:
        artifact_service = ArtifactService()

        artifacts = artifact_service.list_artifacts(task_id=task_id)

        return {
            "success": True,
            "artifacts": [a.to_dict() for a in artifacts],
        }

    except TaskNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify the task_id is correct"
            }
        )

    except Exception as e:
        logger.error(f"Failed to list artifacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to list artifacts: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.post("/tasks/{task_id}/artifacts")
async def register_artifact(
    task_id: str,
    request: RegisterArtifactRequest
) -> Dict[str, Any]:
    """Register a task artifact

    Body:
        {
            "kind": "file",                    # file/dir/url/log/report
            "path": "/path/to/artifact",
            "display_name": "Optional name",
            "hash": "sha256:...",              # optional
            "size_bytes": 1024                 # optional
        }

    Returns:
        {
            "success": true,
            "artifact": {...}
        }

    Errors:
        404 - TASK_NOT_FOUND
        400 - INVALID_KIND
        400 - UNSAFE_PATH
        400 - PATH_NOT_FOUND

    Example:
        POST /api/tasks/task_01HY6XA.../artifacts
        {"kind": "file", "path": "/tmp/output.txt"}
    """
    try:
        artifact_service = ArtifactService()

        artifact = artifact_service.register_artifact(
            task_id=task_id,
            kind=request.kind,
            path=request.path,
            display_name=request.display_name,
            hash=request.hash,
            size_bytes=request.size_bytes,
        )

        return {
            "success": True,
            "artifact": artifact.to_dict(),
        }

    except (
        TaskNotFoundError,
        InvalidKindError,
        UnsafePathError,
        ArtifactNotFoundError,
    ) as e:
        status_code = 404 if isinstance(e, (TaskNotFoundError, ArtifactNotFoundError)) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify task exists, kind is valid (file/dir/url/log/report), and path is safe"
            }
        )

    except Exception as e:
        logger.error(f"Failed to register artifact: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to register artifact: {str(e)}",
                "hint": "Check server logs for details"
            }
        )
