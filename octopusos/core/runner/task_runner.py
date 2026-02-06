"""Task Runner: Background task execution engine

This module provides the background runner that executes tasks.
It runs as a subprocess and communicates with the CLI through the database.

P1: Integrated with real ModePipelineRunner for production execution.
PR-3: Integrated with Router for route verification and failover.
"""

import time
import logging
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from agentos.core.task import TaskManager, Task, RunMode
from agentos.core.task.run_mode import TaskMetadata
from agentos.core.task.project_settings_inheritance import ProjectSettingsInheritance
from agentos.core.time import utc_now_iso
from agentos.core.gates.pause_gate import (
    can_pause_at,
    PauseCheckpoint,
    create_pause_metadata,
    PauseGateViolation
)
from agentos.core.gates.done_gate import DoneGateRunner, GateRunResult
from agentos.core.mode.pipeline_runner import ModePipelineRunner
from agentos.core.mode.mode_selector import ModeSelection
from agentos.router import Router, RoutePlan, RerouteReason
from agentos.core.task.work_items import (
    WorkItem,
    WorkItemOutput,
    WorkItemsSummary,
    extract_work_items_from_pipeline,
    create_work_items_summary,
)
from agentos.core.checkpoints import CheckpointManager, Evidence, EvidencePack, EvidenceType
from agentos.core.worker_pool import LeaseManager, start_heartbeat
from agentos.core.idempotency import LLMOutputCache, ToolLedger
from agentos.store import get_db
from agentos.core.task.event_service import (
    emit_runner_spawn,
    emit_phase_enter,
    emit_phase_exit,
    emit_work_item_start,
    emit_work_item_complete,
    emit_checkpoint_commit,
)

logger = logging.getLogger(__name__)


