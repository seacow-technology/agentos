"""Tool execution ledger for recording and replaying tool calls.

This module provides ToolLedger for recording tool executions and replaying
them on retry/recovery, avoiding redundant tool calls.

Key Features:
- Record tool execution results
- Replay tool results from cache
- Hash-based result validation
- Exit code tracking
- Stdout/stderr hashing for space efficiency

Example:
    ledger = ToolLedger()

    # Execute or replay tool
    result = ledger.execute_or_replay(
        tool_name="bash",
        command="ls -la",
        task_id="task-123",
        execute_fn=lambda: run_bash("ls -la")
    )

    # Result will be cached and replayed on retry
"""

import hashlib
import json
import logging
from typing import Any, Callable, Dict, Optional

from agentos.core.idempotency.store import IdempotencyStore

logger = logging.getLogger(__name__)


class ToolLedger:
    """Ledger for recording and replaying tool executions.

    Records tool execution results including:
    - Exit code
    - Stdout/stderr (hashed for large outputs)
    - Execution duration
    - Tool name and command

    On retry, replays cached results instead of re-executing tools,
    ensuring idempotent task execution.
    """

    def __init__(self, store: Optional[IdempotencyStore] = None):
        """Initialize tool ledger.

        Args:
            store: Optional IdempotencyStore instance. If None, creates new one.
        """
        self.store = store or IdempotencyStore()
        self._executions = 0
        self._replays = 0

    def execute_or_replay(
        self,
        tool_name: str,
        command: str,
        execute_fn: Callable[[], Dict[str, Any]],
        task_id: Optional[str] = None,
        work_item_id: Optional[str] = None,
        force_execute: bool = False
    ) -> Dict[str, Any]:
        """Execute tool or replay cached result.

        Args:
            tool_name: Name of tool (bash, python, etc.)
            command: Command string
            execute_fn: Function to execute tool (should return result dict)
            task_id: Optional task ID for tracking
            work_item_id: Optional work item ID for tracking
            force_execute: If True, bypass cache and re-execute

        Returns:
            Tool execution result dict with:
            - exit_code: Exit code (0 = success)
            - stdout: Standard output
            - stderr: Standard error
            - duration_ms: Execution duration in milliseconds
            - replayed: Whether result was replayed from cache

        Example:
            result = ledger.execute_or_replay(
                tool_name="bash",
                command="echo hello",
                task_id="task-123",
                execute_fn=lambda: {
                    "exit_code": 0,
                    "stdout": "hello\\n",
                    "stderr": "",
                    "duration_ms": 10
                }
            )
        """
        # Build ledger key
        ledger_key = self._build_ledger_key(
            tool_name, command, task_id, work_item_id
        )

        # Compute request hash
        request_data = {
            "tool_name": tool_name,
            "command": command,
            "task_id": task_id,
            "work_item_id": work_item_id,
        }
        request_hash = IdempotencyStore.compute_hash(request_data)

        # Check cache if not forcing execution
        if not force_execute:
            is_cached, cached_result = self.store.check_or_create(
                key=ledger_key,
                request_hash=request_hash,
                task_id=task_id,
                work_item_id=work_item_id,
                expires_in_seconds=30 * 24 * 3600  # 30 days
            )

            if is_cached:
                # Cache hit - replay result
                self._replays += 1
                cached_result["replayed"] = True
                logger.info(
                    f"Tool replay: tool={tool_name}, "
                    f"exit_code={cached_result.get('exit_code')}, "
                    f"task_id={task_id}"
                )
                return cached_result

        # Execute tool
        self._executions += 1
        logger.info(
            f"Tool execution: tool={tool_name}, command={command[:50]}..., "
            f"task_id={task_id}"
        )

        try:
            # Execute
            result = execute_fn()

            # Add metadata
            result["replayed"] = False

            # Hash large outputs for storage efficiency
            result = self._hash_large_outputs(result)

            # Cache result
            self.store.mark_succeeded(ledger_key, result)

            return result

        except Exception as e:
            # Mark as failed
            error_result = {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": 0,
                "error": str(e),
                "replayed": False,
            }
            self.store.mark_failed(ledger_key, str(e))
            raise

    def _build_ledger_key(
        self,
        tool_name: str,
        command: str,
        task_id: Optional[str],
        work_item_id: Optional[str]
    ) -> str:
        """Build ledger key from parameters.

        Format: tool-ledger:{tool_name}:{command_hash}[:task_id][:work_item_id]

        Args:
            tool_name: Tool name
            command: Command string
            task_id: Optional task ID
            work_item_id: Optional work item ID

        Returns:
            Ledger key string
        """
        # Hash command to keep key size reasonable
        command_hash = hashlib.sha256(command.encode()).hexdigest()[:16]

        # Build key components
        parts = [
            "tool-ledger",
            tool_name,
            command_hash
        ]

        if task_id:
            parts.append(task_id)
        if work_item_id:
            parts.append(work_item_id)

        return ":".join(parts)

    def _hash_large_outputs(
        self,
        result: Dict[str, Any],
        size_threshold: int = 10000
    ) -> Dict[str, Any]:
        """Hash large stdout/stderr to save space.

        If stdout or stderr exceeds size_threshold, replace with:
        - First 1000 chars (preview)
        - SHA256 hash
        - Original size

        Args:
            result: Tool execution result
            size_threshold: Size threshold in bytes

        Returns:
            Result with large outputs hashed
        """
        result = result.copy()

        for field in ["stdout", "stderr"]:
            if field not in result:
                continue

            content = result[field]
            if not isinstance(content, str):
                continue

            if len(content) > size_threshold:
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                result[field] = {
                    "preview": content[:1000] + "\n...[truncated]...",
                    "hash": f"sha256:{content_hash}",
                    "size": len(content),
                    "truncated": True,
                }
                logger.debug(
                    f"Hashed large {field}: size={len(content)}, "
                    f"hash={content_hash[:16]}..."
                )

        return result

    def get_execution_history(
        self,
        task_id: str,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Get tool execution history for a task.

        Args:
            task_id: Task ID
            limit: Maximum number of entries to return

        Returns:
            List of execution records
        """
        from agentos.store import get_db

        conn = get_db()
        cursor = conn.execute("""
            SELECT
                idempotency_key,
                response_data,
                status,
                created_at,
                completed_at
            FROM idempotency_keys
            WHERE idempotency_key LIKE 'tool-ledger:%'
              AND task_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (task_id, limit))

        history = []
        for row in cursor.fetchall():
            try:
                response = json.loads(row["response_data"]) if row["response_data"] else {}
                history.append({
                    "key": row["idempotency_key"],
                    "status": row["status"],
                    "exit_code": response.get("exit_code"),
                    "duration_ms": response.get("duration_ms"),
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse execution history: {e}")
                continue

        return history

    def get_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics.

        Returns:
            Dictionary with:
            - executions: Number of actual executions
            - replays: Number of replayed results
            - replay_rate: Replay rate (0-1)
            - total_operations: Total operations
            - store_stats: Statistics from underlying IdempotencyStore
        """
        total = self._executions + self._replays
        replay_rate = self._replays / total if total > 0 else 0.0

        return {
            "executions": self._executions,
            "replays": self._replays,
            "replay_rate": replay_rate,
            "total_operations": total,
            "store_stats": self.store.get_stats(),
        }

    def reset_stats(self) -> None:
        """Reset execution statistics counters."""
        self._executions = 0
        self._replays = 0
        logger.info("Reset tool ledger statistics")
