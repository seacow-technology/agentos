"""
Mock Runner Implementation

Temporary runner for testing the execution pipeline.
Returns fixed output and simulates progress stages.
"""

import time
from datetime import datetime
from typing import Optional

from .base import Runner, Invocation, RunResult, ProgressCallback


class MockRunner(Runner):
    """
    Mock runner for testing

    Simulates execution with fixed output and progress stages.
    Useful for testing the execution pipeline without real tool execution.
    """

    def __init__(self, delay_per_stage: float = 0.5):
        """
        Initialize mock runner

        Args:
            delay_per_stage: Delay in seconds for each progress stage
        """
        self.delay_per_stage = delay_per_stage

    @property
    def runner_type(self) -> str:
        return "mock"

    def run(self, invocation: Invocation, progress_cb: Optional[ProgressCallback] = None) -> RunResult:
        """
        Execute mock invocation

        Simulates execution with:
        - 5 progress stages (VALIDATING, LOADING, EXECUTING, FINALIZING, DONE)
        - Fixed delay per stage
        - Success output

        Args:
            invocation: The invocation request
            progress_cb: Optional progress callback

        Returns:
            RunResult with success status and mock output
        """
        started_at = datetime.now()

        # Stage 1: VALIDATING (5%)
        if progress_cb:
            progress_cb("VALIDATING", 5, "Validating invocation parameters")
        time.sleep(self.delay_per_stage)

        # Stage 2: LOADING (15%)
        if progress_cb:
            progress_cb("LOADING", 15, "Loading extension resources")
        time.sleep(self.delay_per_stage)

        # Stage 3: EXECUTING (60%)
        if progress_cb:
            progress_cb("EXECUTING", 60, f"Executing {invocation.extension_id}/{invocation.action_id}")
        time.sleep(self.delay_per_stage)

        # Stage 4: FINALIZING (90%)
        if progress_cb:
            progress_cb("FINALIZING", 90, "Finalizing results")
        time.sleep(self.delay_per_stage)

        # Stage 5: DONE (100%)
        if progress_cb:
            progress_cb("DONE", 100, "Execution complete")

        completed_at = datetime.now()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # Build mock output
        output = f"Mock execution successful\n"
        output += f"Extension: {invocation.extension_id}\n"
        output += f"Action: {invocation.action_id}\n"
        output += f"Args: {invocation.args}\n"
        output += f"Flags: {invocation.flags}\n"

        return RunResult(
            success=True,
            output=output,
            error=None,
            exit_code=0,
            duration_ms=duration_ms,
            metadata={
                "extension_id": invocation.extension_id,
                "action_id": invocation.action_id,
                "runner_type": self.runner_type
            },
            started_at=started_at,
            completed_at=completed_at
        )
