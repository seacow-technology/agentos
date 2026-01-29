"""Projects & Repositories API - Multi-repository project management

GET /api/projects - List projects
GET /api/projects/{project_id} - Get project details
GET /api/projects/{project_id}/repos - List repositories in a project
GET /api/projects/{project_id}/repos/{repo_id} - Get repository details
GET /api/projects/{project_id}/repos/{repo_id}/tasks - Get tasks affecting a repo
POST /api/projects/{project_id}/repos - Add repository to project
PUT /api/projects/{project_id}/repos/{repo_id} - Update repository
DELETE /api/projects/{project_id}/repos/{repo_id} - Remove repository
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from agentos.core.project.repository import ProjectRepository, RepoRegistry
from agentos.core.task.task_repo_service import TaskRepoService
from agentos.schemas.project import RepoSpec, RepoRole
from agentos.store import get_db

router = APIRouter()


# ============================================
# Response Models
# ============================================


class RepoSummary(BaseModel):
    """Repository summary for list view"""

    repo_id: str
    name: str
    remote_url: Optional[str]
    role: str
    is_writable: bool
    workspace_relpath: str
    default_branch: str = "main"
    last_active: Optional[str] = None
    created_at: str
    updated_at: str


class RepoDetail(RepoSummary):
    """Detailed repository information"""

    auth_profile: Optional[str] = None
    metadata: Dict[str, Any] = {}
    task_count: Optional[int] = None  # Number of tasks using this repo


class TaskSummaryForRepo(BaseModel):
    """Task summary for repository view"""

    task_id: str
    title: str
    status: str
    created_at: str
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    commit_hash: Optional[str] = None


class ProjectSummary(BaseModel):
    """Project summary for list view"""

    project_id: str
    name: str
    description: Optional[str] = None
    repo_count: int = 0
    created_at: str


class ProjectDetail(ProjectSummary):
    """Detailed project information"""

    workspace_root: str
    repos: List[RepoSummary] = []


class AddRepoRequest(BaseModel):
    """Request to add a repository to a project"""

    name: str
    remote_url: Optional[str] = None
    workspace_relpath: str
    role: str = "code"
    is_writable: bool = True
    default_branch: str = "main"
    auth_profile: Optional[str] = None
    metadata: Dict[str, Any] = {}


class UpdateRepoRequest(BaseModel):
    """Request to update a repository"""

    name: Optional[str] = None
    is_writable: Optional[bool] = None
    default_branch: Optional[str] = None
    auth_profile: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================
# Project Endpoints
# ============================================


@router.get("/api/projects")
async def list_projects(
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> List[ProjectSummary]:
    """
    List all projects

    Returns:
        List of project summaries
    """
    try:
        db_path = get_db()
        project_repo = ProjectRepository(db_path)

        # Get unique projects from repos
        # Note: This is a simplified implementation
        # In production, you'd have a dedicated projects table
        registry = RepoRegistry(db_path)
        all_repos = registry.list_repos()

        # Group by project_id
        projects: Dict[str, ProjectSummary] = {}
        for repo in all_repos:
            if repo.project_id not in projects:
                projects[repo.project_id] = ProjectSummary(
                    project_id=repo.project_id,
                    name=repo.project_id.replace("-", " ").title(),
                    description=None,
                    repo_count=0,
                    created_at=repo.created_at.isoformat() if repo.created_at else datetime.now().isoformat(),
                )
            projects[repo.project_id].repo_count += 1

        return list(projects.values())[:limit]

    except Exception as e:
        # Return empty list on error
        return []


@router.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> ProjectDetail:
    """
    Get project details with repositories

    Args:
        project_id: Project ID

    Returns:
        Project details
    """
    try:
        db_path = get_db()
        registry = RepoRegistry(db_path)

        repos = registry.get_project_repos(project_id)

        if not repos:
            raise HTTPException(status_code=404, detail="Project not found")

        repo_summaries = [
            RepoSummary(
                repo_id=repo.repo_id,
                name=repo.name,
                remote_url=repo.remote_url,
                role=repo.role.value if isinstance(repo.role, RepoRole) else repo.role,
                is_writable=repo.is_writable,
                workspace_relpath=repo.workspace_relpath,
                default_branch=repo.default_branch,
                created_at=repo.created_at.isoformat() if repo.created_at else datetime.now().isoformat(),
                updated_at=repo.updated_at.isoformat() if repo.updated_at else datetime.now().isoformat(),
            )
            for repo in repos
        ]

        # Windows 兼容: 使用 Path 获取根目录
        from pathlib import Path
        workspace_root = "."
        if repos:
            parts = Path(repos[0].workspace_relpath).parts
            workspace_root = parts[0] if parts else "."

        return ProjectDetail(
            project_id=project_id,
            name=project_id.replace("-", " ").title(),
            description=None,
            repo_count=len(repos),
            workspace_root=workspace_root,
            repos=repo_summaries,
            created_at=repos[0].created_at.isoformat() if repos and repos[0].created_at else datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


# ============================================
# Repository Endpoints
# ============================================


@router.get("/api/projects/{project_id}/repos")
async def list_repos(
    project_id: str,
    role: Optional[str] = Query(None, description="Filter by role"),
) -> List[RepoSummary]:
    """
    List repositories in a project

    Args:
        project_id: Project ID
        role: Filter by role (code, docs, tests, config, data)

    Returns:
        List of repository summaries
    """
    try:
        db_path = get_db()
        registry = RepoRegistry(db_path)

        repos = registry.get_project_repos(project_id)

        # Filter by role if specified
        if role:
            repos = [r for r in repos if r.role.value == role]

        repo_summaries = [
            RepoSummary(
                repo_id=repo.repo_id,
                name=repo.name,
                remote_url=repo.remote_url,
                role=repo.role.value if isinstance(repo.role, RepoRole) else repo.role,
                is_writable=repo.is_writable,
                workspace_relpath=repo.workspace_relpath,
                default_branch=repo.default_branch,
                created_at=repo.created_at.isoformat() if repo.created_at else datetime.now().isoformat(),
                updated_at=repo.updated_at.isoformat() if repo.updated_at else datetime.now().isoformat(),
            )
            for repo in repos
        ]

        return repo_summaries

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repos: {str(e)}")


@router.get("/api/projects/{project_id}/repos/{repo_id}")
async def get_repo(project_id: str, repo_id: str) -> RepoDetail:
    """
    Get repository details

    Args:
        project_id: Project ID
        repo_id: Repository ID

    Returns:
        Repository details
    """
    try:
        db_path = get_db()
        registry = RepoRegistry(db_path)

        repo = registry.get_repo(repo_id)

        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Count tasks using this repo
        task_count = 0
        try:
            from agentos.core.task.audit_service import TaskAuditService

            audit_service = TaskAuditService(db_path)
            # Get recent audits for this repo (simple count)
            audits = audit_service.get_repo_audits(repo_id, limit=1000)
            task_ids = set(audit.task_id for audit in audits)
            task_count = len(task_ids)
        except Exception as e:
            pass  # Ignore errors counting tasks

        return RepoDetail(
            repo_id=repo.repo_id,
            name=repo.name,
            remote_url=repo.remote_url,
            role=repo.role.value if isinstance(repo.role, RepoRole) else repo.role,
            is_writable=repo.is_writable,
            workspace_relpath=repo.workspace_relpath,
            default_branch=repo.default_branch,
            auth_profile=repo.auth_profile,
            metadata=repo.metadata,
            task_count=task_count,
            created_at=repo.created_at.isoformat() if repo.created_at else datetime.now().isoformat(),
            updated_at=repo.updated_at.isoformat() if repo.updated_at else datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repo: {str(e)}")


@router.get("/api/projects/{project_id}/repos/{repo_id}/tasks")
async def get_repo_tasks(
    project_id: str,
    repo_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> List[TaskSummaryForRepo]:
    """
    Get tasks affecting a repository

    Args:
        project_id: Project ID
        repo_id: Repository ID
        limit: Maximum number of results

    Returns:
        List of tasks that modified this repository
    """
    try:
        db_path = get_db()

        # Verify repo exists
        registry = RepoRegistry(db_path)
        repo = registry.get_repo(repo_id)

        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get audits for this repo
        from agentos.core.task.audit_service import TaskAuditService

        audit_service = TaskAuditService(db_path)
        audits = audit_service.get_repo_audits(repo_id, limit=limit)

        # Group by task_id
        tasks_map: Dict[str, TaskSummaryForRepo] = {}
        for audit in audits:
            if audit.task_id not in tasks_map:
                tasks_map[audit.task_id] = TaskSummaryForRepo(
                    task_id=audit.task_id,
                    title=audit.task_id,  # We don't have task title in audit
                    status="completed",  # Assume completed if audited
                    created_at=audit.created_at,
                    files_changed=0,
                    lines_added=0,
                    lines_deleted=0,
                    commit_hash=audit.commit_hash,
                )

            # Aggregate stats
            task_summary = tasks_map[audit.task_id]
            task_summary.files_changed += len(audit.files_changed)
            task_summary.lines_added += audit.lines_added
            task_summary.lines_deleted += audit.lines_deleted

            # Update commit hash if newer
            if audit.commit_hash and not task_summary.commit_hash:
                task_summary.commit_hash = audit.commit_hash

        return list(tasks_map.values())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repo tasks: {str(e)}")


@router.post("/api/projects/{project_id}/repos")
async def add_repo(project_id: str, request: AddRepoRequest) -> RepoDetail:
    """
    Add a repository to a project

    Args:
        project_id: Project ID
        request: Repository details

    Returns:
        Created repository details
    """
    try:
        db_path = get_db()
        project_repo = ProjectRepository(db_path)

        # Create repo spec
        repo_spec = RepoSpec(
            repo_id=f"{project_id}_{request.name.lower().replace(' ', '_')}",
            project_id=project_id,
            name=request.name,
            remote_url=request.remote_url,
            default_branch=request.default_branch,
            workspace_relpath=request.workspace_relpath,
            role=RepoRole(request.role) if isinstance(request.role, str) else request.role,
            is_writable=request.is_writable,
            auth_profile=request.auth_profile,
            metadata=request.metadata,
        )

        # Add to database
        repo_id = project_repo.add_repo(repo_spec)

        # Return created repo
        return RepoDetail(
            repo_id=repo_id,
            name=repo_spec.name,
            remote_url=repo_spec.remote_url,
            role=repo_spec.role.value if isinstance(repo_spec.role, RepoRole) else repo_spec.role,
            is_writable=repo_spec.is_writable,
            workspace_relpath=repo_spec.workspace_relpath,
            default_branch=repo_spec.default_branch,
            auth_profile=repo_spec.auth_profile,
            metadata=repo_spec.metadata,
            task_count=0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add repo: {str(e)}")


@router.put("/api/projects/{project_id}/repos/{repo_id}")
async def update_repo(
    project_id: str,
    repo_id: str,
    request: UpdateRepoRequest,
) -> RepoDetail:
    """
    Update a repository

    Args:
        project_id: Project ID
        repo_id: Repository ID
        request: Updated repository details

    Returns:
        Updated repository details
    """
    try:
        db_path = get_db()
        project_repo = ProjectRepository(db_path)

        # Get existing repo
        registry = RepoRegistry(db_path)
        repo = registry.get_repo(repo_id)

        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Update fields
        if request.name is not None:
            repo.name = request.name
        if request.is_writable is not None:
            repo.is_writable = request.is_writable
        if request.default_branch is not None:
            repo.default_branch = request.default_branch
        if request.auth_profile is not None:
            repo.auth_profile = request.auth_profile
        if request.metadata is not None:
            repo.metadata.update(request.metadata)

        repo.updated_at = datetime.now()

        # Update in database
        project_repo.update_repo(repo)

        # Return updated repo
        return RepoDetail(
            repo_id=repo.repo_id,
            name=repo.name,
            remote_url=repo.remote_url,
            role=repo.role.value if isinstance(repo.role, RepoRole) else repo.role,
            is_writable=repo.is_writable,
            workspace_relpath=repo.workspace_relpath,
            default_branch=repo.default_branch,
            auth_profile=repo.auth_profile,
            metadata=repo.metadata,
            task_count=None,
            created_at=repo.created_at.isoformat() if repo.created_at else datetime.now().isoformat(),
            updated_at=repo.updated_at.isoformat() if repo.updated_at else datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update repo: {str(e)}")


@router.delete("/api/projects/{project_id}/repos/{repo_id}")
async def delete_repo(project_id: str, repo_id: str) -> Dict[str, str]:
    """
    Remove a repository from a project

    Args:
        project_id: Project ID
        repo_id: Repository ID

    Returns:
        Success message
    """
    try:
        db_path = get_db()
        project_repo = ProjectRepository(db_path)

        # Verify repo exists and belongs to project
        registry = RepoRegistry(db_path)
        repo = registry.get_repo(repo_id)

        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Delete
        project_repo.remove_repo(repo_id)

        return {"message": f"Repository {repo_id} removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repo: {str(e)}")
