#!/usr/bin/env python3
"""
Capability Runner Demo

This script demonstrates how to use the Capability Runner system
to execute extension capabilities.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentos.core.capabilities import (
    CapabilityRunner,
    CommandRoute,
    ExecutionContext,
)


def demo_exec_tool():
    """Demo: Execute a command-line tool"""
    print("\n" + "="*60)
    print("Demo 1: Execute Command-Line Tool (echo)")
    print("="*60)

    runner = CapabilityRunner()

    # Create a command route (as would come from Slash Router)
    route = CommandRoute(
        command_name="/echo",
        extension_id="demo.echo",
        action_id="echo",
        runner="exec.echo",
        args=["Hello", "from", "Capability", "Runner!"],
        description="Echo a message"
    )

    # Create execution context
    context = ExecutionContext(
        session_id="demo_session_1",
        user_id="demo_user",
        extension_id="demo.echo",
        work_dir=Path("/tmp/.agentos/demo/work"),
        timeout=10
    )

    # Execute
    result = runner.execute(route, context)

    # Display result
    print(f"\nSuccess: {result.success}")
    print(f"Output:\n{result.output}")
    print(f"Duration: {result.duration_seconds:.3f} seconds")
    if result.metadata:
        print(f"Metadata: {result.metadata}")


def demo_analyze_response():
    """Demo: Analyze response using LLM (simple analysis without LLM)"""
    print("\n" + "="*60)
    print("Demo 2: Analyze Response")
    print("="*60)

    runner = CapabilityRunner()

    # First, execute a command that produces output
    exec_route = CommandRoute(
        command_name="/demo",
        extension_id="demo.api",
        action_id="echo",
        runner="exec.echo",
        args=['{"status": "success", "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}']
    )

    context = ExecutionContext(
        session_id="demo_session_2",
        user_id="demo_user",
        extension_id="demo.api",
        work_dir=Path("/tmp/.agentos/demo/work"),
        timeout=10
    )

    print("\nStep 1: Execute command to generate response")
    exec_result = runner.execute(exec_route, context)
    print(f"Command output: {exec_result.output[:100]}...")

    # Now analyze the last response
    analyze_route = CommandRoute(
        command_name="/demo",
        extension_id="demo.api",
        action_id="explain",
        runner="analyze.response",
        args=["last_response"],
        description="Explain the API response structure"
    )

    print("\nStep 2: Analyze the response")
    analyze_result = runner.execute(analyze_route, context)

    print(f"\nSuccess: {analyze_result.success}")
    print(f"Analysis:\n{analyze_result.output}")


def demo_error_handling():
    """Demo: Error handling"""
    print("\n" + "="*60)
    print("Demo 3: Error Handling")
    print("="*60)

    runner = CapabilityRunner()

    # Try to execute a nonexistent tool
    route = CommandRoute(
        command_name="/demo",
        extension_id="demo.nonexistent",
        action_id="run",
        runner="exec.nonexistent_tool_xyz",
        args=[]
    )

    context = ExecutionContext(
        session_id="demo_session_3",
        user_id="demo_user",
        extension_id="demo.nonexistent",
        work_dir=Path("/tmp/.agentos/demo/work"),
        timeout=10
    )

    result = runner.execute(route, context)

    print(f"\nSuccess: {result.success}")
    print(f"Error: {result.error}")


def demo_inline_analysis():
    """Demo: Analyze provided content directly"""
    print("\n" + "="*60)
    print("Demo 4: Analyze Inline Content")
    print("="*60)

    runner = CapabilityRunner()

    route = CommandRoute(
        command_name="/demo",
        extension_id="demo.analyze",
        action_id="explain",
        runner="analyze.response",
        args=['{"api": "example", "version": "1.0", "endpoints": ["/users", "/posts", "/comments"]}'],
        description="Analyze API schema"
    )

    context = ExecutionContext(
        session_id="demo_session_4",
        user_id="demo_user",
        extension_id="demo.analyze",
        work_dir=Path("/tmp/.agentos/demo/work"),
        timeout=10,
        usage_doc="API schema analysis for RESTful services"
    )

    result = runner.execute(route, context)

    print(f"\nSuccess: {result.success}")
    print(f"Analysis:\n{result.output}")


def demo_runner_stats():
    """Demo: Get runner statistics"""
    print("\n" + "="*60)
    print("Demo 5: Runner Statistics")
    print("="*60)

    runner = CapabilityRunner()

    stats = runner.get_stats()

    print(f"\nExecutor count: {stats['executor_count']}")
    print(f"Available executors: {', '.join(stats['executors'])}")
    print(f"Base directory: {stats['base_dir']}")


def demo_tool_info():
    """Demo: Get tool information"""
    print("\n" + "="*60)
    print("Demo 6: Tool Information")
    print("="*60)

    from agentos.core.capabilities.tool_executor import ToolExecutor

    executor = ToolExecutor()

    # Check some common tools
    tools = ["echo", "ls", "curl", "nonexistent_tool"]

    for tool in tools:
        exists = executor.check_tool_exists(tool)
        info = executor.get_tool_info(tool)

        print(f"\nTool: {tool}")
        print(f"  Exists: {exists}")
        if info:
            print(f"  Path: {info['path']}")
            print(f"  Executable: {info['executable']}")
            print(f"  Size: {info['size_bytes']} bytes")


def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("Capability Runner System Demo")
    print("="*60)

    demos = [
        ("Execute Command-Line Tool", demo_exec_tool),
        ("Analyze Response", demo_analyze_response),
        ("Error Handling", demo_error_handling),
        ("Analyze Inline Content", demo_inline_analysis),
        ("Runner Statistics", demo_runner_stats),
        ("Tool Information", demo_tool_info),
    ]

    for i, (name, demo_func) in enumerate(demos, 1):
        try:
            demo_func()
        except Exception as e:
            print(f"\nDemo {i} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("All demos completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
