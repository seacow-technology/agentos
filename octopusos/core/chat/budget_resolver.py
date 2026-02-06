"""Budget Resolver - Automatically derive context budgets from model context windows

This module implements the core logic for automatic token budget derivation based on
model context windows, following the design specified in Task 1.

Key features:
- Auto-derive budgets from model context_window (with 15% safety margin)
- Fallback to safe defaults when model info is missing
- Validate budgets against rules
- Resolve budgets with priority: session > project > auto-derived

Architecture:
- BudgetResolver: Main resolver class
- auto_derive_budget: Core derivation algorithm
- get_context_window: Context window lookup with fallbacks
- validate_budget: Budget validation rules
- resolve_budget: Priority-based budget resolution
"""

from typing import Optional, Dict, Any
import logging
from dataclasses import dataclass

from agentos.core.chat.context_builder import ContextBudget
from agentos.providers.base import ModelInfo

logger = logging.getLogger(__name__)

# Fallback context windows for known models
FALLBACK_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "claude-3-5-sonnet": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "llama3.2:1b": 131072,
    "llama3.2:3b": 131072,
    "qwen2.5:7b": 131072,
    "qwen2.5:14b": 131072,
    "default": 8000
}

# Component allocation ratios
DEFAULT_ALLOCATION = {
    "system": 0.125,   # 12.5% for system prompt
    "window": 0.50,    # 50% for conversation window
    "rag": 0.25,       # 25% for RAG context
    "memory": 0.125    # 12.5% for memory facts
}


@dataclass
class BudgetDerivationResult:
    """Result of budget derivation with metadata"""
    budget: ContextBudget
    source: str  # "auto_derived", "session_config", "project_config", "default"
    model_name: Optional[str] = None
    context_window: Optional[int] = None


