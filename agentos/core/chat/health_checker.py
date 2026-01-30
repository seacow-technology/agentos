"""
Chat-specific lightweight health checker

This module provides lightweight health checking specifically for Chat functionality.
Unlike SelfCheckRunner which performs comprehensive system diagnostics, ChatHealthChecker
focuses only on the minimum requirements for Chat to function:
  1. At least one provider is available (cached status only - no network calls)
  2. Storage is writable

Design principles:
- FAST: Uses only cached status, no network probes
- LIGHTWEIGHT: Checks only Chat's minimum requirements
- NON-BLOCKING: All checks are quick local operations
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agentos.providers.base import ProviderState
from agentos.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class ChatHealthStatus:
    """
    Health status for Chat functionality

    Attributes:
        is_healthy: Overall health - True if Chat can function
        provider_available: At least one provider is ready
        provider_name: Name of an available provider (if any)
        storage_ok: Storage directory is writable
        issues: List of problems preventing Chat from working
        hints: List of user-friendly suggestions to resolve issues
    """
    is_healthy: bool
    provider_available: bool
    provider_name: Optional[str] = None
    storage_ok: bool = True
    issues: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)


class ChatHealthChecker:
    """
    Lightweight health checker for Chat functionality

    This checker performs fast, cache-only checks to verify Chat's minimum requirements:
    - At least one model provider is available (using cached status only)
    - Storage directory is writable

    IMPORTANT: This does NOT trigger network calls. It only reads cached provider status.
    """

    def __init__(self):
        """Initialize health checker with ProviderRegistry instance"""
        self.registry = ProviderRegistry.get_instance()

    async def check(self) -> ChatHealthStatus:
        """
        Check Chat's minimum operational requirements

        This is a fast, lightweight check that:
        1. Reads cached provider status (NO network calls)
        2. Verifies storage is writable

        Returns:
            ChatHealthStatus: Health status with issues and hints if any
        """
        issues = []
        hints = []

        # Check provider availability (cache-only)
        provider_available = False
        provider_name = None

        try:
            # Iterate through all registered providers
            for provider in self.registry.list_all():
                # CRITICAL: Only read cached status - DO NOT call probe()
                # Use get_cached_status() which returns _last_status without network calls
                cached_status = provider.get_cached_status()

                if cached_status is None:
                    # No cached status yet - provider hasn't been probed
                    logger.debug(f"Provider {provider.id} has no cached status")
                    continue

                # Check if this provider is READY (healthy and available)
                if cached_status.state == ProviderState.READY:
                    provider_available = True
                    provider_name = provider.id
                    logger.debug(f"Found available provider: {provider.id}")
                    break  # Found at least one, we're good
        except Exception as e:
            logger.error(f"Error checking provider status: {e}", exc_info=True)
            issues.append(f"Failed to check providers: {str(e)}")

        # If no provider available, add helpful hints
        if not provider_available:
            issues.append("No model provider is currently available")
            hints.append("Please start Ollama or configure a cloud service in Settings")
            hints.append("Run 'ollama serve' to start Ollama, or add API keys in Cloud Config")

        # Check storage
        storage_ok = await self._check_storage()
        if not storage_ok:
            issues.append("Storage directory is not writable")
            hints.append("Check permissions on ~/.agentos/runtime directory")

        # Overall health: need provider + storage
        is_healthy = provider_available and storage_ok

        return ChatHealthStatus(
            is_healthy=is_healthy,
            provider_available=provider_available,
            provider_name=provider_name,
            storage_ok=storage_ok,
            issues=issues,
            hints=hints,
        )

    async def _check_storage(self) -> bool:
        """
        Lightweight storage check

        Verifies that the runtime directory exists and is writable.
        This is a quick local filesystem check.

        Returns:
            bool: True if storage is accessible and writable
        """
        try:
            # Check runtime directory
            runtime_dir = Path.home() / ".agentos" / "runtime"

            # Ensure directory exists
            if not runtime_dir.exists():
                logger.warning(f"Runtime directory does not exist: {runtime_dir}")
                try:
                    runtime_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created runtime directory: {runtime_dir}")
                except Exception as e:
                    logger.error(f"Failed to create runtime directory: {e}")
                    return False

            # Test write permission with a temporary file
            test_file = runtime_dir / ".health_check_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True
            except Exception as e:
                logger.error(f"Cannot write to runtime directory: {e}")
                return False

        except Exception as e:
            logger.error(f"Storage check failed: {e}", exc_info=True)
            return False
