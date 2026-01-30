"""
Model Management API - WebUI endpoints for AI model download and management

Provides comprehensive model management capabilities including:
- List installed models (Ollama)
- Get available/recommended models
- Download models with progress tracking
- Delete models
- Check service status

Part of Models Management Feature
"""

import logging
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from agentos.cli.provider_checker import ProviderChecker
from agentos.webui.api.contracts import ReasonCode

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances
_checker: Optional[ProviderChecker] = None

# Global pull progress tracking
_pull_progress: Dict[str, Dict[str, Any]] = {}
_pull_progress_lock = threading.Lock()


def translate_provider_status(status_str: str) -> str:
    """
    Translate Chinese status messages to English

    Args:
        status_str: Status string from ProviderChecker (may contain Chinese)

    Returns:
        Translated English status string
    """
    if not status_str:
        return status_str

    # Order matters: longer phrases first to avoid partial replacements
    translations = [
        ("已安装，服务Not Running", "Installed, service not running"),
        ("进程Running", "Process running"),
        ("个模型", "models"),
        ("Running", "Running"),
        ("Not Running", "Not Running"),
        ("命令不存在", "Command not found"),
        ("不Available", "Not Available"),
        ("Available", "Available"),
        ("已安装", "Installed"),
        ("未知错误", "Unknown error"),
    ]

    # Replace each Chinese phrase with English
    result = status_str
    for cn, en in translations:
        result = result.replace(cn, en)

    return result


def get_checker() -> ProviderChecker:
    """Get provider checker instance"""
    global _checker
    if _checker is None:
        _checker = ProviderChecker()
    return _checker


# ============================================
# Request/Response Models
# ============================================

class ModelInfo(BaseModel):
    """Model information"""
    name: str
    provider: str = "ollama"
    size: Optional[str] = None
    modified: Optional[str] = None
    digest: Optional[str] = None
    family: Optional[str] = None
    parameters: Optional[str] = None


class ModelsListResponse(BaseModel):
    """Models list response"""
    models: List[ModelInfo]


class RecommendedModel(BaseModel):
    """Recommended model information"""
    name: str
    display_name: str
    description: str
    size: str
    tags: List[str] = Field(default_factory=list)


class AvailableModelsResponse(BaseModel):
    """Available models response"""
    recommended: List[RecommendedModel]


class PullModelRequest(BaseModel):
    """Pull model request"""
    model_name: str = Field(description="Model name to pull (e.g., llama3.2:3b)")


class PullModelResponse(BaseModel):
    """Pull model response"""
    pull_id: str
    status: str


class PullProgressResponse(BaseModel):
    """Pull progress response"""
    pull_id: str
    model_name: str
    status: str  # PULLING, COMPLETED, FAILED
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    error: Optional[str] = None
    total_bytes: Optional[int] = None
    downloaded_bytes: Optional[int] = None


class DeleteModelResponse(BaseModel):
    """Delete model response"""
    success: bool
    message: str


class ServiceStatus(BaseModel):
    """Service status information"""
    name: str
    available: bool
    info: Optional[str] = None
    running: bool = False


class ServiceStatusResponse(BaseModel):
    """Service status response"""
    services: List[ServiceStatus]


# ============================================
# API Endpoints
# ============================================

