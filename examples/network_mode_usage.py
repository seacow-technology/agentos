#!/usr/bin/env python3
"""Network mode usage examples.

This script demonstrates how to use the network mode functionality
in different scenarios.
"""

import asyncio
from pathlib import Path

from agentos.core.communication.network_mode import NetworkMode, NetworkModeManager


async def example_basic_usage():
    """Example 1: Basic network mode operations."""
    print("=" * 70)
    print("Example 1: Basic Network Mode Operations")
    print("=" * 70)

    # Create manager (uses default database location)
    manager = NetworkModeManager()

    # Get current mode
    current = manager.get_mode()
    print(f"\nCurrent mode: {current.value}")

    # Set mode to READONLY with metadata
    result = manager.set_mode(
        NetworkMode.READONLY,
        updated_by="admin",
        reason="Scheduled maintenance window"
    )

    print(f"\nMode changed:")
    print(f"  From: {result['previous_mode']}")
    print(f"  To: {result['new_mode']}")
    print(f"  At: {result['timestamp']}")
    print(f"  Changed: {result['changed']}")

    # Restore to ON
    manager.set_mode(NetworkMode.ON, updated_by="admin", reason="Maintenance completed")


async def example_operation_checking():
    """Example 2: Checking operation permissions."""
    print("\n" + "=" * 70)
    print("Example 2: Checking Operation Permissions")
    print("=" * 70)

    manager = NetworkModeManager()

    # Test different operations in different modes
    operations = ["search", "fetch", "send", "delete"]

    for mode in [NetworkMode.ON, NetworkMode.READONLY, NetworkMode.OFF]:
        print(f"\nMode: {mode.value}")
        print("-" * 40)

        for operation in operations:
            allowed, reason = manager.is_operation_allowed(operation, current_mode=mode)
            status = "✓ ALLOWED" if allowed else "✗ DENIED"
            print(f"  {operation:12} {status}")
            if reason:
                print(f"               → {reason}")


async def example_history_tracking():
    """Example 3: Working with mode change history."""
    print("\n" + "=" * 70)
    print("Example 3: Mode Change History")
    print("=" * 70)

    manager = NetworkModeManager()

    # Make several mode changes
    changes = [
        (NetworkMode.READONLY, "Backup in progress"),
        (NetworkMode.OFF, "Security scan"),
        (NetworkMode.READONLY, "Scan completed, restoring access"),
        (NetworkMode.ON, "All clear"),
    ]

    for mode, reason in changes:
        manager.set_mode(mode, updated_by="system", reason=reason)

    # Get history
    history = manager.get_history(limit=10)

    print(f"\nRecent mode changes ({len(history)} total):")
    print("-" * 70)

    for i, record in enumerate(history, 1):
        print(f"{i}. {record['changed_at']}")
        print(f"   {record['previous_mode']:8} → {record['new_mode']:8}")
        print(f"   By: {record['changed_by']}")
        print(f"   Reason: {record['reason']}")
        print()


async def example_mode_info():
    """Example 4: Getting detailed mode information."""
    print("=" * 70)
    print("Example 4: Detailed Mode Information")
    print("=" * 70)

    manager = NetworkModeManager()

    info = manager.get_mode_info()

    # Current state
    state = info['current_state']
    print("\nCurrent State:")
    print(f"  Mode: {state['mode']}")
    print(f"  Updated: {state['updated_at']}")
    print(f"  By: {state['updated_by']}")

    # Available modes
    print(f"\nAvailable Modes: {', '.join(info['available_modes'])}")

    # Operation classifications
    print(f"\nOperation Classifications:")
    print(f"  Readonly operations: {len(info['readonly_operations'])} operations")
    print(f"    {', '.join(sorted(info['readonly_operations']))}")
    print(f"  Write operations: {len(info['write_operations'])} operations")
    print(f"    {', '.join(sorted(info['write_operations']))}")

    # Recent history
    print(f"\nRecent History: {len(info['recent_history'])} changes")
    for record in info['recent_history'][:3]:  # Show last 3
        print(f"  • {record['previous_mode']} → {record['new_mode']} ({record['changed_by']})")


async def example_error_handling():
    """Example 5: Error handling and validation."""
    print("\n" + "=" * 70)
    print("Example 5: Error Handling")
    print("=" * 70)

    manager = NetworkModeManager()

    # Try invalid mode
    print("\n1. Invalid mode value:")
    try:
        manager.set_mode("invalid_mode")
        print("   ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Caught error: {str(e)}")

    # Idempotent set (same mode)
    print("\n2. Setting same mode (idempotent):")
    current = manager.get_mode()
    result = manager.set_mode(current)
    print(f"   Current mode: {current.value}")
    print(f"   Set same mode: {result['changed']} (should be False)")


async def example_integration_service():
    """Example 6: Using with CommunicationService."""
    print("\n" + "=" * 70)
    print("Example 6: Integration with CommunicationService")
    print("=" * 70)

    from agentos.core.communication.service import CommunicationService
    from agentos.core.communication.models import ConnectorType

    # Create service (includes network mode manager)
    service = CommunicationService()

    print("\nService created with network mode support")
    print(f"Current mode: {service.network_mode_manager.get_mode().value}")

    # The service will automatically check network mode before executing operations
    # If mode is OFF or READONLY (for write ops), operations will be blocked

    print("\nNetwork mode is checked automatically in service.execute()")
    print("Operations blocked by network mode return status='denied'")
    print("with error starting with 'NETWORK_MODE_BLOCKED:'")


async def main():
    """Run all examples."""
    await example_basic_usage()
    await example_operation_checking()
    await example_history_tracking()
    await example_mode_info()
    await example_error_handling()
    await example_integration_service()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
    print("\nFor more information, see:")
    print("  - docs/NETWORK_MODE_QUICK_REFERENCE.md")
    print("  - docs/NETWORK_MODE_IMPLEMENTATION_SUMMARY.md")


if __name__ == "__main__":
    asyncio.run(main())
