"""Database Migration System

自动检测并执行未应用的迁移文件。
迁移文件命名规范：schema_vXX.sql (XX 为两位数版本号)

特性：
1. 自动检测未应用的迁移
2. 按版本号顺序执行
3. 幂等性保证（IF NOT EXISTS）
4. 事务支持（每个迁移文件一个事务）
5. 版本追踪（schema_version 表）
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """迁移执行错误"""
    pass


class Migrator:
    """数据库迁移管理器"""

    def __init__(self, db_path: Path, migrations_dir: Path):
        """
        初始化迁移器

        Args:
            db_path: 数据库文件路径
            migrations_dir: 迁移文件目录
        """
        self.db_path = db_path
        self.migrations_dir = migrations_dir

    def get_current_version(self, conn: sqlite3.Connection) -> int:
        """
        获取当前数据库版本

        Args:
            conn: 数据库连接

        Returns:
            当前版本号（整数），如果没有版本表返回 0
        """
        try:
            # 获取所有版本记录
            cursor = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC"
            )
            rows = cursor.fetchall()

            # 提取所有版本号
            versions = []
            for row in rows:
                version_str = row[0]
                # 匹配 "0.XX.0" 格式，提取中间的数字
                match = re.search(r'0\.(\d+)\.', version_str)
                if match:
                    versions.append(int(match.group(1)))

            # 返回最大版本号
            return max(versions) if versions else 0

        except sqlite3.OperationalError:
            # schema_version 表不存在
            return 0

    def get_available_migrations(self) -> List[Tuple[int, Path]]:
        """
        获取所有Available的迁移文件

        Returns:
            (版本号, 文件路径) 元组列表，按版本号排序
        """
        migrations = []

        # 匹配 schema_vXX.sql 或 schema_vXX_suffix.sql 格式
        pattern = re.compile(r'schema_v(\d+)(?:_[a-z_]+)?\.sql')

        for sql_file in self.migrations_dir.glob('schema_v*.sql'):
            match = pattern.match(sql_file.name)
            if match:
                version = int(match.group(1))
                migrations.append((version, sql_file))

        # 按版本号排序
        migrations.sort(key=lambda x: x[0])
        return migrations

    def get_pending_migrations(self, conn: sqlite3.Connection) -> List[Tuple[int, Path]]:
        """
        获取待执行的迁移文件

        Args:
            conn: 数据库连接

        Returns:
            待执行的 (版本号, 文件路径) 元组列表
        """
        current_version = self.get_current_version(conn)
        all_migrations = self.get_available_migrations()

        # 过滤出版本号大于当前版本的迁移
        pending = [(v, p) for v, p in all_migrations if v > current_version]

        logger.info(
            f"Current version: v{current_version:02d}, "
            f"Available migrations: {len(all_migrations)}, "
            f"Pending: {len(pending)}"
        )

        return pending

    def execute_migration(
        self,
        conn: sqlite3.Connection,
        version: int,
        migration_file: Path
    ) -> None:
        """
        执行单个迁移文件

        Args:
            conn: 数据库连接
            version: 迁移版本号
            migration_file: 迁移文件路径

        Raises:
            MigrationError: 迁移执行失败
        """
        logger.info(f"Executing migration v{version:02d}: {migration_file.name}")

        try:
            # 读取迁移文件
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()

            # 执行迁移（在事务中）
            conn.executescript(migration_sql)

            # 记录版本（如果迁移文件没有自己记录的话）
            # 检查是否已经有这个版本的记录
            cursor = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version LIKE ?",
                (f'%{version}%',)
            )
            if cursor.fetchone()[0] == 0:
                # 插入版本记录
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (f'0.{version}.0',)
                )

            conn.commit()
            logger.info(f"Migration v{version:02d} completed successfully")

        except Exception as e:
            conn.rollback()
            error_msg = f"Migration v{version:02d} failed: {e}"
            logger.error(error_msg, exc_info=True)
            raise MigrationError(error_msg) from e

    def migrate(self) -> int:
        """
        执行所有待应用的迁移

        Returns:
            执行的迁移数量

        Raises:
            MigrationError: 迁移执行失败
        """
        # 确保数据库文件存在
        if not self.db_path.exists():
            raise MigrationError(
                f"Database not found: {self.db_path}. "
                "Please run init_db() first."
            )

        conn = sqlite3.connect(str(self.db_path))

        try:
            # 确保 schema_version 表存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            # 获取待执行的迁移
            pending_migrations = self.get_pending_migrations(conn)

            if not pending_migrations:
                logger.info("No pending migrations")
                return 0

            # 执行迁移
            for version, migration_file in pending_migrations:
                self.execute_migration(conn, version, migration_file)

            logger.info(f"Successfully applied {len(pending_migrations)} migrations")
            return len(pending_migrations)

        finally:
            conn.close()

    def status(self) -> dict:
        """
        获取迁移状态

        Returns:
            状态字典：
            {
                "current_version": int,
                "latest_version": int,
                "pending_count": int,
                "applied_migrations": List[str],
                "pending_migrations": List[str]
            }
        """
        if not self.db_path.exists():
            return {
                "current_version": 0,
                "latest_version": 0,
                "pending_count": 0,
                "applied_migrations": [],
                "pending_migrations": [],
                "error": "Database not found"
            }

        conn = sqlite3.connect(str(self.db_path))

        try:
            # 确保 schema_version 表存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            current_version = self.get_current_version(conn)
            all_migrations = self.get_available_migrations()
            pending_migrations = self.get_pending_migrations(conn)

            latest_version = all_migrations[-1][0] if all_migrations else 0

            applied = [f"v{v:02d}" for v, _ in all_migrations if v <= current_version]
            pending = [f"v{v:02d}" for v, _ in pending_migrations]

            return {
                "current_version": current_version,
                "latest_version": latest_version,
                "pending_count": len(pending_migrations),
                "applied_migrations": applied,
                "pending_migrations": pending
            }

        finally:
            conn.close()


def auto_migrate(db_path: Path) -> int:
    """
    自动执行数据库迁移

    Args:
        db_path: 数据库文件路径

    Returns:
        执行的迁移数量

    Raises:
        MigrationError: 迁移失败
    """
    migrations_dir = Path(__file__).parent / 'migrations'
    migrator = Migrator(db_path, migrations_dir)
    return migrator.migrate()


def get_migration_status(db_path: Path) -> dict:
    """
    获取迁移状态

    Args:
        db_path: 数据库文件路径

    Returns:
        迁移状态字典
    """
    migrations_dir = Path(__file__).parent / 'migrations'
    migrator = Migrator(db_path, migrations_dir)
    return migrator.status()