@router.get("/api/models/list", response_model=ModelsListResponse)
async def list_models():
    """
    Get list of installed models

    Returns list of models from Ollama service.

    Returns:
    {
        "models": [
            {
                "name": "llama3.2:3b",
                "provider": "ollama",
                "size": "2.0 GB",
                "modified": "2024-01-15T10:30:00Z",
                "digest": "sha256:abc123...",
                "family": "llama"
            }
        ]
    }
    """
    try:
        checker = get_checker()

        # Check if Ollama is running
        available, info = checker.check_ollama()
        translated_info = translate_provider_status(info)
        if not available or "Running" not in translated_info:
            return ModelsListResponse(models=[])

        # Get models from Ollama API with details
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)

            if response.status_code == 200:
                data = response.json()
                models_data = data.get("models", [])

                models = []
                for model in models_data:
                    # Convert size to human-readable format
                    size_bytes = model.get("size", 0)
                    size_gb = size_bytes / (1024 ** 3)
                    size_str = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.0f} MB"

                    # Convert modified timestamp
                    modified_at = model.get("modified_at")
                    modified_str = None
                    if modified_at:
                        try:
                            # Try to parse ISO format timestamp with standard library
                            if modified_at.endswith('Z'):
                                modified_at = modified_at[:-1] + '+00:00'
                            dt = datetime.fromisoformat(modified_at)
                            modified_str = dt.isoformat()
                        except:
                            # If parsing fails, use raw value
                            modified_str = modified_at

                    # Extract parameter size
                    parameter_size = model.get("details", {}).get("parameter_size")

                    models.append(ModelInfo(
                        name=model.get("name", ""),
                        provider="ollama",
                        size=size_str,
                        modified=modified_str,
                        digest=model.get("digest", "")[:16] + "..." if model.get("digest") else None,
                        family=model.get("details", {}).get("family"),
                        parameters=parameter_size
                    ))

                return ModelsListResponse(models=models)
            else:
                logger.warning(f"Failed to get models from Ollama: {response.status_code}")
                return ModelsListResponse(models=[])

        except Exception as e:
            logger.error(f"Failed to get model details: {e}", exc_info=True)
            # Fallback to simple model list
            model_names = checker.get_ollama_models()
            models = [
                ModelInfo(name=name, provider="ollama")
                for name in model_names
            ]
            return ModelsListResponse(models=models)

    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to list models",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/models/available", response_model=AvailableModelsResponse)
