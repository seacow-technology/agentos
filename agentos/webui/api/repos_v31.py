"""Repos API v0.31 - Repository Management

Implements v0.4 repository management endpoints for individual repository operations.

Endpoints:
- GET /api/repos/{repo_id} - Get repository details
- PATCH /api/repos/{repo_id} - Update repository
- POST /api/repos/{repo_id}/scan - Scan Git repository info (optional P1)

Created for Task #4 Phase 3: RESTful API Implementation
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentos.core.project.repo_service import RepoService
from agentos.core.project.errors import (
    RepoNotFoundError,
    InvalidPathError,
    PathNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class UpdateRepoRequest(BaseModel):
    """Request to update repository fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="New repo name")
    local_path: Optional[str] = Field(None, description="New absolute path")
    remote_url: Optional[str] = Field(None, description="New remote URL")
    default_branch: Optional[str] = Field(None, description="New default branch")


# ============================================================================
# Repository Endpoints
# ============================================================================


@router.get("/repos/{repo_id}")
async def get_repo(repo_id: str) -> Dict[str, Any]:
    """Get repository details by ID

    Returns:
        {
            "success": true,
            "repo": {...}
        }

    Errors:
        404 - REPO_NOT_FOUND: Repository doesn't exist

    Example:
        GET /api/repos/repo_01HY6XA...
    """
    try:
        service = RepoService()
        repo = service.get_repo(repo_id)

        return {
            "success": True,
            "repo": repo.to_dict(),
        }

    except RepoNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify the repo_id is correct"
            }
        )

    except Exception as e:
        logger.error(f"Failed to get repo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to get repo: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.patch("/repos/{repo_id}")
async def update_repo(
    repo_id: str,
    request: UpdateRepoRequest
) -> Dict[str, Any]:
    """Update repository fields (partial update)

    Body:
        {
            "name": "...",              # optional
            "local_path": "...",        # optional, will re-validate
            "remote_url": "...",        # optional
            "default_branch": "..."     # optional
        }

    Returns:
        {
            "success": true,
            "repo": {...}
        }

    Errors:
        404 - REPO_NOT_FOUND
        400 - INVALID_PATH: Path is not absolute or unsafe
        400 - PATH_NOT_FOUND: Path doesn't exist

    Example:
        PATCH /api/repos/repo_01HY6XA...
        {"default_branch": "develop"}
    """
    try:
        service = RepoService()

        # Build update dict (only include non-None fields)
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.local_path is not None:
            updates["local_path"] = request.local_path
        if request.remote_url is not None:
            updates["remote_url"] = request.remote_url
        if request.default_branch is not None:
            updates["default_branch"] = request.default_branch

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

        repo = service.update_repo(repo_id, **updates)

        return {
            "success": True,
            "repo": repo.to_dict(),
        }

    except (RepoNotFoundError, InvalidPathError, PathNotFoundError) as e:
        status_code = 404 if isinstance(e, RepoNotFoundError) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify repo_id and path are valid"
            }
        )

    except Exception as e:
        logger.error(f"Failed to update repo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to update repo: {str(e)}",
                "hint": "Check server logs for details"
            }
        )


@router.post("/repos/{repo_id}/scan")
async def scan_repo(repo_id: str) -> Dict[str, Any]:
    """Scan Git repository for current state (P1 feature)

    Returns:
        {
            "success": true,
            "info": {
                "vcs_type": "git",
                "current_branch": "main",
                "remote_url": "https://...",
                "last_commit": "abc123...",
                "is_dirty": false
            }
        }

    Errors:
        404 - REPO_NOT_FOUND
        400 - NOT_A_GIT_REPO: Repository is not a git repository

    Example:
        POST /api/repos/repo_01HY6XA.../scan
    """
    try:
        service = RepoService()
        repo = service.get_repo(repo_id)

        # Check if repo path exists
        repo_path = Path(repo.local_path)
        if not repo_path.exists():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "reason_code": "PATH_NOT_FOUND",
                    "message": f"Repository path does not exist: {repo.local_path}",
                    "hint": "Verify the repository path is correct"
                }
            )

        # Check if it's a git repository
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "reason_code": "NOT_A_GIT_REPO",
                    "message": "Repository is not a git repository",
                    "hint": "Initialize git with: git init"
                }
            )

        # Scan git info
        info = {
            "vcs_type": "git",
            "current_branch": None,
            "remote_url": None,
            "last_commit": None,
            "is_dirty": False,
        }

        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info["current_branch"] = result.stdout.strip()

            # Get remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info["remote_url"] = result.stdout.strip()

            # Get last commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info["last_commit"] = result.stdout.strip()[:12]

            # Check if dirty
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info["is_dirty"] = bool(result.stdout.strip())

        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timeout for repo {repo_id}")
        except Exception as e:
            logger.warning(f"Failed to scan git info: {e}")

        return {
            "success": True,
            "info": info,
        }

    except RepoNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "reason_code": e.reason_code,
                "message": str(e),
                "hint": "Verify the repo_id is correct"
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to scan repo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "reason_code": "INTERNAL_ERROR",
                "message": f"Failed to scan repo: {str(e)}",
                "hint": "Check server logs for details"
            }
        )
