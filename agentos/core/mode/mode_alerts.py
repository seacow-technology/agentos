"""
Mode Alert System - Aggregates and routes alerts for mode violations and operations.

This module provides a comprehensive alert system for the mode subsystem, supporting
multiple output channels (console, file, webhook) and severity levels.

Usage:
    from agentos.core.mode.mode_alerts import get_alert_aggregator, alert_mode_violation
from agentos.core.time import utc_now_iso


    # Quick violation alert
    alert_mode_violation(
        mode_id="autonomous_mode",
        operation="apply_diff",
        message="Diff application failed",
        context={"error": "permission denied"}
    )

    # Custom severity
    aggregator = get_alert_aggregator()
    aggregator.alert(
        severity=AlertSeverity.WARNING,
        mode_id="manual_mode",
        operation="commit",
        message="Commit took longer than expected",
        context={"duration_seconds": 45}
    )
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AlertSeverity(str, Enum):
    """Alert severity levels for mode operations."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ModeAlert:
    """Represents a single alert from the mode subsystem."""
    timestamp: str  # ISO 8601 format
    severity: AlertSeverity
    mode_id: str
    operation: str  # "apply_diff", "commit", etc.
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert AlertSeverity enum to string
        result['severity'] = self.severity.value
        return result


class AlertOutput:
    """Base class for alert output destinations."""

    def send(self, alert: ModeAlert):
        """Send an alert to this output destination.

        Args:
            alert: The alert to send.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement send()")


class ConsoleAlertOutput(AlertOutput):
    """Output alerts to the console with color and emoji indicators."""

    # Emoji indicators for each severity level
    SEVERITY_EMOJI = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.ERROR: "❌",
        AlertSeverity.CRITICAL: "🚨",
    }

    # ANSI color codes for terminal output
    SEVERITY_COLOR = {
        AlertSeverity.INFO: "\033[36m",      # Cyan
        AlertSeverity.WARNING: "\033[33m",   # Yellow
        AlertSeverity.ERROR: "\033[31m",     # Red
        AlertSeverity.CRITICAL: "\033[35m",  # Magenta
    }

    RESET_COLOR = "\033[0m"

    def __init__(self, use_color: bool = True):
        """Initialize console output.

        Args:
            use_color: Whether to use ANSI color codes (default: True).
        """
        self.use_color = use_color and sys.stdout.isatty()

    def send(self, alert: ModeAlert):
        """Print alert to console with formatting.

        Args:
            alert: The alert to display.
        """
        emoji = self.SEVERITY_EMOJI.get(alert.severity, "📢")

        if self.use_color:
            color = self.SEVERITY_COLOR.get(alert.severity, "")
            reset = self.RESET_COLOR
        else:
            color = ""
            reset = ""

        # Format: [timestamp] 🚨 CRITICAL [mode_id] operation: message
        output = (
            f"{color}[{alert.timestamp}] {emoji} {alert.severity.value.upper()} "
            f"[{alert.mode_id}] {alert.operation}: {alert.message}{reset}"
        )

        print(output, file=sys.stderr)

        # Print context if present
        if alert.context:
            context_str = json.dumps(alert.context, indent=2)
            print(f"{color}  Context: {context_str}{reset}", file=sys.stderr)


class FileAlertOutput(AlertOutput):
    """Output alerts to a file in JSONL format (one JSON object per line)."""

    def __init__(self, file_path: Path):
        """Initialize file output.

        Args:
            file_path: Path to the alert log file.
        """
        self.file_path = Path(file_path)
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, alert: ModeAlert):
        """Append alert to file as JSONL.

        Args:
            alert: The alert to log.
        """
        try:
            with open(self.file_path, 'a', encoding='utf-8') as f:
                json_line = json.dumps(alert.to_dict())
                f.write(json_line + '\n')
                f.flush()  # Ensure immediate write
        except Exception as e:
            # Fallback to console if file write fails
            print(
                f"❌ Failed to write alert to {self.file_path}: {e}",
                file=sys.stderr
            )


class WebhookAlertOutput(AlertOutput):
    """Output alerts to a webhook endpoint.

    Note: This is a simplified implementation for demonstration.
    In production, replace the print statement with actual HTTP POST using requests.
    """

    def __init__(self, webhook_url: str):
        """Initialize webhook output.

        Args:
            webhook_url: The URL to POST alerts to.
        """
        self.webhook_url = webhook_url

    def send(self, alert: ModeAlert):
        """Send alert to webhook endpoint.

        Args:
            alert: The alert to send.
        """
        # Simplified implementation - prints webhook call
        payload = alert.to_dict()
        print(
            f"🌐 [Webhook] POST {self.webhook_url}",
            file=sys.stderr
        )
        print(f"  Payload: {json.dumps(payload, indent=2)}", file=sys.stderr)

        # Production implementation would be:
        # import requests
        # try:
        #     response = requests.post(
        #         self.webhook_url,
        #         json=payload,
        #         timeout=5
        #     )
        #     response.raise_for_status()
        # except requests.RequestException as e:
        #     print(f"❌ Webhook failed: {e}", file=sys.stderr)


class ModeAlertAggregator:
    """Aggregates and distributes mode alerts to multiple output channels."""

    def __init__(self):
        """Initialize the alert aggregator."""
        self.outputs: List[AlertOutput] = []
        self.alert_count = 0
        self.recent_alerts: List[ModeAlert] = []
        self.max_recent = 100  # Keep last 100 alerts in memory

        # Track severity counts
        self._severity_counts: Dict[AlertSeverity, int] = {
            severity: 0 for severity in AlertSeverity
        }

    def add_output(self, output: AlertOutput):
        """Add an output channel for alerts.

        Args:
            output: The alert output to add.
        """
        self.outputs.append(output)

    def alert(
        self,
        severity: AlertSeverity,
        mode_id: str,
        operation: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Send an alert to all configured outputs.

        Args:
            severity: The severity level of the alert.
            mode_id: The mode that generated the alert.
            operation: The operation being performed.
            message: Human-readable alert message.
            context: Additional context data (optional).
        """
        # Create alert with current timestamp
        timestamp = utc_now_iso()
        alert = ModeAlert(
            timestamp=timestamp,
            severity=severity,
            mode_id=mode_id,
            operation=operation,
            message=message,
            context=context or {}
        )

        # Update statistics
        self.alert_count += 1
        self._severity_counts[severity] += 1

        # Add to recent alerts (maintain max size)
        self.recent_alerts.append(alert)
        if len(self.recent_alerts) > self.max_recent:
            self.recent_alerts.pop(0)

        # Send to all outputs (with error isolation)
        for output in self.outputs:
            try:
                output.send(alert)
            except Exception as e:
                # Don't let one output's failure prevent others from receiving alerts
                print(
                    f"❌ Alert output {output.__class__.__name__} failed: {e}",
                    file=sys.stderr
                )

    def get_stats(self) -> dict:
        """Get statistics about alerts.

        Returns:
            Dictionary containing alert statistics.
        """
        return {
            "total_alerts": self.alert_count,
            "recent_count": len(self.recent_alerts),
            "severity_breakdown": {
                severity.value: count
                for severity, count in self._severity_counts.items()
            },
            "max_recent": self.max_recent,
            "output_count": len(self.outputs)
        }

    def get_recent_alerts(self, limit: Optional[int] = None) -> List[ModeAlert]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return (default: all recent).

        Returns:
            List of recent alerts.
        """
        if limit is None:
            return list(self.recent_alerts)
        return list(self.recent_alerts[-limit:])

    def clear_recent(self):
        """Clear the recent alerts buffer (does not affect total count)."""
        self.recent_alerts.clear()


# Global alert aggregator instance
_global_aggregator: Optional[ModeAlertAggregator] = None


def get_alert_aggregator() -> ModeAlertAggregator:
    """Get the global alert aggregator instance.

    Automatically initializes with console output on first call.

    Returns:
        The global ModeAlertAggregator instance.
    """
    global _global_aggregator
    if _global_aggregator is None:
        _global_aggregator = ModeAlertAggregator()
        # Default: add console output
        _global_aggregator.add_output(ConsoleAlertOutput())
    return _global_aggregator


def alert_mode_violation(
    mode_id: str,
    operation: str,
    message: str,
    context: Optional[Dict[str, Any]] = None
):
    """Quick helper to send a mode violation alert at ERROR level.

    Args:
        mode_id: The mode that detected the violation.
        operation: The operation that violated constraints.
        message: Description of the violation.
        context: Additional context data (optional).
    """
    aggregator = get_alert_aggregator()
    aggregator.alert(
        severity=AlertSeverity.ERROR,
        mode_id=mode_id,
        operation=operation,
        message=message,
        context=context
    )


def reset_global_aggregator():
    """Reset the global aggregator (useful for testing).

    Warning: This will lose all alert history and output configurations.
    """
    global _global_aggregator
    _global_aggregator = None


# Convenience exports
__all__ = [
    "AlertSeverity",
    "ModeAlert",
    "AlertOutput",
    "ConsoleAlertOutput",
    "FileAlertOutput",
    "WebhookAlertOutput",
    "ModeAlertAggregator",
    "get_alert_aggregator",
    "alert_mode_violation",
    "reset_global_aggregator",
]
