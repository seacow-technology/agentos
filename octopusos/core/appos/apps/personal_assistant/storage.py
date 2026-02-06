"""
Personal Assistant 存储层

负责待办事项的持久化
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from agentos.core.storage.paths import ensure_db_exists
from agentos.store.timestamp_utils import now_ms

logger = logging.getLogger(__name__)


class TodoStore:
    """待办事项存储"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化存储

        Args:
            db_path: 数据库路径（可选，默认使用 appos 数据库）
        """
        if db_path is None:
            db_path = ensure_db_exists("appos")
        self.db_path = str(db_path)
        self._init_schema()
        logger.info(f"TodoStore initialized at {self.db_path}")

    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """初始化 schema"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personal_assistant_todos (
                    todo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    list_name TEXT NOT NULL DEFAULT 'default',
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    metadata_json TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pa_todos_list_name
                ON personal_assistant_todos(list_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pa_todos_completed
                ON personal_assistant_todos(completed)
            """)
            conn.commit()

    def create_todo(self, text: str, list_name: str = "default",
                   metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        创建待办事项

        Args:
            text: 待办内容
            list_name: 列表名称
            metadata: 元数据（可选）

        Returns:
            todo_id
        """
        if not text or not text.strip():
            raise ValueError("Todo text cannot be empty")

        now = now_ms()
        import json

        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO personal_assistant_todos
                (text, list_name, completed, created_at, metadata_json)
                VALUES (?, ?, 0, ?, ?)
            """, (
                text.strip(),
                list_name,
                now,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
            todo_id = cursor.lastrowid

        logger.info(f"Todo created: {todo_id} in list '{list_name}'")
        return todo_id

    def get_todos(self, list_name: Optional[str] = None,
                 completed: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        获取待办事项列表

        Args:
            list_name: 过滤列表名称（可选）
            completed: 过滤完成状态（可选）

        Returns:
            待办事项列表
        """
        import json

        query = "SELECT * FROM personal_assistant_todos WHERE 1=1"
        params = []

        if list_name:
            query += " AND list_name = ?"
            params.append(list_name)

        if completed is not None:
            query += " AND completed = ?"
            params.append(1 if completed else 0)

        query += " ORDER BY created_at DESC"

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

            todos = []
            for row in rows:
                todos.append({
                    'todo_id': row['todo_id'],
                    'text': row['text'],
                    'list_name': row['list_name'],
                    'completed': bool(row['completed']),
                    'created_at': row['created_at'],
                    'completed_at': row['completed_at'],
                    'metadata': json.loads(row['metadata_json']) if row['metadata_json'] else None
                })

            return todos

    def complete_todo(self, todo_id: int) -> None:
        """
        标记待办为已完成

        Args:
            todo_id: 待办 ID

        Raises:
            ValueError: 待办不存在
        """
        now = now_ms()

        with self._get_conn() as conn:
            cursor = conn.execute("""
                UPDATE personal_assistant_todos
                SET completed = 1, completed_at = ?
                WHERE todo_id = ?
            """, (now, todo_id))
            conn.commit()

            if cursor.rowcount == 0:
                raise ValueError(f"Todo not found: {todo_id}")

        logger.info(f"Todo completed: {todo_id}")

    def delete_todo(self, todo_id: int) -> None:
        """
        删除待办事项

        Args:
            todo_id: 待办 ID

        Raises:
            ValueError: 待办不存在
        """
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM personal_assistant_todos WHERE todo_id = ?
            """, (todo_id,))
            conn.commit()

            if cursor.rowcount == 0:
                raise ValueError(f"Todo not found: {todo_id}")

        logger.info(f"Todo deleted: {todo_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        with self._get_conn() as conn:
            # 总数
            total = conn.execute("""
                SELECT COUNT(*) as count FROM personal_assistant_todos
            """).fetchone()['count']

            # 已完成数
            completed = conn.execute("""
                SELECT COUNT(*) as count FROM personal_assistant_todos WHERE completed = 1
            """).fetchone()['count']

            # 按列表统计
            lists = conn.execute("""
                SELECT list_name, COUNT(*) as count
                FROM personal_assistant_todos
                GROUP BY list_name
            """).fetchall()

            return {
                'total': total,
                'completed': completed,
                'pending': total - completed,
                'lists': {row['list_name']: row['count'] for row in lists}
            }
