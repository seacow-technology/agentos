#!/usr/bin/env python3
"""
Example: Using the Capability Abstraction Layer (PR-1)

This example demonstrates how to use the unified capability abstraction layer
to discover and invoke tools from Extensions (and MCP in PR-2).

Features demonstrated:
1. Initialize CapabilityRegistry
2. List available tools
3. Filter tools by risk level and side effects
4. Get specific tool information
5. Invoke a tool through ToolRouter
6. Handle results and errors

Usage:
    python3 examples/capability_usage_example.py
"""

import asyncio
from datetime import datetime
from pathlib import Path

from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.capabilities import (
    CapabilityRegistry,
    ToolRouter,
    ToolInvocation,
    RiskLevel,
    SideEffect,
    ExecutionMode,
)


def main():
    """Main example function"""
    print("=" * 60)
    print("Capability Abstraction Layer - Example Usage")
    print("=" * 60)
    print()

    # 1. Initialize registries
    print("1. Initializing registries...")
    ext_registry = ExtensionRegistry()
    cap_registry = CapabilityRegistry(ext_registry)
    router = ToolRouter(cap_registry)
    print("   ✓ Registries initialized")
    print()

    # 2. List all available tools
    print("2. Listing all available tools...")
    all_tools = cap_registry.list_tools()
    print(f"   Found {len(all_tools)} tools:")
    for tool in all_tools[:5]:  # Show first 5
        print(f"   - {tool.tool_id}")
        print(f"     Name: {tool.name}")
        print(f"     Risk: {tool.risk_level.value}")
        print(f"     Source: {tool.source_type.value}")
        print()

    # 3. Filter tools by risk level
    print("3. Filtering tools by risk level (MED or lower)...")
    safe_tools = cap_registry.list_tools(risk_level_max=RiskLevel.MED)
    print(f"   Found {len(safe_tools)} safe tools")
    print()

    # 4. Filter tools by side effects
    print("4. Filtering tools (excluding filesystem writes)...")
    readonly_tools = cap_registry.list_tools(
        exclude_side_effects=[SideEffect.FS_WRITE.value, SideEffect.FS_DELETE.value]
    )
    print(f"   Found {len(readonly_tools)} read-only tools")
    print()

    # 5. Get specific tool information
    print("5. Getting specific tool information...")
    if all_tools:
        example_tool_id = all_tools[0].tool_id
        tool = cap_registry.get_tool(example_tool_id)
        if tool:
            print(f"   Tool: {tool.name}")
            print(f"   Description: {tool.description}")
            print(f"   Risk Level: {tool.risk_level.value}")
            print(f"   Side Effects: {', '.join(tool.side_effect_tags) or 'None'}")
            print(f"   Timeout: {tool.timeout_ms}ms")
            print()

    # 6. Invoke a tool (example)
    print("6. Example tool invocation...")
    if all_tools:
        example_tool = all_tools[0]
        print(f"   Invoking: {example_tool.tool_id}")

        # Create invocation
        invocation = ToolInvocation(
            invocation_id="example_inv_001",
            tool_id=example_tool.tool_id,
            task_id="example_task",
            project_id="example_project",
            mode=ExecutionMode.EXECUTION,
            inputs={"example_param": "example_value"},
            actor="example_user@example.com",
            timestamp=datetime.now()
        )

        # Invoke tool (async)
        try:
            result = asyncio.run(router.invoke_tool(example_tool.tool_id, invocation))
            print(f"   ✓ Invocation successful!")
            print(f"   Success: {result.success}")
            print(f"   Duration: {result.duration_ms}ms")
            if result.payload:
                print(f"   Payload: {result.payload}")
        except Exception as e:
            print(f"   ✗ Invocation failed: {e}")
    print()

    # 7. Search tools
    print("7. Searching tools...")
    if all_tools:
        # Search by keyword
        search_results = cap_registry.search_tools("test")
        print(f"   Found {len(search_results)} tools matching 'test'")
    print()

    print("=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
