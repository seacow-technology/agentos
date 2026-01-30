"""
Extension Management API - WebUI endpoints for extension installation and management

Provides comprehensive extension management capabilities including:
- List all extensions (with filtering by status and enabled state)
- Get extension details (including usage docs and commands)
- Install extensions (from ZIP upload or URL)
- Track installation progress (real-time polling)
- Enable/disable extensions
- Configure extensions
- Uninstall extensions
- View extension logs

Part of PR-C: WebUI Extensions Management
"""

import logging
import mimetypes
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.engine import ExtensionInstallEngine
from agentos.core.extensions.installer import ZipInstaller
from agentos.core.extensions.validator import ExtensionValidator
from agentos.core.extensions.models import (
    ExtensionStatus,
    InstallStatus,
    InstallSource,
    ExtensionManifest,
    ExtensionCapability,
)
from agentos.core.extensions.exceptions import RegistryError, InstallationError, ValidationError
from agentos.webui.api.contracts import ReasonCode

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (initialized on startup)
_registry: Optional[ExtensionRegistry] = None
_engine: Optional[ExtensionInstallEngine] = None
_installer: Optional[ZipInstaller] = None


def get_registry() -> ExtensionRegistry:
    """Get extension registry instance"""
    global _registry
    if _registry is None:
        _registry = ExtensionRegistry()
    return _registry


def get_engine() -> ExtensionInstallEngine:
    """Get install engine instance"""
    global _engine
    if _engine is None:
        _engine = ExtensionInstallEngine(registry=get_registry())
    return _engine


def get_installer() -> ZipInstaller:
    """Get zip installer instance"""
    global _installer
    if _installer is None:
        from agentos.store import get_store_path
        extensions_dir = get_store_path("extensions")
        _installer = ZipInstaller(extensions_dir=Path(extensions_dir))
    return _installer


# ============================================
# Request/Response Models
# ============================================

class ExtensionCapabilityResponse(BaseModel):
    """Extension capability response"""
    type: str
    name: str
    description: str = ""
    config: Optional[Dict[str, Any]] = None


class ExtensionListItem(BaseModel):
    """Extension list item (summary)"""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    icon_path: Optional[str] = None
    enabled: bool
    status: str
    installed_at: str
    permissions_required: List[str] = Field(default_factory=list)
    capabilities: List[ExtensionCapabilityResponse] = Field(default_factory=list)


class ExtensionDetail(BaseModel):
    """Extension detailed information"""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    icon_path: Optional[str] = None
    enabled: bool
    status: str
    installed_at: str
    permissions_required: List[str] = Field(default_factory=list)
    capabilities: List[ExtensionCapabilityResponse] = Field(default_factory=list)
    usage_doc: Optional[str] = None
    commands: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class InstallFromURLRequest(BaseModel):
    """Install extension from URL request"""
    url: str = Field(description="URL to download the extension ZIP file")
    sha256: Optional[str] = Field(default=None, description="Expected SHA256 hash for verification")


class InstallResponse(BaseModel):
    """Installation started response"""
    install_id: str
    extension_id: Optional[str] = None
    status: str


class InstallProgressResponse(BaseModel):
    """Installation progress response"""
    install_id: str
    extension_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    completed_steps: Optional[int] = None
    error: Optional[str] = None


class EnableDisableResponse(BaseModel):
    """Enable/disable extension response"""
    success: bool
    enabled: bool


class UninstallResponse(BaseModel):
    """Uninstall extension response"""
    success: bool
    message: str


class ConfigResponse(BaseModel):
    """Extension configuration response"""
    config: Dict[str, Any]


class UpdateConfigRequest(BaseModel):
    """Update extension configuration request"""
    config: Dict[str, Any]


class LogEntry(BaseModel):
    """Extension log entry"""
    timestamp: str
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None


class LogsResponse(BaseModel):
    """Extension logs response"""
    logs: List[LogEntry]
    total: int


# ============================================
# API Endpoints
# ============================================

