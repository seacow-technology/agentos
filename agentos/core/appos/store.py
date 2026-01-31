"""
AppOS 存储层

负责 App 的数据持久化和查询
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from agentos.core.storage.paths import ensure_db_exists
from agentos.store.timestamp_utils import now_ms
from .models import App, AppInstance, AppManifest, AppStatus

logger = logging.getLogger(__name__)


class AppOSStore:
    """AppOS 存储层"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化存储层

        Args:
            db_path: 数据库路径，默认使用 ensure_db_exists("appos")
        """
        if db_path is None:
            db_path = ensure_db_exists("appos")
        self.db_path = str(db_path)
        self._init_schema()
        logger.info(f"AppOSStore initialized at {self.db_path}")

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """初始化数据库 schema"""
        with self._get_conn() as conn:
            # 确保 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=30000;")

            # apps 表：已安装的 App
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    app_id TEXT PRIMARY KEY,
                    manifest_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    installed_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    metadata_json TEXT
                )
            """)

            # app_instances 表：运行中的 App 实例
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_instances (
                    instance_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    stopped_at INTEGER,
                    metadata_json TEXT,
                    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                )
            """)

            # app_events 表：App 事件日志
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id TEXT NOT NULL,
                    instance_id TEXT,
                    event_type TEXT NOT NULL,
                    event_data_json TEXT,
                    created_at INTEGER NOT NULL
                )
            """)

            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_app_instances_app_id ON app_instances(app_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_app_events_app_id ON app_events(app_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_app_events_created_at ON app_events(created_at)")

            conn.commit()

    # ========== App CRUD ==========

    def create_app(self, manifest: AppManifest, status: AppStatus = AppStatus.INSTALLED,
                   metadata: Optional[Dict[str, Any]] = None) -> App:
        """
        创建（安装）一个 App

        Args:
            manifest: App 清单
            status: 初始状态
            metadata: 元数据

        Returns:
            App 对象
        """
        now = now_ms()
        app = App(
            app_id=manifest.app_id,
            manifest=manifest,
            status=status,
            installed_at=now,
            updated_at=now,
            metadata=metadata
        )

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO apps (app_id, manifest_json, status, installed_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                app.app_id,
                json.dumps(manifest.to_dict()),
                status.value,
                now,
                now,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()

        logger.info(f"App created: {app.app_id}")
        return app

    def get_app(self, app_id: str) -> Optional[App]:
        """
        获取 App

        Args:
            app_id: App ID

        Returns:
            App 对象，不存在返回 None
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT * FROM apps WHERE app_id = ?
            """, (app_id,)).fetchone()

            if row is None:
                return None

            manifest_data = json.loads(row['manifest_json'])
            return App(
                app_id=row['app_id'],
                manifest=AppManifest.from_dict(manifest_data),
                status=AppStatus(row['status']),
                installed_at=row['installed_at'],
                updated_at=row['updated_at'],
                metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
            )

    def list_apps(self, status: Optional[AppStatus] = None) -> List[App]:
        """
        列出所有 App

        Args:
            status: 过滤状态（可选）

        Returns:
            App 列表
        """
        with self._get_conn() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM apps WHERE status = ? ORDER BY installed_at DESC
                """, (status.value,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM apps ORDER BY installed_at DESC
                """).fetchall()

            apps = []
            for row in rows:
                manifest_data = json.loads(row['manifest_json'])
                apps.append(App(
                    app_id=row['app_id'],
                    manifest=AppManifest.from_dict(manifest_data),
                    status=AppStatus(row['status']),
                    installed_at=row['installed_at'],
                    updated_at=row['updated_at'],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
                ))
            return apps

    def update_app(self, app_id: str, status: Optional[AppStatus] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        更新 App

        Args:
            app_id: App ID
            status: 新状态（可选）
            metadata: 新元数据（可选）
        """
        now = now_ms()
        updates = ["updated_at = ?"]
        values = [now]

        if status:
            updates.append("status = ?")
            values.append(status.value)

        if metadata is not None:
            updates.append("metadata_json = ?")
            values.append(json.dumps(metadata))

        values.append(app_id)

        with self._get_conn() as conn:
            conn.execute(f"""
                UPDATE apps SET {', '.join(updates)} WHERE app_id = ?
            """, values)
            conn.commit()

        logger.info(f"App updated: {app_id}")

    def delete_app(self, app_id: str) -> None:
        """
        删除（卸载）App

        Args:
            app_id: App ID
        """
        with self._get_conn() as conn:
            conn.execute("DELETE FROM apps WHERE app_id = ?", (app_id,))
            conn.commit()

        logger.info(f"App deleted: {app_id}")

    # ========== Instance CRUD ==========

    def create_instance(self, instance_id: str, app_id: str,
                       metadata: Optional[Dict[str, Any]] = None) -> AppInstance:
        """
        创建 App 实例

        Args:
            instance_id: 实例 ID
            app_id: App ID
            metadata: 元数据

        Returns:
            AppInstance 对象
        """
        now = now_ms()
        instance = AppInstance(
            instance_id=instance_id,
            app_id=app_id,
            status=AppStatus.STARTING,
            started_at=now,
            metadata=metadata
        )

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO app_instances (instance_id, app_id, status, started_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                instance_id,
                app_id,
                AppStatus.STARTING.value,
                now,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()

        logger.info(f"Instance created: {instance_id} (app={app_id})")
        return instance

    def get_instance(self, instance_id: str) -> Optional[AppInstance]:
        """
        获取实例

        Args:
            instance_id: 实例 ID

        Returns:
            AppInstance 对象，不存在返回 None
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT * FROM app_instances WHERE instance_id = ?
            """, (instance_id,)).fetchone()

            if row is None:
                return None

            return AppInstance(
                instance_id=row['instance_id'],
                app_id=row['app_id'],
                status=AppStatus(row['status']),
                started_at=row['started_at'],
                stopped_at=row['stopped_at'],
                metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
            )

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
        with self._get_conn() as conn:
            query = "SELECT * FROM app_instances WHERE 1=1"
            params = []

            if app_id:
                query += " AND app_id = ?"
                params.append(app_id)

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY started_at DESC"

            rows = conn.execute(query, params).fetchall()

            instances = []
            for row in rows:
                instances.append(AppInstance(
                    instance_id=row['instance_id'],
                    app_id=row['app_id'],
                    status=AppStatus(row['status']),
                    started_at=row['started_at'],
                    stopped_at=row['stopped_at'],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
                ))
            return instances

    def update_instance(self, instance_id: str, status: Optional[AppStatus] = None,
                       stopped_at: Optional[int] = None) -> None:
        """
        更新实例

        Args:
            instance_id: 实例 ID
            status: 新状态（可选）
            stopped_at: 停止时间（可选）
        """
        updates = []
        values = []

        if status:
            updates.append("status = ?")
            values.append(status.value)

        if stopped_at is not None:
            updates.append("stopped_at = ?")
            values.append(stopped_at)

        if not updates:
            return

        values.append(instance_id)

        with self._get_conn() as conn:
            conn.execute(f"""
                UPDATE app_instances SET {', '.join(updates)} WHERE instance_id = ?
            """, values)
            conn.commit()

        logger.info(f"Instance updated: {instance_id}")

    def delete_instance(self, instance_id: str) -> None:
        """
        删除实例

        Args:
            instance_id: 实例 ID
        """
        with self._get_conn() as conn:
            conn.execute("DELETE FROM app_instances WHERE instance_id = ?", (instance_id,))
            conn.commit()

        logger.info(f"Instance deleted: {instance_id}")

    # ========== Event Log ==========

    def log_event(self, app_id: str, event_type: str,
                 instance_id: Optional[str] = None,
                 event_data: Optional[Dict[str, Any]] = None) -> None:
        """
        记录 App 事件

        Args:
            app_id: App ID
            event_type: 事件类型
            instance_id: 实例 ID（可选）
            event_data: 事件数据（可选）
        """
        now = now_ms()

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO app_events (app_id, instance_id, event_type, event_data_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                app_id,
                instance_id,
                event_type,
                json.dumps(event_data) if event_data else None,
                now
            ))
            conn.commit()

        logger.debug(f"Event logged: {event_type} for app={app_id}")
