"""
Risk Score Data Models

Defines the data structures for risk scores and their components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class RiskScore:
    """
    Risk score result with dimensions and explanation.

    Attributes:
        score: Risk score value (0-100)
        dimensions: Individual dimension scores
        explanation: Human-readable explanation
        calculated_at: Timestamp of calculation
        window_days: Historical window used
        sample_size: Number of executions analyzed
    """
    score: float
    dimensions: Dict[str, float]
    explanation: str
    calculated_at: datetime
    window_days: int
    sample_size: int

    def to_dict(self) -> Dict:
        """
        Convert risk score to API-friendly dictionary.

        Returns:
            Dictionary with score, level, dimensions, and metadata
        """
        return {
            "score": round(self.score, 2),
            "level": self.get_level(),
            "dimensions": {
                key: round(value, 4) for key, value in self.dimensions.items()
            },
            "explanation": self.explanation,
            "meta": {
                "calculated_at": int(self.calculated_at.timestamp() * 1000),
                "window_days": self.window_days,
                "sample_size": self.sample_size
            }
        }

    def get_level(self) -> str:
        """
        Get risk level category based on score.

        Returns:
            Risk level: "LOW", "MEDIUM", or "HIGH"
        """
        if self.score < 30:
            return "LOW"
        elif self.score < 70:
            return "MEDIUM"
        else:
            return "HIGH"


@dataclass
class DimensionResult:
    """
    Result of a single risk dimension calculation.

    Attributes:
        name: Dimension identifier
        value: Normalized value (0-1)
        weight: Weight in final score
        impact: Impact level description
        details: Additional dimension-specific details
    """
    name: str
    value: float
    weight: float
    impact: str  # "LOW", "MEDIUM", "HIGH"
    details: Optional[str] = None

    def get_impact_level(self) -> str:
        """
        Determine impact level based on normalized value.

        Returns:
            Impact level: "LOW", "MEDIUM", or "HIGH"
        """
        if self.value < 0.3:
            return "LOW"
        elif self.value < 0.7:
            return "MEDIUM"
        else:
            return "HIGH"
