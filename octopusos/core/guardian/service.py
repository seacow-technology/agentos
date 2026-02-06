"""
Guardian Service Layer

提供 Guardian 验收审查记录的 CRUD 操作和统计查询。

核心原则：
1. Guardian 是只读叠加层，不修改 Task 状态
2. Service 层纯粹处理 GuardianReview 的 CRUD
3. 与 task service 集成必须无侵入

Created for Task #2: Guardian Service 和 API 端点
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from agentos.core.guardian.models import GuardianReview
from agentos.core.guardian.storage import GuardianStorage
from agentos.store import get_db_path
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class GuardianService:
    """
    Guardian Service Layer

    提供 Guardian 验收审查记录的高层业务操作。
    所有 GuardianReview 的创建和查询都应通过此服务层。
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化 Guardian 服务

        Args:
            db_path: 数据库路径（默认使用系统数据库）
        """
        if db_path is None:
            db_path = get_db_path()

        self.storage = GuardianStorage(db_path)
        logger.info(f"GuardianService initialized with db_path={db_path}")

    def create_review(
        self,
        target_type: str,
        target_id: str,
        guardian_id: str,
        review_type: str,
        verdict: str,
        confidence: float,
        evidence: Dict[str, Any],
        rule_snapshot_id: Optional[str] = None
    ) -> GuardianReview:
        """
        创建一个新的 Guardian 验收记录

        Args:
            target_type: 审查目标类型（task | decision | finding）
            target_id: 审查目标 ID
            guardian_id: Guardian ID（agent name / human id）
            review_type: 审查类型（AUTO | MANUAL）
            verdict: 验收结论（PASS | FAIL | NEEDS_REVIEW）
            confidence: 置信度（0.0-1.0）
            evidence: 验收证据（JSON 结构）
            rule_snapshot_id: 规则快照 ID（可选）

        Returns:
            GuardianReview 实例

        Raises:
            ValueError: 如果参数无效

        Example:
            ```python
            service = GuardianService()
            review = service.create_review(
                target_type="task",
                target_id="task_123",
                guardian_id="guardian.ruleset.v1",
                review_type="AUTO",
                verdict="PASS",
                confidence=0.92,
                evidence={"checks": ["state_machine_ok"], "metrics": {}},
                rule_snapshot_id="ruleset:v1@sha256:abc"
            )
            ```
        """
        # Create review using factory methods for validation
        if review_type == "AUTO":
            review = GuardianReview.create_auto_review(
                target_type=target_type,
                target_id=target_id,
                guardian_id=guardian_id,
                verdict=verdict,
                confidence=confidence,
                evidence=evidence,
                rule_snapshot_id=rule_snapshot_id
            )
        elif review_type == "MANUAL":
            review = GuardianReview.create_manual_review(
                target_type=target_type,
                target_id=target_id,
                guardian_id=guardian_id,
                verdict=verdict,
                evidence=evidence
            )
        else:
            raise ValueError(f"Invalid review_type: {review_type}. Must be AUTO or MANUAL")

        # Save to storage
        self.storage.save(review)

        logger.info(
            f"Created Guardian review: {review.review_id} "
            f"(target: {target_type}/{target_id}, verdict: {verdict})"
        )

        return review

    def get_review(self, review_id: str) -> Optional[GuardianReview]:
        """
        根据 ID 获取验收记录

        Args:
            review_id: 审查 ID

        Returns:
            GuardianReview 实例或 None

        Example:
            ```python
            service = GuardianService()
            review = service.get_review("review_abc123")
            if review:
                print(f"Verdict: {review.verdict}")
            ```
        """
        return self.storage.get_by_id(review_id)

    def list_reviews(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        guardian_id: Optional[str] = None,
        verdict: Optional[str] = None,
        limit: int = 100
    ) -> List[GuardianReview]:
        """
        查询验收记录列表

        支持按多个维度过滤：目标类型、目标 ID、Guardian ID、验收结论。

        Args:
            target_type: 过滤目标类型（task | decision | finding）
            target_id: 过滤目标 ID
            guardian_id: 过滤 Guardian ID
            verdict: 过滤验收结论（PASS | FAIL | NEEDS_REVIEW）
            limit: 结果数量限制（默认 100）

        Returns:
            GuardianReview 列表（按创建时间倒序）

        Example:
            ```python
            service = GuardianService()

            # 查询所有 FAIL 的记录
            failed_reviews = service.list_reviews(verdict="FAIL")

            # 查询某个 Guardian 的所有记录
            guardian_reviews = service.list_reviews(guardian_id="guardian.ruleset.v1")

            # 查询某个任务的所有记录
            task_reviews = service.list_reviews(
                target_type="task",
                target_id="task_123"
            )
            ```
        """
        return self.storage.query(
            target_type=target_type,
            target_id=target_id,
            guardian_id=guardian_id,
            verdict=verdict,
            limit=limit
        )

    def get_reviews_by_target(
        self,
        target_type: str,
        target_id: str
    ) -> List[GuardianReview]:
        """
        获取特定目标的所有验收记录（按时间排序）

        这是一个便捷方法，专门用于查询某个目标（task/decision/finding）的完整审查历史。

        Args:
            target_type: 目标类型（task | decision | finding）
            target_id: 目标 ID

        Returns:
            GuardianReview 列表（按创建时间倒序）

        Example:
            ```python
            service = GuardianService()

            # 获取某个任务的所有验收记录
            task_reviews = service.get_reviews_by_target("task", "task_123")

            # 检查最新的验收结果
            if task_reviews:
                latest_review = task_reviews[0]
                print(f"Latest verdict: {latest_review.verdict}")
            ```
        """
        return self.storage.get_by_target(target_type, target_id)

    def get_statistics(
        self,
        target_type: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取统计数据（验收通过率、Guardian 活跃度等）

        提供 Guardian 系统的整体健康度指标和活跃度统计。

        Args:
            target_type: 过滤目标类型（可选）
            since: 统计时间起点（可选，默认统计所有时间）

        Returns:
            统计数据字典，包含：
            - total_reviews: 总审查数
            - pass_rate: 通过率（0.0-1.0）
            - guardians: Guardian 活跃度 {guardian_id: count}
            - by_verdict: 按结论分组 {verdict: count}
            - by_target_type: 按目标类型分组 {target_type: count}

        Example:
            ```python
            service = GuardianService()

            # 获取所有时间的统计
            stats = service.get_statistics()
            print(f"Pass rate: {stats['pass_rate']:.2%}")
            print(f"Total reviews: {stats['total_reviews']}")

            # 获取最近 7 天的统计
            from datetime import datetime, timedelta, timezone
            since = utc_now() - timedelta(days=7)
            recent_stats = service.get_statistics(since=since)
            print(f"Recent pass rate: {recent_stats['pass_rate']:.2%}")
            ```
        """
        return self.storage.get_stats(target_type=target_type, since=since)

    def get_verdict_summary(self, target_type: str, target_id: str) -> Dict[str, Any]:
        """
        获取目标的验收结论摘要

        提供某个目标的验收状态快速概览。

        Args:
            target_type: 目标类型（task | decision | finding）
            target_id: 目标 ID

        Returns:
            摘要字典，包含：
            - target_type: 目标类型
            - target_id: 目标 ID
            - total_reviews: 总审查数
            - latest_verdict: 最新验收结论
            - latest_review_id: 最新审查 ID
            - latest_guardian_id: 最新审查者 ID
            - all_verdicts: 所有验收结论列表

        Example:
            ```python
            service = GuardianService()
            summary = service.get_verdict_summary("task", "task_123")

            if summary["latest_verdict"] == "PASS":
                print(f"Task {target_id} passed verification")
            elif summary["latest_verdict"] == "FAIL":
                print(f"Task {target_id} failed verification")
            ```
        """
        reviews = self.get_reviews_by_target(target_type, target_id)

        if not reviews:
            return {
                "target_type": target_type,
                "target_id": target_id,
                "total_reviews": 0,
                "latest_verdict": None,
                "latest_review_id": None,
                "latest_guardian_id": None,
                "all_verdicts": []
            }

        latest = reviews[0]  # Already sorted by created_at DESC

        return {
            "target_type": target_type,
            "target_id": target_id,
            "total_reviews": len(reviews),
            "latest_verdict": latest.verdict,
            "latest_review_id": latest.review_id,
            "latest_guardian_id": latest.guardian_id,
            "all_verdicts": [r.verdict for r in reviews]
        }
