"""
Guardian Registry

Central registry for managing Guardian instances.
"""

import logging
from typing import Dict, List

from .base import Guardian

logger = logging.getLogger(__name__)


class GuardianRegistry:
    """
    Guardian Registry

    Manages registration and retrieval of Guardian instances.
    Thread-safe for read operations (no writes after initialization in typical usage).
    """

    def __init__(self):
        self._guardians: Dict[str, Guardian] = {}
        logger.info("GuardianRegistry initialized")

        # Auto-register built-in guardians
        self._register_builtin_guardians()

    def _register_builtin_guardians(self):
        """Register built-in Guardian implementations"""
        from .smoke_test_guardian import SmokeTestGuardian
        from .mode_guardian import ModeGuardian

        try:
            self.register(SmokeTestGuardian())
            logger.info("Registered built-in guardian: smoke_test")
        except Exception as e:
            logger.error(f"Failed to register SmokeTestGuardian: {e}")

        try:
            self.register(ModeGuardian())
            logger.info("Registered built-in guardian: mode_guardian")
        except Exception as e:
            logger.error(f"Failed to register ModeGuardian: {e}")

    def register(self, guardian: Guardian) -> None:
        """
        Register a Guardian

        Args:
            guardian: Guardian instance to register

        Raises:
            ValueError: If guardian.code is empty or already registered
        """
        if not guardian.code:
            raise ValueError("Guardian must have a non-empty code")

        if guardian.code in self._guardians:
            logger.warning(f"Guardian '{guardian.code}' is already registered, overwriting")

        self._guardians[guardian.code] = guardian
        logger.info(f"Registered Guardian: {guardian.code}")

    def get(self, code: str) -> Guardian:
        """
        Get a Guardian by code

        Args:
            code: Guardian code

        Returns:
            Guardian instance

        Raises:
            ValueError: If Guardian is not found
        """
        if code not in self._guardians:
            raise ValueError(f"Guardian not found: {code}")

        return self._guardians[code]

    def has(self, code: str) -> bool:
        """
        Check if a Guardian is registered

        Args:
            code: Guardian code

        Returns:
            True if Guardian is registered, False otherwise
        """
        return code in self._guardians

    def list_codes(self) -> List[str]:
        """
        Get all registered Guardian codes

        Returns:
            List of Guardian codes
        """
        return list(self._guardians.keys())

    def unregister(self, code: str) -> None:
        """
        Unregister a Guardian

        Args:
            code: Guardian code to unregister

        Raises:
            ValueError: If Guardian is not found
        """
        if code not in self._guardians:
            raise ValueError(f"Guardian not found: {code}")

        del self._guardians[code]
        logger.info(f"Unregistered Guardian: {code}")
