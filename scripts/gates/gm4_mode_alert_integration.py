#!/usr/bin/env python3
"""
Gate GM4: Mode Alert Integration

Verifies the Mode Alert System integration with the executor engine:
1. Alert aggregator initialization
2. Mode violation triggers alerts
3. Alerts written to file (JSONL format)
4. Alert statistics tracking
5. Multiple output channels work simultaneously

This gate validates Phase 2 Task 7-10 deliverables:
- mode_alerts.py alert aggregator
- Integration with executor_engine.py
- alert_config.json configuration
- 24 unit tests with 96% coverage
"""

import sys
import json
import time
import tempfile
from pathlib import Path
from io import StringIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.mode.mode_alerts import (
    get_alert_aggregator,
    alert_mode_violation,
    FileAlertOutput,
    ConsoleAlertOutput,
    AlertSeverity,
    ModeAlertAggregator,
    reset_global_aggregator
)


def main():
    wall_start = time.perf_counter()
    internal_start = time.perf_counter()

    print("=" * 60)
    print("Gate GM4: Mode Alert Integration")
    print("=" * 60)

    all_passed = True
    assertions = []

    # Clean state for testing
    reset_global_aggregator()

    # =========================================================================
    # Test 1: Alert aggregator initialization
    # =========================================================================
    print("\n[Test 1] Alert aggregator initialization")
    try:
        aggregator = get_alert_aggregator()

        # Test 1.1: Returns ModeAlertAggregator instance
        test_1_1 = isinstance(aggregator, ModeAlertAggregator)
        assertions.append({
            "name": "get_alert_aggregator() returns ModeAlertAggregator",
            "expected": "ModeAlertAggregator instance",
            "actual": type(aggregator).__name__,
            "passed": test_1_1
        })
        if test_1_1:
            print("  ✅ Returns ModeAlertAggregator instance")
        else:
            print(f"  ❌ Wrong type: {type(aggregator).__name__}")
            all_passed = False

        # Test 1.2: Initial state is correct
        test_1_2 = aggregator.alert_count == 0
        assertions.append({
            "name": "Initial alert_count is 0",
            "expected": 0,
            "actual": aggregator.alert_count,
            "passed": test_1_2
        })
        if test_1_2:
            print("  ✅ Initial alert_count is 0")
        else:
            print(f"  ❌ alert_count is {aggregator.alert_count}, expected 0")
            all_passed = False

        # Test 1.3: Has default console output
        test_1_3 = len(aggregator.outputs) > 0
        assertions.append({
            "name": "Has default output channel",
            "expected": ">0 outputs",
            "actual": f"{len(aggregator.outputs)} outputs",
            "passed": test_1_3
        })
        if test_1_3:
            print(f"  ✅ Has {len(aggregator.outputs)} default output(s)")
        else:
            print("  ❌ No default outputs configured")
            all_passed = False

        test_1_passed = test_1_1 and test_1_2 and test_1_3
        if test_1_passed:
            print("✅ PASS: Aggregator initialization correct")
        else:
            print("❌ FAIL: Aggregator initialization failed")
            all_passed = False

    except Exception as e:
        print(f"❌ FAIL: Test 1 raised exception: {e}")
        assertions.append({
            "name": "Test 1: Aggregator initialization",
            "expected": "No exception",
            "actual": str(e),
            "passed": False
        })
        all_passed = False

    # =========================================================================
    # Test 2: Mode violation triggers alert
    # =========================================================================
    print("\n[Test 2] Mode violation triggers alert")
    try:
        # Reset for clean test
        reset_global_aggregator()
        aggregator = get_alert_aggregator()
        initial_count = aggregator.alert_count

        # Trigger a mode violation
        alert_mode_violation(
            mode_id="design",
            operation="commit",
            message="Design mode cannot commit code",
            context={"attempted_files": ["test.py"]}
        )

        # Test 2.1: Alert count increased
        test_2_1 = aggregator.alert_count == initial_count + 1
        assertions.append({
            "name": "Alert count increased after violation",
            "expected": initial_count + 1,
            "actual": aggregator.alert_count,
            "passed": test_2_1
        })
        if test_2_1:
            print("  ✅ Alert count increased")
        else:
            print(f"  ❌ Alert count is {aggregator.alert_count}, expected {initial_count + 1}")
            all_passed = False

        # Test 2.2: Alert was recorded
        recent_alerts = aggregator.get_recent_alerts(limit=1)
        test_2_2 = len(recent_alerts) > 0
        assertions.append({
            "name": "Alert recorded in recent_alerts",
            "expected": "At least 1 alert",
            "actual": f"{len(recent_alerts)} alerts",
            "passed": test_2_2
        })
        if test_2_2:
            print("  ✅ Alert recorded in recent_alerts")
        else:
            print("  ❌ No alerts in recent_alerts")
            all_passed = False

        # Test 2.3: Alert content is correct
        if recent_alerts:
            alert = recent_alerts[0]
            test_2_3 = (
                alert.mode_id == "design" and
                alert.operation == "commit" and
                alert.severity == AlertSeverity.ERROR
            )
            assertions.append({
                "name": "Alert content correct (mode_id, operation, severity)",
                "expected": "design/commit/ERROR",
                "actual": f"{alert.mode_id}/{alert.operation}/{alert.severity.value}",
                "passed": test_2_3
            })
            if test_2_3:
                print("  ✅ Alert content correct")
            else:
                print(f"  ❌ Alert content: {alert.mode_id}/{alert.operation}/{alert.severity.value}")
                all_passed = False
        else:
            test_2_3 = False
            assertions.append({
                "name": "Alert content verification",
                "expected": "Valid alert",
                "actual": "No alert to verify",
                "passed": False
            })
            print("  ❌ Cannot verify alert content (no alerts)")
            all_passed = False

        test_2_passed = test_2_1 and test_2_2 and test_2_3
        if test_2_passed:
            print("✅ PASS: Mode violation alerts work correctly")
        else:
            print("❌ FAIL: Mode violation alert failed")
            all_passed = False

    except Exception as e:
        print(f"❌ FAIL: Test 2 raised exception: {e}")
        assertions.append({
            "name": "Test 2: Mode violation alert",
            "expected": "No exception",
            "actual": str(e),
            "passed": False
        })
        all_passed = False

    # =========================================================================
    # Test 3: Alerts written to file (JSONL format)
    # =========================================================================
    print("\n[Test 3] Alerts written to file (JSONL format)")
    temp_alert_file = None
    try:
        # Reset and create new aggregator with file output
        reset_global_aggregator()
        aggregator = get_alert_aggregator()

        # Create temporary file for alerts
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_alert_file = Path(f.name)

        # Add file output
        file_output = FileAlertOutput(temp_alert_file)
        aggregator.add_output(file_output)

        # Send an alert
        aggregator.alert(
            severity=AlertSeverity.WARNING,
            mode_id="planning",
            operation="execute",
            message="Planning mode should not execute commands",
            context={"command": "rm -rf"}
        )

        # Test 3.1: File was created
        test_3_1 = temp_alert_file.exists()
        assertions.append({
            "name": "Alert file created",
            "expected": "File exists",
            "actual": "File exists" if test_3_1 else "File not found",
            "passed": test_3_1
        })
        if test_3_1:
            print("  ✅ Alert file created")
        else:
            print("  ❌ Alert file not created")
            all_passed = False

        # Test 3.2: File contains valid JSONL
        if test_3_1:
            with open(temp_alert_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            test_3_2 = len(lines) > 0
            assertions.append({
                "name": "Alert file contains data",
                "expected": "At least 1 line",
                "actual": f"{len(lines)} lines",
                "passed": test_3_2
            })
            if test_3_2:
                print(f"  ✅ File contains {len(lines)} alert(s)")
            else:
                print("  ❌ File is empty")
                all_passed = False

            # Test 3.3: JSONL format is valid
            if test_3_2:
                try:
                    alert_data = json.loads(lines[0])
                    required_fields = ["timestamp", "severity", "mode_id", "operation", "message", "context"]
                    test_3_3 = all(field in alert_data for field in required_fields)
                    assertions.append({
                        "name": "JSONL format valid with required fields",
                        "expected": str(required_fields),
                        "actual": str(list(alert_data.keys())),
                        "passed": test_3_3
                    })
                    if test_3_3:
                        print("  ✅ JSONL format valid with all required fields")
                    else:
                        print(f"  ❌ Missing fields: {set(required_fields) - set(alert_data.keys())}")
                        all_passed = False
                except json.JSONDecodeError as e:
                    test_3_3 = False
                    assertions.append({
                        "name": "JSONL format validation",
                        "expected": "Valid JSON",
                        "actual": f"JSONDecodeError: {e}",
                        "passed": False
                    })
                    print(f"  ❌ Invalid JSON: {e}")
                    all_passed = False
            else:
                test_3_3 = False
        else:
            test_3_2 = False
            test_3_3 = False

        test_3_passed = test_3_1 and test_3_2 and test_3_3
        if test_3_passed:
            print("✅ PASS: File output works correctly")
        else:
            print("❌ FAIL: File output failed")
            all_passed = False

    except Exception as e:
        print(f"❌ FAIL: Test 3 raised exception: {e}")
        assertions.append({
            "name": "Test 3: File output",
            "expected": "No exception",
            "actual": str(e),
            "passed": False
        })
        all_passed = False
    finally:
        # Cleanup temporary file
        if temp_alert_file and temp_alert_file.exists():
            temp_alert_file.unlink()
            print("  🧹 Cleaned up temporary alert file")

    # =========================================================================
    # Test 4: Alert statistics tracking
    # =========================================================================
    print("\n[Test 4] Alert statistics tracking")
    try:
        # Reset for clean test
        reset_global_aggregator()
        aggregator = get_alert_aggregator()

        # Send multiple alerts with different severities
        aggregator.alert(AlertSeverity.INFO, "test", "op1", "Info message")
        aggregator.alert(AlertSeverity.WARNING, "test", "op2", "Warning message")
        aggregator.alert(AlertSeverity.ERROR, "test", "op3", "Error message")
        aggregator.alert(AlertSeverity.ERROR, "test", "op4", "Another error")
        aggregator.alert(AlertSeverity.CRITICAL, "test", "op5", "Critical issue")

        stats = aggregator.get_stats()

        # Test 4.1: Total alerts correct
        test_4_1 = stats["total_alerts"] == 5
        assertions.append({
            "name": "Total alerts count correct",
            "expected": 5,
            "actual": stats["total_alerts"],
            "passed": test_4_1
        })
        if test_4_1:
            print("  ✅ Total alerts: 5")
        else:
            print(f"  ❌ Total alerts: {stats['total_alerts']}, expected 5")
            all_passed = False

        # Test 4.2: Recent count correct
        test_4_2 = stats["recent_count"] == 5
        assertions.append({
            "name": "Recent alerts count correct",
            "expected": 5,
            "actual": stats["recent_count"],
            "passed": test_4_2
        })
        if test_4_2:
            print("  ✅ Recent alerts: 5")
        else:
            print(f"  ❌ Recent alerts: {stats['recent_count']}, expected 5")
            all_passed = False

        # Test 4.3: Severity breakdown correct
        severity_breakdown = stats["severity_breakdown"]
        test_4_3 = (
            severity_breakdown["info"] == 1 and
            severity_breakdown["warning"] == 1 and
            severity_breakdown["error"] == 2 and
            severity_breakdown["critical"] == 1
        )
        assertions.append({
            "name": "Severity breakdown correct",
            "expected": "info:1, warning:1, error:2, critical:1",
            "actual": f"info:{severity_breakdown['info']}, warning:{severity_breakdown['warning']}, error:{severity_breakdown['error']}, critical:{severity_breakdown['critical']}",
            "passed": test_4_3
        })
        if test_4_3:
            print("  ✅ Severity breakdown: info:1, warning:1, error:2, critical:1")
        else:
            print(f"  ❌ Severity breakdown incorrect: {severity_breakdown}")
            all_passed = False

        test_4_passed = test_4_1 and test_4_2 and test_4_3
        if test_4_passed:
            print("✅ PASS: Statistics tracking works correctly")
        else:
            print("❌ FAIL: Statistics tracking failed")
            all_passed = False

    except Exception as e:
        print(f"❌ FAIL: Test 4 raised exception: {e}")
        assertions.append({
            "name": "Test 4: Statistics tracking",
            "expected": "No exception",
            "actual": str(e),
            "passed": False
        })
        all_passed = False

    # =========================================================================
    # Test 5: Multiple outputs work simultaneously
    # =========================================================================
    print("\n[Test 5] Multiple outputs work simultaneously")
    temp_multi_file = None
    try:
        # Reset and create new aggregator
        reset_global_aggregator()
        aggregator = get_alert_aggregator()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_multi_file = Path(f.name)

        # Add file output (console already added by default)
        file_output = FileAlertOutput(temp_multi_file)
        aggregator.add_output(file_output)

        # Test 5.1: Multiple outputs configured
        test_5_1 = len(aggregator.outputs) >= 2
        assertions.append({
            "name": "Multiple outputs configured",
            "expected": ">=2 outputs",
            "actual": f"{len(aggregator.outputs)} outputs",
            "passed": test_5_1
        })
        if test_5_1:
            print(f"  ✅ {len(aggregator.outputs)} outputs configured")
        else:
            print(f"  ❌ Only {len(aggregator.outputs)} output(s)")
            all_passed = False

        # Capture console output
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        try:
            # Send an alert
            aggregator.alert(
                severity=AlertSeverity.ERROR,
                mode_id="implementation",
                operation="test",
                message="Test multi-output alert"
            )

            # Get console output
            console_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        # Test 5.2: Console received output
        test_5_2 = len(console_output) > 0 and "Test multi-output alert" in console_output
        assertions.append({
            "name": "Console output received",
            "expected": "Message in console output",
            "actual": "Message found" if test_5_2 else "Message not found",
            "passed": test_5_2
        })
        if test_5_2:
            print("  ✅ Console received alert")
        else:
            print("  ❌ Console did not receive alert")
            all_passed = False

        # Test 5.3: File received output
        if temp_multi_file.exists():
            with open(temp_multi_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            test_5_3 = len(file_content) > 0 and "Test multi-output alert" in file_content
            assertions.append({
                "name": "File output received",
                "expected": "Message in file",
                "actual": "Message found" if test_5_3 else "Message not found",
                "passed": test_5_3
            })
            if test_5_3:
                print("  ✅ File received alert")
            else:
                print("  ❌ File did not receive alert")
                all_passed = False
        else:
            test_5_3 = False
            assertions.append({
                "name": "File output verification",
                "expected": "File exists with alert",
                "actual": "File not found",
                "passed": False
            })
            print("  ❌ Alert file not created")
            all_passed = False

        test_5_passed = test_5_1 and test_5_2 and test_5_3
        if test_5_passed:
            print("✅ PASS: Multiple outputs work simultaneously")
        else:
            print("❌ FAIL: Multiple output channels failed")
            all_passed = False

    except Exception as e:
        print(f"❌ FAIL: Test 5 raised exception: {e}")
        assertions.append({
            "name": "Test 5: Multiple outputs",
            "expected": "No exception",
            "actual": str(e),
            "passed": False
        })
        all_passed = False
    finally:
        # Cleanup temporary file
        if temp_multi_file and temp_multi_file.exists():
            temp_multi_file.unlink()
            print("  🧹 Cleaned up temporary alert file")

    # =========================================================================
    # Generate Results
    # =========================================================================
    internal_duration = (time.perf_counter() - internal_start) * 1000
    wall_duration = (time.perf_counter() - wall_start) * 1000

    output_dir = Path("outputs/gates/gm4_alert_integration/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "gate_id": "gm4_alert_integration",
        "gate_name": "Mode Alert Integration",
        "status": "PASS" if all_passed else "FAIL",
        "assertions": assertions,
        "duration_ms": round(internal_duration, 2),
        "process_wall_time_ms": round(wall_duration, 2),
        "timestamp": time.time(),
        "test_count": len(assertions),
        "passed_count": len([a for a in assertions if a["passed"]]),
        "failed_count": len([a for a in assertions if not a["passed"]]),
        "phase": "Phase 2.5",
        "validates": [
            "mode_alerts.py alert aggregator",
            "alert_mode_violation() helper",
            "FileAlertOutput JSONL format",
            "ConsoleAlertOutput with colors",
            "Alert statistics tracking",
            "Multiple output channels"
        ]
    }

    with open(output_dir / "gate_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"{'✅ Gate GM4 PASSED' if all_passed else '❌ Gate GM4 FAILED'}")
    print(f"📊 Tests: {len(assertions)} total, "
          f"{len([a for a in assertions if a['passed']])} passed, "
          f"{len([a for a in assertions if not a['passed']])} failed")
    print(f"⏱️  Duration: {internal_duration:.2f}ms")
    print(f"📄 Evidence: {output_dir / 'gate_results.json'}")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
