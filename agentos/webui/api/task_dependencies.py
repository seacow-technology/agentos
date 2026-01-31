"""Task Dependencies API - Cross-repository task dependencies

GET /api/tasks/{task_id}/dependencies - Get task dependencies
GET /api/tasks/{task_id}/dependencies/graph - Get dependency graph (DOT format)
GET /api/tasks/{task_id}/repos - Get repositories associated with a task
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

from agentos.core.task.dependency_service import TaskDependencyService
from agentos.core.task.task_repo_service import TaskRepoService
from agentos.core.task.audit_service import TaskAuditService
from agentos.schemas.project import RepoRole
from agentos.store import get_db
from agentos.webui.api.time_format import iso_z

router = APIRouter()


# ============================================
# Response Models
# ============================================


class DependencySummary(BaseModel):
    """Task dependency summary"""

    dependency_id: int
    task_id: str
    depends_on_task_id: str
    dependency_type: str  # requires, suggests, blocks
    reason: Optional[str] = None
    created_at: str
    metadata: Dict[str, Any] = {}


class DependencyDetail(DependencySummary):
    """Detailed dependency information with task details"""

    depends_on_task_title: Optional[str] = None
    depends_on_task_status: Optional[str] = None


class TaskRepoSummary(BaseModel):
    """Repository summary for task view"""

    repo_id: str
    name: str
    role: str
    writable: bool
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    commit_hash: Optional[str] = None
    has_changes: bool = False


class TaskRepoChanges(BaseModel):
    """Task repository changes with file details"""

    repo_id: str
    name: str
    role: str
    writable: bool
    files: List[Dict[str, Any]] = []
    total_lines_added: int = 0
    total_lines_deleted: int = 0
    commit_hash: Optional[str] = None


class DependencyGraphResponse(BaseModel):
    """Dependency graph response"""

    task_id: str
    format: str = "dot"
    graph_data: str


# ============================================
# Dependencies Endpoints
# ============================================


@router.get("/api/tasks/{task_id}/dependencies")
async def get_task_dependencies(
    task_id: str,
    include_reverse: bool = Query(False, description="Include reverse dependencies"),
) -> Dict[str, List[DependencySummary]]:
    """
    Get task dependencies (both forward and reverse)

    Args:
        task_id: Task ID
        include_reverse: Include tasks that depend on this task

    Returns:
        Dictionary with 'depends_on' and 'depended_by' lists
    """
    try:
        db_path = get_db()
        dep_service = TaskDependencyService(db_path)

        # Get forward dependencies (tasks this task depends on)
        forward_deps = dep_service.get_dependencies(task_id)
        depends_on = [
            DependencySummary(
                dependency_id=dep.dependency_id,
                task_id=dep.task_id,
                depends_on_task_id=dep.depends_on_task_id,
                dependency_type=dep.dependency_type.value if hasattr(dep.dependency_type, "value") else dep.dependency_type,
                reason=dep.reason,
                created_at=iso_z(dep.created_at) if hasattr(dep.created_at, "isoformat") else dep.created_at,
                metadata=dep.metadata,
            )
            for dep in forward_deps
        ]

        # Get reverse dependencies if requested
        depended_by = []
        if include_reverse:
            reverse_deps = dep_service.get_reverse_dependencies(task_id)
            depended_by = [
                DependencySummary(
                    dependency_id=dep.dependency_id,
                    task_id=dep.task_id,
                    depends_on_task_id=dep.depends_on_task_id,
                    dependency_type=dep.dependency_type.value if hasattr(dep.dependency_type, "value") else dep.dependency_type,
                    reason=dep.reason,
                    created_at=iso_z(dep.created_at) if hasattr(dep.created_at, "isoformat") else dep.created_at,
                    metadata=dep.metadata,
                )
                for dep in reverse_deps
            ]

        return {"depends_on": depends_on, "depended_by": depended_by}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dependencies: {str(e)}")


@router.get("/api/tasks/{task_id}/dependencies/graph")
async def get_dependency_graph(
    task_id: str,
    format: str = Query("dot", description="Output format (dot, json)"),
) -> DependencyGraphResponse:
    """
    Get dependency graph for visualization

    Args:
        task_id: Task ID
        format: Output format (dot for GraphViz, json for custom rendering)

    Returns:
        Dependency graph in requested format
    """
    try:
        db_path = get_db()
        dep_service = TaskDependencyService(db_path)

        # Build dependency graph
        graph = dep_service.build_dependency_graph()

        if format == "dot":
            # Export to DOT format for GraphViz
            dot_data = graph.to_dot()
            return DependencyGraphResponse(task_id=task_id, format="dot", graph_data=dot_data)
        elif format == "json":
            # Export to JSON format
            # Build adjacency list
            graph_dict = {
                "nodes": [],
                "edges": [],
            }

            # Get all tasks in the graph
            all_tasks = set(graph.graph.keys())
            for deps in graph.graph.values():
                all_tasks.update(deps)

            # Add nodes
            for task in all_tasks:
                graph_dict["nodes"].append({"id": task, "label": task})

            # Add edges
            for task, deps in graph.graph.items():
                for dep in deps:
                    graph_dict["edges"].append({"from": task, "to": dep})

            import json

            return DependencyGraphResponse(task_id=task_id, format="json", graph_data=json.dumps(graph_dict))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dependency graph: {str(e)}")


# ============================================
# Task Repos Endpoints
# ============================================


@router.get("/api/tasks/{task_id}/repos")
async def get_task_repos(
    task_id: str,
    detailed: bool = Query(False, description="Include file changes"),
) -> List[TaskRepoSummary] | List[TaskRepoChanges]:
    """
    Get repositories associated with a task

    Args:
        task_id: Task ID
        detailed: Include detailed file changes

    Returns:
        List of repositories with change summaries
    """
    try:
        db_path = get_db()
        audit_service = TaskAuditService(db_path)

        # Get audits for this task
        audits = audit_service.get_task_audits(task_id, limit=1000)

        # Group by repo_id
        repos_map: Dict[str, Dict[str, Any]] = {}

        for audit in audits:
            if not audit.repo_id:
                continue

            if audit.repo_id not in repos_map:
                # Initialize repo entry
                repos_map[audit.repo_id] = {
                    "repo_id": audit.repo_id,
                    "name": audit.repo_id,  # Will try to get real name later
                    "role": "code",  # Default
                    "writable": True,  # Assume writable if we have audits
                    "files_changed": 0,
                    "lines_added": 0,
                    "lines_deleted": 0,
                    "commit_hash": audit.commit_hash,
                    "has_changes": False,
                    "files": [],
                }

            repo_data = repos_map[audit.repo_id]

            # Aggregate stats
            if audit.files_changed:
                repo_data["files_changed"] += len(audit.files_changed)
                repo_data["has_changes"] = True

                if detailed:
                    # Add file details
                    for file_path in audit.files_changed:
                        repo_data["files"].append(
                            {
                                "path": file_path,
                                "lines_added": audit.lines_added // len(audit.files_changed) if audit.files_changed else 0,
                                "lines_deleted": audit.lines_deleted // len(audit.files_changed) if audit.files_changed else 0,
                            }
                        )

            repo_data["lines_added"] += audit.lines_added
            repo_data["lines_deleted"] += audit.lines_deleted

            # Update commit hash if newer
            if audit.commit_hash and not repo_data["commit_hash"]:
                repo_data["commit_hash"] = audit.commit_hash

        # Try to get real repo names from database
        try:
            cursor = db_path.cursor()
            for repo_id, repo_data in repos_map.items():
                cursor.execute(
                    "SELECT name, role, is_writable FROM project_repos WHERE repo_id = ?",
                    (repo_id,)
                )
                row = cursor.fetchone()
                if row:
                    repo_data["name"] = row[0]
                    repo_data["role"] = row[1]
                    repo_data["writable"] = bool(row[2])
        except Exception as e:
            pass  # Ignore errors fetching repo details

        # Convert to response models
        if detailed:
            return [
                TaskRepoChanges(
                    repo_id=repo_data["repo_id"],
                    name=repo_data["name"],
                    role=repo_data["role"],
                    writable=repo_data["writable"],
                    files=repo_data["files"],
                    total_lines_added=repo_data["lines_added"],
                    total_lines_deleted=repo_data["lines_deleted"],
                    commit_hash=repo_data["commit_hash"],
                )
                for repo_data in repos_map.values()
            ]
        else:
            return [
                TaskRepoSummary(
                    repo_id=repo_data["repo_id"],
                    name=repo_data["name"],
                    role=repo_data["role"],
                    writable=repo_data["writable"],
                    files_changed=repo_data["files_changed"],
                    lines_added=repo_data["lines_added"],
                    lines_deleted=repo_data["lines_deleted"],
                    commit_hash=repo_data["commit_hash"],
                    has_changes=repo_data["has_changes"],
                )
                for repo_data in repos_map.values()
            ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task repos: {str(e)}")
