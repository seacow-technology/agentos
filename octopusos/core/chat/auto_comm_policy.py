"""AutoCommPolicy - Automatic communication policy for safe external info execution

This module implements a conservative white-list based policy for automatically
executing communication commands (like web search) without user interaction.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class AutoCommDecision:
    """Decision result from AutoCommPolicy"""
    allowed: bool
    reason: str
    suggested_action: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and serialization"""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class AutoCommPolicy:
    """Policy for automatic communication execution

    This implements a conservative white-list approach:
    - Only allows specific, safe query types (weather, traffic, etc.)
    - Extracts and validates query parameters
    - Returns decision with reasoning for fallback handling
    """

    # White-listed query patterns (conservative list)
    WEATHER_KEYWORDS = {
        'weather', '天气', 'forecast', '预报', 'temperature', '温度',
        'rain', '下雨', 'rain', '雨', 'sunny', '晴天', 'cloudy', '阴天'
    }

    CITY_KEYWORDS = {
        'beijing', '北京', 'shanghai', '上海', 'shenzhen', '深圳',
        'guangzhou', '广州', 'hangzhou', '杭州', 'chengdu', '成都',
        'chongqing', '重庆', 'wuhan', '武汉', 'xian', '西安', 'nanjing', '南京',
        'tokyo', '东京', 'new york', 'new', 'york', 'london', '伦敦',
        'paris', '巴黎', 'sydney', '悉尼', 'dubai', '迪拜'
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize AutoCommPolicy

        Args:
            config: Configuration dict with policy settings
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.max_query_length = self.config.get('max_query_length', 100)
        self.allowed_actions = self.config.get(
            'allowed_actions',
            ['weather_search']  # Only weather for now
        )

        logger.info(
            f"AutoCommPolicy initialized: "
            f"enabled={self.enabled}, "
            f"allowed_actions={self.allowed_actions}"
        )

    def decide(self, message: str, classification: Any) -> AutoCommDecision:
        """Make decision on whether to auto-execute communication

        Args:
            message: User's message
            classification: Classification result from InfoNeedClassifier

        Returns:
            AutoCommDecision with allow/deny decision and reasoning
        """
        try:
            # Check if policy is enabled
            if not self.enabled:
                return AutoCommDecision(
                    allowed=False,
                    reason="Auto-comm policy is disabled",
                    confidence=1.0
                )

            # Only allow REQUIRE_COMM classification
            from agentos.core.chat.models.info_need import DecisionAction
            if classification.decision_action != DecisionAction.REQUIRE_COMM:
                return AutoCommDecision(
                    allowed=False,
                    reason="Classification is not REQUIRE_COMM",
                    confidence=1.0
                )

            # Check if it's a weather query (white-list)
            if self._is_weather_query(message):
                query = self._extract_weather_query(message)
                if query:
                    return AutoCommDecision(
                        allowed=True,
                        reason="Weather query matches white-list",
                        suggested_action=f"weather_search:{query}",
                        confidence=0.95,
                        metadata={
                            "query_type": "weather",
                            "extracted_query": query,
                            "message": message
                        }
                    )

            # Default deny - not in white-list
            return AutoCommDecision(
                allowed=False,
                reason="Query does not match white-listed patterns",
                confidence=0.9
            )

        except Exception as e:
            logger.error(f"Error in AutoCommPolicy.decide: {e}", exc_info=True)
            return AutoCommDecision(
                allowed=False,
                reason=f"Policy evaluation error: {str(e)}",
                confidence=0.0
            )

    def _is_weather_query(self, message: str) -> bool:
        """Check if message is a weather query

        Args:
            message: User's message

        Returns:
            True if this looks like a weather query
        """
        msg_lower = message.lower()

        # Check for weather keywords
        has_weather_keyword = any(
            keyword in msg_lower
            for keyword in self.WEATHER_KEYWORDS
        )

        # Check for city keywords or location patterns
        has_location = any(
            city in msg_lower
            for city in self.CITY_KEYWORDS
        )

        # Weather query needs both weather and location keywords
        return has_weather_keyword and has_location

    def _extract_weather_query(self, message: str) -> Optional[str]:
        """Extract weather query parameters

        Args:
            message: User's message

        Returns:
            Extracted query string or None
        """
        try:
            # Extract city name (conservative extraction)
            city = None
            msg_lower = message.lower()

            for city_name in self.CITY_KEYWORDS:
                if city_name in msg_lower:
                    # Use the city name as primary identifier
                    city = city_name
                    break

            if not city:
                return None

            # Build query string
            query = f"weather {city}"

            # Check length
            if len(query) > self.max_query_length:
                logger.warning(f"Query too long: {len(query)} > {self.max_query_length}")
                return None

            logger.info(f"Extracted weather query: {query}")
            return query

        except Exception as e:
            logger.error(f"Error extracting weather query: {e}")
            return None