@router.get("/api/extensions", response_model=Dict[str, List[ExtensionListItem]])
async def list_extensions(
    enabled_only: bool = Query(False, description="Only return enabled extensions"),
    status: Optional[str] = Query(None, description="Filter by status (INSTALLED, INSTALLING, FAILED)")
):
    """
    List all extensions with optional filtering

    Query params:
    - enabled_only: Only return enabled extensions (default: False)
    - status: Filter by status (INSTALLED, INSTALLING, FAILED)

    Returns:
    {
        "extensions": [
            {
                "id": "tools.postman",
                "name": "Postman Toolkit",
                "version": "0.1.0",
                "description": "...",
                "icon_path": "/api/extensions/tools.postman/icon",
                "enabled": true,
                "status": "INSTALLED",
                "installed_at": "2024-01-15T10:30:00Z",
                "permissions_required": ["network", "exec"],
                "capabilities": [...]
            }
        ]
    }
    """
    try:
        registry = get_registry()
        extensions = registry.list_extensions()

        # Apply filters
        filtered = extensions
        if enabled_only:
            filtered = [ext for ext in filtered if ext.enabled]
        if status:
            filtered = [ext for ext in filtered if ext.status.value == status]

        # Convert to response format
        result = []
        for ext in filtered:
            # Set icon path if icon exists
            icon_path = None
            if ext.icon_path:
                icon_path = f"/api/extensions/{ext.id}/icon"

            # Convert capabilities
            capabilities = [
                ExtensionCapabilityResponse(
                    type=cap.type.value,
                    name=cap.name,
                    description=cap.description,
                    config=cap.config
                )
                for cap in ext.capabilities
            ]

            result.append(ExtensionListItem(
                id=ext.id,
                name=ext.name,
                version=ext.version,
                description=ext.description,
                icon_path=icon_path,
                enabled=ext.enabled,
                status=ext.status.value,
                installed_at=ext.installed_at.isoformat(),
                permissions_required=ext.permissions_required,
                capabilities=capabilities
            ))

        return {"extensions": result}

    except Exception as e:
        logger.error(f"Failed to list extensions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to list extensions",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/{extension_id}", response_model=ExtensionDetail)
async def get_extension_detail(extension_id: str):
    """
    Get detailed information about a specific extension

    Returns extension details including:
    - Basic metadata
    - Capabilities and permissions
    - Usage documentation (from docs/USAGE.md)
    - Commands configuration (from commands/commands.yaml)
    """
    try:
        registry = get_registry()
        ext = registry.get_extension(extension_id)

        if ext is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Extension not found: {extension_id}",
                    "hint": "Check the extension ID and try again",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        # Get extension installation directory
        from agentos.store import get_store_path
        ext_dir = get_store_path("extensions") / extension_id

        # Read usage documentation
        usage_doc = None
        usage_doc_path = ext_dir / "docs" / "USAGE.md"
        if usage_doc_path.exists():
            usage_doc = usage_doc_path.read_text(encoding="utf-8")

        # Read commands configuration
        commands = None
        commands_path = ext_dir / "commands" / "commands.yaml"
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                commands = yaml.safe_load(f)

        # Set icon path if icon exists
        icon_path = None
        if ext.icon_path:
            icon_path = f"/api/extensions/{ext.id}/icon"

        # Convert capabilities
        capabilities = [
            ExtensionCapabilityResponse(
                type=cap.type.value,
                name=cap.name,
                description=cap.description,
                config=cap.config
            )
            for cap in ext.capabilities
        ]

        return ExtensionDetail(
            id=ext.id,
            name=ext.name,
            version=ext.version,
            description=ext.description,
            icon_path=icon_path,
            enabled=ext.enabled,
            status=ext.status.value,
            installed_at=ext.installed_at.isoformat(),
            permissions_required=ext.permissions_required,
            capabilities=capabilities,
            usage_doc=usage_doc,
            commands=commands,
            metadata=ext.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extension details: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get extension details",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/{extension_id}/icon")
async def get_extension_icon(extension_id: str):
    """
    Get extension icon file

    Returns the icon image file if it exists, otherwise 404
    """
    try:
        registry = get_registry()
        ext = registry.get_extension(extension_id)

        if ext is None or not ext.icon_path:
            raise HTTPException(status_code=404, detail="Icon not found")

        # Get absolute path to icon
        from agentos.store import get_store_path
        ext_dir = get_store_path("extensions") / extension_id
        icon_path = ext_dir / ext.icon_path

        if not icon_path.exists():
            raise HTTPException(status_code=404, detail="Icon file not found")

        # Determine media type
        media_type = mimetypes.guess_type(str(icon_path))[0] or "application/octet-stream"

        return FileResponse(
            path=str(icon_path),
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extension icon: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve icon")


@router.post("/api/extensions/install", response_model=InstallResponse)
async def install_extension_upload(file: UploadFile = File(...)):
    """
    Install extension from uploaded ZIP file

    Body: multipart/form-data with 'file' field containing the ZIP

    Returns:
    {
        "install_id": "inst_abc123",
        "extension_id": "tools.postman",
        "status": "INSTALLING"
    }
    """
    temp_file = None
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith('.zip'):
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Invalid file type",
                    "hint": "Only ZIP files are allowed",
                    "reason_code": ReasonCode.INVALID_INPUT
                }
            )

        # Save uploaded file to temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        # Start installation in background
        install_id = f"inst_{uuid.uuid4().hex[:12]}"
        zip_path = Path(temp_file.name)

        # Create install record immediately (before validation)
        # This ensures the frontend can query the status even if validation fails
        registry = get_registry()
        try:
            registry.create_install_record_without_fk(
                install_id=install_id,
                extension_id="unknown",
                status=InstallStatus.INSTALLING
            )
            logger.info(f"Created install record: {install_id}")
        except Exception as e:
            logger.error(f"Failed to create install record: {e}")
            # Continue anyway - the record will be created later if possible

        # Start installation in a background thread
        import asyncio
        import threading

        def run_installation():
            try:
                installer = get_installer()
                registry = get_registry()
                engine = get_engine()

                # Extract and validate first to get extension_id
                try:
                    manifest, sha256, install_dir = installer.install_from_upload(
                        zip_path=zip_path,
                        expected_sha256=None
                    )
                except Exception as validation_error:
                    # Validation failed - update install record with error
                    logger.error(f"Validation failed: {validation_error}")
                    registry.update_install_progress(
                        install_id=install_id,
                        progress=0,
                        current_step=f"Validation failed",
                        extension_id="unknown"
                    )
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=str(validation_error)
                    )
                    return

                # Update install record with actual extension_id
                registry.update_install_progress(
                    install_id=install_id,
                    progress=10,
                    current_step="Extension validated",
                    extension_id=manifest.id
                )

                # Check if extension already exists
                existing = registry.get_extension(manifest.id)
                if existing:
                    # If existing installation is incomplete, clean it up
                    if existing.status in [ExtensionStatus.INSTALLING, ExtensionStatus.FAILED]:
                        logger.info(f"Cleaning up previous incomplete installation: {manifest.id}")
                        # Remove database record
                        registry.unregister_extension(manifest.id)
                        # Remove installation directory
                        from agentos.store import get_store_path
                        ext_dir = get_store_path("extensions") / manifest.id
                        if ext_dir.exists():
                            shutil.rmtree(ext_dir)
                    else:
                        # Extension is already installed and in good state - skip installation
                        logger.info(f"Extension '{manifest.id}' is already installed, skipping installation")
                        registry.complete_install(
                            install_id=install_id,
                            status=InstallStatus.COMPLETED,
                            error=None
                        )
                        # Clean up temp file
                        try:
                            os.unlink(zip_path)
                        except:
                            pass
                        return

                # Register extension with INSTALLING status (placeholder for foreign key)
                registry.register_extension(
                    manifest=manifest,
                    sha256=sha256,
                    source=InstallSource.UPLOAD,
                    source_url=None,
                    icon_path=manifest.icon
                )

                # Update status to INSTALLING
                registry.set_status(manifest.id, ExtensionStatus.INSTALLING)

                # Update progress
                registry.update_install_progress(
                    install_id=install_id,
                    progress=30,
                    current_step="Validating extension"
                )

                # Execute install plan
                plan_path = install_dir / manifest.install.plan
                result = engine.execute_install(
                    extension_id=manifest.id,
                    plan_yaml_path=plan_path,
                    install_id=install_id
                )

                if result.success:
                    # Update extension status to INSTALLED
                    registry.set_status(manifest.id, ExtensionStatus.INSTALLED)

                    # Mark install as complete
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.COMPLETED,
                        error=None
                    )
                else:
                    # Update extension status to FAILED
                    registry.set_status(manifest.id, ExtensionStatus.FAILED)

                    # Mark install as failed
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=result.error
                    )

            except Exception as e:
                logger.error(f"Installation failed: {e}", exc_info=True)
                # Print to console for debugging
                import traceback
                traceback.print_exc()

                # Always try to update install record with failure
                try:
                    # Try to get extension_id if available
                    if 'manifest' in locals():
                        ext_id = manifest.id
                        # Update extension status to FAILED
                        try:
                            registry.set_status(ext_id, ExtensionStatus.FAILED)
                        except Exception as status_error:
                            logger.warning(f"Failed to update extension status: {status_error}")

                    # Complete install record (this should always succeed)
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=str(e)
                    )
                    logger.info(f"Install record marked as FAILED: {install_id}")
                except Exception as completion_error:
                    logger.error(f"CRITICAL: Failed to complete install record: {completion_error}")
                    # Last resort - try to update at least the error message
                    try:
                        registry.update_install_progress(
                            install_id=install_id,
                            progress=0,
                            current_step=f"Failed: {str(e)[:100]}"
                        )
                    except:
                        logger.error(f"CRITICAL: Cannot update install record at all")
            finally:
                # Clean up temp file
                try:
                    os.unlink(zip_path)
                except:
                    pass

        # Start installation thread
        thread = threading.Thread(target=run_installation, daemon=True)
        thread.start()

        return InstallResponse(
            install_id=install_id,
            extension_id=None,  # Will be known after extraction
            status="INSTALLING"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start extension installation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Installation failed: {str(e)}",
                "hint": "Check the extension package and try again",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )
    finally:
        # Note: temp file cleanup is handled in the installation thread
        pass


