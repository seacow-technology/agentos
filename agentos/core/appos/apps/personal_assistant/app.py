"""
Personal Assistant App

个人助手应用，提供待办事项管理功能
"""
import logging
from typing import List, Dict, Any, Optional

from agentos.core.appos.runtime import AppBase
from .storage import TodoStore

logger = logging.getLogger(__name__)


class PersonalAssistantApp(AppBase):
    """
    Personal Assistant 应用

    提供待办事项管理、笔记、提醒等功能
    """

    def __init__(self, app_id: str, instance_id: str):
        """
        初始化 App

        Args:
            app_id: App ID
            instance_id: 实例 ID
        """
        super().__init__(app_id, instance_id)
        self.todo_store: Optional[TodoStore] = None
        self._is_running = False

    def start(self) -> None:
        """启动 App"""
        self.logger.info(f"Starting Personal Assistant instance: {self.instance_id}")

        # 初始化 TodoStore，使用传入的数据库路径
        from pathlib import Path
        db_path = Path(self._db_path) if self._db_path else None
        self.todo_store = TodoStore(db_path=db_path)

        self._is_running = True
        self.logger.info("Personal Assistant started successfully")

    def stop(self) -> None:
        """停止 App"""
        self.logger.info(f"Stopping Personal Assistant instance: {self.instance_id}")

        self._is_running = False
        self.todo_store = None

        self.logger.info("Personal Assistant stopped")

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True 表示健康
        """
        return self._is_running and self.todo_store is not None

    # ========== 业务方法 ==========

    def add_todo(self, text: str, list_name: str = "default",
                metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        添加待办事项

        Args:
            text: 待办内容
            list_name: 列表名称
            metadata: 元数据（可选）

        Returns:
            todo_id

        Raises:
            RuntimeError: App 未启动
            ValueError: 参数错误
        """
        if not self._is_running or not self.todo_store:
            raise RuntimeError("Personal Assistant is not running")

        todo_id = self.todo_store.create_todo(text, list_name, metadata)
        self.logger.info(f"Todo added: {todo_id}")
        return todo_id

    def list_todos(self, list_name: Optional[str] = None,
                  completed: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        列出待办事项

        Args:
            list_name: 过滤列表名称（可选）
            completed: 过滤完成状态（可选）

        Returns:
            待办事项列表

        Raises:
            RuntimeError: App 未启动
        """
        if not self._is_running or not self.todo_store:
            raise RuntimeError("Personal Assistant is not running")

        todos = self.todo_store.get_todos(list_name, completed)
        return todos

    def complete_todo(self, todo_id: int) -> None:
        """
        完成待办事项

        Args:
            todo_id: 待办 ID

        Raises:
            RuntimeError: App 未启动
            ValueError: 待办不存在
        """
        if not self._is_running or not self.todo_store:
            raise RuntimeError("Personal Assistant is not running")

        self.todo_store.complete_todo(todo_id)
        self.logger.info(f"Todo completed: {todo_id}")

    def delete_todo(self, todo_id: int) -> None:
        """
        删除待办事项

        Args:
            todo_id: 待办 ID

        Raises:
            RuntimeError: App 未启动
            ValueError: 待办不存在
        """
        if not self._is_running or not self.todo_store:
            raise RuntimeError("Personal Assistant is not running")

        self.todo_store.delete_todo(todo_id)
        self.logger.info(f"Todo deleted: {todo_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据

        Raises:
            RuntimeError: App 未启动
        """
        if not self._is_running or not self.todo_store:
            raise RuntimeError("Personal Assistant is not running")

        return self.todo_store.get_stats()
