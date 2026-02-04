"""
Simulated Runner Implementation

A production-safe runner for testing and development scenarios.
Returns fixed output and simulates progress stages without actual execution.
"""

import time
from datetime import datetime
from typing import Optional

from .base import Runner, Invocation, RunResult, ProgressCallback


class SimulatedRunner(Runner):
    """
    Simulated runner for testing and development.

    This runner simulates execution without performing actual operations,
    useful for testing, dry-run scenarios, and development workflows.

    Features:
    - Simulates execution with fixed output
    - Provides realistic progress stages
    - No side effects or actual tool execution

    Note: Formerly known as MockRunner (renamed 2026-02-01 per PR-0201-2026-3).
    """

    def __init__(self, delay_per_stage: float = 0.5):
        """
        Initialize simulated runner

        Args:
            delay_per_stage: Delay in seconds for each progress stage
        """
        self.delay_per_stage = delay_per_stage

    @property
    def runner_type(self) -> str:
        return "simulated"

    def run(self, invocation: Invocation, progress_cb: Optional[ProgressCallback] = None) -> RunResult:
        """
        Execute simulated invocation

        Simulates execution with:
        - 5 progress stages (VALIDATING, LOADING, EXECUTING, FINALIZING, DONE)
        - Fixed delay per stage
        - Success output

        Args:
            invocation: The invocation request
            progress_cb: Optional progress callback

        Returns:
            RunResult with success status and simulated output
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

        # Build simulated output
        output = f"Simulated execution successful\n"
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