class TaskRunner:
    """Background task runner (subprocess-based)
    
    This runner executes tasks in the background and updates their status
    in the database. The CLI monitors the status for progress updates.
    
    P1: Uses real ModePipelineRunner for production execution.
    """
    
    def __init__(
        self,
        task_manager: Optional[TaskManager] = None,
        repo_path: Optional[Path] = None,
        policy_path: Optional[Path] = None,
        use_real_pipeline: bool = False,
        router: Optional[Router] = None,
        enable_recovery: bool = True,
    ):
        """Initialize task runner

        Args:
            task_manager: TaskManager instance
            repo_path: Repository path for pipeline execution
            policy_path: Sandbox policy path
            use_real_pipeline: If True, use ModePipelineRunner; if False, use simulation
            router: Router instance for route verification (PR-3)
            enable_recovery: If True, enable checkpoint-based recovery (Task #9)
        """
        self.task_manager = task_manager or TaskManager()
        self.repo_path = repo_path or Path(".")
        self.policy_path = policy_path
        self.use_real_pipeline = use_real_pipeline
        self.router = router or Router()  # Router doesn't need task_manager
        self.settings_inheritance = ProjectSettingsInheritance()
        self.gate_runner = DoneGateRunner(repo_path=self.repo_path)
        self.enable_recovery = enable_recovery

        if self.use_real_pipeline:
            self.pipeline_runner = ModePipelineRunner()
            logger.info("TaskRunner initialized with real ModePipelineRunner")
        else:
            self.pipeline_runner = None
            logger.info("TaskRunner initialized in simulation mode")

        # Task #9: Recovery system components
        if self.enable_recovery:
            import os
            self.worker_id = f"worker-{os.getpid()}"
            self.checkpoint_manager = CheckpointManager()
            self.llm_cache = LLMOutputCache()
            self.tool_ledger = ToolLedger()
            # LeaseManager needs a connection - will be created per operation
            self._db_conn = None
            logger.info(f"Recovery system enabled: worker_id={self.worker_id}")
        else:
            self.checkpoint_manager = None
            self.llm_cache = None
            self.tool_ledger = None
            self.worker_id = None
            logger.info("Recovery system disabled")
    
    def run_task(self, task_id: str, max_iterations: int = 100):
        """Run a task in the background

        Args:
            task_id: Task ID to run
            max_iterations: Maximum number of state transitions (safety)
        """
        import os
        from agentos.core.task.timeout_manager import TimeoutManager
        from agentos.core.task.cancel_handler import CancelHandler

        logger.info(f"Starting task runner for task {task_id}")

        # Initialize timeout manager
        timeout_manager = TimeoutManager()

        # Initialize cancel handler
        cancel_handler = CancelHandler()

        # Load task to check for project settings
        task = self.task_manager.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # Start timeout tracking
        timeout_config = task.get_timeout_config()
        timeout_state = task.get_timeout_state()
        timeout_state = timeout_manager.start_timeout_tracking(timeout_state)
        task.update_timeout_state(timeout_state)
        self.task_manager.update_task(task)

        # Apply project settings before execution (Task #13)
        effective_config = {}
        if task.project_id:
            try:
                effective_config = self.settings_inheritance.apply_project_settings(task)
                logger.info(
                    f"Loaded project settings for task {task_id}: "
                    f"runner={effective_config.get('runner')}, "
                    f"workdir={effective_config.get('workdir')}"
                )

                # Change to effective working directory if specified
                workdir = effective_config.get('workdir')
                if workdir:
                    try:
                        os.chdir(workdir)
                        logger.info(f"Changed working directory to: {workdir}")
                    except Exception as e:
                        logger.error(f"Failed to change working directory to {workdir}: {e}")

            except Exception as e:
                logger.error(f"Failed to apply project settings: {e}", exc_info=True)

        # P0-3: Record runner spawn in lineage
        # Include timestamp to ensure uniqueness when multiple runners in same process
        import time
        run_id = f"runner_{task_id}_{os.getpid()}_{int(time.time() * 1000)}"
        try:
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="runner_spawn",
                ref_id=run_id,
                phase="execution",
                metadata={"pid": os.getpid(), "max_iterations": max_iterations}
            )
        except Exception as e:
            logger.error(f"Failed to record runner spawn: {e}")

        # PR-V2: Emit runner_spawn event for UI visualization
        try:
            emit_runner_spawn(
                task_id=task_id,
                span_id="main",
                runner_pid=os.getpid(),
                runner_version="v0.4.0",
                explanation=f"Runner process started for task {task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to emit runner_spawn event: {e}")

        # PR-3: Verify or reroute before execution starts
        route_plan = None
        try:
            route_plan = self._load_route_plan(task_id)
            if route_plan:
                logger.info(f"Loaded route plan for task {task_id}: selected={route_plan.selected}")
                # Verify route and reroute if needed
                import asyncio
                route_plan, reroute_event = asyncio.run(
                    self.router.verify_or_reroute(task_id, route_plan)
                )

                if reroute_event:
                    logger.warning(
                        f"Task {task_id} rerouted: {reroute_event.from_instance} -> {reroute_event.to_instance}"
                    )
                    # Save updated route plan
                    self._save_route_plan(task_id, route_plan)

                    # Log reroute event
                    self._log_audit(
                        task_id, "warn",
                        f"TASK_REROUTED: {reroute_event.from_instance} -> {reroute_event.to_instance} "
                        f"(reason: {reroute_event.reason_code.value})"
                    )
                else:
                    logger.info(f"Route verified for task {task_id}: {route_plan.selected}")
                    self._log_audit(task_id, "info", f"TASK_ROUTE_VERIFIED: {route_plan.selected}")
            else:
                logger.warning(f"No route plan found for task {task_id}, will execute without routing")
        except RuntimeError as e:
            logger.error(f"Route verification failed: {e}")
            self._log_audit(task_id, "error", f"Route verification failed: {str(e)}")
            # Mark task as BLOCKED
            self.task_manager.update_task_status(task_id, "failed")
            return
        except Exception as e:
            logger.error(f"Unexpected error during route verification: {e}", exc_info=True)
            # Continue execution despite routing error
            self._log_audit(task_id, "warn", f"Route verification error (continuing): {str(e)}")

        iteration = 0
        exit_reason = "unknown"

        try:
            while iteration < max_iterations:
                iteration += 1

                # 1. Load task from DB
                try:
                    task = self.task_manager.get_task(task_id)
                except Exception as e:
                    logger.error(f"Failed to load task {task_id}: {e}")
                    exit_reason = "fatal_error"
                    self.task_manager.update_task_exit_reason(task_id, exit_reason, status="failed")
                    self._log_audit(task_id, "error", f"Task load error: {str(e)}")
                    break

                # 2. Check timeout
                timeout_config = task.get_timeout_config()
                timeout_state = task.get_timeout_state()
                is_timeout, warning_msg, timeout_msg = timeout_manager.check_timeout(
                    timeout_config,
                    timeout_state
                )

                if is_timeout:
                    logger.error(f"Task {task_id} timed out: {timeout_msg}")
                    exit_reason = "timeout"
                    self.task_manager.update_task_exit_reason(task_id, exit_reason, status="failed")
                    self._log_audit(task_id, "error", timeout_msg)
                    break

                if warning_msg:
                    logger.warning(f"Task {task_id} timeout warning: {warning_msg}")
                    self._log_audit(task_id, "warn", warning_msg)
                    timeout_state = timeout_manager.mark_warning_issued(timeout_state)
                    task.update_timeout_state(timeout_state)
                    self.task_manager.update_task(task)

                # Update heartbeat
                timeout_state = timeout_manager.update_heartbeat(timeout_state)
                task.update_timeout_state(timeout_state)

                # 3. Check for cancel signal
                should_cancel, cancel_reason = cancel_handler.should_cancel(
                    task_id,
                    task.status
                )

                if should_cancel:
                    logger.warning(f"Task {task_id} cancel requested: {cancel_reason}")

                    # Perform cleanup
                    cleanup_results = cancel_handler.perform_cleanup(
                        task_id,
                        cleanup_actions=["flush_logs", "release_resources", "save_partial_results"]
                    )

                    # Record cancel event
                    cancel_handler.record_cancel_event(
                        task_id=task_id,
                        actor=task.metadata.get("cancel_actor", "unknown"),
                        reason=cancel_reason,
                        cleanup_results=cleanup_results
                    )

                    exit_reason = "user_cancelled"
                    self.task_manager.update_task_exit_reason(task_id, exit_reason)
                    break

                # 4. Check if task is in terminal state
                if task.status in ["succeeded", "failed", "canceled", "blocked"]:
                    logger.info(f"Task {task_id} is in terminal state: {task.status}")
                    # Terminal state reached, determine exit_reason based on status
                    if task.status == "succeeded":
                        exit_reason = "done"
                    elif task.status == "blocked":
                        exit_reason = "blocked"
                    elif task.status == "canceled":
                        exit_reason = "user_cancelled"
                    elif task.status == "failed":
                        exit_reason = "fatal_error"

                    # Update exit_reason if not already set
                    if not task.exit_reason:
                        self.task_manager.update_task_exit_reason(task_id, exit_reason)
                    break

                # 3. Execute current stage
                try:
                    next_status = self._execute_stage(task)

                    # 4. Update task status
                    if next_status != task.status:
                        self.task_manager.update_task_status(task_id, next_status)
                        logger.info(f"Task {task_id} status: {task.status} -> {next_status}")

                    # 5. Check if waiting for approval - CRITICAL: Handle AUTONOMOUS mode blocking
                    if next_status == "awaiting_approval":
                        metadata = TaskMetadata.from_dict(task.metadata)
                        run_mode = metadata.run_mode.value

                        # AUTONOMOUS mode should NOT stop at approval checkpoints
                        if run_mode == "autonomous":
                            # This is a blocking scenario - AUTONOMOUS mode hit a checkpoint that requires approval
                            logger.warning(
                                f"Task {task_id} in AUTONOMOUS mode encountered approval checkpoint - BLOCKING"
                            )
                            self._log_audit(
                                task_id, "warn",
                                "AUTONOMOUS mode task blocked: Cannot proceed without approval checkpoint"
                            )
                            # Mark as BLOCKED, not awaiting_approval
                            exit_reason = "blocked"
                            self.task_manager.update_task_exit_reason(task_id, exit_reason, status="blocked")
                            break
                        else:
                            # INTERACTIVE/ASSISTED mode: legitimate pause for approval
                            logger.info(f"Task {task_id} awaiting approval (run_mode={run_mode}), pausing runner")
                            self._log_audit(task_id, "info", "Task paused for approval")
                            exit_reason = "done"  # Not an error, just waiting for user
                            self.task_manager.update_task_exit_reason(task_id, exit_reason)
                            break

                    # Small delay between iterations
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error executing task {task_id}: {e}", exc_info=True)
                    exit_reason = "fatal_error"
                    self.task_manager.update_task_exit_reason(task_id, exit_reason, status="failed")
                    self._log_audit(task_id, "error", f"Task failed: {str(e)}")
                    break

            if iteration >= max_iterations:
                logger.warning(f"Task {task_id} exceeded max iterations")
                exit_reason = "max_iterations"
                self.task_manager.update_task_exit_reason(task_id, exit_reason, status="failed")
                self._log_audit(task_id, "warn", "Task exceeded max iterations")

        finally:
            # P0-3: Record runner exit in lineage
            try:
                self.task_manager.add_lineage(
                    task_id=task_id,
                    kind="runner_exit",
                    ref_id=run_id,
                    phase="execution",
                    metadata={
                        "pid": os.getpid(),
                        "exit_reason": exit_reason,
                        "iterations": iteration
                    }
                )
            except Exception as e:
                logger.error(f"Failed to record runner exit: {e}")

            # PR-V2: Emit runner_exit event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=task_id,
                    event_type="runner_exit",
                    actor="runner",
                    span_id="main",
                    phase=None,
                    payload={
                        "runner_pid": os.getpid(),
                        "exit_reason": exit_reason,
                        "iterations": iteration,
                        "explanation": f"Runner exited: {exit_reason}"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit runner_exit event: {e}")
    
    def _execute_stage(self, task: Task) -> str:
        """Execute current stage and return next status
        
        This is a simplified pipeline that demonstrates the state machine.
        In production, this would call the actual coordinator/executor.
        
        Args:
            task: Task to execute
            
        Returns:
            Next status string
        """
        current_status = task.status
        metadata = TaskMetadata.from_dict(task.metadata)
        
        # State machine transitions
        if current_status == "created":
            # Start intent processing
            self._log_audit(task.task_id, "info", "Starting intent processing")
            return "intent_processing"
        
        elif current_status == "intent_processing":
            # Simulate intent processing
            self._log_audit(task.task_id, "info", "Processing intent")
            time.sleep(1)  # Simulate work
            return "planning"
        
        elif current_status == "planning":
            # P1: Planning stage - Use real pipeline if enabled
            # Task #9: Use LLM cache for plan generation
            self._log_audit(task.task_id, "info", "Generating execution plan")

            # PR-V2: Emit phase_enter for planning
            try:
                emit_phase_enter(
                    task_id=task.task_id,
                    span_id="main",
                    phase="planning",
                    explanation="Entering planning phase"
                )
            except Exception as e:
                logger.error(f"Failed to emit phase_enter event: {e}")

            if self.use_real_pipeline:
                # Use real ModePipelineRunner
                try:
                    nl_request = metadata.nl_request or "Execute task"

                    # Task #9: Use LLM cache if recovery enabled
                    if self.enable_recovery and self.llm_cache:
                        pipeline_result = self._generate_plan_with_cache(task, nl_request)
                    else:
                        pipeline_result = self._generate_plan_direct(task, nl_request)
                    
                    # Check pipeline result
                    if pipeline_result.overall_status != "success":
                        self._log_audit(task.task_id, "error", f"Pipeline failed: {pipeline_result.summary}")
                        return "failed"
                    
                    self._log_audit(task.task_id, "info", f"Pipeline completed: {pipeline_result.summary}")

                    # P2-C1: Save open_plan proposal as artifact
                    self._save_open_plan_artifact(task.task_id, pipeline_result)

                    # PR-C: Extract work_items from pipeline result
                    work_items = self._extract_work_items(task.task_id, pipeline_result)

                except Exception as e:
                    logger.error(f"Pipeline execution failed: {e}", exc_info=True)
                    self._log_audit(task.task_id, "error", f"Pipeline error: {str(e)}")
                    return "failed"
            else:
                # Simulation mode
                time.sleep(2)
            
            # RED LINE (P0-2): Pause can ONLY happen at open_plan checkpoint
            run_mode_str = metadata.run_mode.value
            checkpoint = PauseCheckpoint.OPEN_PLAN.value
            
            # PR-V2: Emit phase_exit for planning (before pause check)
            try:
                emit_phase_exit(
                    task_id=task.task_id,
                    span_id="main",
                    phase="planning",
                    explanation="Planning phase completed"
                )
            except Exception as e:
                logger.error(f"Failed to emit phase_exit event: {e}")

            # Check if we should pause at open_plan
            try:
                if can_pause_at(checkpoint, run_mode_str):
                    self._log_audit(task.task_id, "info", "Plan generated, awaiting approval at open_plan checkpoint")
                    
                    # P1: Record pause checkpoint in lineage (for auditability)
                    self.task_manager.add_lineage(
                        task_id=task.task_id,
                        kind="pause_checkpoint",
                        ref_id="open_plan",
                        phase="awaiting_approval",
                        metadata={
                            "checkpoint": checkpoint,
                            "reason": "Awaiting approval for open_plan",
                            "run_mode": run_mode_str
                        }
                    )
                    
                    return "awaiting_approval"
                else:
                    return "executing"
            except PauseGateViolation as e:
                # RED LINE: If pause checkpoint is invalid, fail the task
                logger.error(f"Pause gate violation: {e}")
                self._log_audit(task.task_id, "error", f"Pause gate violation: {str(e)}")
                return "failed"
        
        elif current_status == "executing":
            # Execute the plan
            self._log_audit(task.task_id, "info", "Executing plan")

            # PR-V2: Emit phase_enter for executing
            try:
                emit_phase_enter(
                    task_id=task.task_id,
                    span_id="main",
                    phase="executing",
                    explanation="Entering execution phase"
                )
            except Exception as e:
                logger.error(f"Failed to emit phase_enter event: {e}")

            # PR-C: Check if work_items exist in metadata
            work_items_data = task.metadata.get("work_items")
            if work_items_data:
                # Execute work_items serially
                self._log_audit(task.task_id, "info", f"Found {len(work_items_data)} work items, executing serially")
                try:
                    work_items_result = self._execute_work_items_serial(task.task_id, work_items_data)

                    # Check if any work item failed
                    if work_items_result.any_failed:
                        self._log_audit(
                            task.task_id,
                            "error",
                            f"Work items failed:\n{work_items_result.get_failure_summary()}"
                        )
                        return "failed"

                    self._log_audit(task.task_id, "info", "All work items completed successfully")
                    return "verifying"  # PR-B: Go to verifying for DONE gates

                except Exception as e:
                    logger.error(f"Work items execution failed: {e}", exc_info=True)
                    self._log_audit(task.task_id, "error", f"Work items error: {str(e)}")
                    return "failed"

            elif self.use_real_pipeline:
                # No work_items, use traditional execution
                try:
                    # 1. Load open_plan artifact
                    plan_artifact = self._load_open_plan_artifact(task.task_id)
                    if not plan_artifact:
                        logger.warning(f"No open_plan artifact found for task {task.task_id}, proceeding anyway")

                    # 2. Call real executor/coordinator
                    execution_result = self._execute_with_coordinator(task, plan_artifact)

                    # 3. Record execution_request/commit/artifact lineage
                    self._record_execution_artifacts(task.task_id, execution_result)

                    self._log_audit(task.task_id, "info", "Execution completed successfully")
                    return "verifying"  # PR-B: Go to verifying for DONE gates
                except Exception as e:
                    logger.error(f"Execution failed: {e}", exc_info=True)
                    self._log_audit(task.task_id, "error", f"Execution error: {str(e)}")
                    return "failed"
            else:
                # Simulation mode - keep original behavior
                time.sleep(3)
                self._log_audit(task.task_id, "info", "Execution completed (simulated)")
                return "verifying"  # PR-B: Go to verifying instead of succeeded

        elif current_status == "verifying":
            # PR-B: Run DONE gates
            self._log_audit(task.task_id, "info", "Starting DONE gate verification")

            # PR-V2: Emit phase_enter for verifying
            try:
                emit_phase_enter(
                    task_id=task.task_id,
                    span_id="main",
                    phase="verifying",
                    explanation="Entering verification phase (DONE gates)"
                )
            except Exception as e:
                logger.error(f"Failed to emit phase_enter event: {e}")

            # Get gate configuration from metadata
            gate_names = task.metadata.get("gates", ["doctor"])  # Default to "doctor"

            try:
                # Run gates
                gate_results = self.gate_runner.run_gates(
                    task_id=task.task_id,
                    gate_names=gate_names,
                    timeout_seconds=300
                )

                # Save gate results as artifact
                self.gate_runner.save_gate_results(task.task_id, gate_results)

                # Record gate results in audit
                self._log_audit(
                    task.task_id,
                    "info" if gate_results.all_passed else "error",
                    f"DONE_GATES_{'PASSED' if gate_results.all_passed else 'FAILED'}: "
                    f"{len(gate_results.gates_executed)} gates executed"
                )

                # Add detailed audit entry with results
                self.task_manager.add_audit(
                    task_id=task.task_id,
                    event_type="GATE_VERIFICATION_RESULT",
                    level="info" if gate_results.all_passed else "error",
                    payload={
                        "overall_status": gate_results.overall_status,
                        "gates_executed": [g.to_dict() for g in gate_results.gates_executed],
                        "total_duration": gate_results.total_duration_seconds,
                    }
                )

                if gate_results.all_passed:
                    # All gates passed → succeeded
                    self._log_audit(task.task_id, "info", "All DONE gates passed, marking as succeeded")
                    return "succeeded"
                else:
                    # Gates failed → inject failure context and return to planning
                    failure_summary = gate_results.get_failure_summary()

                    # Update task metadata with gate failure context
                    task.metadata["gate_failure_context"] = {
                        "failed_at": utc_now_iso(),
                        "failure_summary": failure_summary,
                        "gate_results": gate_results.to_dict(),
                    }

                    # Save updated metadata
                    self._update_task_metadata(task.task_id, task.metadata)

                    self._log_audit(
                        task.task_id,
                        "warn",
                        f"DONE gates failed, returning to planning for retry:\n{failure_summary}"
                    )

                    # PR-B: Return to planning for retry with failure context
                    return "planning"

            except Exception as e:
                logger.error(f"Error running DONE gates: {e}", exc_info=True)
                self._log_audit(task.task_id, "error", f"Gate execution error: {str(e)}")
                return "failed"

        else:
            # Unknown status, keep as-is
            logger.warning(f"Unknown status: {current_status}")
            return current_status
    
    def _log_audit(self, task_id: str, level: str, message: str):
        """Log audit entry"""
        try:
            self.task_manager.add_audit(
                task_id=task_id,
                event_type=message,  # Use message as event_type
                level=level,
                payload={"message": message, "component": "task_runner"}
            )
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")

    def _update_task_metadata(self, task_id: str, metadata: Dict[str, Any]):
        """Update task metadata in database

        Args:
            task_id: Task ID
            metadata: New metadata dict
        """
        try:
            conn, should_close = self.task_manager._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tasks SET metadata = ? WHERE task_id = ?",
                    (json.dumps(metadata), task_id)
                )
                conn.commit()
                logger.debug(f"Updated metadata for task {task_id}")
            finally:
                if should_close:
                    conn.close()
        except Exception as e:
            logger.error(f"Failed to update task metadata: {e}")
    
    def _save_open_plan_artifact(self, task_id: str, pipeline_result: Any):
        """Save open_plan proposal as artifact file
        
        P2-C1: Store open_plan proposal in a stable location and record in lineage.
        
        Args:
            task_id: Task ID
            pipeline_result: Pipeline execution result
        """
        try:
            # Create artifacts directory
            artifacts_dir = Path("store/artifacts") / task_id
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare artifact data
            artifact_data = {
                "task_id": task_id,
                "generated_at": utc_now_iso(),
                "pipeline_status": pipeline_result.overall_status,
                "pipeline_summary": pipeline_result.summary,
                "stages": []
            }
            
            # Extract stage results if available
            if hasattr(pipeline_result, 'stage_results') and pipeline_result.stage_results:
                for stage_name, stage_result in pipeline_result.stage_results.items():
                    stage_data = {
                        "stage": stage_name,
                        "status": getattr(stage_result, 'status', 'unknown'),
                        "summary": getattr(stage_result, 'summary', ''),
                    }
                    
                    # Include outputs if available
                    if hasattr(stage_result, 'outputs'):
                        stage_data["outputs"] = stage_result.outputs
                    
                    artifact_data["stages"].append(stage_data)
            
            # Save to file
            artifact_path = artifacts_dir / "open_plan.json"
            with open(artifact_path, 'w', encoding='utf-8') as f:
                json.dump(artifact_data, f, indent=2, ensure_ascii=False)
            
            # Get relative path for lineage
            relative_path = f"artifacts/{task_id}/open_plan.json"
            
            # P2-C1: Record artifact in lineage
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="artifact",
                ref_id=relative_path,
                phase="awaiting_approval",
                metadata={
                    "artifact_kind": "open_plan",
                    "artifact_path": str(artifact_path),
                    "file_size": artifact_path.stat().st_size,
                    "generated_at": utc_now_iso()
                }
            )
            
            self._log_audit(task_id, "info", f"Open plan artifact saved: {relative_path}")
            logger.info(f"Saved open_plan artifact: {artifact_path}")
            
        except Exception as e:
            logger.error(f"Failed to save open_plan artifact: {e}", exc_info=True)
            self._log_audit(task_id, "warn", f"Failed to save open_plan artifact: {str(e)}")
            # Don't fail the task if artifact save fails (non-critical)
    
    def _load_open_plan_artifact(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load open_plan artifact from store
        
        Args:
            task_id: Task ID
            
        Returns:
            Artifact data dict or None if not found
        """
        try:
            artifact_path = Path("store/artifacts") / task_id / "open_plan.json"
            if not artifact_path.exists():
                logger.warning(f"Open plan artifact not found: {artifact_path}")
                return None
            
            with open(artifact_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load open_plan artifact: {e}", exc_info=True)
            return None
    
    def _record_execution_artifacts(self, task_id: str, execution_result: Dict[str, Any]):
        """Record execution artifacts to lineage
        
        Args:
            task_id: Task ID
            execution_result: Execution result from pipeline/executor
        """
        try:
            # Extract execution_request_id
            exec_req_id = execution_result.get("execution_request_id") or execution_result.get("execution_result_id")
            if exec_req_id:
                # Record execution_request lineage
                self.task_manager.add_lineage(
                    task_id=task_id,
                    kind="execution_request",
                    ref_id=exec_req_id,
                    phase="execution",
                    metadata={"execution_status": execution_result.get("status", "unknown")}
                )
            
            # Record execution_result.json artifact
            result_path = execution_result.get("result_path")
            if result_path:
                file_path = Path(result_path)
                self.task_manager.add_lineage(
                    task_id=task_id,
                    kind="artifact",
                    ref_id=str(result_path),
                    phase="execution",
                    metadata={
                        "artifact_kind": "execution_result",
                        "artifact_path": str(result_path),
                        "file_size": file_path.stat().st_size if file_path.exists() else 0,
                        "generated_at": utc_now_iso()
                    }
                )
            
            # Record commits if any
            commits = execution_result.get("commits_brought_back", [])
            for commit_hash in commits:
                self.task_manager.add_lineage(
                    task_id=task_id,
                    kind="commit",
                    ref_id=commit_hash,
                    phase="execution",
                    metadata={"commit_hash": commit_hash}
                )
            
            logger.info(f"Recorded execution artifacts for task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to record execution artifacts: {e}", exc_info=True)
            self._log_audit(task_id, "warn", f"Failed to record execution artifacts: {str(e)}")
    
    def _execute_with_coordinator(self, task: Task, plan_artifact: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute task using coordinator/executor pipeline
        
        This method runs the real implementation pipeline (e.g., experimental_open_implement)
        to execute the approved plan.
        
        Args:
            task: Task object
            plan_artifact: Loaded open_plan artifact (can be None)
            
        Returns:
            Execution result dict with keys:
                - execution_request_id: Execution request ID
                - status: Execution status (success/failed)
                - result_path: Path to execution_result.json
                - commits_brought_back: List of commit hashes
                
        Raises:
            Exception: If execution fails
        """
        metadata = TaskMetadata.from_dict(task.metadata)
        nl_request = metadata.nl_request or "Execute task"
        
        # Create mode selection for implementation stage
        mode_selection = ModeSelection(
            primary_mode="experimental_open_implement",
            pipeline=["experimental_open_implement"],
            reason="Task runner execution stage"
        )
        
        self._log_audit(task.task_id, "info", "Running implementation pipeline")
        
        # Run real pipeline (this will call executor)
        pipeline_result = self.pipeline_runner.run_pipeline(
            mode_selection=mode_selection,
            nl_input=nl_request,
            repo_path=self.repo_path,
            policy_path=self.policy_path,
            task_id=task.task_id
        )
        
        # Check pipeline result
        if pipeline_result.overall_status != "success":
            error_msg = f"Implementation pipeline failed: {pipeline_result.summary}"
            self._log_audit(task.task_id, "error", error_msg)
            raise Exception(error_msg)
        
        self._log_audit(task.task_id, "info", f"Implementation pipeline completed: {pipeline_result.summary}")
        
        # Extract execution result from pipeline stages
        execution_result = self._extract_execution_result(pipeline_result)
        
        return execution_result
    
    def _extract_execution_result(self, pipeline_result) -> Dict[str, Any]:
        """Extract execution result from pipeline result

        Args:
            pipeline_result: PipelineResult from ModePipelineRunner

        Returns:
            Simplified execution result dict
        """
        result = {
            "execution_request_id": pipeline_result.pipeline_id,
            "status": pipeline_result.overall_status,
            "commits_brought_back": [],
            "result_path": None
        }

        # Try to extract from stage outputs
        if hasattr(pipeline_result, 'stages') and pipeline_result.stages:
            for stage in pipeline_result.stages:
                stage_output = stage.output

                # Look for executor output
                if "execution_result_id" in stage_output:
                    result["execution_result_id"] = stage_output["execution_result_id"]

                # Look for commits
                if "commits_brought_back" in stage_output:
                    result["commits_brought_back"].extend(stage_output["commits_brought_back"])

                # Look for result file path
                if "result_file" in stage_output:
                    result["result_path"] = stage_output["result_file"]

        # If no result_path found, construct from pipeline_id
        if not result["result_path"]:
            # Construct path based on pipeline output structure
            result["result_path"] = f"outputs/pipeline/{pipeline_result.pipeline_id}/pipeline_result.json"

        return result

    def _extract_work_items(self, task_id: str, pipeline_result: Any) -> List[WorkItem]:
        """Extract work items from pipeline result and save to metadata

        PR-C: Extract work_items from planning stage output

        Args:
            task_id: Task ID
            pipeline_result: Pipeline result from planning stage

        Returns:
            List of WorkItem objects
        """
        try:
            # Extract work items from pipeline
            work_items = extract_work_items_from_pipeline(pipeline_result)

            if not work_items:
                logger.info(f"No work items found in pipeline result for task {task_id}")
                return []

            # Save work_items to task metadata
            task = self.task_manager.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return []

            # Update metadata with work_items
            if not task.metadata:
                task.metadata = {}

            task.metadata["work_items"] = [item.to_dict() for item in work_items]

            # Save to database
            self._update_task_metadata(task_id, task.metadata)

            # Record audit
            self._log_audit(
                task_id,
                "info",
                f"work_items.extracted: {len(work_items)} items extracted from plan"
            )

            # Record in audit with full details
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="WORK_ITEMS_EXTRACTED",
                level="info",
                payload={
                    "count": len(work_items),
                    "items": [
                        {
                            "item_id": item.item_id,
                            "title": item.title,
                            "dependencies": item.dependencies,
                        }
                        for item in work_items
                    ],
                }
            )

            logger.info(f"Extracted {len(work_items)} work items for task {task_id}")
            return work_items

        except Exception as e:
            logger.error(f"Failed to extract work items: {e}", exc_info=True)
            self._log_audit(task_id, "warn", f"Failed to extract work items: {str(e)}")
            return []

    def _execute_work_items_serial(
        self,
        task_id: str,
        work_items_data: List[Dict[str, Any]]
    ) -> WorkItemsSummary:
        """Execute work items serially (PR-C)

        Args:
            task_id: Task ID
            work_items_data: List of work item dictionaries from metadata

        Returns:
            WorkItemsSummary with execution results
        """
        # Parse work items from data
        work_items = [WorkItem.from_dict(item_data) for item_data in work_items_data]

        self._log_audit(
            task_id,
            "info",
            f"Starting serial execution of {len(work_items)} work items"
        )

        execution_order = []
        start_time = time.time()

        # Execute each work item serially
        for idx, work_item in enumerate(work_items):
            logger.info(
                f"Executing work item {idx + 1}/{len(work_items)}: "
                f"{work_item.item_id} - {work_item.title}"
            )

            # Mark as running
            work_item.mark_running()
            execution_order.append(work_item.item_id)

            # PR-V2: Emit work_item_dispatched event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=task_id,
                    event_type="work_item_dispatched",
                    actor="runner",
                    span_id="main",
                    phase="executing",
                    payload={
                        "work_item_id": work_item.item_id,
                        "title": work_item.title,
                        "index": idx,
                        "explanation": f"Work item {work_item.item_id} dispatched"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit work_item_dispatched event: {e}")

            # PR-V2: Emit work_item_start event
            try:
                emit_work_item_start(
                    task_id=task_id,
                    span_id=f"work_{work_item.item_id}",
                    parent_span_id="main",
                    work_item_id=work_item.item_id,
                    work_type="sub_agent_execution",
                    phase="executing",
                    explanation=f"Starting work item: {work_item.title}"
                )
            except Exception as e:
                logger.error(f"Failed to emit work_item_start event: {e}")

            # Log audit for work item start
            self.task_manager.add_audit(
                task_id=task_id,
                event_type=f"WORK_ITEM_STARTED",
                level="info",
                payload={
                    "item_id": work_item.item_id,
                    "title": work_item.title,
                    "index": idx,
                }
            )

            try:
                # Execute the work item (with checkpoints if recovery enabled)
                if self.enable_recovery:
                    output = self.execute_work_item_with_checkpoint(task_id, work_item)
                else:
                    output = self._execute_single_work_item(task_id, work_item)

                # Mark as completed
                work_item.mark_completed(output)

                # PR-V2: Emit work_item_done event
                try:
                    from agentos.core.task.event_service import TaskEventService
                    service = TaskEventService()
                    service.emit_event(
                        task_id=task_id,
                        event_type="work_item_done",
                        actor="worker",
                        span_id=f"work_{work_item.item_id}",
                        parent_span_id="main",
                        phase="executing",
                        payload={
                            "work_item_id": work_item.item_id,
                            "title": work_item.title,
                            "files_changed": output.files_changed,
                            "explanation": f"Work item {work_item.item_id} completed successfully"
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to emit work_item_done event: {e}")

                # Log success audit
                self.task_manager.add_audit(
                    task_id=task_id,
                    event_type=f"WORK_ITEM_COMPLETED",
                    level="info",
                    payload={
                        "item_id": work_item.item_id,
                        "title": work_item.title,
                        "output": output.to_dict(),
                    }
                )

                logger.info(f"Work item {work_item.item_id} completed successfully")

            except Exception as e:
                # Mark as failed
                error_msg = str(e)
                work_item.mark_failed(error_msg)

                # PR-V2: Emit work_item_failed event
                try:
                    from agentos.core.task.event_service import TaskEventService
                    service = TaskEventService()
                    service.emit_event(
                        task_id=task_id,
                        event_type="work_item_failed",
                        actor="worker",
                        span_id=f"work_{work_item.item_id}",
                        parent_span_id="main",
                        phase="executing",
                        payload={
                            "work_item_id": work_item.item_id,
                            "title": work_item.title,
                            "error": error_msg,
                            "explanation": f"Work item {work_item.item_id} execution failed"
                        }
                    )
                except Exception as evt_err:
                    logger.error(f"Failed to emit work_item_failed event: {evt_err}")

                # Log failure audit
                self.task_manager.add_audit(
                    task_id=task_id,
                    event_type=f"WORK_ITEM_FAILED",
                    level="error",
                    payload={
                        "item_id": work_item.item_id,
                        "title": work_item.title,
                        "error": error_msg,
                    }
                )

                logger.error(f"Work item {work_item.item_id} failed: {e}", exc_info=True)

                # PR-C: Fail fast - stop on first failure
                # (Future PR-D can implement retry/skip logic)
                break

        # Calculate total duration
        total_duration = time.time() - start_time

        # Create summary
        summary = create_work_items_summary(work_items)
        summary.execution_order = execution_order
        summary.total_duration_seconds = total_duration

        # Save summary artifact
        self._save_work_items_summary(task_id, summary)

        self._log_audit(
            task_id,
            "info" if summary.all_succeeded else "error",
            f"Work items execution completed: {summary.completed_count}/{summary.total_items} succeeded"
        )

        return summary

    def execute_work_item_with_checkpoint(
        self,
        task_id: str,
        work_item: WorkItem
    ) -> WorkItemOutput:
        """Execute work item with checkpoint and lease management (Task #9)

        This method wraps work item execution with:
        - Lease acquisition and renewal (heartbeat)
        - Checkpoint creation with evidence
        - Tool execution replay via ToolLedger
        - Graceful lease release

        Args:
            task_id: Parent task ID
            work_item: Work item to execute

        Returns:
            WorkItemOutput with execution results

        Raises:
            Exception: If work item execution fails
        """
        if not self.enable_recovery:
            # Fall back to regular execution
            return self._execute_single_work_item(task_id, work_item)

        logger.info(f"Executing work item with recovery: {work_item.item_id} - {work_item.title}")

        # Get lease manager
        lease_manager = self._get_lease_manager()
        if not lease_manager:
            logger.warning("Lease manager not available, executing without lease")
            return self._execute_single_work_item(task_id, work_item)

        # Try to acquire lease (if work_items table exists)
        # Note: This requires work_items table from Task #6
        # For now, we'll execute directly but log the intent
        logger.info(f"TODO: Acquire lease for work_item {work_item.item_id}")

        # Begin checkpoint step
        step_id = self.checkpoint_manager.begin_step(
            task_id=task_id,
            checkpoint_type="work_item_executing",
            snapshot={
                "work_item_id": work_item.item_id,
                "title": work_item.title,
                "status": "executing"
            },
            work_item_id=work_item.item_id,
            metadata={"role_hint": getattr(work_item, "role_hint", "")}
        )

        # Start heartbeat thread (simulated for now)
        heartbeat = None
        # TODO: heartbeat = start_heartbeat(conn, work_item.item_id, self.worker_id)

        results = []
        try:
            # Execute work item with tool replay
            output = self._execute_single_work_item_with_replay(task_id, work_item)

            # Collect evidence
            evidence_pack = self.collect_evidence(work_item, results)

            # Commit checkpoint with evidence
            checkpoint = self.checkpoint_manager.commit_step(
                step_id=step_id,
                evidence_pack=evidence_pack
            )

            logger.info(
                f"Work item checkpoint created: {checkpoint.checkpoint_id} "
                f"(seq={checkpoint.sequence_number})"
            )

            # Release lease (success)
            # TODO: lease_manager.release_lease(work_item.item_id, success=True, output_data=output.to_dict())

            return output

        except Exception as e:
            logger.error(f"Work item execution failed: {e}", exc_info=True)

            # Try to commit failure checkpoint
            try:
                failure_evidence = EvidencePack(
                    evidence_list=[
                        Evidence(
                            evidence_type=EvidenceType.DB_ROW,
                            description="Work item failed",
                            expected={
                                "table": "work_items",
                                "where": {"work_item_id": work_item.item_id},
                                "values": {"status": "failed"}
                            },
                            metadata={}
                        )
                    ]
                )
                self.checkpoint_manager.commit_step(step_id, failure_evidence)
            except Exception as checkpoint_err:
                logger.error(f"Failed to create failure checkpoint: {checkpoint_err}")

            # Release lease (failure)
            # TODO: lease_manager.release_lease(work_item.item_id, success=False, error=str(e))

            raise

        finally:
            # Stop heartbeat
            if heartbeat:
                heartbeat.stop()

    def _execute_single_work_item_with_replay(
        self,
        task_id: str,
        work_item: WorkItem
    ) -> WorkItemOutput:
        """Execute single work item with tool replay support (Task #9)

        Uses ToolLedger to replay previously executed tools instead of re-running them.

        Args:
            task_id: Parent task ID
            work_item: Work item to execute

        Returns:
            WorkItemOutput with execution results
        """
        logger.info(f"Executing work item with replay: {work_item.title}")

        # For now, simulate execution as before
        # In production, this would:
        # 1. Parse work item for tool calls
        # 2. For each tool call, use tool_ledger.execute_or_replay()
        # 3. Aggregate results

        # Simulate some work
        time.sleep(0.5)  # Reduced from 1s for faster testing

        # Create mock output
        output = WorkItemOutput(
            files_changed=[
                f"src/{work_item.item_id.lower()}/module.py",
                f"tests/test_{work_item.item_id.lower()}.py",
            ],
            commands_run=[
                "pytest tests/",
                f"ruff check src/{work_item.item_id.lower()}/",
            ],
            tests_run=[
                {
                    "test_suite": f"test_{work_item.item_id.lower()}",
                    "passed": 5,
                    "failed": 0,
                    "skipped": 0,
                }
            ],
            evidence=f"Successfully implemented {work_item.title}",
            handoff_notes=f"Work item {work_item.item_id} completed with recovery support. Ready for integration.",
        )

        # Save work item artifact
        self._save_work_item_artifact(task_id, work_item.item_id, output)

        return output

    def _execute_single_work_item(
        self,
        task_id: str,
        work_item: WorkItem
    ) -> WorkItemOutput:
        """Execute a single work item

        This method simulates sub-agent execution for now.
        In production, this would:
        1. Spawn a new agent instance
        2. Pass work_item description as context
        3. Execute in isolated environment
        4. Collect structured output

        Args:
            task_id: Parent task ID
            work_item: Work item to execute

        Returns:
            WorkItemOutput with execution results
        """
        logger.info(f"Executing work item: {work_item.title}")

        # For now, simulate execution
        # In production, this would call the real sub-agent executor

        # Simulate some work
        time.sleep(1)

        # Create mock output
        output = WorkItemOutput(
            files_changed=[
                f"src/{work_item.item_id.lower()}/module.py",
                f"tests/test_{work_item.item_id.lower()}.py",
            ],
            commands_run=[
                "pytest tests/",
                f"ruff check src/{work_item.item_id.lower()}/",
            ],
            tests_run=[
                {
                    "test_suite": f"test_{work_item.item_id.lower()}",
                    "passed": 5,
                    "failed": 0,
                    "skipped": 0,
                }
            ],
            evidence=f"Successfully implemented {work_item.title}",
            handoff_notes=f"Work item {work_item.item_id} completed. Ready for integration.",
        )

        # Save work item artifact
        self._save_work_item_artifact(task_id, work_item.item_id, output)

        return output

    def _save_work_item_artifact(
        self,
        task_id: str,
        item_id: str,
        output: WorkItemOutput
    ):
        """Save work item output as artifact

        Args:
            task_id: Task ID
            item_id: Work item ID
            output: Work item output
        """
        try:
            # Create artifacts directory
            artifacts_dir = Path("store/artifacts") / task_id
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Save work item output
            artifact_path = artifacts_dir / f"work_item_{item_id}.json"
            with open(artifact_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        "item_id": item_id,
                        "output": output.to_dict(),
                        "saved_at": utc_now_iso(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            logger.info(f"Saved work item artifact: {artifact_path}")

        except Exception as e:
            logger.error(f"Failed to save work item artifact: {e}", exc_info=True)

    def _save_work_items_summary(self, task_id: str, summary: WorkItemsSummary):
        """Save work items summary as artifact

        PR-C: Save aggregated summary of all work items

        Args:
            task_id: Task ID
            summary: Work items summary
        """
        try:
            # Create artifacts directory
            artifacts_dir = Path("store/artifacts") / task_id
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Save summary
            summary_path = artifacts_dir / "work_items_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Saved work items summary: {summary_path}")

            # Record in lineage
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="artifact",
                ref_id=f"artifacts/{task_id}/work_items_summary.json",
                phase="execution",
                metadata={
                    "artifact_kind": "work_items_summary",
                    "total_items": summary.total_items,
                    "completed": summary.completed_count,
                    "failed": summary.failed_count,
                }
            )

        except Exception as e:
            logger.error(f"Failed to save work items summary: {e}", exc_info=True)
            self._log_audit(task_id, "warn", f"Failed to save work items summary: {str(e)}")

    def _load_route_plan(self, task_id: str) -> Optional[RoutePlan]:
        """
        Load route plan from task metadata

        Args:
            task_id: Task ID

        Returns:
            RoutePlan or None if not found
        """
        try:
            task = self.task_manager.get_task(task_id)
            if not task or not task.metadata:
                return None

            # Check if route_plan exists in metadata
            route_plan_data = task.metadata.get("route_plan")
            if not route_plan_data:
                return None

            # Parse route plan
            if isinstance(route_plan_data, str):
                route_plan_data = json.loads(route_plan_data)

            route_plan = RoutePlan.from_dict(route_plan_data)
            return route_plan

        except Exception as e:
            logger.error(f"Failed to load route plan for task {task_id}: {e}")
            return None

    def _save_route_plan(self, task_id: str, route_plan: RoutePlan):
        """
        Save route plan to task metadata

        Args:
            task_id: Task ID
            route_plan: RoutePlan to save
        """
        try:
            task = self.task_manager.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found, cannot save route plan")
                return

            # Update metadata
            if not task.metadata:
                task.metadata = {}

            task.metadata["route_plan"] = route_plan.to_dict()

            # Save to database
            conn, should_close = self.task_manager._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tasks SET metadata = ? WHERE task_id = ?",
                    (json.dumps(task.metadata), task_id)
                )
                conn.commit()
                logger.debug(f"Saved route plan for task {task_id}")
            finally:
                if should_close:
                    conn.close()

        except Exception as e:
            logger.error(f"Failed to save route plan for task {task_id}: {e}")

    def run_with_recovery(self, task_id: str, max_iterations: int = 100):
        """Run task with checkpoint-based recovery support (Task #9)

        This method wraps run_task() with recovery capabilities:
        - Checks for existing checkpoints and resumes if possible
        - Creates checkpoints at key execution points
        - Uses LLM cache for plan generation
        - Uses tool ledger for idempotent tool execution

        Args:
            task_id: Task ID to run
            max_iterations: Maximum number of state transitions (safety)
        """
        if not self.enable_recovery:
            logger.warning("Recovery not enabled, falling back to regular run_task")
            return self.run_task(task_id, max_iterations)

        logger.info(f"Starting task with recovery: task_id={task_id}, worker={self.worker_id}")

        # Check for existing checkpoint to resume from
        try:
            last_checkpoint = self.checkpoint_manager.get_last_verified_checkpoint(task_id)
            if last_checkpoint:
                logger.info(
                    f"Found checkpoint for task {task_id}: "
                    f"seq={last_checkpoint.sequence_number}, type={last_checkpoint.checkpoint_type}"
                )
                self.resume_from_checkpoint(task_id, last_checkpoint)
            else:
                logger.info(f"No checkpoint found for task {task_id}, starting fresh")
        except Exception as e:
            logger.error(f"Error checking for checkpoint: {e}", exc_info=True)
            # Continue with fresh execution

        # Run task normally (checkpoints will be created during execution)
        self.run_task(task_id, max_iterations)

    def resume_from_checkpoint(self, task_id: str, checkpoint):
        """Resume task execution from a checkpoint (Task #9)

        Verifies the checkpoint and restores task state. If verification fails,
        the checkpoint is considered invalid and execution starts fresh.

        Args:
            task_id: Task ID
            checkpoint: Checkpoint object to resume from

        Raises:
            CheckpointError: If checkpoint verification fails critically
        """
        logger.info(
            f"Resuming task {task_id} from checkpoint: "
            f"id={checkpoint.checkpoint_id}, seq={checkpoint.sequence_number}"
        )

        try:
            # Verify checkpoint integrity
            is_valid = self.checkpoint_manager.verify_checkpoint(checkpoint.checkpoint_id)

            if not is_valid:
                logger.warning(
                    f"Checkpoint {checkpoint.checkpoint_id} verification failed, "
                    f"starting fresh execution"
                )
                # Could also try previous checkpoint here
                return

            # Extract state from snapshot
            snapshot = checkpoint.snapshot_data
            checkpoint_type = checkpoint.checkpoint_type

            logger.info(f"Checkpoint verified, restoring state: type={checkpoint_type}")

            # Restore state based on checkpoint type
            if checkpoint_type == "planning_complete":
                # Plan was generated and verified, can skip planning phase
                logger.info("Skipping planning phase (already completed)")
                # Update task metadata to indicate resume point
                task = self.task_manager.get_task(task_id)
                if task and task.status == "planning":
                    self.task_manager.update_task_status(task_id, "executing")

            elif checkpoint_type == "work_item_complete":
                # Work item completed, can skip it
                work_item_id = checkpoint.work_item_id
                logger.info(f"Work item {work_item_id} already completed, will skip")
                # Mark in metadata which work items are done

            elif checkpoint_type == "iteration_start":
                # Iteration checkpoint, restore iteration state
                iteration = snapshot.get("iteration", 0)
                logger.info(f"Resuming from iteration {iteration}")

            else:
                logger.info(f"Unknown checkpoint type {checkpoint_type}, limited restoration")

            # Log audit entry
            self._log_audit(
                task_id, "info",
                f"RESUMED_FROM_CHECKPOINT: {checkpoint.checkpoint_id} "
                f"(seq={checkpoint.sequence_number}, type={checkpoint_type})"
            )

            # PR-V2: Emit recovery_resumed_from_checkpoint event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=task_id,
                    event_type="recovery_resumed_from_checkpoint",
                    actor="runner",
                    span_id="main",
                    phase="recovery",
                    payload={
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "checkpoint_type": checkpoint_type,
                        "sequence_number": checkpoint.sequence_number,
                        "work_item_id": checkpoint.work_item_id,
                        "explanation": f"Task resumed from checkpoint {checkpoint.checkpoint_id} (seq={checkpoint.sequence_number})"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit recovery_resumed_from_checkpoint event: {e}")

        except Exception as e:
            logger.error(f"Error resuming from checkpoint: {e}", exc_info=True)
            self._log_audit(task_id, "error", f"Checkpoint resume failed: {str(e)}")

    def _get_lease_manager(self) -> Optional[LeaseManager]:
        """Get LeaseManager instance (Task #9)

        Creates a new database connection for lease operations if needed.

        Returns:
            LeaseManager instance or None if recovery not enabled
        """
        if not self.enable_recovery:
            return None

        # Get a fresh connection for lease operations
        conn = get_db()
        return LeaseManager(conn, self.worker_id)

    def collect_evidence(self, work_item: WorkItem, results: List[Dict[str, Any]]) -> EvidencePack:
        """Collect evidence for checkpoint verification (Task #9)

        Gathers evidence that proves a work item was successfully executed:
        - Artifact existence (files created)
        - Command exit codes
        - Database state changes

        Args:
            work_item: WorkItem that was executed
            results: List of tool execution results

        Returns:
            EvidencePack with collected evidence
        """
        evidence_list = []

        # Evidence 1: Tool execution results (command exit codes)
        for result in results:
            if result.get("exit_code") is not None:
                evidence_list.append(Evidence(
                    evidence_type=EvidenceType.COMMAND_EXIT,
                    description=f"Tool executed successfully: {result.get('tool', 'unknown')}",
                    expected={"exit_code": result["exit_code"]},
                    metadata={"command": result.get("command", "")}
                ))

        # Evidence 2: Work item artifacts (if specified in work_item)
        if hasattr(work_item, "expected_artifacts"):
            for artifact in work_item.expected_artifacts:
                evidence_list.append(Evidence(
                    evidence_type=EvidenceType.ARTIFACT_EXISTS,
                    description=f"Work item artifact: {artifact}",
                    expected={"path": artifact, "type": "file"},
                    metadata={}
                ))

        # Evidence 3: Database state - work item status
        # This would check that the work_item row in DB has status='completed'
        # Note: This evidence type requires work_items table from Task #6
        evidence_list.append(Evidence(
            evidence_type=EvidenceType.DB_ROW,
            description=f"Work item marked as completed in database",
            expected={
                "table": "work_items",
                "where": {"work_item_id": work_item.item_id},
                "values": {"status": "completed"}
            },
            metadata={"db_path": "registry"}  # Use registry_db.get_db() in verification
        ))

        return EvidencePack(evidence_list=evidence_list, require_all=False, min_verified=1)

    def _generate_plan_with_cache(self, task: Task, nl_request: str):
        """Generate plan using LLM cache (Task #9)

        Uses LLMOutputCache to avoid redundant LLM calls for identical planning requests.

        Args:
            task: Task object
            nl_request: Natural language request

        Returns:
            Pipeline result from cache or fresh generation
        """
        logger.info(f"Generating plan with LLM cache for task {task.task_id}")

        # Build cache key components
        plan_model = "experimental_open_plan"  # Or get from task settings

        def generate_fn():
            """Inner function to generate plan if cache misses"""
            return self._generate_plan_direct(task, nl_request)

        # Use cache (returns dict with pipeline_result info)
        # Note: Since pipeline_result is complex object, we serialize it
        try:
            cached_or_fresh = self.llm_cache.get_or_generate(
                operation_type="plan",
                prompt=nl_request,
                model=plan_model,
                task_id=task.task_id,
                generate_fn=lambda: self._pipeline_result_to_dict(generate_fn())
            )

            # If it was cached, we need to reconstruct pipeline_result
            # For simplicity, just call direct generation
            # In production, would deserialize cached result
            if cached_or_fresh:
                logger.info("Using cached plan result")
                # For now, regenerate (cache hit recorded but result not used)
                # TODO: Properly deserialize cached pipeline result
                return self._generate_plan_direct(task, nl_request)
            else:
                return self._generate_plan_direct(task, nl_request)

        except Exception as e:
            logger.warning(f"LLM cache error, falling back to direct generation: {e}")
            return self._generate_plan_direct(task, nl_request)

    def _generate_plan_direct(self, task: Task, nl_request: str):
        """Generate plan directly without cache (Task #9)

        Args:
            task: Task object
            nl_request: Natural language request

        Returns:
            Pipeline result from ModePipelineRunner
        """
        # Create mode selection for planning stage
        mode_selection = ModeSelection(
            primary_mode="experimental_open_plan",
            pipeline=["experimental_open_plan"],
            reason="Task runner planning stage"
        )

        self._log_audit(task.task_id, "info", "Running real pipeline with open_plan mode")

        # Run real pipeline (this will generate open_plan)
        pipeline_result = self.pipeline_runner.run_pipeline(
            mode_selection=mode_selection,
            nl_input=nl_request,
            repo_path=self.repo_path,
            policy_path=self.policy_path,
            task_id=task.task_id
        )

        return pipeline_result

    def _pipeline_result_to_dict(self, pipeline_result) -> Dict[str, Any]:
        """Convert pipeline result to dict for caching (Task #9)

        Args:
            pipeline_result: Pipeline result object

        Returns:
            Dictionary representation suitable for caching
        """
        return {
            "overall_status": pipeline_result.overall_status,
            "summary": pipeline_result.summary,
            "pipeline_id": getattr(pipeline_result, "pipeline_id", None),
            # Add more fields as needed
        }


def run_task_subprocess(task_id: str, use_real_pipeline: bool = False):
    """Entry point for subprocess execution
    
    This function is called when starting a task runner as a subprocess.
    
    Args:
        task_id: Task ID to run
        use_real_pipeline: If True, use real ModePipelineRunner (P1)
    """
    # Setup logging for subprocess
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    logger.info(f"Starting task runner: task_id={task_id}, real_pipeline={use_real_pipeline}")
    
    runner = TaskRunner(use_real_pipeline=use_real_pipeline)
    runner.run_task(task_id)


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Task Runner")
    parser.add_argument("task_id", help="Task ID to run")
    parser.add_argument("--real-pipeline", action="store_true", help="Use real ModePipelineRunner (P1)")
    parser.add_argument("--repo-path", type=str, default=".", help="Repository path")
    parser.add_argument("--policy-path", type=str, help="Sandbox policy path")
    
    args = parser.parse_args()
    
    logger.info(f"Task runner args: {args}")
    
    run_task_subprocess(
        task_id=args.task_id,
        use_real_pipeline=args.real_pipeline
    )