async def get_available_models():
    """
    Get list of recommended models

    Returns a curated list of recommended models for download.

    Returns:
    {
        "recommended": [
            {
                "name": "qwen2.5:7b",
                "display_name": "Qwen 2.5 (7B)",
                "description": "中文优化的大语言模型",
                "size": "4.7 GB",
                "tags": ["chat", "code", "chinese"]
            }
        ]
    }
    """
    try:
        recommended = [
            RecommendedModel(
                name="qwen2.5:7b",
                display_name="Qwen 2.5 (7B)",
                description="Chinese-optimized LLM with code generation support",
                size="4.7 GB",
                tags=["chat", "code", "chinese"]
            ),
            RecommendedModel(
                name="llama3.2:3b",
                display_name="Llama 3.2 (3B)",
                description="Fast response, suitable for daily conversations",
                size="2.0 GB",
                tags=["chat", "fast"]
            ),
            RecommendedModel(
                name="llama3.2:1b",
                display_name="Llama 3.2 (1B)",
                description="Ultra-lightweight with fast response",
                size="1.3 GB",
                tags=["chat", "fast", "lightweight"]
            ),
            RecommendedModel(
                name="gemma2:2b",
                display_name="Gemma 2 (2B)",
                description="Google's open-source model, lightweight and efficient",
                size="1.6 GB",
                tags=["chat", "fast", "google"]
            ),
            RecommendedModel(
                name="qwen2.5-coder:7b",
                display_name="Qwen 2.5 Coder (7B)",
                description="Specialized model for code generation",
                size="4.7 GB",
                tags=["code", "chinese"]
            ),
            RecommendedModel(
                name="phi3:mini",
                display_name="Phi-3 Mini",
                description="Microsoft's compact model with strong performance",
                size="2.3 GB",
                tags=["chat", "fast", "efficient"]
            ),
            RecommendedModel(
                name="mistral:7b",
                display_name="Mistral (7B)",
                description="High-performance open model from Mistral AI",
                size="4.1 GB",
                tags=["chat", "versatile"]
            ),
            RecommendedModel(
                name="codellama:7b",
                display_name="Code Llama (7B)",
                description="Specialized for code generation and completion",
                size="3.8 GB",
                tags=["code"]
            ),
        ]

        return AvailableModelsResponse(recommended=recommended)

    except Exception as e:
        logger.error(f"Failed to get available models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get available models",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.post("/api/models/pull", response_model=PullModelResponse)
async def pull_model(request: PullModelRequest):
    """
    Start downloading a model

    Starts a background thread to pull the model from Ollama registry.
    Returns a pull_id that can be used to track progress.

    Body:
    {
        "model_name": "llama3.2:3b"
    }

    Returns:
    {
        "pull_id": "pull_abc123",
        "status": "PULLING"
    }
    """
    try:
        checker = get_checker()

        # Check if Ollama is running
        available, info = checker.check_ollama()
        translated_info = translate_provider_status(info)
        if not available or "Running" not in translated_info:
            raise HTTPException(
                status_code=503,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Ollama service not running",
                    "hint": "Start Ollama service with 'ollama serve'",
                    "reason_code": ReasonCode.SERVICE_UNAVAILABLE
                }
            )

        # Generate pull ID
        pull_id = f"pull_{uuid.uuid4().hex[:12]}"
        model_name = request.model_name

        # Initialize progress tracking
        with _pull_progress_lock:
            _pull_progress[pull_id] = {
                "pull_id": pull_id,
                "model_name": model_name,
                "status": "PULLING",
                "progress": 0,
                "current_step": "Starting download...",
                "error": None,
                "total_bytes": None,
                "downloaded_bytes": None,
                "started_at": datetime.now(timezone.utc).isoformat()
            }

        # Start background thread to pull model
        def pull_model_background():
            try:
                logger.info(f"Starting model pull: {model_name} (pull_id={pull_id})")

                # Run ollama pull command
                process = subprocess.Popen(
                    ["ollama", "pull", model_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Parse output for progress
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue

                    logger.debug(f"Pull output: {line}")

                    # Update progress based on output
                    with _pull_progress_lock:
                        if pull_id not in _pull_progress:
                            break

                        # Parse progress from line
                        if "pulling manifest" in line.lower():
                            _pull_progress[pull_id]["current_step"] = "Pulling manifest"
                            _pull_progress[pull_id]["progress"] = 10
                        elif "pulling" in line.lower() and "%" in line:
                            # Extract percentage if available
                            try:
                                # Example: "pulling 4c7f9d6...: 45%"
                                parts = line.split("%")
                                if parts:
                                    # Find the last number before %
                                    percent_part = parts[0].split()[-1]
                                    progress = int(float(percent_part))
                                    _pull_progress[pull_id]["progress"] = min(90, 10 + int(progress * 0.8))
                                    _pull_progress[pull_id]["current_step"] = f"Downloading: {progress}%"
                            except:
                                pass
                        elif "verifying" in line.lower():
                            _pull_progress[pull_id]["current_step"] = "Verifying checksum"
                            _pull_progress[pull_id]["progress"] = 95
                        elif "success" in line.lower():
                            _pull_progress[pull_id]["current_step"] = "Download complete"
                            _pull_progress[pull_id]["progress"] = 100

                process.wait()

                # Update final status
                with _pull_progress_lock:
                    if pull_id in _pull_progress:
                        if process.returncode == 0:
                            _pull_progress[pull_id]["status"] = "COMPLETED"
                            _pull_progress[pull_id]["progress"] = 100
                            _pull_progress[pull_id]["current_step"] = "Download complete"
                            logger.info(f"Model pull completed: {model_name}")
                        else:
                            _pull_progress[pull_id]["status"] = "FAILED"
                            _pull_progress[pull_id]["error"] = f"Pull failed with exit code {process.returncode}"
                            logger.error(f"Model pull failed: {model_name}, exit code {process.returncode}")

            except Exception as e:
                logger.error(f"Model pull background thread failed: {e}", exc_info=True)
                with _pull_progress_lock:
                    if pull_id in _pull_progress:
                        _pull_progress[pull_id]["status"] = "FAILED"
                        _pull_progress[pull_id]["error"] = str(e)

        # Start background thread
        thread = threading.Thread(target=pull_model_background, daemon=True)
        thread.start()

        return PullModelResponse(
            pull_id=pull_id,
            status="PULLING"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start model pull: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Failed to start model pull: {str(e)}",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/models/pull/{pull_id}", response_model=PullProgressResponse)
async def get_pull_progress(pull_id: str):
    """
    Query download progress

    Returns real-time progress information for an ongoing model download.

    Returns:
    {
        "pull_id": "pull_abc123",
        "model_name": "llama3.2:3b",
        "status": "PULLING",
        "progress": 45,
        "current_step": "Downloading: 45%",
        "error": null,
        "total_bytes": 2147483648,
        "downloaded_bytes": 966367641
    }
    """
    try:
        with _pull_progress_lock:
            if pull_id not in _pull_progress:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "ok": False,
                        "data": None,
                        "error": f"Pull record not found: {pull_id}",
                        "hint": "Check the pull_id and try again",
                        "reason_code": ReasonCode.NOT_FOUND
                    }
                )

            progress_data = _pull_progress[pull_id].copy()

        return PullProgressResponse(**progress_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pull progress: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get pull progress",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.delete("/api/models/{provider}/{model_name}", response_model=DeleteModelResponse)
async def delete_model(provider: str, model_name: str):
    """
    Delete an installed model

    Removes the model from the provider (currently only Ollama is supported).

    Returns:
    {
        "success": true,
        "message": "Model deleted successfully"
    }
    """
    try:
        if provider != "ollama":
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "data": None,
                    "error": f"Unsupported provider: {provider}",
                    "hint": "Only 'ollama' provider is currently supported",
                    "reason_code": ReasonCode.INVALID_INPUT
                }
            )

        checker = get_checker()

        # Check if Ollama is running
        available, info = checker.check_ollama()
        translated_info = translate_provider_status(info)
        if not available or "Running" not in translated_info:
            raise HTTPException(
                status_code=503,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Ollama service not running",
                    "hint": "Start Ollama service with 'ollama serve'",
                    "reason_code": ReasonCode.SERVICE_UNAVAILABLE
                }
            )

        # Delete model using ollama rm command
        try:
            result = subprocess.run(
                ["ollama", "rm", model_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Model deleted successfully: {model_name}")
                return DeleteModelResponse(
                    success=True,
                    message=f"Model '{model_name}' deleted successfully"
                )
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"Failed to delete model: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "ok": False,
                        "data": None,
                        "error": f"Failed to delete model: {error_msg}",
                        "hint": "Check if the model exists and Ollama is running",
                        "reason_code": ReasonCode.INTERNAL_ERROR
                    }
                )

        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=500,
                detail={
                    "ok": False,
                    "data": None,
                    "error": "Model deletion timed out",
                    "hint": "Try again later",
                    "reason_code": ReasonCode.INTERNAL_ERROR
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Failed to delete model: {str(e)}",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/models/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """
    Get AI provider service status

    Checks the status of all supported AI providers.

    Returns:
    {
        "services": [
            {
                "name": "Ollama",
                "available": true,
                "info": "v0.1.20 (Running)",
                "running": true
            },
            {
                "name": "LM Studio",
                "available": false,
                "info": "Not Running",
                "running": false
            }
        ]
    }
    """
    try:
        checker = get_checker()
        provider_status = checker.get_provider_status()

        services = []
        for provider_key, provider_data in provider_status.items():
            available = provider_data["available"]
            info = provider_data["info"]
            name = provider_data["name"]

            # Translate Chinese status messages to English
            translated_info = translate_provider_status(info)

            # Determine if service is running (for Ollama)
            running = False
            if provider_key == "ollama" and available:
                running = "Running" in translated_info

            services.append(ServiceStatus(
                name=name,
                available=available,
                info=translated_info,
                running=running
            ))

        return ServiceStatusResponse(services=services)

    except Exception as e:
        logger.error(f"Failed to get service status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": "Failed to get service status",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


# ============================================
# Cleanup on shutdown
# ============================================

def cleanup_pull_progress():
    """Clean up old pull progress records (older than 1 hour)"""
    with _pull_progress_lock:
        now = datetime.now(timezone.utc)
        to_remove = []

        for pull_id, data in _pull_progress.items():
            if data["status"] in ["COMPLETED", "FAILED"]:
                try:
                    started_at = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
                    age_seconds = (now - started_at).total_seconds()

                    # Remove records older than 1 hour
                    if age_seconds > 3600:
                        to_remove.append(pull_id)
                except:
                    pass

        for pull_id in to_remove:
            del _pull_progress[pull_id]
            logger.debug(f"Cleaned up old pull progress record: {pull_id}")


# Start cleanup task in background
def start_cleanup_task():
    """Start background cleanup task"""
    def cleanup_loop():
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                cleanup_pull_progress()
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}", exc_info=True)

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info("Pull progress cleanup task started")


# Start cleanup on module load
start_cleanup_task()
