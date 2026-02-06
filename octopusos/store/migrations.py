"""Database migration utilities for AgentOS Store

改进要点：
1. ✅ 禁止版本号硬编码 - 从迁移文件自动扫描
2. ✅ 统一迁移脚本位置 - 全部在 migrations/ 目录
3. ✅ 动态版本管理 - 从数据库和文件系统读取
4. ✅ 自动迁移链构建 - 无需手动维护
"""

import sqlite3
import re
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration errors with helpful context"""
    
    def __init__(self, version_from: str, version_to: str, error: str, hint: str = ""):
        self.version_from = version_from
        self.version_to = version_to
        self.error = error
        self.hint = hint
        
        message = f"""
╔══════════════════════════════════════════════════════════════════
║ 数据库迁移失败
╠══════════════════════════════════════════════════════════════════
║ 迁移路径: v{version_from} → v{version_to}
║ 错误信息: {error}
"""
        if hint:
            message += f"║ 解决建议: {hint}\n"
        
        message += """╠══════════════════════════════════════════════════════════════════
║ 常见解决方案:
║  1. 检查数据库文件权限
║  2. 查看完整日志: agentos migrate --verbose
║  3. 备份数据库文件
║  4. 寻求帮助: github.com/agentos/issues
╚══════════════════════════════════════════════════════════════════
"""
        super().__init__(message)


def get_current_version(conn: sqlite3.Connection) -> Optional[str]:
    """
    Get current schema version from database
    
    Uses semantic version sorting to handle cases where multiple versions
    have the same applied_at timestamp.
    """
    try:
        cursor = conn.cursor()
        # Get all versions
        results = cursor.execute(
            "SELECT version FROM schema_version"
        ).fetchall()
        
        if not results:
            return None
        
        # Sort versions semantically (0.5.0 < 0.6.0 < 0.10.0)
        versions = [row[0] for row in results]
        versions.sort(key=lambda v: tuple(map(int, v.split('.'))))
        
        # Return the latest version
        return versions[-1]
        
    except sqlite3.OperationalError:
        # schema_version table doesn't exist
        return None


def parse_migration_version(filename: str) -> Optional[Tuple[str, str]]:
    """
    Parse migration filename to extract version number
    
    Examples:
        v07_project_kb.sql -> ("0.7.0", "Project KB")
        v10_fix_fts_triggers.sql -> ("0.10.0", "Fix FTS Triggers")
    
    Returns:
        (version, description) or None if not a migration file
    """
    pattern = r'^v(\d+)_(.+)\.sql$'
    match = re.match(pattern, filename)
    if match:
        minor = int(match.group(1))
        description = match.group(2).replace('_', ' ').title()
        return (f"0.{minor}.0", description)
    return None


def scan_available_migrations(migrations_dir: Path) -> List[Tuple[str, str, Path]]:
    """
    Scan migrations directory to discover available migrations
    
    Returns:
        List of (version, description, filepath) sorted by version
    """
    migrations = []
    
    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return []
    
    for file in migrations_dir.iterdir():
        if file.suffix == '.sql' and file.name.startswith('v'):
            parsed = parse_migration_version(file.name)
            if parsed:
                version, description = parsed
                migrations.append((version, description, file))
    
    # Sort by version (semantic version comparison)
    migrations.sort(key=lambda x: tuple(map(int, x[0].split('.'))))
    
    return migrations


def get_latest_version(migrations_dir: Path) -> Optional[str]:
    """
    Get the latest available migration version from filesystem
    
    Returns:
        Latest version string (e.g., "0.10.0") or None if no migrations
    """
    migrations = scan_available_migrations(migrations_dir)
    return migrations[-1][0] if migrations else None


def build_migration_chain(
    migrations_dir: Path,
    from_version: str,
    to_version: str
) -> List[Tuple[str, str, Path, str]]:
    """
    Build migration chain from current version to target version
    
    Args:
        migrations_dir: Path to migrations directory
        from_version: Starting version (e.g., "0.6.0")
        to_version: Target version (e.g., "0.10.0")
    
    Returns:
        List of (from_ver, to_ver, filepath, description)
    
    Raises:
        MigrationError: If no valid migration path exists
    """
    all_migrations = scan_available_migrations(migrations_dir)
    
    # Extract just versions for comparison
    versions = [m[0] for m in all_migrations]
    
    # Check if versions are in range
    if from_version not in versions and from_version != "0.5.0":  # 0.5.0 is implicit
        raise MigrationError(
            version_from=from_version,
            version_to=to_version,
            error=f"Starting version v{from_version} not found in migration chain",
            hint=f"Available versions: {', '.join(versions)}"
        )
    
    if to_version not in versions:
        raise MigrationError(
            version_from=from_version,
            version_to=to_version,
            error=f"Target version v{to_version} not found in migration chain",
            hint=f"Available versions: {', '.join(versions)}"
        )
    
    # Build chain - find migrations between from_version and to_version
    chain = []
    prev_version = from_version
    
    for version, description, filepath in all_migrations:
        # Parse major.minor.patch
        from_parts = tuple(map(int, from_version.split('.')))
        to_parts = tuple(map(int, to_version.split('.')))
        version_parts = tuple(map(int, version.split('.')))
        
        # Only include migrations in range
        if from_parts < version_parts <= to_parts:
            chain.append((prev_version, version, filepath, description))
            prev_version = version
    
    if not chain:
        raise MigrationError(
            version_from=from_version,
            version_to=to_version,
            error=f"No migration path found",
            hint=f"Cannot migrate from v{from_version} to v{to_version}"
        )
    
    return chain


def execute_migration_file(
    conn: sqlite3.Connection,
    filepath: Path,
    from_version: str,
    to_version: str,
    description: str
) -> None:
    """
    Execute a single migration SQL file
    
    Args:
        conn: Database connection
        filepath: Path to migration SQL file
        from_version: Source version
        to_version: Target version
        description: Migration description
    
    Raises:
        MigrationError: If migration fails
    """
    logger.info(f"🔄 Executing migration: {filepath.name} ({description})")
    
    cursor = conn.cursor()
    
    try:
        # Read and execute migration SQL
        with open(filepath, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        cursor.executescript(migration_sql)
        conn.commit()
        
        logger.info(f"✅ Migration v{from_version} → v{to_version} completed")
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "UNIQUE constraint failed: schema_version.version" in str(e):
            logger.warning(f"⚠️  Version {to_version} already exists - skipping")
        else:
            raise MigrationError(
                version_from=from_version,
                version_to=to_version,
                error=str(e),
                hint="数据库约束冲突。可能是迁移部分完成，请检查数据完整性。"
            )
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration failed: {e}")
        raise MigrationError(
            version_from=from_version,
            version_to=to_version,
            error=str(e),
            hint=f"执行迁移脚本 {filepath.name} 时失败。请检查 SQL 语法和数据库状态。"
        )


def migrate(db_path: Path, target_version: Optional[str] = None) -> None:
    """
    Run database migrations from current version to target version
    
    Args:
        db_path: Path to database file
        target_version: Target schema version (None = latest available)
    
    Raises:
        MigrationError: If migration fails or path not found
    """
    migrations_dir = Path(__file__).parent / "migrations"
    
    # Determine target version (latest if not specified)
    if target_version is None:
        target_version = get_latest_version(migrations_dir)
        if target_version is None:
            logger.error("❌ No migration files found in migrations directory")
            raise ValueError("No migrations available")
        logger.info(f"📌 Target version not specified, using latest: v{target_version}")
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # Get current version from database
        current_version = get_current_version(conn)
        
        if current_version is None:
            error_msg = """
