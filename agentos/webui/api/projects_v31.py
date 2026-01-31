"""Projects API v0.31 - Project-Aware Task OS

Implements v0.4 project management endpoints that expose Phase 2 Services as HTTP API.

Endpoints:
- GET /api/projects - List projects with pagination and tag filtering
- POST /api/projects - Create new project
- GET /api/projects/{project_id} - Get project details
- PATCH /api/projects/{project_id} - Update project
- DELETE /api/projects/{project_id} - Delete project (force option)
- GET /api/projects/{project_id}/repos - List repos in project
- POST /api/projects/{project_id}/repos - Add repo to project

Created for Task #4 Phase 3: RESTful API Implementation
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request, HTTPException, Header
from pydantic import BaseModel, Field

from agentos.core.project.service import ProjectService
from agentos.core.project.repo_service import RepoService
from agentos.core.project.idempotency import get_idempotency_store
from agentos.core.project.errors import (
    ProjectNotFoundError,
    ProjectNameConflictError,
    ProjectHasTasksError,
    RepoNotFoundError,
    RepoNameConflictError,
    InvalidPathError,
    PathNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateProjectRequest(BaseModel):
    """Request to create a new project"""
    name: str = Field(..., min_length=1, max_length=200, description="Project name (unique)")
    description: Optional[str] = Field(None, description="Project description")
    tags: Optional[List[str]] = Field(default_factory=list, description="Project tags")
    default_repo_id: Optional[str] = Field(None, description="Default repository ID")


class UpdateProjectRequest(BaseModel):
    """Request to update project fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="New project name")
    description: Optional[str] = Field(None, description="New description")
    tags: Optional[List[str]] = Field(None, description="New tags list")
    default_repo_id: Optional[str] = Field(None, description="New default repo ID")


class AddRepoRequest(BaseModel):
    """Request to add repository to project"""
    name: str = Field(..., min_length=1, max_length=200, description="Repository name")
    local_path: str = Field(..., description="Absolute path to repository")
    vcs_type: str = Field(default="git", description="VCS type (git/none)")
    remote_url: Optional[str] = Field(None, description="Remote repository URL")
    default_branch: Optional[str] = Field(None, description="Default branch name")


# ============================================================================
# Projects Endpoints
# ============================================================================


@router.get("/projects")
async def list_projects(
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
) -> Dict[str, Any]:
    """List all projects with pagination and tag filtering

    Query Parameters:
        limit: Maximum results (default 100, max 500)
        offset: Pagination offset (default 0)
        tags: Filter by tags (comma-separated, OR logic)

    Returns:
        {
            "success": true,
            "projects": [...],
            "total": 10,
            "limit": 100,
            "offset": 0
        }

    Example:
        GET /api/projects?limit=50&offset=0&tags=backend,api
    """
    try:
        service = ProjectService()

        # Parse tags filter
        tags_list = None
        if tags:
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        # Get projects
        projects = service.list_projects(limit=limit, offset=offset, tags=tags_list)

        # Convert to dict
        projects_data = [p.to_dict() for p in projects]

        return {
            "success": True,
            "projects": projects_data,
            "total": len(projects_data),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to list projects: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Dict[str, Any]:
    """Create a new project (with idempotency support)

    Headers:
        Idempotency-Key: Optional client-provided key to prevent duplicate creates

    Body:
        {
            "name": "My Project",
            "description": "Optional description",
            "tags": ["backend", "api"],
            "default_repo_id": null
        }

    Returns:
        {
            "success": true,
            "project": {...}
        }

    Errors:
        400 - PROJECT_NAME_CONFLICT: Name already exists
        409 - DUPLICATE_REQUEST: Idempotency key already used with different parameters

    Example:
        POST /api/projects
        Idempotency-Key: create-proj-2026-01-31-abc123
        {"name": "E-Commerce Platform", "tags": ["backend", "api"]}

    Idempotency Behavior:
        - If Idempotency-Key provided and matches cached request, returns cached response (200)
        - If Idempotency-Key provided and matches cached request with different params, returns 409
        - If no Idempotency-Key provided, proceeds normally (may create duplicates if name unique)
        - Cached responses expire after 24 hours
    """
    try:
        # Check idempotency
        if idempotency_key:
            store = get_idempotency_store()
            cached = store.get(idempotency_key)

            if cached is not None:
                # Verify request matches cached request
                cached_request = cached.get("request")
                current_request = {
                    "name": request.name,
                    "description": request.description,
                    "tags": request.tags or [],
                    "default_repo_id": request.default_repo_id,
                }

                if cached_request != current_request:
                    # Different parameters with same key - conflict
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "success": False,
                            "reason_code": "DUPLICATE_IDEMPOTENCY_KEY",
                            "message": f"Idempotency key '{idempotency_key}' already used with different parameters",
                            "hint": "Use a different idempotency key or ensure request parameters match the original",
                        }
                    )

                # Return cached response
                logger.info(f"Returning cached project creation for key: {idempotency_key}")
                return cached.get("response")

        # Create project
        service = ProjectService()

        project = service.create_project(
            name=request.name,
            description=request.description,
            tags=request.tags or [],
            default_repo_id=request.default_repo_id,
        )

        response = {
            "success": True,
            "project": project.to_dict(),
        }

        # Cache response if idempotency key provided
        if idempotency_key:
            store = get_idempotency_store()
            store.set(
                idempotency_key,
                {
                    "request": {
                        "name": request.name,
                        "description": request.description,
                        "tags": request.tags or [],
                        "default_repo_id": request.default_repo_id,
                    },
                    "response": response,
                }
            )
            logger.info(f"Cached project creation with key: {idempotency_key}")

        return response

    except ProjectNameConflictError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Choose a different project name"
            }
        )

    except Exception as e:
        logger.error(f"Failed to create project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to create project: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """Get project details by ID

    Returns:
        {
            "success": true,
            "project": {...},
            "repos": [...],
            "tasks_count": 10
        }

    Errors:
        404 - PROJECT_NOT_FOUND: Project doesn't exist

    Example:
        GET /api/projects/proj_01HY6X9...
    """
    try:
        service = ProjectService()
        repo_service = RepoService()

        # Get project
        project = service.get_project(project_id)

        # Check if project exists
        if project is None:
            raise ProjectNotFoundError(project_id)

        # Get repos
        repos = repo_service.list_repos(project_id=project_id)
        repos_data = [r.to_dict() for r in repos]

        # Get task count
        tasks = service.get_project_tasks(project_id)

        return {
            "success": True,
            "project": project.to_dict(),
            "repos": repos_data,
            "tasks_count": len(tasks),
        }

    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify the project_id is correct"
            }
        )

    except Exception as e:
        logger.error(f"Failed to get project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to get project: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest
) -> Dict[str, Any]:
    """Update project fields (partial update)

    Body:
        {
            "name": "New Name",         # optional
            "description": "...",       # optional
            "tags": ["..."],            # optional
            "default_repo_id": "..."    # optional
        }

    Returns:
        {
            "success": true,
            "project": {...}
        }

    Errors:
        404 - PROJECT_NOT_FOUND
        400 - PROJECT_NAME_CONFLICT

    Example:
        PATCH /api/projects/proj_01HY6X9...
        {"name": "Updated Project Name"}
    """
    try:
        service = ProjectService()

        # Build update dict (only include non-None fields)
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.default_repo_id is not None:
            updates["default_repo_id"] = request.default_repo_id

        if not updates:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "reason_code": "NO_FIELDS_TO_UPDATE",
                    "message": "No fields provided for update",
                    "hint": "Provide at least one field to update"
                }
            )

        project = service.update_project(project_id, **updates)

        return {
            "success": True,
            "project": project.to_dict(),
        }

    except (ProjectNotFoundError, ProjectNameConflictError) as e:
        status_code = 404 if isinstance(e, ProjectNotFoundError) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify project_id and name are valid"
            }
        )

    except Exception as e:
        logger.error(f"Failed to update project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to update project: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    force: bool = Query(False, description="Force delete even if has tasks")
) -> Dict[str, Any]:
    """Delete project

    Query Parameters:
        force: If true, attempt to delete even if has tasks (may fail due to FK constraints)

    Returns:
        {
            "success": true,
            "message": "Project deleted"
        }

    Errors:
        404 - PROJECT_NOT_FOUND
        400 - PROJECT_HAS_TASKS: Cannot delete project with tasks (when force=false)

    Example:
        DELETE /api/projects/proj_01HY6X9...?force=false
    """
    try:
        service = ProjectService()

        service.delete_project(project_id, force=force)

        return {
            "success": True,
            "message": f"Project {project_id} deleted successfully",
        }

    except (ProjectNotFoundError, ProjectHasTasksError) as e:
        status_code = 404 if isinstance(e, ProjectNotFoundError) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Use force=true to attempt deletion anyway, or archive the project instead"
            }
        )

    except Exception as e:
        logger.error(f"Failed to delete project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to delete project: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


# ============================================================================
# Repository Endpoints (nested under project)
# ============================================================================


@router.get("/projects/{project_id}/repos")
async def get_project_repos(project_id: str) -> Dict[str, Any]:
    """Get all repositories for a project

    Returns:
        {
            "success": true,
            "repos": [...]
        }

    Errors:
        404 - PROJECT_NOT_FOUND

    Example:
        GET /api/projects/proj_01HY6X9.../repos
    """
    try:
        # Verify project exists
        project_service = ProjectService()
        project_service.get_project(project_id)

        # Get repos
        repo_service = RepoService()
        repos = repo_service.list_repos(project_id=project_id)

        return {
            "success": True,
            "repos": [r.to_dict() for r in repos],
        }

    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify the project_id is correct"
            }
        )

    except Exception as e:
        logger.error(f"Failed to get project repos: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to get project repos: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.post("/projects/{project_id}/repos")
async def add_repo_to_project(
    project_id: str,
    request: AddRepoRequest
) -> Dict[str, Any]:
    """Add a repository to a project

    Body:
        {
            "name": "api-service",
            "local_path": "/absolute/path/to/repo",
            "vcs_type": "git",
            "remote_url": "https://...",
            "default_branch": "main"
        }

    Returns:
        {
            "success": true,
            "repo": {...}
        }

    Errors:
        404 - PROJECT_NOT_FOUND
        400 - REPO_NAME_CONFLICT: Name already exists in project
        400 - INVALID_PATH: Path is not absolute or unsafe
        400 - PATH_NOT_FOUND: Path doesn't exist

    Example:
        POST /api/projects/proj_01HY6X9.../repos
        {"name": "backend", "local_path": "/Users/dev/backend"}
    """
    try:
        # Verify project exists
        project_service = ProjectService()
        project_service.get_project(project_id)

        # Add repo
        repo_service = RepoService()
        repo = repo_service.add_repo(
            project_id=project_id,
            name=request.name,
            local_path=request.local_path,
            vcs_type=request.vcs_type,
            remote_url=request.remote_url,
            default_branch=request.default_branch,
        )

        return {
            "success": True,
            "repo": repo.to_dict(),
        }

    except (
        ProjectNotFoundError,
        RepoNameConflictError,
        InvalidPathError,
        PathNotFoundError
    ) as e:
        status_code = 404 if isinstance(e, ProjectNotFoundError) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify project_id, path is absolute and exists, and name is unique"
            }
        )

    except Exception as e:
        logger.error(f"Failed to add repo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to add repo: {str(e)}",
                "hint": "Check server logs for details"
            }
        )
