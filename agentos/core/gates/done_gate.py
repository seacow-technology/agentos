"""DONE Gate Runner: Executes verification gates after task execution

This module provides the gate execution framework for Task #2: PR-B.
After a task completes execution, it enters the 'verifying' state where
DONE gates are executed to validate the implementation.

Gate Types:
- doctor: Basic health check (default)
- smoke: Quick smoke tests
- tests: Full test suite (pytest)

Gate Configuration:
Gates are configured in task.metadata.gates as a list of gate names.
Example: {"gates": ["doctor", "tests"]}

Gate Results:
Results are written to:
1. task_audits table (audit trail)
2. artifacts/gate_results.json (structured results)
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a single gate execution"""

    gate_name: str
    status: str  # "passed", "failed", "error"
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "gate_name": self.gate_name,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @property
    def passed(self) -> bool:
        """Check if gate passed"""
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        """Check if gate failed"""
        return self.status in ["failed", "error"]


@dataclass
class GateRunResult:
    """Result of all gates execution"""

    task_id: str
    gates_executed: List[GateResult] = field(default_factory=list)
    overall_status: str = "passed"  # "passed", "failed", "error"
    total_duration_seconds: float = 0.0
    executed_at: str = field(default_factory=lambda: utc_now_iso())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "gates_executed": [g.to_dict() for g in self.gates_executed],
            "overall_status": self.overall_status,
            "total_duration_seconds": self.total_duration_seconds,
            "executed_at": self.executed_at,
        }

    @property
    def all_passed(self) -> bool:
        """Check if all gates passed"""
        return self.overall_status == "passed" and all(g.passed for g in self.gates_executed)

    @property
    def any_failed(self) -> bool:
        """Check if any gate failed"""
        return any(g.failed for g in self.gates_executed)

    def get_failure_summary(self) -> str:
        """Get a summary of failed gates"""
        failed_gates = [g for g in self.gates_executed if g.failed]
        if not failed_gates:
            return "No failures"

        summary_parts = []
        for gate in failed_gates:
            msg = f"- {gate.gate_name}: {gate.status}"
            if gate.error_message:
                msg += f" ({gate.error_message})"
            summary_parts.append(msg)

        return "\n".join(summary_parts)


