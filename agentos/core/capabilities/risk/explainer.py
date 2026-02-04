"""
Risk Explainer

Generates human-readable explanations for risk scores.
Every score must be explainable and traceable to source data.
"""

from typing import Dict
from .models import RiskScore, DimensionResult


class RiskExplainer:
    """
    Generates human-readable risk score explanations.

    Provides clear, actionable explanations that help users understand:
    - Why a risk score is high/medium/low
    - Which dimensions contribute most
    - What the evidence is for each dimension
    """

    # Dimension metadata
    DIMENSION_INFO = {
        "write_ratio": {
            "name": "Write Operations",
            "weight": 0.30,
            "description": "Proportion of executions involving write operations"
        },
        "external_call": {
            "name": "External Calls",
            "weight": 0.25,
            "description": "Presence of network/API calls"
        },
        "failure_rate": {
            "name": "Failure Rate",
            "weight": 0.25,
            "description": "Historical execution failure rate"
        },
        "revoke_count": {
            "name": "Revocations",
            "weight": 0.15,
            "description": "Number of times authorization was revoked"
        },
        "duration_anomaly": {
            "name": "Duration Anomaly",
            "weight": 0.05,
            "description": "Execution time deviation from baseline"
        }
    }

    @staticmethod
    def explain(risk_score: RiskScore, dimension_details: Dict[str, str]) -> str:
        """
        Generate comprehensive risk score explanation.

        Args:
            risk_score: RiskScore object with all dimensions
            dimension_details: Dict mapping dimension names to detail strings

        Returns:
            Multi-line human-readable explanation
        """
        lines = []

        # Overall score and level
        level = risk_score.get_level()
        lines.append(f"Risk Score: {risk_score.score:.1f}/100 ({level})")
        lines.append("")

        # Add context
        lines.append(f"Based on {risk_score.sample_size} execution(s) in the last {risk_score.window_days} days")
        lines.append("")

        # Dimension breakdown
        lines.append("Risk Factors:")

        # Sort dimensions by contribution (value * weight)
        sorted_dims = sorted(
            risk_score.dimensions.items(),
            key=lambda x: x[1] * RiskExplainer.DIMENSION_INFO.get(x[0], {}).get("weight", 0),
            reverse=True
        )

        for dim_name, dim_value in sorted_dims:
            info = RiskExplainer.DIMENSION_INFO.get(dim_name, {})
            weight = info.get("weight", 0)
            display_name = info.get("name", dim_name)

            # Calculate impact level
            impact = RiskExplainer._get_impact_level(dim_value)

            # Get details if available
            details = dimension_details.get(dim_name, "")

            # Format dimension line
            contribution = dim_value * weight * 100
            lines.append(
                f"  - {display_name}: {dim_value*100:.1f}% "
                f"(weight: {weight*100:.0f}%, contribution: {contribution:.1f}) "
                f"[{impact}]"
            )
            if details:
                lines.append(f"    {details}")

        lines.append("")

        # Add interpretation
        lines.append(RiskExplainer._interpret_level(level))

        return "\n".join(lines)

    @staticmethod
    def _get_impact_level(value: float) -> str:
        """
        Determine impact level from normalized value.

        Args:
            value: Normalized dimension value (0-1)

        Returns:
            Impact level string
        """
        if value < 0.3:
            return "LOW"
        elif value < 0.7:
            return "MEDIUM"
        else:
            return "HIGH"

    @staticmethod
    def _interpret_level(level: str) -> str:
        """
        Provide interpretation guidance for risk level.

        Args:
            level: Risk level ("LOW", "MEDIUM", "HIGH")

        Returns:
            Interpretation text
        """
        interpretations = {
            "LOW": (
                "Interpretation: This extension has a low risk profile based on historical data. "
                "It shows stable execution patterns with minimal write operations and few failures."
            ),
            "MEDIUM": (
                "Interpretation: This extension has a moderate risk profile. "
                "Review the key risk factors above and consider if additional monitoring or "
                "restrictions are needed based on your security requirements."
            ),
            "HIGH": (
                "Interpretation: This extension has a high risk profile based on historical behavior. "
                "Consider additional safeguards such as stricter authorization controls, "
                "sandbox isolation, or manual approval for critical operations."
            )
        }
        return interpretations.get(level, "Interpretation: Risk level assessment available.")

    @staticmethod
    def explain_compact(risk_score: RiskScore) -> str:
        """
        Generate compact single-line explanation.

        Args:
            risk_score: RiskScore object

        Returns:
            One-line summary
        """
        level = risk_score.get_level()
        top_risks = []

        # Find top 2 contributing dimensions
        sorted_dims = sorted(
            risk_score.dimensions.items(),
            key=lambda x: x[1] * RiskExplainer.DIMENSION_INFO.get(x[0], {}).get("weight", 0),
            reverse=True
        )

        for dim_name, dim_value in sorted_dims[:2]:
            if dim_value > 0.3:  # Only mention if significant
                info = RiskExplainer.DIMENSION_INFO.get(dim_name, {})
                display_name = info.get("name", dim_name)
                top_risks.append(f"{display_name}: {dim_value*100:.0f}%")

        if top_risks:
            risk_summary = ", ".join(top_risks)
            return f"Risk: {risk_score.score:.1f}/100 ({level}) - Key factors: {risk_summary}"
        else:
            return f"Risk: {risk_score.score:.1f}/100 ({level}) - Based on {risk_score.sample_size} execution(s)"