@router.post("/api/extensions/install-url", response_model=InstallResponse)
async def install_extension_url(req: InstallFromURLRequest):
    """
    Install extension from URL

    Body:
    {
        "url": "https://extensions.example.com/postman-v1.0.0.zip",
        "sha256": "abc123..." (optional)
    }

    Returns:
    {
        "install_id": "inst_abc123",
        "extension_id": "tools.postman",
        "status": "INSTALLING"
    }
    """
    try:
        # Start installation in background
        install_id = f"inst_{uuid.uuid4().hex[:12]}"

        # Create install record immediately (before validation)
        registry = get_registry()
        try:
            registry.create_install_record_without_fk(
                install_id=install_id,
                extension_id="unknown",
                status=InstallStatus.INSTALLING
            )
            logger.info(f"Created install record: {install_id}")
        except Exception as e:
            logger.error(f"Failed to create install record: {e}")

        # Start installation in a background thread
        import threading

        def run_installation():
            try:
                installer = get_installer()
                registry = get_registry()
                engine = get_engine()

                # Download and validate first to get extension_id
                try:
                    manifest, sha256, install_dir = installer.install_from_url(
                        url=req.url,
                        expected_sha256=req.sha256
                    )
                except Exception as validation_error:
                    # Validation failed - update install record with error
                    logger.error(f"Validation failed: {validation_error}")
                    registry.update_install_progress(
                        install_id=install_id,
                        progress=0,
                        current_step=f"Validation failed",
                        extension_id="unknown"
                    )
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=str(validation_error)
                    )
                    return

                # Update install record with actual extension_id
                registry.update_install_progress(
                    install_id=install_id,
                    progress=10,
                    current_step="Extension validated",
                    extension_id=manifest.id
                )

                # Check if extension already exists
                existing = registry.get_extension(manifest.id)
                if existing:
                    # If existing installation is incomplete, clean it up
                    if existing.status in [ExtensionStatus.INSTALLING, ExtensionStatus.FAILED]:
                        logger.info(f"Cleaning up previous incomplete installation: {manifest.id}")
                        # Remove database record
                        registry.unregister_extension(manifest.id)
                        # Remove installation directory
                        from agentos.store import get_store_path
                        ext_dir = get_store_path("extensions") / manifest.id
                        if ext_dir.exists():
                            shutil.rmtree(ext_dir)
                    else:
                        # Extension is already installed and in good state - skip installation
                        logger.info(f"Extension '{manifest.id}' is already installed, skipping installation")
                        registry.complete_install(
                            install_id=install_id,
                            status=InstallStatus.COMPLETED,
                            error=None
                        )
                        # Clean up temp file
                        try:
                            os.unlink(zip_path)
                        except:
                            pass
                        return

                # Register extension (placeholder for foreign key)
                registry.register_extension(
                    manifest=manifest,
                    sha256=sha256,
                    source=InstallSource.URL,
                    source_url=req.url,
                    icon_path=manifest.icon
                )

                # Update status to INSTALLING
                registry.set_status(manifest.id, ExtensionStatus.INSTALLING)

                # Update progress
                registry.update_install_progress(
                    install_id=install_id,
                    progress=30,
                    current_step="Validating extension"
                )

                # Execute install plan
                plan_path = install_dir / manifest.install.plan
                result = engine.execute_install(
                    extension_id=manifest.id,
                    plan_yaml_path=plan_path,
                    install_id=install_id
                )

                if result.success:
                    # Update extension status to INSTALLED
                    registry.set_status(manifest.id, ExtensionStatus.INSTALLED)

                    # Mark install as complete
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.COMPLETED,
                        error=None
                    )
                else:
                    # Update extension status to FAILED
                    registry.set_status(manifest.id, ExtensionStatus.FAILED)

                    # Mark install as failed
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=result.error
                    )

            except Exception as e:
                logger.error(f"Installation failed: {e}", exc_info=True)
                import traceback
                traceback.print_exc()

                # Always try to update install record with failure
                try:
                    # Try to get extension_id if available
                    if 'manifest' in locals():
                        ext_id = manifest.id
                        # Update extension status to FAILED
                        try:
                            registry.set_status(ext_id, ExtensionStatus.FAILED)
                        except Exception as status_error:
                            logger.warning(f"Failed to update extension status: {status_error}")

                    # Complete install record
                    registry.complete_install(
                        install_id=install_id,
                        status=InstallStatus.FAILED,
                        error=str(e)
                    )
                    logger.info(f"Install record marked as FAILED: {install_id}")
                except Exception as completion_error:
                    logger.error(f"CRITICAL: Failed to complete install record: {completion_error}")
                    try:
                        registry.update_install_progress(
                            install_id=install_id,
                            progress=0,
                            current_step=f"Failed: {str(e)[:100]}"
                        )
                    except:
                        logger.error(f"CRITICAL: Cannot update install record at all")

        # Start installation thread
        thread = threading.Thread(target=run_installation, daemon=True)
        thread.start()

        return InstallResponse(
            install_id=install_id,
            extension_id=None,  # Will be known after extraction
            status="INSTALLING"
        )

    except Exception as e:
        logger.error(f"Failed to start extension installation from URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Installation failed: {str(e)}",
                "hint": "Check the URL and try again",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/install/{install_id}", response_model=InstallProgressResponse)
async def get_install_progress(install_id: str):
    """
    Query installation progress

    Returns real-time progress information:
    {
        "install_id": "inst_abc123",
        "extension_id": "tools.postman",
        "status": "INSTALLING",
        "progress": 60,
        "current_step": "verify",
        "total_steps": 5,
        "completed_steps": 3,
        "error": null
    }
    """
    try:
        registry = get_registry()
        install_record = registry.get_install_record(install_id)

        if install_record is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Installation record not found: {install_id}",
                    "hint": "Check the install ID and try again",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        # Calculate step information from progress
        # Assuming 5 standard steps: download, extract, validate, verify, finalize
        total_steps = 5
        completed_steps = int((install_record.progress / 100) * total_steps)

        return InstallProgressResponse(
            install_id=install_record.install_id,
            extension_id=install_record.extension_id,
            status=install_record.status.value,
            progress=install_record.progress,
            current_step=install_record.current_step,
            total_steps=total_steps,
            completed_steps=completed_steps,
            error=install_record.error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get installation progress: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get installation progress",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.post("/api/extensions/{extension_id}/enable", response_model=EnableDisableResponse)
async def enable_extension(extension_id: str):
    """
    Enable an extension

    Returns:
    {
        "success": true,
        "enabled": true
    }
    """
    try:
        registry = get_registry()
        registry.set_enabled(extension_id, enabled=True)

        return EnableDisableResponse(success=True, enabled=True)

    except RegistryError as e:
        logger.error(f"Failed to enable extension: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "data": None,
                "error": str(e),
                "hint": "Check that the extension exists",
                "reason_code": ReasonCode.NOT_FOUND
            }
        )
    except Exception as e:
        logger.error(f"Failed to enable extension: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to enable extension",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.post("/api/extensions/{extension_id}/disable", response_model=EnableDisableResponse)
async def disable_extension(extension_id: str):
    """
    Disable an extension

    Returns:
    {
        "success": true,
        "enabled": false
    }
    """
    try:
        registry = get_registry()
        registry.set_enabled(extension_id, enabled=False)

        return EnableDisableResponse(success=True, enabled=False)

    except RegistryError as e:
        logger.error(f"Failed to disable extension: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "data": None,
                "error": str(e),
                "hint": "Check that the extension exists",
                "reason_code": ReasonCode.NOT_FOUND
            }
        )
    except Exception as e:
        logger.error(f"Failed to disable extension: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to disable extension",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.delete("/api/extensions/{extension_id}", response_model=UninstallResponse)
async def uninstall_extension(extension_id: str):
    """
    Uninstall an extension

    This will:
    - Remove extension from registry
    - Delete extension files
    - Clean up any associated data

    Returns:
    {
        "success": true,
        "message": "Extension uninstalled successfully"
    }
    """
    try:
        registry = get_registry()

        # Check if extension exists
        ext = registry.get_extension(extension_id)
        if ext is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Extension not found: {extension_id}",
                    "hint": "Check the extension ID and try again",
                    "reason_code": ReasonCode.NOT_FOUND
                }
            )

        # Unregister from database
        registry.unregister_extension(extension_id)

        # Delete extension files
        from agentos.store import get_store_path
        ext_dir = get_store_path("extensions") / extension_id
        if ext_dir.exists():
            shutil.rmtree(ext_dir)

        return UninstallResponse(
            success=True,
            message="Extension uninstalled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to uninstall extension: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Failed to uninstall extension: {str(e)}",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/{extension_id}/config", response_model=ConfigResponse)
async def get_extension_config(extension_id: str):
    """
    Get extension configuration

    Returns:
    {
        "config": {
            "api_key": "***",
            "base_url": "https://api.example.com"
        }
    }

    Note: Sensitive values are masked with "***"
    """
    try:
        registry = get_registry()
        config = registry.get_config(extension_id)

        if config is None:
            return ConfigResponse(config={})

        # Mask sensitive fields
        masked_config = config.config_json.copy() if config.config_json else {}
        for key in masked_config:
            if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                masked_config[key] = "***"

        return ConfigResponse(config=masked_config)

    except Exception as e:
        logger.error(f"Failed to get extension config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get extension configuration",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.put("/api/extensions/{extension_id}/config")
async def update_extension_config(extension_id: str, req: UpdateConfigRequest):
    """
    Update extension configuration

    Body:
    {
        "config": {
            "api_key": "new_key",
            "base_url": "https://api.example.com"
        }
    }

    Returns:
    {
        "success": true
    }
    """
    try:
        registry = get_registry()
        registry.save_config(extension_id, req.config)

        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to update extension config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to update extension configuration",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/{extension_id}/logs", response_model=LogsResponse)
async def get_extension_logs(
    extension_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get extension-related logs

    Query params:
    - limit: Maximum number of logs to return (default: 100, max: 1000)
    - offset: Number of logs to skip (default: 0)

    Returns:
    {
        "logs": [
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "level": "INFO",
                "message": "Extension step executed",
                "context": {...}
            }
        ],
        "total": 250
    }
    """
    try:
        # TODO: Implement log retrieval from system_logs table
        # For now, return empty list
        # This would query: SELECT * FROM system_logs WHERE context->>'extension_id' = extension_id

        return LogsResponse(logs=[], total=0)

    except Exception as e:
        logger.error(f"Failed to get extension logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get extension logs",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )
