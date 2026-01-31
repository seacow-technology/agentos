"""
Skills API - Skill registry management with Admin Token protection

Endpoints:
- GET /api/skills - List all skills (public)
- GET /api/skills/{skill_id} - Get skill details (public)
- POST /api/skills/import - Import skill from local or GitHub (protected)
- POST /api/skills/{skill_id}/enable - Enable skill (protected)
- POST /api/skills/{skill_id}/disable - Disable skill (protected)

Admin Token Protection:
- Import/enable/disable operations require Admin Token
- Token validated via require_admin dependency
- 401 Unauthorized if token missing or invalid
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from agentos.skills.registry import SkillRegistry
from agentos.skills.importer.local_importer import LocalImporter
from agentos.skills.importer.github_importer import GitHubImporter, GitHubFetchError
from agentos.webui.auth.simple_token import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Request/Response Models ====================

class ImportLocalRequest(BaseModel):
    """Request model for local skill import."""
    type: str = Field(..., description="Must be 'local'")
    path: str = Field(..., description="Local filesystem path to skill directory")


class ImportGitHubRequest(BaseModel):
    """Request model for GitHub skill import."""
    type: str = Field(..., description="Must be 'github'")
    owner: str = Field(..., description="GitHub repository owner")
    repo: str = Field(..., description="GitHub repository name")
    ref: Optional[str] = Field(None, description="Git ref (branch/tag/commit), defaults to main")
    subdir: Optional[str] = Field(None, description="Subdirectory path within repository")


class ImportResponse(BaseModel):
    """Response model for skill import."""
    skill_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    """Response model for status change operations."""
    skill_id: str
    status: str
    message: str


# ==================== Public Endpoints (No Admin Token) ====================

@router.get("")
async def list_skills(status: Optional[str] = None) -> Dict[str, Any]:
    """
    List all skills, optionally filtered by status.

    Query Parameters:
        status: Optional status filter (enabled | disabled | imported_disabled | all)

    Returns:
        {
            "ok": true,
            "data": [
                {
                    "skill_id": "example.skill",
                    "name": "Example Skill",
                    "version": "1.0.0",
                    "status": "enabled",
                    "manifest_json": {...},
                    ...
                }
            ]
        }
    """
    try:
        registry = SkillRegistry()

        # Convert 'all' to None for list_skills
        filter_status = None if status == 'all' else status

        skills = registry.list_skills(status=filter_status)

        return {
            "ok": True,
            "data": skills
        }
    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list skills: {str(e)}")


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific skill.

    Path Parameters:
        skill_id: Skill identifier

    Returns:
        {
            "ok": true,
            "data": {
                "skill_id": "example.skill",
                "name": "Example Skill",
                "version": "1.0.0",
                "status": "enabled",
                "manifest_json": {...},
                "source_type": "local",
                "source_ref": "/path/to/skill",
                "created_at": 1234567890000,
                "updated_at": 1234567890000,
                ...
            }
        }
    """
    try:
        registry = SkillRegistry()
        skill = registry.get_skill(skill_id)

        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

        return {
            "ok": True,
            "data": skill
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get skill: {str(e)}")


# ==================== Protected Endpoints (Admin Token Required) ====================

@router.post("/import", dependencies=[Depends(require_admin)])
async def import_skill(
    local_req: Optional[ImportLocalRequest] = None,
    github_req: Optional[ImportGitHubRequest] = None
) -> ImportResponse:
    """
    Import a skill from local path or GitHub repository.

    Requires: Admin Token (via Authorization: Bearer <token> header)

    Request Body (Local):
        {
            "type": "local",
            "path": "/path/to/skill"
        }

    Request Body (GitHub):
        {
            "type": "github",
            "owner": "owner",
            "repo": "repo",
            "ref": "main",  # optional
            "subdir": "skills/example"  # optional
        }

    Returns:
        {
            "skill_id": "example.skill",
            "status": "imported_disabled",
            "message": "Successfully imported skill"
        }

    Errors:
        401: Missing or invalid admin token
        400: Invalid request or import failed
        500: Internal server error
    """
    registry = SkillRegistry()

    try:
        # Determine import type from request body
        if local_req and local_req.type == 'local':
            # Import from local path
            if not local_req.path:
                raise HTTPException(status_code=400, detail="Missing 'path' field")

            logger.info(f"Importing skill from local path: {local_req.path}")
            importer = LocalImporter(registry)
            skill_id = importer.import_from_path(local_req.path)

            return ImportResponse(
                skill_id=skill_id,
                status="imported_disabled",
                message=f"Successfully imported skill from local path: {local_req.path}"
            )

        elif github_req and github_req.type == 'github':
            # Import from GitHub
            if not github_req.owner or not github_req.repo:
                raise HTTPException(status_code=400, detail="Missing 'owner' or 'repo' field")

            logger.info(f"Importing skill from GitHub: {github_req.owner}/{github_req.repo}")
            importer = GitHubImporter(registry)
            skill_id = importer.import_from_github(
                github_req.owner,
                github_req.repo,
                github_req.ref,
                github_req.subdir
            )

            return ImportResponse(
                skill_id=skill_id,
                status="imported_disabled",
                message=f"Successfully imported skill from GitHub: {github_req.owner}/{github_req.repo}"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid import type. Expected 'local' or 'github'"
            )

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"File not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except GitHubFetchError as e:
        raise HTTPException(status_code=400, detail=f"GitHub fetch error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import skill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/{skill_id}/enable", dependencies=[Depends(require_admin)])
async def enable_skill(skill_id: str) -> StatusResponse:
    """
    Enable a skill.

    Requires: Admin Token (via Authorization: Bearer <token> header)

    Path Parameters:
        skill_id: Skill identifier

    Returns:
        {
            "skill_id": "example.skill",
            "status": "enabled",
            "message": "Skill enabled successfully"
        }

    Errors:
        401: Missing or invalid admin token
        404: Skill not found
        500: Internal server error
    """
    try:
        registry = SkillRegistry()

        # Check if skill exists
        skill = registry.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

        # Enable skill
        registry.set_status(skill_id, 'enabled')
        logger.info(f"Skill enabled: {skill_id}")

        return StatusResponse(
            skill_id=skill_id,
            status="enabled",
            message=f"Skill enabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable skill: {str(e)}")


@router.post("/{skill_id}/disable", dependencies=[Depends(require_admin)])
async def disable_skill(skill_id: str) -> StatusResponse:
    """
    Disable a skill.

    Requires: Admin Token (via Authorization: Bearer <token> header)

    Path Parameters:
        skill_id: Skill identifier

    Returns:
        {
            "skill_id": "example.skill",
            "status": "disabled",
            "message": "Skill disabled successfully"
        }

    Errors:
        401: Missing or invalid admin token
        404: Skill not found
        500: Internal server error
    """
    try:
        registry = SkillRegistry()

        # Check if skill exists
        skill = registry.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

        # Disable skill
        registry.set_status(skill_id, 'disabled')
        logger.info(f"Skill disabled: {skill_id}")

        return StatusResponse(
            skill_id=skill_id,
            status="disabled",
            message=f"Skill disabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable skill: {str(e)}")


__all__ = ["router"]
