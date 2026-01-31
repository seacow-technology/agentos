#!/usr/bin/env python3
"""
Demo: Mode Alert System Usage

This example demonstrates how to use the Mode Alert System to monitor
and report mode violations and operations.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.mode.mode_alerts import (
    AlertSeverity,
    ConsoleAlertOutput,
    FileAlertOutput,
    WebhookAlertOutput,
    get_alert_aggregator,
    alert_mode_violation,
)


def demo_basic_usage():
    """Demo 1: Basic usage with quick helper."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Usage - Quick Violation Alert")
    print("="*70)

    # The simplest way to report a violation
    alert_mode_violation(
        mode_id="autonomous_mode",
        operation="apply_diff",
        message="Attempted to delete protected file",
        context={
            "file": "critical_config.py",
            "constraint": "no_delete_protected",
            "action": "blocked"
        }
    )

    print("\nℹ️  Alert sent to default console output")


def demo_custom_severity():
    """Demo 2: Custom severity levels."""
    print("\n" + "="*70)
    print("DEMO 2: Custom Severity Levels")
    print("="*70)

    aggregator = get_alert_aggregator()

    # INFO: Informational message
    aggregator.alert(
        severity=AlertSeverity.INFO,
        mode_id="manual_mode",
        operation="stage_files",
        message="Successfully staged 5 files",
        context={"files_count": 5}
    )

    # WARNING: Potential issue
    aggregator.alert(
        severity=AlertSeverity.WARNING,
        mode_id="autonomous_mode",
        operation="commit",
        message="Commit took longer than expected",
        context={"duration_seconds": 45, "threshold": 30}
    )

    # ERROR: Operation failed
    aggregator.alert(
        severity=AlertSeverity.ERROR,
        mode_id="autonomous_mode",
        operation="push",
        message="Push failed: remote rejected",
        context={"remote": "origin", "branch": "main", "error": "permission denied"}
    )

    # CRITICAL: System-level failure
    aggregator.alert(
        severity=AlertSeverity.CRITICAL,
        mode_id="system",
        operation="policy_check",
        message="Policy engine failed to load",
        context={"policy_file": "mode_policy.json", "error": "file not found"}
    )

    print("\nℹ️  Sent alerts at all severity levels")


def demo_multiple_outputs():
    """Demo 3: Configure multiple output channels."""
    print("\n" + "="*70)
    print("DEMO 3: Multiple Output Channels")
    print("="*70)

    # Get a fresh aggregator for this demo
    from agentos.core.mode.mode_alerts import reset_global_aggregator
    reset_global_aggregator()
    aggregator = get_alert_aggregator()

    # Add file output
    log_file = Path("/tmp/mode_alerts.jsonl")
    aggregator.add_output(FileAlertOutput(log_file))
    print(f"✅ Added file output: {log_file}")

    # Add webhook output
    aggregator.add_output(WebhookAlertOutput("https://monitoring.example.com/alerts"))
    print("✅ Added webhook output")

    # Send a test alert
    aggregator.alert(
        severity=AlertSeverity.ERROR,
        mode_id="demo_mode",
        operation="multi_output_test",
        message="This alert goes to console, file, and webhook",
        context={"demo": True, "outputs": 3}
    )

    print(f"\nℹ️  Alert sent to {len(aggregator.outputs)} outputs")

    # Show file contents
    if log_file.exists():
        print(f"\n📄 File contents ({log_file}):")
        with open(log_file, 'r') as f:
            print(f.read())


def demo_statistics():
    """Demo 4: View alert statistics."""
    print("\n" + "="*70)
    print("DEMO 4: Alert Statistics")
    print("="*70)

    aggregator = get_alert_aggregator()

    # Get current statistics
    stats = aggregator.get_stats()

    print("\n📊 Alert Statistics:")
    print(f"   Total alerts sent: {stats['total_alerts']}")
    print(f"   Recent alerts buffered: {stats['recent_count']}")
    print(f"   Max recent buffer size: {stats['max_recent']}")
    print(f"   Output channels: {stats['output_count']}")
    print(f"\n   Severity breakdown:")
    for severity, count in stats['severity_breakdown'].items():
        print(f"      {severity}: {count}")

    # Get recent alerts
    recent = aggregator.get_recent_alerts(limit=5)
    print(f"\n📋 Last {len(recent)} alerts:")
    for i, alert in enumerate(recent, 1):
        print(f"   {i}. [{alert.severity.value}] {alert.mode_id}/{alert.operation}: {alert.message}")


def demo_real_world_scenario():
    """Demo 5: Real-world scenario - Mode operation monitoring."""
    print("\n" + "="*70)
    print("DEMO 5: Real-World Scenario - Mode Operation Monitoring")
    print("="*70)

    aggregator = get_alert_aggregator()

    # Scenario: Autonomous mode performing a series of operations
    print("\n🤖 Autonomous mode starting operations...")

    # 1. Start operation
    aggregator.alert(
        severity=AlertSeverity.INFO,
        mode_id="autonomous_mode",
        operation="start",
        message="Autonomous mode activated",
        context={"user": "alice", "session_id": "abc123"}
    )

    # 2. Policy check passes
    aggregator.alert(
        severity=AlertSeverity.INFO,
        mode_id="autonomous_mode",
        operation="policy_check",
        message="Policy constraints validated",
        context={"constraints_checked": 5, "all_passed": True}
    )

    # 3. Warning during diff application
    aggregator.alert(
        severity=AlertSeverity.WARNING,
        mode_id="autonomous_mode",
        operation="apply_diff",
        message="Large diff detected, may need review",
        context={"lines_changed": 250, "threshold": 200}
    )

    # 4. Constraint violation detected
    alert_mode_violation(
        mode_id="autonomous_mode",
        operation="apply_diff",
        message="Attempted modification of protected directory",
        context={
            "path": "/etc/system",
            "constraint": "no_modify_system_dirs",
            "action": "blocked"
        }
    )

    # 5. Recovery action
    aggregator.alert(
        severity=AlertSeverity.INFO,
        mode_id="autonomous_mode",
        operation="recovery",
        message="Reverted unsafe changes",
        context={"files_reverted": 3, "status": "safe"}
    )

    # 6. Operation completed
    aggregator.alert(
        severity=AlertSeverity.INFO,
        mode_id="autonomous_mode",
        operation="complete",
        message="Autonomous operation completed successfully",
        context={
            "duration_seconds": 12,
            "files_modified": 7,
            "violations": 1,
            "actions_blocked": 1
        }
    )

    print("\n✅ Operation sequence complete")

    # Show final statistics
    stats = aggregator.get_stats()
    print(f"\n📊 Session statistics:")
    print(f"   Total alerts: {stats['total_alerts']}")
    print(f"   Errors: {stats['severity_breakdown']['error']}")
    print(f"   Warnings: {stats['severity_breakdown']['warning']}")


def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("MODE ALERT SYSTEM - USAGE DEMONSTRATIONS")
    print("="*70)
    print("\nThis demo shows how to use the Mode Alert System to monitor")
    print("mode operations and report violations.")

    demo_basic_usage()
    demo_custom_severity()
    demo_multiple_outputs()
    demo_statistics()
    demo_real_world_scenario()

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nFor more information, see:")
    print("  - agentos/core/mode/mode_alerts.py")
    print("  - agentos/core/mode/README_POLICY.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
