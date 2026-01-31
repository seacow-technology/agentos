"""
Guardian Storage Adapter

提供 Guardian 验收审查记录的数据库 CRUD 操作。

数据源：
- guardian_reviews 表：Guardian 验收审查记录

设计原则：
1. 只读查询为主，写操作仅限于创建新记录
2. 使用索引优化查询性能
3. 所有查询按 created_at DESC 排序（最新的在前）
4. 支持灵活的过滤条件组合

Created for Task #2: Guardian Service 和 API 端点
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from agentos.core.guardian.models import GuardianReview
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class GuardianStorage:
    """
    Guardian Storage Adapter

    提供 guardian_reviews 表的数据库访问层。
    所有数据库操作都通过此类进行。
    """

    def __init__(self, db_path: Path):
        """
        初始化存储适配器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        logger.info(f"GuardianStorage initialized with db_path={db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, review: GuardianReview) -> None:
        """
        保存验收记录

        Args:
            review: GuardianReview 实例

        Raises:
            sqlite3.IntegrityError: 如果 review_id 已存在
            sqlite3.Error: 数据库错误

        Example:
            ```python
            storage = GuardianStorage(db_path)
            review = GuardianReview.create_auto_review(
                target_type="task",
                target_id="task_123",
                guardian_id="guardian.v1",
                verdict="PASS",
                confidence=0.95,
                evidence={"checks": ["all_pass"]}
            )
            storage.save(review)
            ```
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO guardian_reviews (
                    review_id, target_type, target_id, guardian_id,
                    review_type, verdict, confidence, rule_snapshot_id,
                    evidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.target_type,
                    review.target_id,
                    review.guardian_id,
                    review.review_type,
                    review.verdict,
                    review.confidence,
                    review.rule_snapshot_id,
                    json.dumps(review.evidence),
                    review.created_at
                )
            )
            conn.commit()
            logger.debug(f"Saved review: {review.review_id}")
        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to save review {review.review_id}: {e}")
            raise
        finally:
            conn.close()

    def get_by_id(self, review_id: str) -> Optional[GuardianReview]:
        """
        根据 ID 查询验收记录

        Args:
            review_id: 审查 ID

        Returns:
            GuardianReview 实例或 None

        Example:
            ```python
            storage = GuardianStorage(db_path)
            review = storage.get_by_id("review_abc123")
            if review:
                print(f"Verdict: {review.verdict}")
            ```
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT review_id, target_type, target_id, guardian_id,
                       review_type, verdict, confidence, rule_snapshot_id,
                       evidence, created_at
                FROM guardian_reviews
                WHERE review_id = ?
                """,
                (review_id,)
            )

            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_review(row)

        finally:
            conn.close()

    def query(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        guardian_id: Optional[str] = None,
        verdict: Optional[str] = None,
        limit: int = 100
    ) -> List[GuardianReview]:
        """
        灵活查询验收记录

        支持按多个维度过滤，所有过滤条件都是 AND 关系。

        Args:
            target_type: 过滤目标类型（task | decision | finding）
            target_id: 过滤目标 ID
            guardian_id: 过滤 Guardian ID
            verdict: 过滤验收结论（PASS | FAIL | NEEDS_REVIEW）
            limit: 结果数量限制（默认 100）

        Returns:
            GuardianReview 列表（按 created_at DESC 排序）

        Example:
            ```python
            storage = GuardianStorage(db_path)

            # 查询所有 FAIL 的记录
            failed = storage.query(verdict="FAIL", limit=50)

            # 查询某个 Guardian 的所有任务审查
            task_reviews = storage.query(
                target_type="task",
                guardian_id="guardian.v1"
            )
            ```
        """
        conn = self._get_conn()
        try:
            # Build dynamic WHERE clause
            conditions = []
            params = []

            if target_type is not None:
                conditions.append("target_type = ?")
                params.append(target_type)

            if target_id is not None:
                conditions.append("target_id = ?")
                params.append(target_id)

            if guardian_id is not None:
                conditions.append("guardian_id = ?")
                params.append(guardian_id)

            if verdict is not None:
                conditions.append("verdict = ?")
                params.append(verdict)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Add limit
            params.append(limit)

            query = f"""
                SELECT review_id, target_type, target_id, guardian_id,
                       review_type, verdict, confidence, rule_snapshot_id,
                       evidence, created_at
                FROM guardian_reviews
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """

            cursor = conn.cursor()
            cursor.execute(query, params)

            rows = cursor.fetchall()
            return [self._row_to_review(row) for row in rows]

        finally:
            conn.close()

    def get_by_target(
        self,
        target_type: str,
        target_id: str
    ) -> List[GuardianReview]:
        """
        获取特定目标的所有验收记录

        这是一个专用查询，针对 (target_type, target_id) 进行优化。
        使用 idx_guardian_reviews_target 索引。

        Args:
            target_type: 目标类型（task | decision | finding）
            target_id: 目标 ID

        Returns:
            GuardianReview 列表（按 created_at DESC 排序）

        Example:
            ```python
            storage = GuardianStorage(db_path)
            reviews = storage.get_by_target("task", "task_123")
            for review in reviews:
                print(f"{review.created_at}: {review.verdict}")
            ```
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT review_id, target_type, target_id, guardian_id,
                       review_type, verdict, confidence, rule_snapshot_id,
                       evidence, created_at
                FROM guardian_reviews
                WHERE target_type = ? AND target_id = ?
                ORDER BY created_at DESC
                """,
                (target_type, target_id)
            )

            rows = cursor.fetchall()
            return [self._row_to_review(row) for row in rows]

        finally:
            conn.close()

    def get_stats(
        self,
        target_type: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        统计聚合

        提供 Guardian 系统的整体统计数据。

        Args:
            target_type: 过滤目标类型（可选）
            since: 统计时间起点（可选）

        Returns:
            统计数据字典，包含：
            - total_reviews: 总审查数
            - pass_rate: 通过率（0.0-1.0）
            - guardians: Guardian 活跃度 {guardian_id: count}
            - by_verdict: 按结论分组 {verdict: count}
            - by_target_type: 按目标类型分组 {target_type: count}

        Example:
            ```python
            storage = GuardianStorage(db_path)
            stats = storage.get_stats()
            print(f"Pass rate: {stats['pass_rate']:.2%}")

            # 统计最近 7 天
            from datetime import datetime, timedelta, timezone
            since = utc_now() - timedelta(days=7)
            recent = storage.get_stats(since=since)
            ```
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Build WHERE clause
            conditions = []
            params = []

            if target_type is not None:
                conditions.append("target_type = ?")
                params.append(target_type)

            if since is not None:
                conditions.append("created_at >= ?")
                params.append(since.isoformat())

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Query 1: Total reviews and verdict counts
            query_verdict = f"""
                SELECT verdict, COUNT(*) as count
                FROM guardian_reviews
                {where_clause}
                GROUP BY verdict
            """
            cursor.execute(query_verdict, params)
            verdict_rows = cursor.fetchall()

            by_verdict = {}
            total_reviews = 0
            pass_count = 0

            for row in verdict_rows:
                verdict = row["verdict"]
                count = row["count"]
                by_verdict[verdict] = count
                total_reviews += count
                if verdict == "PASS":
                    pass_count = count

            pass_rate = pass_count / total_reviews if total_reviews > 0 else 0.0

            # Query 2: Guardian activity
            query_guardians = f"""
                SELECT guardian_id, COUNT(*) as count
                FROM guardian_reviews
                {where_clause}
                GROUP BY guardian_id
                ORDER BY count DESC
            """
            cursor.execute(query_guardians, params)
            guardian_rows = cursor.fetchall()

            guardians = {row["guardian_id"]: row["count"] for row in guardian_rows}

            # Query 3: Target type distribution (only if not filtered)
            by_target_type = {}
            if target_type is None:
                query_types = f"""
                    SELECT target_type, COUNT(*) as count
                    FROM guardian_reviews
                    {where_clause}
                    GROUP BY target_type
                """
                cursor.execute(query_types, params)
                type_rows = cursor.fetchall()
                by_target_type = {row["target_type"]: row["count"] for row in type_rows}

            return {
                "total_reviews": total_reviews,
                "pass_rate": pass_rate,
                "guardians": guardians,
                "by_verdict": by_verdict,
                "by_target_type": by_target_type
            }

        finally:
            conn.close()

    def _row_to_review(self, row: sqlite3.Row) -> GuardianReview:
        """
        将数据库行转换为 GuardianReview 实例

        Args:
            row: 数据库行

        Returns:
            GuardianReview 实例
        """
        try:
            evidence = json.loads(row["evidence"]) if row["evidence"] else {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evidence JSON for review {row['review_id']}")
            evidence = {}

        return GuardianReview(
            review_id=row["review_id"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            guardian_id=row["guardian_id"],
            review_type=row["review_type"],
            verdict=row["verdict"],
            confidence=row["confidence"],
            rule_snapshot_id=row["rule_snapshot_id"],
            evidence=evidence,
            created_at=row["created_at"]
        )