╔══════════════════════════════════════════════════════════════════
║ 无法确定数据库版本
╠══════════════════════════════════════════════════════════════════
║ 原因: schema_version 表不存在或为空
║ 
║ 可能的解决方案:
║  1. 如果是新数据库: agentos init
║  2. 如果是旧数据库: 手动添加版本信息
║  3. 备份后重新初始化数据库
╚══════════════════════════════════════════════════════════════════
"""
            logger.error(error_msg)
            raise ValueError("Database schema version unknown")
        
        if current_version == target_version:
            logger.info(f"✅ 已经是目标版本 v{target_version}，无需迁移")
            return
        
        # Check if downgrade (not supported by default)
        current_parts = tuple(map(int, current_version.split('.')))
        target_parts = tuple(map(int, target_version.split('.')))
        
        if current_parts > target_parts:
            raise MigrationError(
                version_from=current_version,
                version_to=target_version,
                error="Downgrade not supported",
                hint=f"Cannot downgrade from v{current_version} to v{target_version}. "
                     f"Use rollback command if available."
            )
        
        # Build migration chain
        migration_chain = build_migration_chain(
            migrations_dir,
            current_version,
            target_version
        )
        
        # Print migration plan
        logger.info(f"""
╔══════════════════════════════════════════════════════════════════
║ 数据库迁移计划
╠══════════════════════════════════════════════════════════════════
║ 数据库: {db_path.name}
║ 当前版本: v{current_version}
║ 目标版本: v{target_version}
║ 迁移步骤: {len(migration_chain)} 个
╠══════════════════════════════════════════════════════════════════
║ 迁移链:
""")
        for i, (from_v, to_v, _, desc) in enumerate(migration_chain, 1):
            logger.info(f"║  {i}. v{from_v} → v{to_v}: {desc}")
        logger.info("╚══════════════════════════════════════════════════════════════════")
        
        # Execute migrations
        migrations_executed = 0
        for from_v, to_v, filepath, desc in migration_chain:
            logger.info(f"\n🔄 [{migrations_executed + 1}/{len(migration_chain)}] "
                       f"Migrating v{from_v} → v{to_v}")
            
            execute_migration_file(conn, filepath, from_v, to_v, desc)
            migrations_executed += 1
        
        # Verify final version
        final_version = get_current_version(conn)
        if final_version != target_version:
            raise MigrationError(
                version_from=current_version,
                version_to=target_version,
                error=f"Migration stopped at v{final_version}",
                hint=f"预期版本 v{target_version}，但实际为 v{final_version}。"
                     f"请检查迁移脚本是否正确更新了 schema_version。"
            )
        
        logger.info(f"""
