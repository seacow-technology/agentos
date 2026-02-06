"""Project Snapshot Schemas

Data models for project snapshot export/import functionality.
Supports auditable project delivery and configuration freezing.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class SnapshotRepo(BaseModel):
    """Repository snapshot reference

    Captures repository binding at snapshot time.
    """
    repo_id: str = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    remote_url: Optional[str] = Field(None, description="Remote URL if available")
    workspace_relpath: str = Field(..., description="Relative path in workspace")
    role: str = Field(..., description="Repository role (code/docs/infra/mono-subdir)")
    commit_hash: Optional[str] = Field(None, description="Current commit hash (future: for git-tracked repos)")


class SnapshotTasksSummary(BaseModel):
    """Task statistics at snapshot time"""
    total: int = Field(default=0, description="Total tasks")
    completed: int = Field(default=0, description="Completed tasks")
    failed: int = Field(default=0, description="Failed tasks")
    running: int = Field(default=0, description="Running tasks")


class ProjectSnapshot(BaseModel):
    """Complete project snapshot for export/import

    Captures project state at a point in time for:
    - Configuration freeze
    - Auditable delivery
    - Backup/restore
    - Migration between environments
    """

    # Snapshot metadata
    snapshot_version: str = Field(
        default="1.0",
        description="Snapshot format version"
    )
    snapshot_id: str = Field(..., description="Unique snapshot identifier")
    timestamp: datetime = Field(..., description="Snapshot creation time")

    # Project data
    project: Dict[str, Any] = Field(..., description="Complete project data (from projects table)")
    repos: List[SnapshotRepo] = Field(default_factory=list, description="Repository references")
    tasks_summary: SnapshotTasksSummary = Field(..., description="Task statistics")

    # Integrity
    settings_hash: str = Field(..., description="SHA256 hash of settings JSON")

    # Extension point
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extension metadata (e.g., export_user, export_tool, tags)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "snapshot_version": "1.0",
                    "snapshot_id": "snap-01HQXYZ-1234567890",
                    "timestamp": "2025-01-29T10:30:00Z",
                    "project": {
                        "id": "01HQXYZ",
                        "name": "my-project",
                        "description": "Example project",
                        "status": "active"
                    },
                    "repos": [
                        {
                            "repo_id": "01HQXYZ_default",
                            "name": "default",
                            "remote_url": "https://github.com/user/repo.git",
                            "workspace_relpath": ".",
                            "role": "code",
                            "commit_hash": "abc123def456"
                        }
                    ],
                    "tasks_summary": {
                        "total": 42,
                        "completed": 40,
                        "failed": 1,
                        "running": 1
                    },
                    "settings_hash": "sha256:abcdef123456...",
                    "metadata": {
                        "created_by": "system",
                        "format_version": "1.0",
                        "export_tool": "AgentOS WebUI"
                    }
                }
            ]
        }


# Future extension points (reserved for import/diff features)
class SnapshotImportResult(BaseModel):
    """Result of snapshot import operation (future)"""
    success: bool
    project_id: Optional[str] = None
    message: str
    warnings: List[str] = Field(default_factory=list)


class SnapshotDiff(BaseModel):
    """Difference between two snapshots (future)"""
    snapshot_a_id: str
    snapshot_b_id: str
    project_changes: Dict[str, Any] = Field(default_factory=dict)
    repos_added: List[str] = Field(default_factory=list)
    repos_removed: List[str] = Field(default_factory=list)
    repos_modified: List[str] = Field(default_factory=list)
    settings_changed: bool = False
