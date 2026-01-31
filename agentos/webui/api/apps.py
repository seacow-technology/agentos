"""
AppOS WebUI API

提供 App 管理的 HTTP API
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from agentos.core.appos import AppOSService, AppStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局服务实例
_appos_service: Optional[AppOSService] = None


def initialize_appos() -> None:
    """
    初始化 AppOS 服务

    在 WebUI 启动时调用
    """
    global _appos_service
    try:
        _appos_service = AppOSService()
        logger.info("AppOS service initialized successfully")

        # 自动安装内置 App（如果未安装）
        _install_builtin_apps()

    except Exception as e:
        logger.error(f"Failed to initialize AppOS service: {e}", exc_info=True)
        raise


def _install_builtin_apps() -> None:
    """自动安装内置 App"""
    if not _appos_service:
        return

    # Personal Assistant manifest 路径
    manifest_path = Path(__file__).parent.parent.parent / \
                   "core/appos/apps/personal_assistant/manifest.yaml"

    if not manifest_path.exists():
        logger.warning(f"Personal Assistant manifest not found: {manifest_path}")
        return

    try:
        # 检查是否已安装
        existing = _appos_service.get_app("personal_assistant")
        if existing:
            logger.info("Personal Assistant already installed")
            return

        # 安装
        _appos_service.install_app(str(manifest_path))
        logger.info("Personal Assistant installed successfully")

    except Exception as e:
        logger.warning(f"Failed to install Personal Assistant: {e}")


def get_appos_service() -> AppOSService:
    """
    获取 AppOS 服务实例

    Raises:
        HTTPException: 服务未初始化
    """
    if _appos_service is None:
        raise HTTPException(status_code=503, detail="AppOS service not initialized")
    return _appos_service


# ========== Request/Response Models ==========

class AppResponse(BaseModel):
    """App 响应模型"""
    app_id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    status: str
    installed_at: int
    updated_at: int


class AppStatusResponse(BaseModel):
    """App 状态响应模型"""
    app_id: str
    name: str
    version: str
    status: str
    installed_at: int
    updated_at: int
    total_instances: int
    running_instances: int
    instances: List[Dict[str, Any]]


class StartAppRequest(BaseModel):
    """启动 App 请求模型"""
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="实例元数据")


class StartAppResponse(BaseModel):
    """启动 App 响应模型"""
    instance_id: str
    message: str


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    total_apps: int
    running_instances: int
    healthy_instances: int
    unhealthy_instances: int


# ========== API Endpoints ==========

@router.get("/apps", response_model=List[AppResponse])
def list_apps(status: Optional[str] = None):
    """
    列出所有 App

    Args:
        status: 过滤状态（可选）
    """
    service = get_appos_service()

    # 解析状态
    status_filter = None
    if status:
        try:
            status_filter = AppStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    apps = service.list_apps(status_filter)

    return [
        AppResponse(
            app_id=app.app_id,
            name=app.manifest.name,
            version=app.manifest.version,
            description=app.manifest.description,
            author=app.manifest.author,
            category=app.manifest.category,
            status=app.status.value,
            installed_at=app.installed_at,
            updated_at=app.updated_at,
        )
        for app in apps
    ]


@router.post("/apps/{app_id}/start", response_model=StartAppResponse)
def start_app(app_id: str, request: StartAppRequest = Body(default=StartAppRequest())):
    """
    启动 App

    Args:
        app_id: App ID
        request: 启动请求
    """
    service = get_appos_service()

    try:
        instance_id = service.start_app(app_id, request.metadata)
        return StartAppResponse(
            instance_id=instance_id,
            message=f"App {app_id} started successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apps/{app_id}/stop")
def stop_app(app_id: str):
    """
    停止 App

    Args:
        app_id: App ID
    """
    service = get_appos_service()

    try:
        service.stop_app(app_id)
        return {"message": f"App {app_id} stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop app {app_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apps/{app_id}/status", response_model=AppStatusResponse)
def get_app_status(app_id: str):
    """
    获取 App 状态

    Args:
        app_id: App ID
    """
    service = get_appos_service()

    try:
        status = service.get_app_status(app_id)
        return AppStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/apps/health", response_model=HealthCheckResponse)
def health_check():
    """
    系统健康检查
    """
    service = get_appos_service()

    try:
        health = service.health_check()
        return HealthCheckResponse(
            total_apps=health['total_apps'],
            running_instances=health['running_instances'],
            healthy_instances=health['healthy_instances'],
            unhealthy_instances=health['unhealthy_instances'],
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