╔══════════════════════════════════════════════════════════════════
║ 迁移成功完成 🎉
╠══════════════════════════════════════════════════════════════════
║ 最终版本: v{final_version}
║ 执行步骤: {migrations_executed} 个迁移
║ 数据库: {db_path}
╚══════════════════════════════════════════════════════════════════
""")
        
    except MigrationError:
        raise
    except Exception as e:
        logger.error(f"❌ 迁移过程发生错误: {e}")
        raise
    finally:
        conn.close()


def list_migrations(migrations_dir: Optional[Path] = None) -> Dict[str, any]:
    """
    List all available migrations
    
    Returns:
        Dictionary with migration info:
        {
            'latest': '0.10.0',
            'migrations': [(version, description, filepath), ...]
        }
    """
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"
    
    migrations = scan_available_migrations(migrations_dir)
    
    return {
        'latest': migrations[-1][0] if migrations else None,
        'count': len(migrations),
        'migrations': migrations
    }


if __name__ == "__main__":
    # CLI usage
    import sys
    from agentos.store import get_db_path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python migrations.py [migrate|list] [target_version]")
        print("\nExamples:")
        print("  python migrations.py list              # List all available migrations")
        print("  python migrations.py migrate           # Migrate to latest version")
        print("  python migrations.py migrate 0.8.0     # Migrate to specific version")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        migrations_dir = Path(__file__).parent / "migrations"
        info = list_migrations(migrations_dir)
        
        print("\n╔══════════════════════════════════════════════════════════════════")
        print("║ Available Migrations")
        print("╠══════════════════════════════════════════════════════════════════")
        print(f"║ Latest Version: v{info['latest']}")
        print(f"║ Total Migrations: {info['count']}")
        print("╠══════════════════════════════════════════════════════════════════")
        print("║ Migration Files:")
        
        for version, description, filepath in info['migrations']:
            print(f"║  • v{version}: {description}")
            print(f"║    {filepath.name}")
        
        print("╚══════════════════════════════════════════════════════════════════\n")
        
    elif command == "migrate":
        db_path = get_db_path()
        target_version = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            migrate(db_path, target_version)
        except MigrationError as e:
            print(str(e))
            sys.exit(1)
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: migrate, list")
        sys.exit(1)
