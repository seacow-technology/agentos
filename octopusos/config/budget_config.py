"""Budget Configuration Management

Provides configuration management for token budgets in Chat Mode.
Supports global, project-level, and session-level configurations with priority resolution.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetAllocation:
    """Token budget allocation for different context components"""
    window_tokens: int = 4000  # Recent conversation messages
    rag_tokens: int = 2000  # RAG/KB search results
    memory_tokens: int = 1000  # Pinned memory facts
    summary_tokens: int = 1000  # Summary artifacts
    system_tokens: int = 1000  # System prompt and policy


@dataclass
class BudgetConfig:
    """Token budget configuration

    Attributes:
        max_tokens: Maximum total context tokens (default: 8000)
        auto_derive: Whether to auto-derive from model context window
        allocation: Token allocation for different components
        safety_margin: Safety margin ratio (e.g., 0.2 = 20%)
        generation_max_tokens: Maximum tokens for model generation
    """
    max_tokens: int = 8000
    auto_derive: bool = False
    allocation: BudgetAllocation = field(default_factory=BudgetAllocation)
    safety_margin: float = 0.2  # 20% safety margin
    generation_max_tokens: int = 2000

    # Watermark thresholds (as ratio of budget)
    safe_threshold: float = 0.6  # 60%
    critical_threshold: float = 0.8  # 80%

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert nested dataclass
        if isinstance(self.allocation, BudgetAllocation):
            data["allocation"] = asdict(self.allocation)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetConfig":
        """Create from dictionary"""
        # Parse allocation
        allocation_data = data.get("allocation", {})
        allocation = BudgetAllocation(**allocation_data) if allocation_data else BudgetAllocation()

        return cls(
            max_tokens=data.get("max_tokens", 8000),
            auto_derive=data.get("auto_derive", False),
            allocation=allocation,
            safety_margin=data.get("safety_margin", 0.2),
            generation_max_tokens=data.get("generation_max_tokens", 2000),
            safe_threshold=data.get("safe_threshold", 0.6),
            critical_threshold=data.get("critical_threshold", 0.8),
        )

    def derive_from_model_window(self, model_context_window: int) -> "BudgetConfig":
        """Derive budget from model context window

        Args:
            model_context_window: Model's maximum context window (e.g., 128000 for GPT-4)

        Returns:
            New BudgetConfig with derived values
        """
        # Apply safety margin
        effective_window = int(model_context_window * (1 - self.safety_margin))

        # Reserve for generation
        available_for_context = effective_window - self.generation_max_tokens

        # Derive allocation (proportional to defaults)
        total_default = (self.allocation.window_tokens +
                        self.allocation.rag_tokens +
                        self.allocation.memory_tokens +
                        self.allocation.summary_tokens +
                        self.allocation.system_tokens)

        scale_factor = available_for_context / total_default

        new_allocation = BudgetAllocation(
            window_tokens=int(self.allocation.window_tokens * scale_factor),
            rag_tokens=int(self.allocation.rag_tokens * scale_factor),
            memory_tokens=int(self.allocation.memory_tokens * scale_factor),
            summary_tokens=int(self.allocation.summary_tokens * scale_factor),
            system_tokens=int(self.allocation.system_tokens * scale_factor),
        )

        return BudgetConfig(
            max_tokens=available_for_context,
            auto_derive=True,
            allocation=new_allocation,
            safety_margin=self.safety_margin,
            generation_max_tokens=self.generation_max_tokens,
            safe_threshold=self.safe_threshold,
            critical_threshold=self.critical_threshold,
        )


class BudgetConfigManager:
    """Manage budget configuration persistence

    Supports three-tier configuration:
    1. Global: ~/.agentos/config/budget.json
    2. Project: Stored in project settings (ProjectSettings.budget)
    3. Session: Stored in session metadata

    Priority: Session > Project > Global > Default
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize budget config manager

        Args:
            config_path: Custom config file path (default: ~/.agentos/config/budget.json)
        """
        if config_path:
            self.config_path = config_path
        else:
            # Default: ~/.agentos/config/budget.json
            home = Path.home()
            agentos_dir = home / ".agentos"
            config_dir = agentos_dir / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "budget.json"

    def load(self) -> BudgetConfig:
        """Load global budget configuration

        Returns:
            BudgetConfig instance (defaults if file doesn't exist)
        """
        if not self.config_path.exists():
            logger.info(f"Budget config not found at {self.config_path}, using defaults")
            # Create default config on first load
            default_config = BudgetConfig()
            self.save(default_config)
            return default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            config = BudgetConfig.from_dict(data)
            logger.info(f"Loaded budget config from {self.config_path}")
            return config

        except Exception as e:
            logger.warning(f"Failed to load budget config: {e}, using defaults")
            return BudgetConfig()

    def save(self, config: BudgetConfig) -> None:
        """Save budget configuration atomically

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            config: BudgetConfig to save
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file, then rename
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.config_path.parent,
                delete=False,
                suffix=".tmp"
            ) as tmp_file:
                json.dump(config.to_dict(), tmp_file, indent=2)
                tmp_path = Path(tmp_file.name)

            # Atomic rename (overwrites existing file)
            tmp_path.replace(self.config_path)
            logger.info(f"Saved budget config to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save budget config: {e}")
            # Clean up temp file if it exists
            if 'tmp_path' in locals() and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def update_max_tokens(self, max_tokens: int) -> None:
        """Update max_tokens and save

        Args:
            max_tokens: New maximum tokens value
        """
        config = self.load()
        config.max_tokens = max_tokens
        self.save(config)
        logger.info(f"Updated max_tokens to {max_tokens}")

    def update_allocation(
        self,
        window_tokens: Optional[int] = None,
        rag_tokens: Optional[int] = None,
        memory_tokens: Optional[int] = None,
        summary_tokens: Optional[int] = None,
        system_tokens: Optional[int] = None,
    ) -> None:
        """Update allocation and save

        Args:
            window_tokens: Window tokens (None to keep current)
            rag_tokens: RAG tokens (None to keep current)
            memory_tokens: Memory tokens (None to keep current)
            summary_tokens: Summary tokens (None to keep current)
            system_tokens: System tokens (None to keep current)
        """
        config = self.load()

        if window_tokens is not None:
            config.allocation.window_tokens = window_tokens
        if rag_tokens is not None:
            config.allocation.rag_tokens = rag_tokens
        if memory_tokens is not None:
            config.allocation.memory_tokens = memory_tokens
        if summary_tokens is not None:
            config.allocation.summary_tokens = summary_tokens
        if system_tokens is not None:
            config.allocation.system_tokens = system_tokens

        self.save(config)
        logger.info("Updated budget allocation")

    def update_auto_derive(self, enabled: bool) -> None:
        """Update auto_derive flag

        Args:
            enabled: Whether to enable auto-derivation from model context window
        """
        config = self.load()
        config.auto_derive = enabled
        self.save(config)
        logger.info(f"Updated auto_derive to {enabled}")

    def resolve_config(
        self,
        session_budget: Optional[Dict[str, Any]] = None,
        project_budget: Optional[Dict[str, Any]] = None,
    ) -> BudgetConfig:
        """Resolve budget configuration with priority

        Priority: Session > Project > Global > Default

        Args:
            session_budget: Session-level budget config (from session metadata)
            project_budget: Project-level budget config (from ProjectSettings.budget)

        Returns:
            Resolved BudgetConfig
        """
        # Start with global config
        config = self.load()

        # Override with project config if present
        if project_budget:
            project_config = BudgetConfig.from_dict(project_budget)
            logger.debug("Applying project-level budget overrides")
            config = self._merge_configs(config, project_config)

        # Override with session config if present
        if session_budget:
            session_config = BudgetConfig.from_dict(session_budget)
            logger.debug("Applying session-level budget overrides")
            config = self._merge_configs(config, session_config)

        logger.info(f"Resolved budget config: max_tokens={config.max_tokens}, auto_derive={config.auto_derive}")
        return config

    def _merge_configs(self, base: BudgetConfig, override: BudgetConfig) -> BudgetConfig:
        """Merge two configs (override takes precedence for non-default values)

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged BudgetConfig
        """
        # For simplicity, override completely replaces base
        # In a more sophisticated implementation, you could merge field by field
        return override


# Global instance
_budget_config_manager: Optional[BudgetConfigManager] = None


def get_budget_config_manager() -> BudgetConfigManager:
    """Get global budget config manager"""
    global _budget_config_manager
    if _budget_config_manager is None:
        _budget_config_manager = BudgetConfigManager()
    return _budget_config_manager


def load_budget_config() -> BudgetConfig:
    """Load global budget configuration (convenience function)"""
    return get_budget_config_manager().load()


def save_budget_config(config: BudgetConfig) -> None:
    """Save global budget configuration (convenience function)"""
    get_budget_config_manager().save(config)
