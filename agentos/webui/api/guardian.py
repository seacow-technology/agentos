"""
Guardian API - Guardian 验收审查记录

提供 Guardian Review CRUD 操作的 REST API 端点。

核心原则：
1. Guardian 是只读叠加层，不修改 Task 状态
2. 所有验收记录都是不可变的（immutable）
3. API 仅提供查询和创建功能，不支持修改或删除

Endpoints:
- GET  /api/guardian/reviews - 查询验收记录列表
- POST /api/guardian/reviews - 创建验收记录
- GET  /api/guardian/reviews/{review_id} - 获取单个验收记录
- GET  /api/guardian/statistics - 获取统计数据
- GET  /api/guardian/targets/{target_type}/{target_id}/reviews - 获取目标的所有验收记录
- GET  /api/guardian/targets/{target_type}/{target_id}/verdict - 获取目标的验收摘要

Created for Task #2: Guardian Service 和 API 端点
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from agentos.core.guardian import GuardianService, GuardianReview
from agentos.core.time import utc_now


router = APIRouter(prefix="/api/guardian", tags=["guardian"])


# ============================================
# Request Models
# ============================================

class CreateReviewRequest(BaseModel):
    """创建验收记录请求"""
    target_type: str = Field(..., description="审查目标类型：task | decision | finding")
    target_id: str = Field(..., description="审查目标 ID")
    guardian_id: str = Field(..., description="Guardian ID（agent name / human id）")
    review_type: str = Field(..., description="审查类型：AUTO | MANUAL")
    verdict: str = Field(..., description="验收结论：PASS | FAIL | NEEDS_REVIEW")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度（0.0-1.0）")
    rule_snapshot_id: Optional[str] = Field(None, description="规则快照 ID（可选）")
    evidence: Dict[str, Any] = Field(..., description="验收证据（JSON 结构）")

    class Config:
        json_schema_extra = {
            "example": {
                "target_type": "task",
                "target_id": "task_123",
                "guardian_id": "guardian.ruleset.v1",
                "review_type": "AUTO",
                "verdict": "PASS",
                "confidence": 0.92,
                "rule_snapshot_id": "ruleset:v1@sha256:abc",
                "evidence": {
                    "checks": ["state_machine_ok"],
                    "metrics": {"coverage": 0.85}
                }
            }
        }


# ============================================
# Response Models
# ============================================

class GuardianReviewResponse(BaseModel):
    """验收记录响应"""
    review_id: str
    target_type: str
    target_id: str
    guardian_id: str
    review_type: str
    verdict: str
    confidence: float
    rule_snapshot_id: Optional[str]
    evidence: Dict[str, Any]
    created_at: str

    @classmethod
    def from_review(cls, review: GuardianReview) -> "GuardianReviewResponse":
        """从 GuardianReview 实例创建响应"""
        return cls(
            review_id=review.review_id,
            target_type=review.target_type,
            target_id=review.target_id,
            guardian_id=review.guardian_id,
            review_type=review.review_type,
            verdict=review.verdict,
            confidence=review.confidence,
            rule_snapshot_id=review.rule_snapshot_id,
            evidence=review.evidence,
            created_at=review.created_at
        )


class ListReviewsResponse(BaseModel):
    """查询验收记录列表响应"""
    reviews: List[GuardianReviewResponse]
    total: int


class CreateReviewResponse(BaseModel):
    """创建验收记录响应"""
    review_id: str
    status: str = "created"


class StatisticsResponse(BaseModel):
    """统计数据响应"""
    total_reviews: int
    pass_rate: float
    guardians: Dict[str, int]
    by_verdict: Dict[str, int]
    by_target_type: Dict[str, int]


class VerdictSummaryResponse(BaseModel):
    """验收摘要响应"""
    target_type: str
    target_id: str
    total_reviews: int
    latest_verdict: Optional[str]
    latest_review_id: Optional[str]
    latest_guardian_id: Optional[str]
    all_verdicts: List[str]


# ============================================
# API Endpoints
# ============================================

@router.get("/reviews", response_model=ListReviewsResponse)
async def list_guardian_reviews(
    target_type: Optional[str] = Query(None, description="过滤目标类型：task | decision | finding"),
    target_id: Optional[str] = Query(None, description="过滤目标 ID"),
    guardian_id: Optional[str] = Query(None, description="过滤 Guardian ID"),
    verdict: Optional[str] = Query(None, description="过滤验收结论：PASS | FAIL | NEEDS_REVIEW"),
    limit: int = Query(100, ge=1, le=500, description="结果数量限制")
) -> ListReviewsResponse:
    """
    查询验收记录列表

    支持按多个维度过滤：目标类型、目标 ID、Guardian ID、验收结论。
    所有过滤条件都是 AND 关系。

    Args:
        target_type: 过滤目标类型（可选）
        target_id: 过滤目标 ID（可选）
        guardian_id: 过滤 Guardian ID（可选）
        verdict: 过滤验收结论（可选）
        limit: 结果数量限制（1-500，默认 100）

    Returns:
        验收记录列表和总数

    Example:
        ```bash
        # 查询所有 FAIL 的记录
        curl "http://localhost:8080/api/guardian/reviews?verdict=FAIL"

        # 查询某个任务的所有记录
        curl "http://localhost:8080/api/guardian/reviews?target_type=task&target_id=task_123"

        # 查询某个 Guardian 的所有记录
        curl "http://localhost:8080/api/guardian/reviews?guardian_id=guardian.v1"
        ```
    """
    try:
        service = GuardianService()
        reviews = service.list_reviews(
            target_type=target_type,
            target_id=target_id,
            guardian_id=guardian_id,
            verdict=verdict,
            limit=limit
        )

        return ListReviewsResponse(
            reviews=[GuardianReviewResponse.from_review(r) for r in reviews],
            total=len(reviews)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list reviews: {str(e)}"
        )


@router.post("/reviews", response_model=CreateReviewResponse, status_code=201)
async def create_guardian_review(request: CreateReviewRequest) -> CreateReviewResponse:
    """
    创建验收记录

    创建一个新的 Guardian 验收审查记录。
    所有验收记录都是不可变的，一旦创建就无法修改。

    Args:
        request: 创建请求（包含所有必需字段）

    Returns:
        创建的验收记录 ID 和状态

    Raises:
        HTTPException: 400 如果参数无效，500 如果创建失败

    Example:
        ```bash
        curl -X POST "http://localhost:8080/api/guardian/reviews" \\
          -H "Content-Type: application/json" \\
          -d '{
            "target_type": "task",
            "target_id": "task_123",
            "guardian_id": "guardian.ruleset.v1",
            "review_type": "AUTO",
            "verdict": "PASS",
            "confidence": 0.92,
            "rule_snapshot_id": "ruleset:v1@sha256:abc",
            "evidence": {
              "checks": ["state_machine_ok"],
              "metrics": {}
            }
          }'
        ```
    """
    try:
        service = GuardianService()
        review = service.create_review(
            target_type=request.target_type,
            target_id=request.target_id,
            guardian_id=request.guardian_id,
            review_type=request.review_type,
            verdict=request.verdict,
            confidence=request.confidence,
            evidence=request.evidence,
            rule_snapshot_id=request.rule_snapshot_id
        )

        return CreateReviewResponse(
            review_id=review.review_id,
            status="created"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create review: {str(e)}"
        )


@router.get("/reviews/{review_id}", response_model=GuardianReviewResponse)
async def get_guardian_review(review_id: str) -> GuardianReviewResponse:
    """
    获取单个验收记录详情

    Args:
        review_id: 审查 ID

    Returns:
        验收记录详情

    Raises:
        HTTPException: 404 如果记录不存在

    Example:
        ```bash
        curl "http://localhost:8080/api/guardian/reviews/review_abc123"
        ```
    """
    try:
        service = GuardianService()
        review = service.get_review(review_id)

        if not review:
            raise HTTPException(
                status_code=404,
                detail=f"Review not found: {review_id}"
            )

        return GuardianReviewResponse.from_review(review)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get review: {str(e)}"
        )


@router.get("/statistics", response_model=StatisticsResponse)
async def get_guardian_statistics(
    target_type: Optional[str] = Query(None, description="过滤目标类型（可选）"),
    since_hours: Optional[int] = Query(None, ge=1, description="统计最近 N 小时（可选）")
) -> StatisticsResponse:
    """
    获取 Guardian 统计数据

    提供 Guardian 系统的整体健康度指标和活跃度统计。

    Args:
        target_type: 过滤目标类型（可选）
        since_hours: 统计最近 N 小时（可选，默认统计所有时间）

    Returns:
        统计数据，包含：
        - total_reviews: 总审查数
        - pass_rate: 通过率（0.0-1.0）
        - guardians: Guardian 活跃度 {guardian_id: count}
        - by_verdict: 按结论分组 {verdict: count}
        - by_target_type: 按目标类型分组 {target_type: count}

    Example:
        ```bash
        # 获取所有时间的统计
        curl "http://localhost:8080/api/guardian/statistics"

        # 获取最近 24 小时的统计
        curl "http://localhost:8080/api/guardian/statistics?since_hours=24"

        # 获取任务类型的统计
        curl "http://localhost:8080/api/guardian/statistics?target_type=task"
        ```
    """
    try:
        service = GuardianService()

        # 计算 since 时间点
        since = None
        if since_hours is not None:
            from datetime import timedelta, timezone
            since = utc_now() - timedelta(hours=since_hours)

        stats = service.get_statistics(target_type=target_type, since=since)

        return StatisticsResponse(
            total_reviews=stats["total_reviews"],
            pass_rate=stats["pass_rate"],
            guardians=stats["guardians"],
            by_verdict=stats["by_verdict"],
            by_target_type=stats["by_target_type"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get("/targets/{target_type}/{target_id}/reviews", response_model=ListReviewsResponse)
async def get_target_reviews(
    target_type: str,
    target_id: str
) -> ListReviewsResponse:
    """
    获取目标的所有验收记录

    专用端点，用于查询某个目标（task/decision/finding）的完整审查历史。

    Args:
        target_type: 目标类型（task | decision | finding）
        target_id: 目标 ID

    Returns:
        验收记录列表（按时间倒序）

    Example:
        ```bash
        # 获取某个任务的所有验收记录
        curl "http://localhost:8080/api/guardian/targets/task/task_123/reviews"

        # 获取某个决策的所有验收记录
        curl "http://localhost:8080/api/guardian/targets/decision/dec_456/reviews"
        ```
    """
    try:
        service = GuardianService()
        reviews = service.get_reviews_by_target(target_type, target_id)

        return ListReviewsResponse(
            reviews=[GuardianReviewResponse.from_review(r) for r in reviews],
            total=len(reviews)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get target reviews: {str(e)}"
        )


@router.get("/targets/{target_type}/{target_id}/verdict", response_model=VerdictSummaryResponse)
async def get_target_verdict_summary(
    target_type: str,
    target_id: str
) -> VerdictSummaryResponse:
    """
    获取目标的验收结论摘要

    提供某个目标的验收状态快速概览。

    Args:
        target_type: 目标类型（task | decision | finding）
        target_id: 目标 ID

    Returns:
        验收摘要，包含：
        - target_type: 目标类型
        - target_id: 目标 ID
        - total_reviews: 总审查数
        - latest_verdict: 最新验收结论
        - latest_review_id: 最新审查 ID
        - latest_guardian_id: 最新审查者 ID
        - all_verdicts: 所有验收结论列表

    Example:
        ```bash
        # 获取任务的验收摘要
        curl "http://localhost:8080/api/guardian/targets/task/task_123/verdict"
        ```
    """
    try:
        service = GuardianService()
        summary = service.get_verdict_summary(target_type, target_id)

        return VerdictSummaryResponse(**summary)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get verdict summary: {str(e)}"
        )
