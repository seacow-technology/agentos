#!/usr/bin/env python3
"""
Backfill v21 冗余列

将历史 task_audits 的 payload JSON 字段提取并填充到 v21 冗余列：
- source_event_ts
- supervisor_processed_at

用法:
    python backfill_audit_decision_fields.py --dry-run
    python backfill_audit_decision_fields.py --batch-size 1000
    python backfill_audit_decision_fields.py --help
"""

import argparse
import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class BackfillStats:
    """统计信息"""
    def __init__(self):
        self.total_rows = 0
        self.already_filled = 0
        self.filled_successfully = 0
        self.failed_to_parse = 0
        self.missing_payload_fields = 0
        self.updated_rows = 0

    def print_summary(self):
        """打印统计摘要"""
        print("\n" + "=" * 60)
        print("Backfill 统计摘要")
        print("=" * 60)
        print(f"总记录数:           {self.total_rows:,}")
        print(f"已填充（跳过）:     {self.already_filled:,}")
        print(f"成功填充:           {self.filled_successfully:,}")
        print(f"解析失败:           {self.failed_to_parse:,}")
        print(f"缺少字段:           {self.missing_payload_fields:,}")
        print(f"更新行数:           {self.updated_rows:,}")
        print("=" * 60)

        if self.total_rows > 0:
            coverage = (self.already_filled + self.filled_successfully) / self.total_rows * 100
            print(f"最终覆盖率:         {coverage:.2f}%")
        print()


def extract_timestamps(payload_str: str, created_at: str) -> Dict[str, Optional[str]]:
    """
    从 payload JSON 提取时间戳

    Args:
        payload_str: JSON 字符串
        created_at: 记录创建时间（fallback）

    Returns:
        {
            "source_event_ts": "...",
            "supervisor_processed_at": "..."
        }
    """
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except json.JSONDecodeError:
        return {"source_event_ts": None, "supervisor_processed_at": None}

    # 提取 source_event_ts（多个可能的字段名）
    source_event_ts = (
        payload.get("source_event_ts") or
        payload.get("source_ts") or
        payload.get("event_timestamp") or
        payload.get("task_created_at") or
        created_at  # Fallback: 使用记录创建时间
    )

    # 提取 supervisor_processed_at（多个可能的字段名）
    supervisor_processed_at = (
        payload.get("supervisor_processed_at") or
        payload.get("processed_at") or
        payload.get("timestamp") or
        created_at  # Fallback: 使用记录创建时间
    )

    return {
        "source_event_ts": source_event_ts,
        "supervisor_processed_at": supervisor_processed_at
    }


