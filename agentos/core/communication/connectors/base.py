"""Base connector interface for external communications.

This module defines the base interface that all communication
connectors must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Base class for all communication connectors.

    All connectors must inherit from this class and implement
    the required methods.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize connector.

        Args:
            config: Connector configuration
        """
        self.config = config or {}
        self.enabled = True
        self.name = self.__class__.__name__

    @abstractmethod
    async def execute(self, operation: str, params: Dict[str, Any]) -> Any:
        """Execute a connector operation.

        Args:
            operation: Operation to perform
            params: Operation parameters

        Returns:
            Operation result

        Raises:
            NotImplementedError: If operation is not supported
            Exception: If operation fails
        """
        raise NotImplementedError("Connector must implement execute method")

    @abstractmethod
    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations.

        Returns:
            List of operation names
        """
        raise NotImplementedError("Connector must implement get_supported_operations")

    def validate_config(self) -> bool:
        """Validate connector configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        return True

    def get_config(self) -> Dict[str, Any]:
        """Get connector configuration.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def set_config(self, config: Dict[str, Any]) -> None:
        """Set connector configuration.

        Args:
            config: Configuration dictionary
        """
        self.config.update(config)

    def enable(self) -> None:
        """Enable the connector."""
        self.enabled = True
        logger.info(f"Enabled connector: {self.name}")

    def disable(self) -> None:
        """Disable the connector."""
        self.enabled = False
        logger.info(f"Disabled connector: {self.name}")

    def is_enabled(self) -> bool:
        """Check if connector is enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        """Get connector status.

        Returns:
            Status dictionary
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "supported_operations": self.get_supported_operations(),
            "config_valid": self.validate_config(),
        }

    async def health_check(self) -> bool:
        """Perform health check.

        Returns:
            True if healthy, False otherwise
        """
        return self.enabled and self.validate_config()

    def __repr__(self) -> str:
        """String representation of connector."""
        return f"<{self.name} enabled={self.enabled}>"