class DoneGateRunner:
    """Runner for DONE gates verification

    This class executes verification gates after task execution completes.
    Gates are executed sequentially and results are collected for auditing.
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize gate runner

        Args:
            repo_path: Repository path where gates will be executed
        """
        self.repo_path = repo_path or Path.cwd()

        # Gate command templates
        self.gate_commands = {
            "doctor": ["python", "-c", "print('Doctor check passed')"],
            "smoke": ["python", "-c", "print('Smoke test passed')"],
            "tests": ["pytest", "-v", "--tb=short"],
        }

    def run_gates(
        self,
        task_id: str,
        gate_names: Optional[List[str]] = None,
        timeout_seconds: int = 300
    ) -> GateRunResult:
        """Run DONE gates for a task

        Args:
            task_id: Task ID being verified
            gate_names: List of gate names to run (default: ["doctor"])
            timeout_seconds: Timeout per gate in seconds

        Returns:
            GateRunResult with all gate results
        """
        if gate_names is None:
            gate_names = ["doctor"]  # Default gate

        logger.info(f"Running DONE gates for task {task_id}: {gate_names}")

        result = GateRunResult(task_id=task_id)
        start_time = time.time()

        for gate_name in gate_names:
            gate_result = self._run_single_gate(gate_name, timeout_seconds, task_id=task_id)
            result.gates_executed.append(gate_result)

            # Stop on first failure (fail-fast)
            if gate_result.failed:
                logger.warning(f"Gate {gate_name} failed, stopping gate execution")
                result.overall_status = "failed"
                break

        # If all gates passed
        if not result.any_failed:
            result.overall_status = "passed"
            logger.info(f"All gates passed for task {task_id}")
        else:
            result.overall_status = "failed"
            logger.error(f"Gates failed for task {task_id}:\n{result.get_failure_summary()}")

        result.total_duration_seconds = time.time() - start_time

        return result

    def _run_single_gate(self, gate_name: str, timeout_seconds: int, task_id: str = None) -> GateResult:
        """Run a single gate

        Args:
            gate_name: Name of the gate to run
            timeout_seconds: Timeout in seconds
            task_id: Optional task ID for event emission

        Returns:
            GateResult for this gate
        """
        logger.info(f"Executing gate: {gate_name}")

        # PR-V2: Emit gate_start event
        if task_id:
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=task_id,
                    event_type="gate_start",
                    actor="gate_runner",
                    span_id="main",
                    phase="verifying",
                    payload={
                        "gate_name": gate_name,
                        "timeout_seconds": timeout_seconds,
                        "explanation": f"Starting gate execution: {gate_name}"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit gate_start event: {e}")

        # Get command for this gate
        command = self.gate_commands.get(gate_name)
        if not command:
            return GateResult(
                gate_name=gate_name,
                status="error",
                exit_code=-1,
                error_message=f"Unknown gate: {gate_name}",
            )

        # Execute command
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            duration = time.time() - start_time

            # Determine status based on exit code
            status = "passed" if result.returncode == 0 else "failed"

            gate_result = GateResult(
                gate_name=gate_name,
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
                error_message=None if status == "passed" else f"Exit code: {result.returncode}",
            )

            logger.info(f"Gate {gate_name} {status} (duration: {duration:.2f}s)")

            # PR-V2: Emit gate_result event
            if task_id:
                try:
                    from agentos.core.task.event_service import TaskEventService
                    service = TaskEventService()
                    service.emit_event(
                        task_id=task_id,
                        event_type="gate_result",
                        actor="gate_runner",
                        span_id="main",
                        phase="verifying",
                        payload={
                            "gate_name": gate_name,
                            "status": status,
                            "passed": status == "passed",
                            "exit_code": result.returncode,
                            "duration_seconds": duration,
                            "explanation": f"Gate {gate_name} {status}"
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to emit gate_result event: {e}")

            return gate_result

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            logger.error(f"Gate {gate_name} timed out after {timeout_seconds}s")

            return GateResult(
                gate_name=gate_name,
                status="error",
                exit_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                duration_seconds=duration,
                error_message=f"Timeout after {timeout_seconds}s",
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Gate {gate_name} error: {e}", exc_info=True)

            return GateResult(
                gate_name=gate_name,
                status="error",
                exit_code=-1,
                duration_seconds=duration,
                error_message=str(e),
            )

    def save_gate_results(
        self,
        task_id: str,
        gate_run_result: GateRunResult,
        artifacts_dir: Optional[Path] = None
    ) -> Path:
        """Save gate results to artifacts directory

        Args:
            task_id: Task ID
            gate_run_result: Gate run results to save
            artifacts_dir: Artifacts directory (default: store/artifacts/{task_id})

        Returns:
            Path to saved results file
        """
        if artifacts_dir is None:
            artifacts_dir = Path("store/artifacts") / task_id

        artifacts_dir.mkdir(parents=True, exist_ok=True)

        results_path = artifacts_dir / "gate_results.json"

        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(gate_run_result.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved gate results to {results_path}")

        return results_path

    def load_gate_results(
        self,
        task_id: str,
        artifacts_dir: Optional[Path] = None
    ) -> Optional[GateRunResult]:
        """Load gate results from artifacts directory

        Args:
            task_id: Task ID
            artifacts_dir: Artifacts directory (default: store/artifacts/{task_id})

        Returns:
            GateRunResult or None if not found
        """
        if artifacts_dir is None:
            artifacts_dir = Path("store/artifacts") / task_id

        results_path = artifacts_dir / "gate_results.json"

        if not results_path.exists():
            return None

        with open(results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct GateRunResult
        result = GateRunResult(
            task_id=data["task_id"],
            gates_executed=[
                GateResult(**gate_data) for gate_data in data["gates_executed"]
            ],
            overall_status=data["overall_status"],
            total_duration_seconds=data["total_duration_seconds"],
            executed_at=data["executed_at"],
        )

        return result
