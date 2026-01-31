"""
AppOS 运行时引擎

负责 App 的生命周期管理和执行
"""
import uuid
import logging
import importlib
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from threading import Lock

from agentos.store.timestamp_utils import now_ms
from .models import AppInstance, AppStatus
from .store import AppOSStore

logger = logging.getLogger(__name__)


class AppBase(ABC):
    """
    App 基类

    所有 AppOS App 必须继承此类并实现抽象方法
    """

    def __init__(self, app_id: str, instance_id: str):
        """
        初始化 App

        Args:
            app_id: App ID
            instance_id: 实例 ID
        """
        self.app_id = app_id
        self.instance_id = instance_id
        self.logger = logging.getLogger(f"appos.{app_id}")
        self._db_path = None  # 由 Runtime 设置

    @abstractmethod
    def start(self) -> None:
        """启动 App（子类必须实现）"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止 App（子类必须实现）"""
        pass

    def health_check(self) -> bool:
        """
        健康检查（子类可选实现）

        Returns:
            True 表示健康，False 表示异常
        """
        return True


class AppRuntime:
    """
    App 运行时管理器

    负责动态加载、启动、停止 App 实例
    """

    def __init__(self, store: AppOSStore):
        """
        初始化运行时

        Args:
            store: AppOSStore 实例
        """
        self.store = store
        self._db_path = store.db_path  # 保存数据库路径
        self._instances: Dict[str, AppBase] = {}  # instance_id -> AppBase
        self._lock = Lock()
        logger.info("AppRuntime initialized")

    def start_instance(self, app_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        启动 App 实例

        Args:
            app_id: App ID
            metadata: 实例元数据（可选）

        Returns:
            实例 ID

        Raises:
            ValueError: App 不存在或已有运行实例
            RuntimeError: App 启动失败
        """
        with self._lock:
            # 检查 App 是否存在
            app = self.store.get_app(app_id)
            if app is None:
                raise ValueError(f"App not found: {app_id}")

            # 检查是否已有运行实例
            running_instances = self.store.list_instances(
                app_id=app_id,
                status=AppStatus.RUNNING
            )
            if running_instances:
                raise ValueError(f"App {app_id} already has a running instance: {running_instances[0].instance_id}")

            # 生成实例 ID
            instance_id = f"{app_id}_{uuid.uuid4().hex[:8]}"

            # 创建实例记录
            self.store.create_instance(instance_id, app_id, metadata)
            self.store.log_event(app_id, "instance_starting", instance_id)

            try:
                # 动态加载 App 模块
                manifest = app.manifest
                module_name = manifest.entry_module
                class_name = manifest.entry_class

                logger.info(f"Loading App module: {module_name}.{class_name}")
                module = importlib.import_module(module_name)
                app_class = getattr(module, class_name)

                # 实例化 App
                app_instance = app_class(app_id=app_id, instance_id=instance_id)

                # 设置数据库路径
                app_instance._db_path = self._db_path

                # 启动 App
                logger.info(f"Starting App instance: {instance_id}")
                app_instance.start()

                # 更新状态
                self.store.update_instance(instance_id, status=AppStatus.RUNNING)
                self.store.update_app(app_id, status=AppStatus.RUNNING)
                self.store.log_event(app_id, "instance_started", instance_id)

                # 保存实例引用
                self._instances[instance_id] = app_instance

                logger.info(f"App instance started successfully: {instance_id}")
                return instance_id

            except Exception as e:
                logger.error(f"Failed to start App instance {instance_id}: {e}", exc_info=True)

                # 更新失败状态
                self.store.update_instance(instance_id, status=AppStatus.FAILED)
                self.store.update_app(app_id, status=AppStatus.FAILED)
                self.store.log_event(app_id, "instance_failed", instance_id, {
                    "error": str(e)
                })

                raise RuntimeError(f"Failed to start App {app_id}: {e}") from e

    def stop_instance(self, instance_id: str) -> None:
        """
        停止 App 实例

        Args:
            instance_id: 实例 ID

        Raises:
            ValueError: 实例不存在
            RuntimeError: 停止失败
        """
        with self._lock:
            # 检查实例是否存在
            instance = self.store.get_instance(instance_id)
            if instance is None:
                raise ValueError(f"Instance not found: {instance_id}")

            app_id = instance.app_id

            # 更新状态为 stopping
            self.store.update_instance(instance_id, status=AppStatus.STOPPING)
            self.store.log_event(app_id, "instance_stopping", instance_id)

            try:
                # 获取实例引用
                app_instance = self._instances.get(instance_id)

                if app_instance:
                    # 调用 stop 方法
                    logger.info(f"Stopping App instance: {instance_id}")
                    app_instance.stop()

                    # 移除实例引用
                    del self._instances[instance_id]
                else:
                    logger.warning(f"Instance {instance_id} not found in runtime, marking as stopped")

                # 更新状态
                now = now_ms()
                self.store.update_instance(
                    instance_id,
                    status=AppStatus.STOPPED,
                    stopped_at=now
                )
                self.store.update_app(app_id, status=AppStatus.STOPPED)
                self.store.log_event(app_id, "instance_stopped", instance_id)

                logger.info(f"App instance stopped successfully: {instance_id}")

            except Exception as e:
                logger.error(f"Failed to stop App instance {instance_id}: {e}", exc_info=True)

                # 更新失败状态
                self.store.update_instance(instance_id, status=AppStatus.FAILED)
                self.store.update_app(app_id, status=AppStatus.FAILED)
                self.store.log_event(app_id, "instance_stop_failed", instance_id, {
                    "error": str(e)
                })

                raise RuntimeError(f"Failed to stop instance {instance_id}: {e}") from e

    def get_instance(self, instance_id: str) -> Optional[AppBase]:
        """
        获取运行中的实例引用

        Args:
            instance_id: 实例 ID

        Returns:
            AppBase 实例，不存在返回 None
        """
        return self._instances.get(instance_id)

    def list_running_instances(self) -> Dict[str, AppBase]:
        """
        列出所有运行中的实例

        Returns:
            instance_id -> AppBase 的字典
        """
        return dict(self._instances)

    def health_check_all(self) -> Dict[str, bool]:
        """
        对所有运行中的实例执行健康检查

        Returns:
            instance_id -> 健康状态 的字典
        """
        results = {}
        for instance_id, app_instance in self._instances.items():
            try:
                results[instance_id] = app_instance.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {instance_id}: {e}")
                results[instance_id] = False
        return results