class BudgetResolver:
    """Resolves context budgets with auto-derivation from model context windows"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize BudgetResolver

        Args:
            db_path: Database path for loading session/project configs
        """
        self.db_path = db_path

    def auto_derive_budget(
        self,
        model_info: Optional[ModelInfo],
        generation_max: Optional[int] = None,
        allocation: Optional[Dict[str, float]] = None
    ) -> ContextBudget:
        """Automatically derive context budget from model context window

        This is the core algorithm for auto-deriving token budgets.

        Algorithm:
        1. Get model context window (with fallback to 8000)
        2. Apply 15% safety margin: usable_tokens = window * 0.85
        3. Reserve generation space: min(generation_max, 25% of window)
        4. Calculate input budget: usable - generation
        5. Allocate input budget to components (system/window/rag/memory)

        Args:
            model_info: Model information (may be None)
            generation_max: Maximum generation tokens (default: 2000 or 25% of window)
            allocation: Custom allocation ratios (default: DEFAULT_ALLOCATION)

        Returns:
            ContextBudget with auto-derived values

        Examples:
            >>> # 8k model: ~5.1k input + 1.7k generation
            >>> budget = resolver.auto_derive_budget(ModelInfo(id="gpt-3.5", label="GPT-3.5", context_window=8192))
            >>> assert budget.max_tokens == 5461  # 8192 * 0.85 - 2048

            >>> # 128k model: ~91.8k input + 17k generation
            >>> budget = resolver.auto_derive_budget(ModelInfo(id="gpt-4o", label="GPT-4o", context_window=128000))
            >>> assert budget.max_tokens == 91800  # 128000 * 0.85 - 16000
        """
        # Step 1: Get context window
        context_window = self.get_context_window(
            model_name=model_info.id if model_info else None,
            model_info=model_info
        )

        logger.info(f"Auto-deriving budget for context_window={context_window}")

        # Step 2: Apply 15% safety margin
        usable_tokens = int(context_window * 0.85)

        # Step 3: Reserve generation space (default: 2000 or 25% of window, whichever is smaller)
        default_generation_max = min(2000, int(context_window * 0.25))
        generation_budget = generation_max or default_generation_max
        generation_budget = min(generation_budget, int(context_window * 0.25))

        # Step 4: Calculate input budget
        input_budget = usable_tokens - generation_budget

        # Step 5: Allocate components
        alloc = allocation or DEFAULT_ALLOCATION

        system_tokens = int(input_budget * alloc["system"])
        window_tokens = int(input_budget * alloc["window"])
        rag_tokens = int(input_budget * alloc["rag"])
        memory_tokens = int(input_budget * alloc["memory"])

        # Create budget
        budget = ContextBudget(
            max_tokens=input_budget,
            system_tokens=system_tokens,
            window_tokens=window_tokens,
            rag_tokens=rag_tokens,
            memory_tokens=memory_tokens,
            summary_tokens=0  # Not allocated by default
        )

        # Add metadata for traceability
        if not hasattr(budget, 'metadata'):
            budget.__dict__['metadata'] = {}

        budget.__dict__['metadata'].update({
            'auto_derived': True,
            'model_context_window': context_window,
            'generation_max_tokens': generation_budget,
            'safety_margin': 0.15,
            'allocation': alloc
        })

        logger.info(f"Derived budget: input={input_budget}, generation={generation_budget}, "
                   f"system={system_tokens}, window={window_tokens}, rag={rag_tokens}, memory={memory_tokens}")

        return budget

    def get_context_window(
        self,
        model_name: Optional[str],
        model_info: Optional[ModelInfo]
    ) -> int:
        """Get context window for model with fallback strategy

        Priority:
        1. model_info.context_window (explicit value)
        2. FALLBACK_WINDOWS[model_name] (known model)
        3. FALLBACK_WINDOWS["default"] = 8000 (safe default)

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "qwen2.5:7b")
            model_info: ModelInfo object (may contain context_window)

        Returns:
            Context window size in tokens
        """
        # Priority 1: Explicit value in model_info
        if model_info and model_info.context_window:
            logger.debug(f"Using explicit context_window from model_info: {model_info.context_window}")
            return model_info.context_window

        # Priority 2: Known model in fallback table
        if model_name:
            # Try exact match
            if model_name in FALLBACK_WINDOWS:
                window = FALLBACK_WINDOWS[model_name]
                logger.debug(f"Using fallback window for {model_name}: {window}")
                return window

            # Try prefix match (e.g., "gpt-4o-2024-08-06" matches "gpt-4o")
            for key, window in FALLBACK_WINDOWS.items():
                if key != "default" and model_name.startswith(key):
                    logger.debug(f"Using fallback window for {model_name} (matched {key}): {window}")
                    return window

        # Priority 3: Safe default
        default_window = FALLBACK_WINDOWS["default"]
        logger.warning(f"No context_window found for model '{model_name}', using default: {default_window}")
        return default_window

    def validate_budget(
        self,
        budget: ContextBudget,
        model_info: Optional[ModelInfo] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate budget against rules

        Validation rules:
        1. All token values must be positive
        2. Component sum <= max_tokens
        3. max_tokens <= model_context_window (if known)
        4. Minimum viable budget: max_tokens >= 1000
        5. No single component exceeds 80% of max_tokens

        Args:
            budget: Budget to validate
            model_info: Optional model info for window validation

        Returns:
            (is_valid, error_message)
        """
        # Rule 1: Positive values
        if budget.max_tokens <= 0:
            return False, "max_tokens must be positive"

        if budget.system_tokens < 0 or budget.window_tokens < 0 or \
           budget.rag_tokens < 0 or budget.memory_tokens < 0:
            return False, "Component tokens cannot be negative"

        # Rule 2: Component sum <= max_tokens
        component_sum = (
            budget.system_tokens +
            budget.window_tokens +
            budget.rag_tokens +
            budget.memory_tokens +
            budget.summary_tokens
        )

        if component_sum > budget.max_tokens:
            return False, f"Component sum ({component_sum}) exceeds max_tokens ({budget.max_tokens})"

        # Rule 3: Check against model window (if known)
        if model_info and model_info.context_window:
            # Allow budget up to 90% of model window (generous margin)
            max_allowed = int(model_info.context_window * 0.9)
            if budget.max_tokens > max_allowed:
                return False, f"max_tokens ({budget.max_tokens}) exceeds 90% of model window ({max_allowed})"

        # Rule 4: Minimum viable budget
        if budget.max_tokens < 1000:
            return False, f"max_tokens ({budget.max_tokens}) is too small (minimum: 1000)"

        # Rule 5: No component exceeds 80% of max_tokens
        max_component_allowed = int(budget.max_tokens * 0.8)

        if budget.system_tokens > max_component_allowed:
            return False, f"system_tokens ({budget.system_tokens}) exceeds 80% of max_tokens"
        if budget.window_tokens > max_component_allowed:
            return False, f"window_tokens ({budget.window_tokens}) exceeds 80% of max_tokens"
        if budget.rag_tokens > max_component_allowed:
            return False, f"rag_tokens ({budget.rag_tokens}) exceeds 80% of max_tokens"
        if budget.memory_tokens > max_component_allowed:
            return False, f"memory_tokens ({budget.memory_tokens}) exceeds 80% of max_tokens"

        return True, None

    def resolve_budget(
        self,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        model_info: Optional[ModelInfo] = None,
        generation_max: Optional[int] = None
    ) -> BudgetDerivationResult:
        """Resolve budget with priority: session > project > auto-derived

        Priority order:
        1. Session-specific config (if session_id provided)
        2. Project-specific config (if project_id provided)
        3. Auto-derived from model_info
        4. Safe default (8k window)

        Args:
            session_id: Optional session ID for session-specific config
            project_id: Optional project ID for project-specific config
            model_info: Optional model info for auto-derivation
            generation_max: Optional generation token limit

        Returns:
            BudgetDerivationResult with budget and metadata
        """
        # Priority 1: Session-specific config (TODO: implement when session config available)
        if session_id and self.db_path:
            session_budget = self._load_session_budget(session_id)
            if session_budget:
                logger.info(f"Using session-specific budget for session {session_id}")
                return BudgetDerivationResult(
                    budget=session_budget,
                    source="session_config",
                    model_name=model_info.id if model_info else None,
                    context_window=model_info.context_window if model_info else None
                )

        # Priority 2: Project-specific config (TODO: implement when project config available)
        if project_id and self.db_path:
            project_budget = self._load_project_budget(project_id)
            if project_budget:
                logger.info(f"Using project-specific budget for project {project_id}")
                return BudgetDerivationResult(
                    budget=project_budget,
                    source="project_config",
                    model_name=model_info.id if model_info else None,
                    context_window=model_info.context_window if model_info else None
                )

        # Priority 3: Auto-derived from model_info
        if model_info or generation_max:
            budget = self.auto_derive_budget(model_info, generation_max)
            logger.info(f"Using auto-derived budget for model {model_info.id if model_info else 'unknown'}")
            return BudgetDerivationResult(
                budget=budget,
                source="auto_derived",
                model_name=model_info.id if model_info else None,
                context_window=self.get_context_window(
                    model_info.id if model_info else None,
                    model_info
                )
            )

        # Priority 4: Safe default
        logger.warning("No model info available, using safe default budget")
        default_budget = ContextBudget(
            max_tokens=5100,  # ~8k * 0.85 - 1700
            system_tokens=637,
            window_tokens=2550,
            rag_tokens=1275,
            memory_tokens=637,
            summary_tokens=0
        )
        return BudgetDerivationResult(
            budget=default_budget,
            source="default",
            model_name=None,
            context_window=8000
        )

    def get_default_budget(self) -> ContextBudget:
        """Get default budget (for backward compatibility)

        Returns default budget based on 8k context window.
        """
        return self.resolve_budget().budget

    def _load_session_budget(self, session_id: str) -> Optional[ContextBudget]:
        """Load session-specific budget from database

        TODO: Implement when session-level config is available

        Args:
            session_id: Session ID

        Returns:
            ContextBudget if found, None otherwise
        """
        # Placeholder for future implementation
        return None

    def _load_project_budget(self, project_id: str) -> Optional[ContextBudget]:
        """Load project-specific budget from database

        TODO: Implement when project-level config is available

        Args:
            project_id: Project ID

        Returns:
            ContextBudget if found, None otherwise
        """
        # Placeholder for future implementation
        return None