def backfill_batch(
    db_path: Path,
    batch_size: int,
    dry_run: bool,
    stats: BackfillStats
) -> bool:
    """
    处理一批记录

    Returns:
        bool: 是否还有更多记录需要处理
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 查询需要 backfill 的记录（冗余列为 NULL）
        cursor.execute("""
            SELECT audit_id, payload, created_at
            FROM task_audits
            WHERE (source_event_ts IS NULL OR supervisor_processed_at IS NULL)
              AND event_type LIKE '%SUPERVISOR%'
            LIMIT ?
        """, (batch_size,))

        rows = cursor.fetchall()

        if not rows:
            return False  # 没有更多记录

        stats.total_rows += len(rows)

        for row in rows:
            audit_id, payload_str, created_at = row

            # 提取时间戳
            timestamps = extract_timestamps(payload_str, created_at)

            if not timestamps["source_event_ts"] and not timestamps["supervisor_processed_at"]:
                stats.missing_payload_fields += 1
                print(f"⚠️  audit_id={audit_id}: 无法提取时间戳（payload 缺少字段）")
                continue

            # 更新冗余列
            if not dry_run:
                try:
                    cursor.execute("""
                        UPDATE task_audits
                        SET source_event_ts = ?,
                            supervisor_processed_at = ?
                        WHERE audit_id = ?
                    """, (
                        timestamps["source_event_ts"],
                        timestamps["supervisor_processed_at"],
                        audit_id
                    ))
                    stats.filled_successfully += 1
                except Exception as e:
                    stats.failed_to_parse += 1
                    print(f"❌ audit_id={audit_id}: 更新失败 - {e}")
            else:
                stats.filled_successfully += 1
                if timestamps["source_event_ts"] and timestamps["supervisor_processed_at"]:
                    source_ts_preview = timestamps["source_event_ts"][:19] if len(timestamps["source_event_ts"]) >= 19 else timestamps["source_event_ts"]
                    processed_ts_preview = timestamps["supervisor_processed_at"][:19] if len(timestamps["supervisor_processed_at"]) >= 19 else timestamps["supervisor_processed_at"]
                    print(f"[DRY-RUN] audit_id={audit_id}: 将填充 source_event_ts={source_ts_preview}, supervisor_processed_at={processed_ts_preview}")

        # 提交事务
        if not dry_run:
            conn.commit()
            stats.updated_rows += cursor.rowcount

        return len(rows) == batch_size  # 还有更多记录

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill v21 冗余列（将 payload JSON 提取到冗余列）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览模式（不实际执行）
  python backfill_audit_decision_fields.py --dry-run

  # 实际执行（默认批量 1000）
  python backfill_audit_decision_fields.py

  # 自定义批量大小
  python backfill_audit_decision_fields.py --batch-size 5000

  # 指定数据库路径
  python backfill_audit_decision_fields.py --db-path /path/to/store.db
        """
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path.home() / ".agentos" / "store.db",
        help="数据库路径（默认: ~/.agentos/store.db）"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="批量处理大小（默认: 1000）"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式（不实际执行更新）"
    )

    args = parser.parse_args()

    # 验证数据库存在
    if not args.db_path.exists():
        print(f"❌ 错误: 数据库文件不存在: {args.db_path}")
        sys.exit(1)

    # 打印配置
    print("=" * 60)
    print("Backfill v21 冗余列")
    print("=" * 60)
    print(f"数据库路径:    {args.db_path}")
    print(f"批量大小:      {args.batch_size:,}")
    print(f"模式:          {'DRY-RUN（预览）' if args.dry_run else '实际执行'}")
    print("=" * 60)
    print()

    # 检查 schema 版本
    conn = sqlite3.connect(str(args.db_path))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(task_audits)")
    columns = {row[1] for row in cursor.fetchall()}

    if "source_event_ts" not in columns or "supervisor_processed_at" not in columns:
        print("❌ 错误: 数据库未执行 v21 migration")
        print("请先执行: sqlite3 ~/.agentos/store.db < agentos/store/migrations/v21_audit_decision_fields.sql")
        conn.close()
        sys.exit(1)

    # 统计需要 backfill 的记录数
    cursor.execute("""
        SELECT COUNT(*)
        FROM task_audits
        WHERE (source_event_ts IS NULL OR supervisor_processed_at IS NULL)
          AND event_type LIKE '%SUPERVISOR%'
    """)
    total_to_backfill = cursor.fetchone()[0]

    print(f"需要 backfill 的记录数: {total_to_backfill:,}\n")

    if total_to_backfill == 0:
        print("✅ 所有记录已填充，无需 backfill")
        conn.close()
        return

    conn.close()

    # 开始 backfill
    stats = BackfillStats()
    batch_num = 0

    start_time = datetime.now()

    while True:
        batch_num += 1
        print(f"\n--- Batch {batch_num} ---")

        has_more = backfill_batch(
            db_path=args.db_path,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            stats=stats
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        rate = stats.total_rows / elapsed if elapsed > 0 else 0
        remaining = (total_to_backfill - stats.total_rows) / rate if rate > 0 else 0

        print(f"进度: {stats.total_rows:,}/{total_to_backfill:,} ({stats.total_rows/total_to_backfill*100:.1f}%)")
        print(f"速度: {rate:.0f} 行/秒")
        print(f"预计剩余时间: {remaining/60:.1f} 分钟")

        if not has_more:
            break

    # 打印统计摘要
    stats.print_summary()

    if args.dry_run:
        print("⚠️  这是 DRY-RUN 模式，未实际更新数据库")
        print("   移除 --dry-run 参数以执行实际更新")
    else:
        print("✅ Backfill 完成！")


if __name__ == "__main__":
    main()
