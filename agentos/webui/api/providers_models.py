"""
Models Directory Management API

Manages provider models directory configuration:
- Get/set models directories for each provider
- Auto-detect default models directories
- Browse model files in directories
- Security validation for path traversal

Sprint B+ Provider Architecture Refactor
Phase 3.2: Models Directory Management
Phase 3.3: Unified Error Handling
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.providers import platform_utils
from agentos.providers.providers_config import ProvidersConfigManager
from agentos.webui.api import providers_errors


from agentos.webui.api.time_format import iso_z
logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ModelsDirectoriesResponse(BaseModel):
    """Response for get models directories"""
    global_dir: Optional[str] = Field(None, description="Global shared models directory")
    providers: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Provider-specific models directories"
    )


class SetModelsDirectoryRequest(BaseModel):
    """Request to set a models directory"""
    provider_id: str = Field(..., description="Provider ID or 'global'")
    path: str = Field(..., description="Absolute path to models directory")


class SetModelsDirectoryResponse(BaseModel):
    """Response for set models directory"""
    success: bool
    provider_id: str
    path: str
    message: Optional[str] = None


class DetectedDirectory(BaseModel):
    """Detected models directory for a provider"""
    path: Optional[str] = Field(None, description="Detected directory path")
    exists: bool = Field(False, description="Whether directory exists")
    model_count: Optional[int] = Field(None, description="Number of model files found")


class DetectDirectoriesResponse(BaseModel):
    """Response for detect models directories"""
    providers: Dict[str, DetectedDirectory] = Field(
        default_factory=dict,
        description="Detected directories for each provider"
    )


class ModelFileInfo(BaseModel):
    """Information about a model file"""
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    size_human: str = Field(..., description="Human-readable file size")
    modified: str = Field(..., description="Last modified timestamp (ISO format)")
    extension: str = Field(..., description="File extension")


class ModelFilesResponse(BaseModel):
    """Response for list model files"""
    directory: str = Field(..., description="Directory path")
    files: List[ModelFileInfo] = Field(default_factory=list, description="Model files")


# ============================================================================
# Helper Functions
# ============================================================================


def get_allowed_directories() -> List[Path]:
    """
    Get list of allowed directories from configuration.

    Returns directories that users have configured for models browsing.
    This creates an allow-list for security purposes.

    Returns:
        List[Path]: List of allowed absolute paths (resolved)

    Note:
        - All paths are resolved to absolute paths
        - Non-existent paths are included in the list
        - Duplicate paths are removed
    """
    try:
        config_manager = ProvidersConfigManager()
        allowed = []

        # Get global models directory
        global_dir = config_manager.get_models_directory("global")
        if global_dir:
            try:
                allowed.append(global_dir.resolve())
            except (OSError, RuntimeError):
                allowed.append(global_dir.absolute())

        # Get provider-specific directories
        for provider_id in ["ollama", "llamacpp", "lmstudio"]:
            provider_dir = config_manager.get_models_directory(provider_id)
            if provider_dir:
                try:
                    resolved = provider_dir.resolve()
                    if resolved not in allowed:
                        allowed.append(resolved)
                except (OSError, RuntimeError):
                    abs_path = provider_dir.absolute()
                    if abs_path not in allowed:
                        allowed.append(abs_path)

        return allowed
    except Exception as e:
        logger.warning(f"Failed to get allowed directories: {e}")
        return []


def add_to_allowed_list(directory: Path) -> None:
    """
    Add a directory to the allowed list by configuring it.

    This is called when a user sets a models directory for a provider.
    The configuration is saved persistently.

    Args:
        directory: Directory to add to allowed list

    Note:
        This function doesn't directly manage an allow-list.
        Instead, it ensures the directory is configured, which automatically
        adds it to the allowed list via get_allowed_directories().
    """
    # This is handled by set_models_directory in the API endpoint
    # The function exists for documentation purposes
    pass


def is_safe_path(user_path: str, allowed_dirs: List[Path]) -> Tuple[bool, str]:
    """
    Check if a user-provided path is safe to access.

    Security checks:
    1. Resolve the path to absolute form (prevents .. traversal)
    2. Check if path is within any allowed directory tree
    3. Handle edge cases (invalid paths, permission errors)

    Args:
        user_path: User-provided path string
        allowed_dirs: List of allowed base directories

    Returns:
        Tuple[bool, str]: (is_safe, error_message)
            - (True, "") if path is safe
            - (False, "error message") if path is unsafe

    Examples:
        >>> is_safe_path("/home/user/.ollama/models", [Path("/home/user/.ollama/models")])
        (True, "")

        >>> is_safe_path("/home/user/.ollama/models/../../etc/passwd", [Path("/home/user/.ollama/models")])
        (False, "Path not in allowed directories: ['/home/user/.ollama/models']")

        >>> is_safe_path("invalid:path", [Path("/home/user/.ollama/models")])
        (False, "Invalid path: ...")
    """
    try:
        # Normalize and resolve the path
        from agentos.providers import platform_utils
        normalized = platform_utils.expand_user_path(user_path)

        # Check if path is within any allowed directory
        for allowed_dir in allowed_dirs:
            try:
                # Resolve the allowed directory as well
                try:
                    resolved_allowed = allowed_dir.resolve()
                except (OSError, RuntimeError):
                    resolved_allowed = allowed_dir.absolute()

                # Check if the normalized path is relative to the allowed directory
                if normalized.is_relative_to(resolved_allowed):
                    return True, ""
            except (ValueError, TypeError):
                # is_relative_to can raise ValueError on Windows with different drives
                continue

        # Path is not in any allowed directory
        allowed_str = ", ".join(str(d) for d in allowed_dirs)
        return False, f"Path not in allowed directories: [{allowed_str}]"

    except Exception as e:
        return False, f"Invalid path: {str(e)}"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        str: Formatted size (e.g., "4.2 GB", "512.5 MB", "1.5 KB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_kb = size_bytes / 1024
        return f"{size_kb:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.1f} MB"
    else:
        size_gb = size_bytes / (1024 * 1024 * 1024)
        return f"{size_gb:.1f} GB"


def is_safe_path_legacy(base_path: Path, user_path: str) -> bool:
    """
    Legacy function: Prevent path traversal attacks for a single base path.

    Deprecated: Use is_safe_path() with allowed directories list instead.

    Args:
        base_path: Base directory path
        user_path: User-provided path

    Returns:
        bool: True if the path is safe (within base_path), False otherwise

    Note:
        This function resolves symlinks and ensures the final path
        is relative to the base_path.
    """
    try:
        # Resolve the full path
        if Path(user_path).is_absolute():
            resolved = Path(user_path).resolve()
        else:
            resolved = (base_path / user_path).resolve()

        # Check if resolved path is relative to base_path
        return resolved.is_relative_to(base_path)
    except (ValueError, RuntimeError, OSError):
        return False


def is_model_file(file_path: Path) -> bool:
    """
    Check if a file is a model file based on extension.

    Args:
        file_path: Path to the file

    Returns:
        bool: True if the file is a model file, False otherwise

    Supported extensions:
        - .gguf (GGUF format, used by llama.cpp)
        - .bin (Binary model files)
        - .safetensors (SafeTensors format)
        - .pt, .pth (PyTorch models)
        - .onnx (ONNX models)
    """
    model_extensions = {'.gguf', '.bin', '.safetensors', '.pt', '.pth', '.onnx'}
    return file_path.suffix.lower() in model_extensions


def count_model_files(directory: Path) -> int:
    """
    Count model files in a directory.

    Args:
        directory: Directory path

    Returns:
        int: Number of model files found
    """
    if not directory.exists() or not directory.is_dir():
        return 0

    count = 0
    try:
        for item in directory.iterdir():
            if item.is_file() and is_model_file(item):
                count += 1
    except (PermissionError, OSError) as e:
        logger.warning(f"Failed to count model files in {directory}: {e}")
        return 0

    return count


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/models/directories", response_model=ModelsDirectoriesResponse)
async def get_models_directories():
    """
    Get models directory configuration for all providers.

    Returns current configuration including:
    - Global shared models directory
    - Provider-specific directories (ollama, llamacpp, lmstudio)

    Example response:
    ```json
    {
      "global_dir": "/shared/models",
      "providers": {
        "ollama": "~/.ollama/models",
        "llamacpp": "/shared/models",
        "lmstudio": "~/.cache/lm-studio/models"
      }
    }
    ```
    """
    try:
        config_manager = ProvidersConfigManager()

        # Get global directory
        global_dir = config_manager.get_models_directory("global")

        # Get provider-specific directories
        providers = {}
        for provider_id in ["ollama", "llamacpp", "lmstudio"]:
            provider_dir = config_manager.get_models_directory(provider_id)
            providers[provider_id] = str(provider_dir) if provider_dir else None

        return ModelsDirectoriesResponse(
            global_dir=str(global_dir) if global_dir else None,
            providers=providers
        )

    except Exception as e:
        logger.error(f"Failed to get models directories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get models directories: {str(e)}"
        )


@router.put("/models/directories", response_model=SetModelsDirectoryResponse)
async def set_models_directory(request: SetModelsDirectoryRequest):
    """
    Set models directory for a provider or global.

    Args:
        request: Contains provider_id ('ollama', 'llamacpp', 'lmstudio', or 'global')
                 and path (absolute path to directory)

    Returns:
        Success response with confirmed path

    Validation:
    - Directory must exist
    - Directory must be readable
    - Path must be absolute

    Raises:
        HTTPException: With standardized error format for validation failures

    Example request:
    ```json
    {
      "provider_id": "ollama",
      "path": "/custom/ollama/models"
    }
    ```
    """
    try:
        # Normalize and validate path
        from agentos.providers import platform_utils
        path_obj = platform_utils.normalize_path(request.path)

        # Make it absolute if not already
        if not path_obj.is_absolute():
            path_obj = path_obj.absolute()

        # Double-check after normalization
        if not path_obj.is_absolute():
            providers_errors.raise_provider_error(
                code=providers_errors.INVALID_PATH,
                message="Path must be absolute",
                details={"path": request.path},
                suggestion="Provide an absolute path (e.g., /full/path/to/directory)",
                status_code=400
            )

        if not path_obj.exists():
            error_info = providers_errors.build_directory_not_found_error(
                path=str(path_obj),
                provider_id=request.provider_id
            )
            providers_errors.raise_provider_error(**error_info)

        if not path_obj.is_dir():
            providers_errors.raise_provider_error(
                code=providers_errors.NOT_A_DIRECTORY,
                message=f"Path is not a directory: {request.path}",
                details={"path": request.path},
                suggestion="Provide a path to a directory, not a file",
                status_code=400
            )

        # Check if directory is readable
        try:
            list(path_obj.iterdir())
        except PermissionError:
            error_info = providers_errors.build_permission_denied_error(
                path=str(path_obj),
                operation="read"
            )
            providers_errors.raise_provider_error(**error_info)

        # Validate provider_id
        valid_provider_ids = ["ollama", "llamacpp", "lmstudio", "global"]
        if request.provider_id not in valid_provider_ids:
            providers_errors.raise_provider_error(
                code=providers_errors.INVALID_CONFIG,
                message=f"Invalid provider_id: {request.provider_id}",
                details={
                    "provider_id": request.provider_id,
                    "valid_provider_ids": valid_provider_ids
                },
                suggestion=f"Use one of: {', '.join(valid_provider_ids)}",
                status_code=400
            )

        # Save configuration
        config_manager = ProvidersConfigManager()
        config_manager.set_models_directory(request.provider_id, str(path_obj))

        logger.info(f"Set models directory for {request.provider_id}: {path_obj}")

        return SetModelsDirectoryResponse(
            success=True,
            provider_id=request.provider_id,
            path=str(path_obj),
            message=f"Models directory set for {request.provider_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        providers_errors.log_provider_error(
            error_code=providers_errors.INTERNAL_ERROR,
            message=f"Failed to set models directory for {request.provider_id}",
            exc=e
        )
        providers_errors.raise_provider_error(
            code=providers_errors.INTERNAL_ERROR,
            message=f"Failed to set models directory: {str(e)}",
            details={"provider_id": request.provider_id},
            suggestion="Check server logs for more details",
            status_code=500
        )


@router.get("/models/directories/detect", response_model=DetectDirectoriesResponse)
async def detect_models_directories():
    """
    Auto-detect default models directories for all providers.

    For each provider:
    - Detects the default models directory location
    - Checks if the directory exists
    - Counts model files if directory exists

    Example response:
    ```json
    {
      "providers": {
        "ollama": {
          "path": "/Users/username/.ollama/models",
          "exists": true,
          "model_count": 5
        },
        "lmstudio": {
          "path": "/Users/username/.cache/lm-studio/models",
          "exists": false,
          "model_count": null
        }
      }
    }
    ```
    """
    try:
        providers = {}

        for provider_id in ["ollama", "llamacpp", "lmstudio"]:
            try:
                # Get default directory from platform_utils
                default_dir = platform_utils.get_models_dir(provider_id)

                if default_dir:
                    exists = default_dir.exists()
                    model_count = count_model_files(default_dir) if exists else None

                    providers[provider_id] = DetectedDirectory(
                        path=str(default_dir),
                        exists=exists,
                        model_count=model_count
                    )
                else:
                    providers[provider_id] = DetectedDirectory(
                        path=None,
                        exists=False,
                        model_count=None
                    )

            except Exception as e:
                logger.warning(f"Failed to detect directory for {provider_id}: {e}")
                providers[provider_id] = DetectedDirectory(
                    path=None,
                    exists=False,
                    model_count=None
                )

        return DetectDirectoriesResponse(providers=providers)

    except Exception as e:
        logger.error(f"Failed to detect models directories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect models directories: {str(e)}"
        )


@router.get("/models/files", response_model=ModelFilesResponse)
async def list_model_files(
    provider_id: Optional[str] = Query(None, description="Provider ID to use its models directory"),
    path: Optional[str] = Query(None, description="Custom directory path (overrides provider_id)")
):
    """
    Browse model files in a directory.

    Query parameters:
    - provider_id: Use this provider's models directory (e.g., 'ollama', 'llamacpp')
    - path: Custom directory path (takes precedence over provider_id)

    Returns:
    - List of model files with metadata (size, modified time, etc.)
    - Files are sorted by modification time (newest first)

    Security:
    - Path traversal attacks are prevented
    - Only files within the specified directory are listed
    - Only model files (.gguf, .bin, .safetensors, etc.) are included

    Raises:
        HTTPException: With standardized error format for various failure scenarios

    Example response:
    ```json
    {
      "directory": "/Users/username/.ollama/models",
      "files": [
        {
          "name": "model.gguf",
          "size": 4294967296,
          "size_human": "4.0 GB",
          "modified": "2026-01-20T10:30:00",
          "extension": ".gguf"
        }
      ]
    }
    ```
    """
    try:
        # Get allowed directories for security validation
        allowed_dirs = get_allowed_directories()

        # Determine directory to browse
        directory = None

        if path:
            # Use custom path (with security validation)
            # First check if path is in allowed directories
            is_safe, error_msg = is_safe_path(path, allowed_dirs)
            if not is_safe:
                providers_errors.raise_provider_error(
                    code=providers_errors.INVALID_PATH,
                    message="Access denied: Path not in allowed directories",
                    details={
                        "path": path,
                        "error": error_msg,
                        "allowed_directories": [str(d) for d in allowed_dirs]
                    },
                    suggestion="Only directories configured in models settings can be accessed. Configure this directory first.",
                    status_code=403
                )

            # Normalize the path
            from agentos.providers import platform_utils
            directory = platform_utils.expand_user_path(path)

        elif provider_id:
            # Use provider's models directory
            config_manager = ProvidersConfigManager()
            directory = config_manager.get_models_directory(provider_id)

            if not directory:
                providers_errors.raise_provider_error(
                    code=providers_errors.CONFIG_ERROR,
                    message=f"Models directory not configured for provider '{provider_id}'",
                    details={"provider_id": provider_id},
                    suggestion=f"Configure models directory for {provider_id} first",
                    status_code=404
                )
        else:
            providers_errors.raise_provider_error(
                code=providers_errors.INVALID_CONFIG,
                message="Either provider_id or path parameter must be specified",
                details={},
                suggestion="Provide either provider_id or path query parameter",
                status_code=400
            )

        # Validate directory exists
        if not directory.exists():
            error_info = providers_errors.build_directory_not_found_error(
                path=str(directory),
                provider_id=provider_id
            )
            providers_errors.raise_provider_error(**error_info)

        if not directory.is_dir():
            providers_errors.raise_provider_error(
                code=providers_errors.NOT_A_DIRECTORY,
                message=f"Path is not a directory: {directory}",
                details={"path": str(directory)},
                suggestion="Provide a path to a directory, not a file",
                status_code=400
            )

        # Additional security: Validate resolved path is still absolute and safe
        try:
            resolved = directory.resolve()
            if not resolved.is_absolute():
                providers_errors.raise_provider_error(
                    code=providers_errors.INVALID_PATH,
                    message="Path must be absolute after resolution",
                    details={"path": str(directory), "resolved": str(resolved)},
                    suggestion="Provide an absolute path",
                    status_code=400
                )
        except (ValueError, RuntimeError, OSError) as e:
            providers_errors.raise_provider_error(
                code=providers_errors.INVALID_PATH,
                message=f"Invalid path: {str(e)}",
                details={"path": str(directory)},
                suggestion="Check path syntax and permissions",
                status_code=400
            )

        # List model files
        files = []

        try:
            for item in directory.iterdir():
                if item.is_file() and is_model_file(item):
                    try:
                        stat = item.stat()
                        modified = datetime.fromtimestamp(stat.st_mtime)

                        files.append(ModelFileInfo(
                            name=item.name,
                            size=stat.st_size,
                            size_human=format_file_size(stat.st_size),
                            modified=iso_z(modified),
                            extension=item.suffix
                        ))
                    except (OSError, ValueError) as e:
                        logger.warning(f"Failed to get info for {item}: {e}")
                        continue

        except PermissionError:
            error_info = providers_errors.build_permission_denied_error(
                path=str(directory),
                operation="read"
            )
            providers_errors.raise_provider_error(**error_info)
        except OSError as e:
            providers_errors.log_provider_error(
                error_code=providers_errors.INTERNAL_ERROR,
                message=f"Error reading directory {directory}",
                exc=e
            )
            providers_errors.raise_provider_error(
                code=providers_errors.INTERNAL_ERROR,
                message=f"Error reading directory: {str(e)}",
                details={"directory": str(directory)},
                suggestion="Check directory permissions and disk health",
                status_code=500
            )

        # Sort by modification time (newest first)
        files.sort(key=lambda f: f.modified, reverse=True)

        logger.info(f"Listed {len(files)} model files from {directory}")

        return ModelFilesResponse(
            directory=str(directory),
            files=files
        )

    except HTTPException:
        raise
    except Exception as e:
        providers_errors.log_provider_error(
            error_code=providers_errors.INTERNAL_ERROR,
            message="Failed to list model files",
            exc=e
        )
        providers_errors.raise_provider_error(
            code=providers_errors.INTERNAL_ERROR,
            message=f"Failed to list model files: {str(e)}",
            details={},
            suggestion="Check server logs for more details",
            status_code=500
        )
