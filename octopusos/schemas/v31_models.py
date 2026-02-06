"""v0.31 Schema Models - Project-Aware Task OS

Data models for v0.4 multi-repository project management.
Maps to schema_v31 tables: projects, repos, task_specs, task_bindings, task_artifacts.

Created for Task #3 Phase 2: Core Service Implementation
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from agentos.core.time import parse_db_time, iso_z


# ============================================================================
# Project Models
# ============================================================================


class Project(BaseModel):
    """Project entity (maps to projects table)

    A Project is a logical container that can bind to multiple repositories.
    """

    project_id: str = Field(..., description="Unique project ID (ULID)")
    name: str = Field(..., description="Project name (unique, user-friendly)")
    description: Optional[str] = Field(None, description="Project description")
    tags: List[str] = Field(default_factory=list, description="Project tags (JSON array)")
    default_repo_id: Optional[str] = Field(None, description="Default repository ID")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extended metadata (JSON)")

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> List[str]:
        """Parse tags from JSON string if needed"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return v if isinstance(v, list) else []

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Project":
        """Create from database row with proper timezone handling"""
        # Parse and format timestamps to ensure Z suffix
        created_dt = parse_db_time(row["created_at"])
        updated_dt = parse_db_time(row["updated_at"])

        return cls(
            project_id=row["project_id"],
            name=row["name"],
            description=row.get("description"),
            tags=row.get("tags", "[]"),
            default_repo_id=row.get("default_repo_id"),
            created_at=iso_z(created_dt) or row["created_at"],
            updated_at=iso_z(updated_dt) or row["updated_at"],
            metadata=row.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "default_repo_id": self.default_repo_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ============================================================================
# Repository Models
# ============================================================================


class Repo(BaseModel):
    """Repository entity (maps to repos table)

    A Repo represents a code repository bound to a project.
    """

    repo_id: str = Field(..., description="Unique repository ID (ULID)")
    project_id: str = Field(..., description="Parent project ID (FK)")
    name: str = Field(..., description="Repository name (unique within project)")
    local_path: str = Field(..., description="Local absolute path to repository")
    vcs_type: str = Field(default="git", description="Version control system type")
    remote_url: Optional[str] = Field(None, description="Remote repository URL")
    default_branch: Optional[str] = Field(None, description="Default branch name")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extended metadata (JSON)")

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Repo":
        """Create from database row with proper timezone handling"""
        # Parse and format timestamps to ensure Z suffix
        created_dt = parse_db_time(row["created_at"])
        updated_dt = parse_db_time(row["updated_at"])

        return cls(
            repo_id=row["repo_id"],
            project_id=row["project_id"],
            name=row["name"],
            local_path=row["local_path"],
            vcs_type=row.get("vcs_type", "git"),
            remote_url=row.get("remote_url"),
            default_branch=row.get("default_branch"),
            created_at=iso_z(created_dt) or row["created_at"],
            updated_at=iso_z(updated_dt) or row["updated_at"],
            metadata=row.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "repo_id": self.repo_id,
            "project_id": self.project_id,
            "name": self.name,
            "local_path": self.local_path,
            "vcs_type": self.vcs_type,
            "remote_url": self.remote_url,
            "default_branch": self.default_branch,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ============================================================================
# Task Spec Models
# ============================================================================


class TaskSpec(BaseModel):
    """Task specification entity (maps to task_specs table)

    A TaskSpec represents a versioned specification for a task.
    Specs are frozen (immutable) once a task enters READY state.
    """

    spec_id: str = Field(..., description="Unique spec ID (ULID)")
    task_id: str = Field(..., description="Associated task ID (FK)")
    spec_version: int = Field(..., description="Spec version number (starts at 0)")
    title: str = Field(..., description="Task title")
    intent: Optional[str] = Field(None, description="Task intent (short description)")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Constraints (JSON)")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Acceptance criteria (JSON array)")
    inputs: Optional[Dict[str, Any]] = Field(None, description="Input data (JSON)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extended metadata (JSON)")

    @field_validator("constraints", "inputs", "metadata", mode="before")
    @classmethod
    def parse_json_field(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Parse JSON field from string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def parse_acceptance_criteria(cls, v: Any) -> List[str]:
        """Parse acceptance criteria from JSON string if needed"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return v if isinstance(v, list) else []

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskSpec":
        """Create from database row with proper timezone handling"""
        # Parse and format timestamp to ensure Z suffix
        created_dt = parse_db_time(row["created_at"])

        return cls(
            spec_id=row["spec_id"],
            task_id=row["task_id"],
            spec_version=row["spec_version"],
            title=row["title"],
            intent=row.get("intent"),
            constraints=row.get("constraints"),
            acceptance_criteria=row.get("acceptance_criteria", "[]"),
            inputs=row.get("inputs"),
            created_at=iso_z(created_dt) or row["created_at"],
            metadata=row.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "spec_id": self.spec_id,
            "task_id": self.task_id,
            "spec_version": self.spec_version,
            "title": self.title,
            "intent": self.intent,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "inputs": self.inputs,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ============================================================================
# Task Binding Models
# ============================================================================


class TaskBinding(BaseModel):
    """Task binding entity (maps to task_bindings table)

    A TaskBinding associates a task with a project and optional repository.
    """

    task_id: str = Field(..., description="Task ID (PK, FK)")
    project_id: str = Field(..., description="Bound project ID (FK)")
    repo_id: Optional[str] = Field(None, description="Bound repository ID (FK, optional)")
    workdir: Optional[str] = Field(None, description="Working directory (relative path)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extended metadata (JSON)")

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskBinding":
        """Create from database row with proper timezone handling"""
        # Parse and format timestamp to ensure Z suffix
        created_dt = parse_db_time(row["created_at"])

        return cls(
            task_id=row["task_id"],
            project_id=row["project_id"],
            repo_id=row.get("repo_id"),
            workdir=row.get("workdir"),
            created_at=iso_z(created_dt) or row["created_at"],
            metadata=row.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "repo_id": self.repo_id,
            "workdir": self.workdir,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ============================================================================
# Task Artifact Models
# ============================================================================


class TaskArtifact(BaseModel):
    """Task artifact entity (maps to task_artifacts table)

    A TaskArtifact represents a file, directory, URL, or other output
    generated by a task.
    """

    artifact_id: str = Field(..., description="Unique artifact ID (ULID)")
    task_id: str = Field(..., description="Associated task ID (FK)")
    kind: str = Field(..., description="Artifact kind (file/dir/url/log/report)")
    path: str = Field(..., description="Artifact path or URL")
    display_name: Optional[str] = Field(None, description="User-friendly display name")
    hash: Optional[str] = Field(None, description="Content hash (e.g., sha256:...)")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extended metadata (JSON)")

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskArtifact":
        """Create from database row with proper timezone handling"""
        # Parse and format timestamp to ensure Z suffix
        created_dt = parse_db_time(row["created_at"])

        return cls(
            artifact_id=row["artifact_id"],
            task_id=row["task_id"],
            kind=row["kind"],
            path=row["path"],
            display_name=row.get("display_name"),
            hash=row.get("hash"),
            size_bytes=row.get("size_bytes"),
            created_at=iso_z(created_dt) or row["created_at"],
            metadata=row.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "artifact_id": self.artifact_id,
            "task_id": self.task_id,
            "kind": self.kind,
            "path": self.path,
            "display_name": self.display_name,
            "hash": self.hash,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
