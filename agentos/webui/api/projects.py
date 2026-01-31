"""Projects & Repositories API - Multi-repository project management

GET /api/projects - List projects
POST /api/projects - Create project
GET /api/projects/{project_id} - Get project details
PATCH /api/projects/{project_id} - Update project
POST /api/projects/{project_id}/archive - Archive project
DELETE /api/projects/{project_id} - Delete project
GET /api/projects/{project_id}/repos - List repositories in a project
GET /api/projects/{project_id}/repos/{repo_id} - Get repository details
GET /api/projects/{project_id}/repos/{repo_id}/tasks - Get tasks affecting a repo
POST /api/projects/{project_id}/repos - Add repository to project
PUT /api/projects/{project_id}/repos/{repo_id} - Update repository
DELETE /api/projects/{project_id}/repos/{repo_id} - Remove repository
POST /api/projects/{project_id}/snapshot - Create project snapshot
GET /api/projects/{project_id}/snapshots - List project snapshots
GET /api/projects/{project_id}/snapshots/{snapshot_id} - Get snapshot details
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import uuid
import hashlib
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


# Try to import ulid, fallback to uuid if not available
try:
    import ulid
    def generate_id():
        return str(ulid.ULID())
except ImportError:
    def generate_id():
        return str(uuid.uuid4())

from agentos.core.project.repository import ProjectRepository, RepoRegistry
from agentos.core.task.task_repo_service import TaskRepoService
from agentos.schemas.project import RepoSpec, RepoRole, Project, ProjectSettings
from agentos.schemas.snapshot import ProjectSnapshot, SnapshotRepo, SnapshotTasksSummary
from agentos.store import get_db, get_db_path

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


class CreateProjectRequest(BaseModel):
    """Request to create a project"""

    name: str
    description: Optional[str] = None
    tags: List[str] = []
    default_workdir: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class UpdateProjectRequest(BaseModel):
    """Request to update a project"""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    default_workdir: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


# ============================================
# Project Endpoints
# ============================================


@router.get("/api/projects")
async def list_projects(
    search: Optional[str] = Query(None, description="Search in name or description"),
    status: Optional[str] = Query(None, description="Filter by status (active/archived/deleted)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> Dict[str, Any]:
    """
    List all projects with search and filtering

    Args:
        search: Search term to filter by name or description
        status: Filter by project status (active/archived/deleted)
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        Dictionary with projects list and metadata
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT
                project_id,
                name,
                description,
                status,
                tags,
                default_repo_id,
                default_workdir,
                settings,
                created_at,
                updated_at,
                created_by,
                path,
                metadata
            FROM projects
            WHERE 1=1
        """
        params = []

        # Apply status filter
        if status:
            if status not in ("active", "archived", "deleted"):
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            query += " AND status = ?"
            params.append(status)

        # Apply search filter
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            search_term = f"%{search}%"
            params.append(search_term)
            params.append(search_term)

        # Order by updated_at DESC
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to Project objects
        projects = []
        workspace_root = Path.cwd()
        registry = RepoRegistry(get_db_path(), workspace_root)

        for row in rows:
            # Get repos for this project
            repos = registry.list_repos(row["project_id"])

            # Create Project object
            project = Project.from_db_row(dict(row), repos)

            # Convert to summary format
            projects.append({
                "project_id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "tags": project.tags,
                "repo_count": len(repos),
                "created_at": iso_z(project.created_at) if project.created_at else None,
                "updated_at": iso_z(project.updated_at) if project.updated_at else None,
            })

        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM projects WHERE 1=1"
        count_params = []
        if status:
            count_query += " AND status = ?"
            count_params.append(status)
        if search:
            count_query += " AND (name LIKE ? OR description LIKE ?)"
            count_params.append(search_term)
            count_params.append(search_term)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        return {
            "projects": projects,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """
    Get project details with full metadata

    Args:
        project_id: Project ID

    Returns:
        Project details with repos and statistics
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Query project from projects table
        cursor.execute("""
            SELECT
                project_id,
                name,
                description,
                status,
                tags,
                default_repo_id,
                default_workdir,
                settings,
                created_at,
                updated_at,
                created_by,
                path,
                metadata
            FROM projects
            WHERE project_id = ?
        """, (project_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get repos for this project
        workspace_root = Path.cwd()
        registry = RepoRegistry(get_db_path(), workspace_root)
        repos = registry.list_repos(project_id)

        # Create Project object
        project = Project.from_db_row(dict(row), repos)

        # Get statistics
        # 1. Count recent tasks (last 7 days)
        seven_days_ago = iso_z(utc_now() - timedelta(days=7))
        cursor.execute("""
            SELECT COUNT(DISTINCT trs.task_id)
            FROM task_repo_scope trs
            INNER JOIN project_repos pr ON trs.repo_id = pr.repo_id
            INNER JOIN tasks t ON trs.task_id = t.task_id
            WHERE pr.project_id = ?
            AND t.created_at >= ?
        """, (project_id, seven_days_ago))
        recent_tasks_count = cursor.fetchone()[0]

        # Convert repos to summaries
        repo_summaries = [
            {
                "repo_id": repo.repo_id,
                "name": repo.name,
                "remote_url": repo.remote_url,
                "role": repo.role.value if isinstance(repo.role, RepoRole) else repo.role,
                "is_writable": repo.is_writable,
                "workspace_relpath": repo.workspace_relpath,
                "default_branch": repo.default_branch,
                "created_at": iso_z(repo.created_at) if repo.created_at else None,
                "updated_at": iso_z(repo.updated_at) if repo.updated_at else None,
            }
            for repo in repos
        ]

        # Return full project details
        return {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "tags": project.tags,
            "default_repo_id": project.default_repo_id,
            "default_workdir": project.default_workdir,
            "settings": project.settings.model_dump() if project.settings else None,
            "created_at": iso_z(project.created_at) if project.created_at else None,
            "updated_at": iso_z(project.updated_at) if project.updated_at else None,
            "created_by": project.created_by,
            "repos": repo_summaries,
            "repos_count": len(repos),
            "recent_tasks_count": recent_tasks_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.post("/api/projects")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """
    Create a new project

    Args:
        request: Project creation details

    Returns:
        Created project information
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Generate unique project ID
        project_id = generate_id()

        # Check if name already exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE name = ?", (request.name,))
        if cursor.fetchone()[0] > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Project with name '{request.name}' already exists"
            )

        # Validate settings if provided
        settings_json = None
        if request.settings:
            try:
                # Validate settings structure
                project_settings = ProjectSettings(**request.settings)
                settings_json = json.dumps(project_settings.model_dump())
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid settings: {str(e)}"
                )

        # Insert project
        now = iso_z(utc_now())
        # Use default_workdir as path for backward compatibility, or default to "."
        path = request.default_workdir or "."

        cursor.execute("""
            INSERT INTO projects (
                project_id,
                path,
                name,
                description,
                status,
                tags,
                default_workdir,
                settings,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            path,
            request.name,
            request.description,
            "active",
            json.dumps(request.tags) if request.tags else "[]",
            request.default_workdir,
            settings_json or "{}",
            now,
            now,
        ))
        conn.commit()

        # Return created project
        cursor.execute("""
            SELECT
                project_id,
                name,
                description,
                status,
                tags,
                default_repo_id,
                default_workdir,
                settings,
                created_at,
                updated_at,
                created_by,
                path,
                metadata
            FROM projects
            WHERE project_id = ?
        """, (project_id,))

        row = cursor.fetchone()
        project = Project.from_db_row(dict(row), [])

        return {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "tags": project.tags,
            "default_workdir": project.default_workdir,
            "settings": project.settings.model_dump() if project.settings else None,
            "created_at": iso_z(project.created_at) if project.created_at else None,
            "updated_at": iso_z(project.updated_at) if project.updated_at else None,
            "repos": [],
            "repos_count": 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.patch("/api/projects/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest) -> Dict[str, Any]:
    """
    Update an existing project

    Args:
        project_id: Project ID
        request: Project update details (partial update supported)

    Returns:
        Updated project information
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if project exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        # Build update query dynamically
        update_fields = []
        params = []

        if request.name is not None:
            # Check if new name conflicts with another project
            cursor.execute(
                "SELECT COUNT(*) FROM projects WHERE name = ? AND project_id != ?",
                (request.name, project_id)
            )
            if cursor.fetchone()[0] > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project with name '{request.name}' already exists"
                )
            update_fields.append("name = ?")
            params.append(request.name)

        if request.description is not None:
            update_fields.append("description = ?")
            params.append(request.description)

        if request.tags is not None:
            update_fields.append("tags = ?")
            params.append(json.dumps(request.tags))

        if request.default_workdir is not None:
            update_fields.append("default_workdir = ?")
            params.append(request.default_workdir)

        if request.settings is not None:
            try:
                # Validate settings structure
                project_settings = ProjectSettings(**request.settings)
                update_fields.append("settings = ?")
                params.append(json.dumps(project_settings.model_dump()))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid settings: {str(e)}"
                )

        # Always update updated_at
        update_fields.append("updated_at = ?")
        params.append(iso_z(utc_now()))

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Execute update
        params.append(project_id)
        query = f"UPDATE projects SET {', '.join(update_fields)} WHERE project_id = ?"
        cursor.execute(query, params)
        conn.commit()

        # Return updated project
        cursor.execute("""
            SELECT
                project_id,
                name,
                description,
                status,
                tags,
                default_repo_id,
                default_workdir,
                settings,
                created_at,
                updated_at,
                created_by,
                path,
                metadata
            FROM projects
            WHERE project_id = ?
        """, (project_id,))

        row = cursor.fetchone()
        workspace_root = Path.cwd()
        registry = RepoRegistry(get_db_path(), workspace_root)
        repos = registry.list_repos(project_id)

        project = Project.from_db_row(dict(row), repos)

        return {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "tags": project.tags,
            "default_repo_id": project.default_repo_id,
            "default_workdir": project.default_workdir,
            "settings": project.settings.model_dump() if project.settings else None,
            "created_at": iso_z(project.created_at) if project.created_at else None,
            "updated_at": iso_z(project.updated_at) if project.updated_at else None,
            "repos_count": len(repos),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


@router.post("/api/projects/{project_id}/archive")
async def archive_project(project_id: str) -> Dict[str, str]:
    """
    Archive a project

    Args:
        project_id: Project ID

    Returns:
        Success message
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if project exists
        cursor.execute("SELECT status FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        if row[0] == "archived":
            raise HTTPException(status_code=400, detail="Project is already archived")

        # Update status to archived
        cursor.execute("""
            UPDATE projects
            SET status = ?, updated_at = ?
            WHERE project_id = ?
        """, ("archived", iso_z(utc_now()), project_id))
        conn.commit()

        return {
            "message": f"Project '{project_id}' archived successfully",
            "project_id": project_id,
            "status": "archived"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to archive project: {str(e)}")


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> Dict[str, str]:
    """
    Delete a project

    Args:
        project_id: Project ID

    Returns:
        Success message

    Note:
        - Cannot delete project with existing tasks (returns 400 error)
        - If no tasks exist, deletes the project and cascades to project_repos
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if project exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if project has any tasks
        cursor.execute("""
            SELECT COUNT(DISTINCT trs.task_id)
            FROM task_repo_scope trs
            INNER JOIN project_repos pr ON trs.repo_id = pr.repo_id
            WHERE pr.project_id = ?
        """, (project_id,))

        task_count = cursor.fetchone()[0]

        if task_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete project with existing tasks ({task_count} tasks found). Archive instead."
            )

        # Delete project (CASCADE will delete project_repos automatically)
        cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        conn.commit()

        return {
            "message": f"Project '{project_id}' deleted successfully",
            "project_id": project_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


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
        db_path = get_db_path()
        workspace_root = Path.cwd()
        registry = RepoRegistry(db_path, workspace_root)

        repos = registry.list_repos(project_id)

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
                created_at=iso_z(repo.created_at) if repo.created_at else iso_z(utc_now()),
                updated_at=iso_z(repo.updated_at) if repo.updated_at else iso_z(utc_now()),
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
        db_path = get_db_path()
        workspace_root = Path.cwd()
        registry = RepoRegistry(db_path, workspace_root)

        repo = registry.get_repo(project_id, repo_id)

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
            created_at=iso_z(repo.created_at) if repo.created_at else iso_z(utc_now()),
            updated_at=iso_z(repo.updated_at) if repo.updated_at else iso_z(utc_now()),
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
        db_path = get_db_path()

        # Verify repo exists
        workspace_root = Path.cwd()
        registry = RepoRegistry(db_path, workspace_root)
        repo = registry.get_repo(project_id, repo_id)

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
        db_path = get_db_path()
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
            created_at=iso_z(utc_now()),
            updated_at=iso_z(utc_now()),
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
        db_path = get_db_path()
        project_repo = ProjectRepository(db_path)

        # Get existing repo
        workspace_root = Path.cwd()
        registry = RepoRegistry(db_path, workspace_root)
        repo = registry.get_repo(project_id, repo_id)

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

        repo.updated_at = utc_now()

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
            created_at=iso_z(repo.created_at) if repo.created_at else iso_z(utc_now()),
            updated_at=iso_z(repo.updated_at) if repo.updated_at else iso_z(utc_now()),
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
        db_path = get_db_path()
        project_repo = ProjectRepository(db_path)

        # Verify repo exists and belongs to project
        workspace_root = Path.cwd()
        registry = RepoRegistry(db_path, workspace_root)
        repo = registry.get_repo(project_id, repo_id)

        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Delete
        project_repo.remove_repo(project_id, repo_id)

        return {"message": f"Repository {repo_id} removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repo: {str(e)}")


# ============================================
# Task Graph Endpoint
# ============================================


class TaskGraphNode(BaseModel):
    """Task node in the graph"""
    task_id: str
    title: str
    status: str
    repos: List[str]
    created_at: str


class TaskGraphEdge(BaseModel):
    """Dependency edge in the graph"""
    from_task: str = Field(alias="from")
    to_task: str = Field(alias="to")
    type: str
    reason: Optional[str] = None

    class Config:
        populate_by_name = True


class RepoInfo(BaseModel):
    """Repository information for the graph"""
    repo_id: str
    name: str
    role: str
    color: str


class TaskGraphResponse(BaseModel):
    """Task graph response"""
    project_id: str
    nodes: List[TaskGraphNode]
    edges: List[TaskGraphEdge]
    repos: List[RepoInfo]


def get_repo_color(role: str) -> str:
    """Get color for repository role"""
    colors = {
        "code": "#007bff",
        "docs": "#7b1fa2",
        "infra": "#f57c00",
        "mono-subdir": "#388e3c"
    }
    return colors.get(role, "#666")


@router.get("/api/projects/{project_id}/task-graph")
async def get_project_task_graph(project_id: str) -> TaskGraphResponse:
    """
    Get project task dependency graph for visualization

    Args:
        project_id: Project ID

    Returns:
        Task graph with nodes, edges, and repo information
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # 1. Check if project exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        # 2. Get all tasks for this project (via task_repo_scope -> project_repos)
        cursor.execute("""
            SELECT DISTINCT t.task_id, t.title, t.status, t.created_at
            FROM tasks t
            INNER JOIN task_repo_scope trs ON t.task_id = trs.task_id
            INNER JOIN project_repos pr ON trs.repo_id = pr.repo_id
            WHERE pr.project_id = ?
            ORDER BY t.created_at DESC
        """, (project_id,))
        tasks = cursor.fetchall()

        # 3. Build nodes with repo associations
        nodes = []
        task_ids = []
        for task in tasks:
            task_id = task[0]
            task_ids.append(task_id)

            # Get repos for this task
            cursor.execute("""
                SELECT DISTINCT pr.repo_id
                FROM task_repo_scope trs
                INNER JOIN project_repos pr ON trs.repo_id = pr.repo_id
                WHERE trs.task_id = ? AND pr.project_id = ?
            """, (task_id, project_id))
            task_repos = [row[0] for row in cursor.fetchall()]

            nodes.append(TaskGraphNode(
                task_id=task_id,
                title=task[1] or task_id[:12],
                status=task[2] or "created",
                repos=task_repos,
                created_at=task[3] or iso_z(utc_now())
            ))

        # 4. Get task dependencies (only for tasks in this project)
        edges = []
        if task_ids:
            placeholders = ','.join(['?'] * len(task_ids))
            cursor.execute(f"""
                SELECT task_id, depends_on_task_id, dependency_type, reason
                FROM task_dependency
                WHERE task_id IN ({placeholders})
                  AND depends_on_task_id IN ({placeholders})
            """, task_ids + task_ids)

            dependencies = cursor.fetchall()
            for dep in dependencies:
                edges.append(TaskGraphEdge(
                    from_task=dep[0],
                    to_task=dep[1],
                    type=dep[2] or "blocks",
                    reason=dep[3]
                ))

        # 5. Get all repos for this project
        cursor.execute("""
            SELECT repo_id, name, role
            FROM project_repos
            WHERE project_id = ?
            ORDER BY created_at
        """, (project_id,))

        repos = [
            RepoInfo(
                repo_id=row[0],
                name=row[1],
                role=row[2],
                color=get_repo_color(row[2])
            )
            for row in cursor.fetchall()
        ]

        return TaskGraphResponse(
            project_id=project_id,
            nodes=nodes,
            edges=edges,
            repos=repos
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task graph: {str(e)}")


# ============================================
# Snapshot Endpoints
# ============================================


@router.post("/api/projects/{project_id}/snapshot")
async def create_project_snapshot(project_id: str) -> Dict[str, Any]:
    """
    Create a project snapshot

    Captures complete project state including:
    - Project metadata and settings
    - Repository bindings
    - Task statistics
    - Settings integrity hash

    Args:
        project_id: Project ID

    Returns:
        Complete snapshot data (ProjectSnapshot schema)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # 1. Query project data
        cursor.execute("""
            SELECT
                project_id,
                name,
                description,
                status,
                tags,
                default_repo_id,
                default_workdir,
                settings,
                created_at,
                updated_at,
                created_by,
                path,
                metadata
            FROM projects
            WHERE project_id = ?
        """, (project_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        # Convert to dict
        project_data = dict(zip([col[0] for col in cursor.description], row))

        # 2. Get repositories
        cursor.execute("""
            SELECT
                repo_id,
                name,
                remote_url,
                workspace_relpath,
                role
            FROM project_repos
            WHERE project_id = ?
        """, (project_id,))

        repos = []
        for repo_row in cursor.fetchall():
            repo_dict = dict(zip([col[0] for col in cursor.description], repo_row))
            repos.append(SnapshotRepo(
                repo_id=repo_dict['repo_id'],
                name=repo_dict['name'],
                remote_url=repo_dict.get('remote_url'),
                workspace_relpath=repo_dict['workspace_relpath'],
                role=repo_dict['role'],
                commit_hash=None  # Future: add git commit tracking
            ))

        # 3. Get task statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' OR status = 'succeeded' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' OR status = 'error' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'running' OR status = 'pending' THEN 1 ELSE 0 END) as running
            FROM tasks
            WHERE project_id = ?
        """, (project_id,))

        stats = cursor.fetchone()
        tasks_summary = SnapshotTasksSummary(
            total=stats[0] or 0,
            completed=stats[1] or 0,
            failed=stats[2] or 0,
            running=stats[3] or 0
        )

        # 4. Calculate settings hash
        settings_json = project_data.get('settings') or '{}'
        settings_hash = hashlib.sha256(settings_json.encode()).hexdigest()

        # 5. Generate snapshot ID
        timestamp = utc_now()
        snapshot_id = f"snap-{project_id}-{int(timestamp.timestamp())}"

        # 6. Create snapshot
        snapshot = ProjectSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            project=project_data,
            repos=[repo.model_dump() for repo in repos],
            tasks_summary=tasks_summary,
            settings_hash=settings_hash,
            metadata={
                "created_by": "system",
                "format_version": "1.0",
                "export_tool": "AgentOS WebUI"
            }
        )

        # 7. Save to database (for history)
        cursor.execute("""
            INSERT INTO project_snapshots (snapshot_id, project_id, data, created_at)
            VALUES (?, ?, ?, ?)
        """, (snapshot_id, project_id, snapshot.model_dump_json(), iso_z(timestamp)))
        conn.commit()

        return snapshot.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {str(e)}")


@router.get("/api/projects/{project_id}/snapshots")
async def list_project_snapshots(
    project_id: str,
    limit: int = Query(10, ge=1, le=100, description="Max results")
) -> Dict[str, Any]:
    """
    List project snapshot history

    Args:
        project_id: Project ID
        limit: Maximum number of snapshots to return

    Returns:
        Dictionary with snapshots list
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Verify project exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        # Query snapshots
        cursor.execute("""
            SELECT snapshot_id, created_at
            FROM project_snapshots
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (project_id, limit))

        snapshots = []
        for row in cursor.fetchall():
            snapshots.append({
                "snapshot_id": row[0],
                "created_at": row[1]
            })

        return {"snapshots": snapshots, "total": len(snapshots)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {str(e)}")


@router.get("/api/projects/{project_id}/snapshots/{snapshot_id}")
async def get_project_snapshot(project_id: str, snapshot_id: str) -> Dict[str, Any]:
    """
    Get snapshot details (for download)

    Args:
        project_id: Project ID
        snapshot_id: Snapshot ID

    Returns:
        Complete snapshot data
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT data
            FROM project_snapshots
            WHERE project_id = ? AND snapshot_id = ?
        """, (project_id, snapshot_id))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        return json.loads(row[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get snapshot: {str(e)}")
