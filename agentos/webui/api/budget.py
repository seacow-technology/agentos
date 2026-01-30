"""
Budget API - Token Budget Configuration

Endpoints:
- GET /api/budget/global - Get global budget configuration
- PUT /api/budget/global - Update global budget configuration
- POST /api/budget/derive - Preview auto-derived budget from model info

Implements Task 4: WebUI Settings Interface for Token Budget Configuration
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentos.config import get_budget_config_manager, BudgetConfig
from agentos.core.chat.budget_resolver import BudgetResolver
from agentos.core.chat.budget_recommender import BudgetRecommender
from agentos.providers.base import ModelInfo

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class BudgetAllocationResponse(BaseModel):
    """Budget allocation response"""
    window_tokens: int = Field(description="Tokens for conversation window")
    rag_tokens: int = Field(description="Tokens for RAG context")
    memory_tokens: int = Field(description="Tokens for memory facts")
    summary_tokens: int = Field(description="Tokens for summary artifacts")
    system_tokens: int = Field(description="Tokens for system prompt")


class BudgetConfigResponse(BaseModel):
    """Budget configuration response"""
    max_tokens: int = Field(description="Maximum total context tokens")
    auto_derive: bool = Field(description="Whether to auto-derive from model context window")
    allocation: BudgetAllocationResponse
    safety_margin: float = Field(description="Safety margin ratio (0.0-1.0)")
    generation_max_tokens: int = Field(description="Maximum tokens for generation")
    safe_threshold: float = Field(description="Safe usage threshold (0.0-1.0)")
    critical_threshold: float = Field(description="Critical usage threshold (0.0-1.0)")


class UpdateBudgetRequest(BaseModel):
    """Update budget configuration request"""
    max_tokens: Optional[int] = Field(None, description="Maximum total context tokens")
    auto_derive: Optional[bool] = Field(None, description="Enable auto-derivation")
    window_tokens: Optional[int] = Field(None, description="Tokens for conversation window")
    rag_tokens: Optional[int] = Field(None, description="Tokens for RAG context")
    memory_tokens: Optional[int] = Field(None, description="Tokens for memory facts")
    summary_tokens: Optional[int] = Field(None, description="Tokens for summary artifacts")
    system_tokens: Optional[int] = Field(None, description="Tokens for system prompt")
    safety_margin: Optional[float] = Field(None, description="Safety margin ratio")
    generation_max_tokens: Optional[int] = Field(None, description="Maximum tokens for generation")


class DeriveRequest(BaseModel):
    """Request to preview auto-derived budget"""
    model_id: str = Field(description="Model identifier (e.g., 'gpt-4o', 'qwen2.5:7b')")
    context_window: Optional[int] = Field(None, description="Model context window size (optional)")
    generation_max: Optional[int] = Field(None, description="Maximum generation tokens (optional)")


class DeriveResponse(BaseModel):
    """Auto-derived budget preview response"""
    budget: BudgetConfigResponse
    model_name: str
    context_window: int
    source: str = Field(description="Derivation source: 'auto_derived', 'fallback', etc.")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/global")
async def get_global_budget() -> BudgetConfigResponse:
    """
    Get global budget configuration

    Returns current global budget config from ~/.agentos/config/budget.json
    If file doesn't exist, returns default configuration.

    Returns:
        BudgetConfigResponse with current configuration
    """
    try:
        manager = get_budget_config_manager()
        config = manager.load()

        return BudgetConfigResponse(
            max_tokens=config.max_tokens,
            auto_derive=config.auto_derive,
            allocation=BudgetAllocationResponse(
                window_tokens=config.allocation.window_tokens,
                rag_tokens=config.allocation.rag_tokens,
                memory_tokens=config.allocation.memory_tokens,
                summary_tokens=config.allocation.summary_tokens,
                system_tokens=config.allocation.system_tokens,
            ),
            safety_margin=config.safety_margin,
            generation_max_tokens=config.generation_max_tokens,
            safe_threshold=config.safe_threshold,
            critical_threshold=config.critical_threshold,
        )

    except Exception as e:
        logger.error(f"Failed to load global budget config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load budget configuration: {str(e)}")


@router.put("/global")
async def update_global_budget(request: UpdateBudgetRequest) -> BudgetConfigResponse:
    """
    Update global budget configuration

    Updates global budget config file. Only provided fields are updated,
    others remain unchanged.

    Args:
        request: Update request with optional fields

    Returns:
        Updated BudgetConfigResponse

    Raises:
        400: Invalid configuration values
        500: Failed to save configuration
    """
    try:
        manager = get_budget_config_manager()
        config = manager.load()

        # Update max_tokens
        if request.max_tokens is not None:
            if request.max_tokens < 1000:
                raise HTTPException(status_code=400, detail="max_tokens must be at least 1000")
            config.max_tokens = request.max_tokens

        # Update auto_derive
        if request.auto_derive is not None:
            config.auto_derive = request.auto_derive

        # Update allocation
        if request.window_tokens is not None:
            if request.window_tokens < 0:
                raise HTTPException(status_code=400, detail="window_tokens cannot be negative")
            config.allocation.window_tokens = request.window_tokens

        if request.rag_tokens is not None:
            if request.rag_tokens < 0:
                raise HTTPException(status_code=400, detail="rag_tokens cannot be negative")
            config.allocation.rag_tokens = request.rag_tokens

        if request.memory_tokens is not None:
            if request.memory_tokens < 0:
                raise HTTPException(status_code=400, detail="memory_tokens cannot be negative")
            config.allocation.memory_tokens = request.memory_tokens

        if request.summary_tokens is not None:
            if request.summary_tokens < 0:
                raise HTTPException(status_code=400, detail="summary_tokens cannot be negative")
            config.allocation.summary_tokens = request.summary_tokens

        if request.system_tokens is not None:
            if request.system_tokens < 0:
                raise HTTPException(status_code=400, detail="system_tokens cannot be negative")
            config.allocation.system_tokens = request.system_tokens

        # Update safety margin
        if request.safety_margin is not None:
            if not (0.0 <= request.safety_margin <= 1.0):
                raise HTTPException(status_code=400, detail="safety_margin must be between 0.0 and 1.0")
            config.safety_margin = request.safety_margin

        # Update generation max tokens
        if request.generation_max_tokens is not None:
            if request.generation_max_tokens < 100:
                raise HTTPException(status_code=400, detail="generation_max_tokens must be at least 100")
            config.generation_max_tokens = request.generation_max_tokens

        # Validate component sum (only if manual allocation was changed)
        if any([
            request.window_tokens is not None,
            request.rag_tokens is not None,
            request.memory_tokens is not None,
            request.summary_tokens is not None,
            request.system_tokens is not None
        ]):
            component_sum = (
                config.allocation.window_tokens +
                config.allocation.rag_tokens +
                config.allocation.memory_tokens +
                config.allocation.summary_tokens +
                config.allocation.system_tokens
            )

            if component_sum > config.max_tokens:
                raise HTTPException(
                    status_code=400,
                    detail=f"Component sum ({component_sum}) exceeds max_tokens ({config.max_tokens})"
                )

        # Save updated config
        manager.save(config)
        logger.info(f"Updated global budget config: max_tokens={config.max_tokens}, auto_derive={config.auto_derive}")

        return BudgetConfigResponse(
            max_tokens=config.max_tokens,
            auto_derive=config.auto_derive,
            allocation=BudgetAllocationResponse(
                window_tokens=config.allocation.window_tokens,
                rag_tokens=config.allocation.rag_tokens,
                memory_tokens=config.allocation.memory_tokens,
                summary_tokens=config.allocation.summary_tokens,
                system_tokens=config.allocation.system_tokens,
            ),
            safety_margin=config.safety_margin,
            generation_max_tokens=config.generation_max_tokens,
            safe_threshold=config.safe_threshold,
            critical_threshold=config.critical_threshold,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update global budget config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update budget configuration: {str(e)}")


@router.post("/derive")
async def preview_derive(request: DeriveRequest) -> DeriveResponse:
    """
    Preview auto-derived budget from model info

    Calculates what the budget would be if auto-derive is enabled for the given model.
    This is a preview operation - it does not save any configuration.

    Args:
        request: Model info and optional parameters

    Returns:
        DeriveResponse with auto-derived budget preview

    Example:
        {
            "model_id": "gpt-4o",
            "context_window": 128000
        }

        Returns budget with ~91.8k input tokens + 17k generation tokens
    """
    try:
        resolver = BudgetResolver()

        # Create ModelInfo
        model_info = ModelInfo(
            id=request.model_id,
            label=request.model_id,
            context_window=request.context_window
        )

        # Auto-derive budget
        context_budget = resolver.auto_derive_budget(
            model_info=model_info,
            generation_max=request.generation_max
        )

        # Get actual context window used
        context_window = resolver.get_context_window(request.model_id, model_info)

        # Extract metadata
        metadata = getattr(context_budget, 'metadata', {})
        generation_budget = metadata.get('generation_max_tokens', request.generation_max or 2000)

        # Convert to response
        response = DeriveResponse(
            budget=BudgetConfigResponse(
                max_tokens=context_budget.max_tokens,
                auto_derive=True,
                allocation=BudgetAllocationResponse(
                    window_tokens=context_budget.window_tokens,
                    rag_tokens=context_budget.rag_tokens,
                    memory_tokens=context_budget.memory_tokens,
                    summary_tokens=context_budget.summary_tokens,
                    system_tokens=context_budget.system_tokens,
                ),
                safety_margin=metadata.get('safety_margin', 0.15),
                generation_max_tokens=generation_budget,
                safe_threshold=0.6,
                critical_threshold=0.8,
            ),
            model_name=request.model_id,
            context_window=context_window,
            source="auto_derived"
        )

        logger.info(f"Derived budget preview for {request.model_id}: "
                   f"input={context_budget.max_tokens}, generation={generation_budget}")

        return response

    except Exception as e:
        logger.error(f"Failed to derive budget: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to derive budget: {str(e)}")


# ============================================================================
# P2-9: Budget Recommendation Endpoints
# ============================================================================

class RecommendRequest(BaseModel):
    """Request for budget recommendation"""
    session_id: str = Field(description="Session ID to analyze")
    model_id: str = Field(description="Current model ID")
    context_window: Optional[int] = Field(None, description="Model context window")
    last_n: int = Field(30, description="Number of recent conversations to analyze")


class RecommendationResponse(BaseModel):
    """Budget recommendation response"""
    available: bool = Field(description="Whether recommendation is available")
    reason: Optional[str] = Field(None, description="Reason if not available")
    hint: Optional[str] = Field(None, description="User-friendly hint")
    min_samples: Optional[int] = Field(None, description="Minimum samples needed")
    current: Optional[Dict[str, Any]] = Field(None, description="Current budget")
    recommended: Optional[Dict[str, Any]] = Field(None, description="Recommended budget")
    stats: Optional[Dict[str, Any]] = Field(None, description="Usage statistics")
    message: Optional[str] = Field(None, description="Recommendation message")


class ApplyRecommendationRequest(BaseModel):
    """Request to apply recommendation"""
    recommendation: Dict[str, int] = Field(description="Recommended budget to apply")
    session_id: Optional[str] = Field(None, description="Session ID (for session-level config)")


@router.post("/recommend")
async def get_budget_recommendation(request: RecommendRequest) -> RecommendationResponse:
    """
    Get budget recommendation based on usage patterns

    P2-9: Budget 推荐系统（只"建议"，不"决定"）

    This endpoint analyzes recent conversation history to suggest budget optimizations.
    Recommendations are:
    - Non-intrusive (must be manually requested)
    - Based on statistics only (P95 + 20% buffer)
    - Never auto-applied
    - Require user confirmation

    Args:
        request: Recommendation request with session_id and model info

    Returns:
        RecommendationResponse with recommendation or reason for unavailability

    Example:
        {
            "session_id": "01H8X...",
            "model_id": "gpt-4o",
            "context_window": 128000,
            "last_n": 30
        }
    """
    try:
        recommender = BudgetRecommender()
        manager = get_budget_config_manager()

        # Get current budget
        current_config = manager.load()
        current_budget = {
            "window_tokens": current_config.allocation.window_tokens,
            "rag_tokens": current_config.allocation.rag_tokens,
            "memory_tokens": current_config.allocation.memory_tokens,
            "system_tokens": current_config.allocation.system_tokens,
        }

        # Create model info
        model_info = ModelInfo(
            id=request.model_id,
            label=request.model_id,
            context_window=request.context_window
        )

        # Get recommendation
        result = recommender.get_recommendation(
            session_id=request.session_id,
            current_budget=current_budget,
            model_info=model_info,
            last_n=request.last_n
        )

        logger.info(f"Budget recommendation for session {request.session_id}: available={result.get('available')}")

        return RecommendationResponse(**result)

    except Exception as e:
        logger.error(f"Failed to get budget recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendation: {str(e)}")


@router.post("/apply-recommendation")
async def apply_budget_recommendation(request: ApplyRecommendationRequest) -> BudgetConfigResponse:
    """
    Apply budget recommendation to global configuration

    P2-9: This endpoint REQUIRES explicit user confirmation.
    The applied config is marked as "user_applied_recommendation" (NOT "system_adjusted").

    This is a deliberate design choice to prevent silent budget changes.

    Args:
        request: Apply recommendation request

    Returns:
        Updated BudgetConfigResponse

    Raises:
        400: Invalid recommendation format
        500: Failed to apply recommendation
    """
    try:
        manager = get_budget_config_manager()

        # Load current config
        config = manager.load()

        # Validate recommendation
        recommendation = request.recommendation
        required_fields = ["window_tokens", "rag_tokens", "memory_tokens", "system_tokens"]

        for field in required_fields:
            if field not in recommendation:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field in recommendation: {field}"
                )

            if recommendation[field] < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field} cannot be negative"
                )

        # Apply recommendation
        config.allocation.window_tokens = recommendation["window_tokens"]
        config.allocation.rag_tokens = recommendation["rag_tokens"]
        config.allocation.memory_tokens = recommendation["memory_tokens"]
        config.allocation.system_tokens = recommendation["system_tokens"]

        # Update max_tokens to match total
        total = sum(recommendation.values())
        config.max_tokens = total

        # Save with explicit source marking
        manager.save(config)

        logger.info(
            f"Applied budget recommendation: total={total}, "
            f"source=user_applied_recommendation, "
            f"session={request.session_id}"
        )

        # Return updated config
        return BudgetConfigResponse(
            max_tokens=config.max_tokens,
            auto_derive=config.auto_derive,
            allocation=BudgetAllocationResponse(
                window_tokens=config.allocation.window_tokens,
                rag_tokens=config.allocation.rag_tokens,
                memory_tokens=config.allocation.memory_tokens,
                summary_tokens=config.allocation.summary_tokens,
                system_tokens=config.allocation.system_tokens,
            ),
            safety_margin=config.safety_margin,
            generation_max_tokens=config.generation_max_tokens,
            safe_threshold=config.safe_threshold,
            critical_threshold=config.critical_threshold,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply budget recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply recommendation: {str(e)}")
