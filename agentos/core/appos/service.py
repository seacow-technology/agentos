"""
AppOS 服务层

提供 App 管理和操作的高级 API
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import App, AppInstance, AppManifest, AppStatus
from .store import AppOSStore
from .runtime import AppRuntime
from .manifest import load_manifest

logger = logging.getLogger(__name__)


class AppOSService:
    """
    AppOS 服务

    提供 App 的完整生命周期管理
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化服务

        Args:
            db_path: 数据库路径（可选，默认使用 ensure_db_exists("appos")）
        """
        self.store = AppOSStore(db_path)
        self.runtime = AppRuntime(self.store)
        logger.info("AppOSService initialized")

    def install_app(self, manifest_path: str) -> App:
        """
        安装 App

        Args:
            manifest_path: manifest.yaml 文件路径

        Returns:
            App 对象

        Raises:
            ValueError: manifest 无效或 App 已存在
            FileNotFoundError: manifest 文件不存在
        """
        # 加载并验证 manifest
        manifest = load_manifest(manifest_path)

        # 检查是否已安装
        existing = self.store.get_app(manifest.app_id)
        if existing:
            raise ValueError(f"App {manifest.app_id} is already installed")

        # 创建 App 记录
        app = self.store.create_app(manifest, status=AppStatus.INSTALLED)
        self.store.log_event(manifest.app_id, "app_installed")

        logger.info(f"App installed: {manifest.app_id} v{manifest.version}")
        return app

    def uninstall_app(self, app_id: str, force: bool = False) -> None:
        """
        卸载 App

        Args:
            app_id: App ID
            force: 是否强制卸载（即使有运行实例）

        Raises:
            ValueError: App 不存在或有运行实例
        """
        # 检查 App 是否存在
        app = self.store.get_app(app_id)
        if app is None:
            raise ValueError(f"App not found: {app_id}")

        # 检查运行实例
        running_instances = self.store.list_instances(
            app_id=app_id,
            status=AppStatus.RUNNING
        )

        if running_instances and not force:
            raise ValueError(f"App {app_id} has running instances, stop them first or use force=True")

        # 停止所有运行实例
        for instance in running_instances:
            try:
                self.runtime.stop_instance(instance.instance_id)
            except Exception as e:
                logger.warning(f"Failed to stop instance {instance.instance_id}: {e}")

        # 删除 App
        self.store.delete_app(app_id)
        self.store.log_event(app_id, "app_uninstalled")

        logger.info(f"App uninstalled: {app_id}")

    def start_app(self, app_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        启动 App

        Args:
            app_id: App ID
            metadata: 实例元数据（可选）

        Returns:
            实例 ID

        Raises:
            ValueError: App 不存在或已有运行实例
            RuntimeError: 启动失败
        """
        instance_id = self.runtime.start_instance(app_id, metadata)
        logger.info(f"App started: {app_id} (instance={instance_id})")
        return instance_id

    def stop_app(self, app_id: str) -> None:
        """
        停止 App（停止所有运行实例）

        Args:
            app_id: App ID

        Raises:
            ValueError: App 不存在
        """
        # 检查 App 是否存在
        app = self.store.get_app(app_id)
        if app is None:
            raise ValueError(f"App not found: {app_id}")

        # 获取所有运行实例
        running_instances = self.store.list_instances(
            app_id=app_id,
            status=AppStatus.RUNNING
        )

        if not running_instances:
            logger.info(f"No running instances for App: {app_id}")
            return

        # 停止所有实例
        for instance in running_instances:
            try:
                self.runtime.stop_instance(instance.instance_id)
            except Exception as e:
                logger.error(f"Failed to stop instance {instance.instance_id}: {e}")

        logger.info(f"App stopped: {app_id}")

    def list_apps(self, status: Optional[AppStatus] = None) -> List[App]:
        """
        列出所有 App

        Args:
            status: 过滤状态（可选）

        Returns:
            App 列表
        """
        return self.store.list_apps(status)

    def get_app(self, app_id: str) -> Optional[App]:
        """
        获取 App 信息

        Args:
            app_id: App ID

        Returns:
            App 对象，不存在返回 None
        """
        return self.store.get_app(app_id)

    def get_app_status(self, app_id: str) -> Dict[str, Any]:
        """
        获取 App 状态

        Args:
            app_id: App ID

        Returns:
            状态信息字典

        Raises:
            ValueError: App 不存在
        """
        app = self.store.get_app(app_id)
        if app is None:
            raise ValueError(f"App not found: {app_id}")

        # 获取实例列表
        instances = self.store.list_instances(app_id=app_id)

        # 获取运行中的实例
        running_instances = [i for i in instances if i.status == AppStatus.RUNNING]

        return {
            'app_id': app.app_id,
            'name': app.manifest.name,
            'version': app.manifest.version,
            'status': app.status.value,
            'installed_at': app.installed_at,
            'updated_at': app.updated_at,
            'total_instances': len(instances),
            'running_instances': len(running_instances),
            'instances': [i.to_dict() for i in instances],
        }

    def list_instances(self, app_id: Optional[str] = None,
                      status: Optional[AppStatus] = None) -> List[AppInstance]:
        """
        列出实例

        Args:
            app_id: 过滤 App ID（可选）
            status: 过滤状态（可选）

        Returns:
            AppInstance 列表
        """
        return self.store.list_instances(app_id, status)

    def health_check(self) -> Dict[str, Any]:
        """
        执行系统健康检查

        Returns:
            健康状态信息
        """
        apps = self.store.list_apps()
        running_instances = self.store.list_instances(status=AppStatus.RUNNING)
        health_results = self.runtime.health_check_all()

        return {
            'total_apps': len(apps),
            'running_instances': len(running_instances),
            'healthy_instances': sum(1 for h in health_results.values() if h),
            'unhealthy_instances': sum(1 for h in health_results.values() if not h),
            'instance_health': health_results,
        }
