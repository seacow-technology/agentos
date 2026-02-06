"""Project and Repository Error Definitions

Custom exceptions for project-aware task management (v0.4).
All errors include reason_code field for structured error handling.

Created for Task #3 Phase 2: Core Service Implementation
"""


# ============================================================================
# Base Errors
# ============================================================================


class ProjectError(Exception):
    """Base exception for project-related errors"""

    reason_code: str = "PROJECT_ERROR"

    def __init__(self, message: str, **kwargs):
        self.message = message
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


class RepoError(Exception):
    """Base exception for repository-related errors"""

    reason_code: str = "REPO_ERROR"

    def __init__(self, message: str, **kwargs):
        self.message = message
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


class SpecError(Exception):
    """Base exception for task spec-related errors"""

    reason_code: str = "SPEC_ERROR"

    def __init__(self, message: str, **kwargs):
        self.message = message
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


class BindingError(Exception):
    """Base exception for task binding-related errors"""

    reason_code: str = "BINDING_ERROR"

    def __init__(self, message: str, **kwargs):
        self.message = message
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


class ArtifactError(Exception):
    """Base exception for task artifact-related errors"""

    reason_code: str = "ARTIFACT_ERROR"

    def __init__(self, message: str, **kwargs):
        self.message = message
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


# ============================================================================
# Project Errors
# ============================================================================


class ProjectNotFoundError(ProjectError):
    """Raised when a project is not found"""

    reason_code = "PROJECT_NOT_FOUND"

    def __init__(self, project_id: str):
        super().__init__(f"Project not found", project_id=project_id)


class ProjectNameConflictError(ProjectError):
    """Raised when a project name already exists"""

    reason_code = "PROJECT_NAME_CONFLICT"

    def __init__(self, name: str):
        super().__init__(f"Project name already exists", name=name)


class ProjectHasTasksError(ProjectError):
    """Raised when attempting to delete a project that has tasks"""

    reason_code = "PROJECT_HAS_TASKS"

    def __init__(self, project_id: str, task_count: int):
        super().__init__(
            f"Cannot delete project with tasks",
            project_id=project_id,
            task_count=task_count,
        )


# ============================================================================
# Repository Errors
# ============================================================================


class RepoNotFoundError(RepoError):
    """Raised when a repository is not found"""

    reason_code = "REPO_NOT_FOUND"

    def __init__(self, repo_id: str):
        super().__init__(f"Repository not found", repo_id=repo_id)


class RepoNameConflictError(RepoError):
    """Raised when a repository name already exists in a project"""

    reason_code = "REPO_NAME_CONFLICT"

    def __init__(self, project_id: str, name: str):
        super().__init__(
            f"Repository name already exists in project",
            project_id=project_id,
            name=name,
        )


class RepoNotInProjectError(RepoError):
    """Raised when a repository does not belong to a project"""

    reason_code = "REPO_NOT_IN_PROJECT"

    def __init__(self, repo_id: str, project_id: str):
        super().__init__(
            f"Repository does not belong to project",
            repo_id=repo_id,
            project_id=project_id,
        )


class InvalidPathError(RepoError):
    """Raised when a path is invalid or unsafe"""

    reason_code = "INVALID_PATH"

    def __init__(self, path: str, reason: str = ""):
        super().__init__(f"Invalid or unsafe path: {reason}", path=path)


class PathNotFoundError(RepoError):
    """Raised when a path does not exist"""

    reason_code = "PATH_NOT_FOUND"

    def __init__(self, path: str):
        super().__init__(f"Path not found", path=path)


# ============================================================================
# Task Spec Errors
# ============================================================================


class SpecNotFoundError(SpecError):
    """Raised when a task spec is not found"""

    reason_code = "SPEC_NOT_FOUND"

    def __init__(self, task_id: str, version: int = None):
        if version is not None:
            super().__init__(
                f"Task spec not found",
                task_id=task_id,
                version=version,
            )
        else:
            super().__init__(f"Task spec not found", task_id=task_id)


class SpecAlreadyFrozenError(SpecError):
    """Raised when attempting to freeze an already-frozen spec"""

    reason_code = "SPEC_ALREADY_FROZEN"

    def __init__(self, task_id: str):
        super().__init__(f"Task spec already frozen", task_id=task_id)


class SpecIncompleteError(SpecError):
    """Raised when a spec is incomplete and cannot be frozen"""

    reason_code = "SPEC_INCOMPLETE"

    def __init__(self, task_id: str, missing_fields: list):
        super().__init__(
            f"Task spec incomplete, missing fields: {', '.join(missing_fields)}",
            task_id=task_id,
            missing_fields=missing_fields,
        )


class SpecValidationError(SpecError):
    """Raised when a spec fails validation"""

    reason_code = "SPEC_VALIDATION_ERROR"

    def __init__(self, task_id: str, errors: list):
        super().__init__(
            f"Task spec validation failed",
            task_id=task_id,
            errors=errors,
        )


# ============================================================================
# Task Binding Errors
# ============================================================================


class BindingNotFoundError(BindingError):
    """Raised when a task binding is not found"""

    reason_code = "BINDING_NOT_FOUND"

    def __init__(self, task_id: str):
        super().__init__(f"Task binding not found", task_id=task_id)


class BindingAlreadyExistsError(BindingError):
    """Raised when a task already has a binding"""

    reason_code = "BINDING_ALREADY_EXISTS"

    def __init__(self, task_id: str):
        super().__init__(f"Task already has a binding", task_id=task_id)


class InvalidWorkdirError(BindingError):
    """Raised when a workdir is invalid or unsafe"""

    reason_code = "INVALID_WORKDIR"

    def __init__(self, workdir: str, reason: str = ""):
        super().__init__(f"Invalid workdir: {reason}", workdir=workdir)


class BindingValidationError(BindingError):
    """Raised when a binding fails validation"""

    reason_code = "BINDING_VALIDATION_ERROR"

    def __init__(self, task_id: str, errors: list):
        super().__init__(
            f"Task binding validation failed",
            task_id=task_id,
            errors=errors,
        )


# ============================================================================
# Task Artifact Errors
# ============================================================================


class ArtifactNotFoundError(ArtifactError):
    """Raised when an artifact is not found"""

    reason_code = "ARTIFACT_NOT_FOUND"

    def __init__(self, artifact_id: str):
        super().__init__(f"Artifact not found", artifact_id=artifact_id)


class InvalidKindError(ArtifactError):
    """Raised when an artifact kind is invalid"""

    reason_code = "INVALID_KIND"

    def __init__(self, kind: str):
        super().__init__(
            f"Invalid artifact kind (must be: file/dir/url/log/report)",
            kind=kind,
        )


class UnsafePathError(ArtifactError):
    """Raised when an artifact path is unsafe"""

    reason_code = "UNSAFE_PATH"

    def __init__(self, path: str, reason: str = ""):
        super().__init__(f"Unsafe artifact path: {reason}", path=path)


class ArtifactPathNotFoundError(ArtifactError):
    """Raised when an artifact path does not exist"""

    reason_code = "ARTIFACT_PATH_NOT_FOUND"

    def __init__(self, path: str):
        super().__init__(f"Artifact path not found", path=path)


# ============================================================================
# Task Errors (imported from task/errors.py)
# ============================================================================

# Note: Task-related errors like TaskNotFoundError are defined in
# agentos/core/task/errors.py and should be imported from there
# when needed in project/repo services.
