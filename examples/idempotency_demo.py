#!/usr/bin/env python3
"""Demonstration of idempotency and caching features.

This script demonstrates:
1. LLM output caching to save tokens
2. Tool execution replay to avoid redundant calls
3. Statistics tracking for monitoring cache effectiveness

Run this script multiple times to see caching in action.
"""

import time
from agentos.core.idempotency import LLMOutputCache, ToolLedger, IdempotencyStore


def mock_llm_call(prompt: str, tokens: int = 100) -> dict:
    """Mock LLM API call (simulates delay and token usage)."""
    print(f"  [LLM] Calling API with prompt: {prompt[:50]}...")
    time.sleep(0.1)  # Simulate API latency
    return {
        "content": f"Response to: {prompt}",
        "tokens": tokens,
        "model": "gpt-4"
    }


def mock_tool_execution(command: str) -> dict:
    """Mock tool execution (simulates command execution)."""
    print(f"  [TOOL] Executing: {command}")
    time.sleep(0.05)  # Simulate execution time
    return {
        "exit_code": 0,
        "stdout": f"Output of {command}",
        "stderr": "",
        "duration_ms": 50
    }


def demo_llm_cache():
    """Demonstrate LLM output caching."""
    print("\n" + "="*70)
    print("DEMO 1: LLM Output Caching")
    print("="*70)

    cache = LLMOutputCache()

    # First call - will execute LLM
    print("\n1. First call (cache miss - will execute LLM):")
    result1 = cache.get_or_generate(
        operation_type="plan",
        prompt="Write a plan to implement user authentication",
        model="gpt-4",
        generate_fn=lambda: mock_llm_call(
            "Write a plan to implement user authentication",
            tokens=150
        )
    )
    print(f"   Result: {result1['content'][:60]}...")
    print(f"   Tokens: {result1['tokens']}")

    # Second call - will use cache
    print("\n2. Second call (cache hit - returns cached result):")
    result2 = cache.get_or_generate(
        operation_type="plan",
        prompt="Write a plan to implement user authentication",
        model="gpt-4",
        generate_fn=lambda: mock_llm_call(
            "Write a plan to implement user authentication",
            tokens=150
        )
    )
    print(f"   Result: {result2['content'][:60]}...")
    print(f"   Tokens: {result2['tokens']}")
    print(f"   Cache hit! No LLM call made.")

    # Show statistics
    stats = cache.get_stats()
    print(f"\n3. Cache Statistics:")
    print(f"   Hit rate: {stats['hit_rate']:.1%}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Cache misses: {stats['cache_misses']}")


def demo_tool_ledger():
    """Demonstrate tool execution recording and replay."""
    print("\n" + "="*70)
    print("DEMO 2: Tool Execution Ledger")
    print("="*70)

    ledger = ToolLedger()

    # First execution - will run tool
    print("\n1. First execution (will run tool):")
    result1 = ledger.execute_or_replay(
        tool_name="bash",
        command="ls -la /tmp",
        execute_fn=lambda: mock_tool_execution("ls -la /tmp")
    )
    print(f"   Exit code: {result1['exit_code']}")
    print(f"   Stdout: {result1['stdout']}")
    print(f"   Replayed: {result1['replayed']}")

    # Second execution - will replay
    print("\n2. Second execution (will replay cached result):")
    result2 = ledger.execute_or_replay(
        tool_name="bash",
        command="ls -la /tmp",
        execute_fn=lambda: mock_tool_execution("ls -la /tmp")
    )
    print(f"   Exit code: {result2['exit_code']}")
    print(f"   Stdout: {result2['stdout']}")
    print(f"   Replayed: {result2['replayed']}")
    print(f"   Cache hit! Tool not re-executed.")

    # Show statistics
    stats = ledger.get_stats()
    print(f"\n3. Ledger Statistics:")
    print(f"   Replay rate: {stats['replay_rate']:.1%}")
    print(f"   Executions: {stats['executions']}")
    print(f"   Replays: {stats['replays']}")


def demo_idempotency_store():
    """Demonstrate direct use of IdempotencyStore."""
    print("\n" + "="*70)
    print("DEMO 3: Direct IdempotencyStore Usage")
    print("="*70)

    store = IdempotencyStore()
    key = "expensive-operation-123"

    # Compute request hash
    request_data = {"operation": "process_data", "file": "data.csv"}
    request_hash = IdempotencyStore.compute_hash(request_data)

    # Check if already executed
    print("\n1. Check if operation already executed:")
    is_cached, result = store.check_or_create(
        key=key,
        request_hash=request_hash
    )

    if is_cached:
        print(f"   Operation already completed!")
        print(f"   Cached result: {result}")
    else:
        print(f"   Operation not found in cache, executing...")

        # Simulate expensive operation
        time.sleep(0.1)
        result = {"status": "success", "rows_processed": 1000}

        # Store result
        store.mark_succeeded(key, result)
        print(f"   Operation completed: {result}")

    # Get statistics
    stats = store.get_stats()
    print(f"\n2. Store Statistics:")
    print(f"   Total keys: {stats['total']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Pending: {stats['pending']}")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "IDEMPOTENCY & CACHING DEMO" + " "*27 + "║")
    print("╚" + "="*68 + "╝")

    demo_llm_cache()
    demo_tool_ledger()
    demo_idempotency_store()

    print("\n" + "="*70)
    print("OVERALL SYSTEM STATISTICS")
    print("="*70)
    print("\nRun this script multiple times to see caching in action!")
    print("Use 'python scripts/tools/print_token_savings.py' for detailed stats.")
    print()


if __name__ == "__main__":
    main()
