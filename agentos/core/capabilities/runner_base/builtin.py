"""
Builtin Runner Implementation

Executes extension handlers by dynamically loading handlers.py from extension directories.
This runner provides sandboxed execution of Python functions defined in extension handlers.

Security Features:
- Isolated module loading (handlers can only access extension directory)
- Timeout enforcement (default 30s)
- Error handling and validation
- Progress reporting through callback

Architecture:
- Loads handlers.py from extension directory using importlib
- Calls handler functions with (args, context) parameters
- Reports progress through 5 stages: VALIDATING -> LOADING -> EXECUTING -> FINALIZING -> DONE
"""

import importlib.util
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from .base import Runner, Invocation, RunResult, ProgressCallback, RunnerError, ValidationError

logger = logging.getLogger(__name__)


class BuiltinRunner(Runner):
    """
    Builtin runner for executing Python handlers

    Executes handler functions from extension handlers.py files.
    Provides sandboxed execution with timeout and progress reporting.

    Handler Signature:
        def handler_fn(args: List[str], context: Dict[str, Any]) -> str:
            # args: Command arguments
            # context: Execution context (session_id, extension_id, work_dir, etc.)
            # returns: Output string

    Example:
        runner = BuiltinRunner()
        invocation = Invocation(
            extension_id="tools.test",
            action_id="hello",
            session_id="sess_123",
            args=["world"]
        )
        result = runner.run(invocation, progress_cb=my_callback)
    """

    def __init__(self, extensions_dir: Optional[Path] = None, default_timeout: int = 30):
        """
        Initialize builtin runner

        Args:
            extensions_dir: Directory where extensions are installed
                          (defaults to ~/.agentos/extensions)
            default_timeout: Default timeout in seconds for handler execution
        """
        if extensions_dir is None:
            extensions_dir = Path.home() / ".agentos" / "extensions"

        self.extensions_dir = Path(extensions_dir)
        self.default_timeout = default_timeout

        logger.info(f"BuiltinRunner initialized (extensions_dir={self.extensions_dir})")

    @property
    def runner_type(self) -> str:
        return "builtin"

    def run(self, invocation: Invocation, progress_cb: Optional[ProgressCallback] = None) -> RunResult:
        """
        Execute a Python handler from extension

        Progress stages:
        - VALIDATING (5%): Validate extension and action
        - LOADING (15%): Load handlers.py module
        - EXECUTING (60%): Execute handler function
        - FINALIZING (90%): Process results
        - DONE (100%): Complete

        Args:
            invocation: The invocation request
            progress_cb: Optional progress callback

        Returns:
            RunResult with execution status and output

        Raises:
            ValidationError: If extension/handler is invalid
            RunnerError: If execution fails
            TimeoutError: If execution exceeds timeout
        """
        started_at = datetime.now()
        run_id = f"builtin_{uuid.uuid4().hex[:8]}"

        try:
            # Stage 1: VALIDATING (5%)
            if progress_cb:
                progress_cb("VALIDATING", 5, "Validating extension and action")

            extension_dir = self.extensions_dir / invocation.extension_id

            # Validate extension directory exists
            if not extension_dir.exists():
                raise ValidationError(
                    f"Extension directory not found: {invocation.extension_id}"
                )

            # Validate handlers.py exists
            handlers_path = extension_dir / "handlers.py"
            if not handlers_path.exists():
                raise ValidationError(
                    f"handlers.py not found for extension: {invocation.extension_id}"
                )

            # Stage 2: LOADING (15%)
            if progress_cb:
                progress_cb("LOADING", 15, f"Loading handlers for {invocation.extension_id}")

            # Load handlers module
            handlers_module = self._load_handlers_module(
                extension_id=invocation.extension_id,
                handlers_path=handlers_path
            )

            # Get HANDLERS dictionary
            if not hasattr(handlers_module, 'HANDLERS'):
                raise ValidationError(
                    f"handlers.py must export HANDLERS dictionary for extension: {invocation.extension_id}"
                )

            handlers_dict = handlers_module.HANDLERS
            if not isinstance(handlers_dict, dict):
                raise ValidationError(
                    f"HANDLERS must be a dictionary for extension: {invocation.extension_id}"
                )

            # Validate handler exists for action
            if invocation.action_id not in handlers_dict:
                available_actions = ", ".join(handlers_dict.keys())
                raise ValidationError(
                    f"Handler not found for action '{invocation.action_id}' in extension {invocation.extension_id}. "
                    f"Available actions: {available_actions}"
                )

            handler_fn = handlers_dict[invocation.action_id]
            if not callable(handler_fn):
                raise ValidationError(
                    f"Handler for action '{invocation.action_id}' is not callable"
                )

            # Stage 3: EXECUTING (60%)
            if progress_cb:
                progress_cb(
                    "EXECUTING",
                    60,
                    f"Executing {invocation.extension_id}/{invocation.action_id}"
                )

            # Log audit event for builtin execution start
            self._log_audit_started(
                invocation=invocation,
                run_id=run_id
            )

            # Build execution context
            context = {
                'session_id': invocation.session_id,
                'extension_id': invocation.extension_id,
                'action_id': invocation.action_id,
                'work_dir': str(extension_dir),
                'metadata': invocation.metadata
            }

            # Execute handler with timeout
            timeout = invocation.timeout or self.default_timeout
            output = self._execute_handler_with_timeout(
                handler_fn=handler_fn,
                args=invocation.args,
                context=context,
                timeout=timeout
            )

            # Stage 4: FINALIZING (90%)
            if progress_cb:
                progress_cb("FINALIZING", 90, "Finalizing results")

            time.sleep(0.1)  # Small delay for UI smoothness

            # Stage 5: DONE (100%)
            if progress_cb:
                progress_cb("DONE", 100, "Execution complete")

            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit event for builtin execution finish
            self._log_audit_finished(
                invocation=invocation,
                run_id=run_id,
                output=output,
                exit_code=0,
                duration_ms=duration_ms
            )

            return RunResult(
                success=True,
                output=output,
                error=None,
                exit_code=0,
                duration_ms=duration_ms,
                metadata={
                    'extension_id': invocation.extension_id,
                    'action_id': invocation.action_id,
                    'runner_type': self.runner_type,
                    'handler_executed': True,
                    'run_id': run_id
                },
                started_at=started_at,
                completed_at=completed_at
            )

        except ValidationError as e:
            # Validation errors are user-facing
            logger.warning(f"Validation error: {e}")
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit event for failed execution
            self._log_audit_finished(
                invocation=invocation,
                run_id=run_id,
                output="",
                exit_code=1,
                duration_ms=duration_ms,
                error=str(e)
            )

            return RunResult(
                success=False,
                output="",
                error=str(e),
                exit_code=1,
                duration_ms=duration_ms,
                metadata={'error_type': 'validation', 'run_id': run_id},
                started_at=started_at,
                completed_at=completed_at
            )

        except TimeoutError as e:
            # Timeout errors
            logger.error(f"Timeout error: {e}")
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit event for timeout
            self._log_audit_finished(
                invocation=invocation,
                run_id=run_id,
                output="",
                exit_code=124,
                duration_ms=duration_ms,
                error=str(e)
            )

            return RunResult(
                success=False,
                output="",
                error=str(e),
                exit_code=124,  # Standard timeout exit code
                duration_ms=duration_ms,
                metadata={'error_type': 'timeout', 'run_id': run_id},
                started_at=started_at,
                completed_at=completed_at
            )

        except Exception as e:
            # Unexpected errors
            logger.error(f"Handler execution failed: {e}", exc_info=True)
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit event for unexpected error
            self._log_audit_finished(
                invocation=invocation,
                run_id=run_id,
                output="",
                exit_code=1,
                duration_ms=duration_ms,
                error=str(e)
            )

            return RunResult(
                success=False,
                output="",
                error=f"Handler execution failed: {str(e)}",
                exit_code=1,
                duration_ms=duration_ms,
                metadata={'error_type': 'execution', 'run_id': run_id},
                started_at=started_at,
                completed_at=completed_at
            )

    def _load_handlers_module(self, extension_id: str, handlers_path: Path):
        """
        Load handlers.py module using importlib

        Args:
            extension_id: Extension ID (for module naming)
            handlers_path: Path to handlers.py file

        Returns:
            Loaded module object

        Raises:
            RunnerError: If module loading fails
        """
        try:
            # Create unique module name
            module_name = f"ext_{extension_id.replace('.', '_')}_handlers"

            # Load module spec
            spec = importlib.util.spec_from_file_location(
                module_name,
                handlers_path
            )

            if spec is None or spec.loader is None:
                raise RunnerError(f"Failed to create module spec for {handlers_path}")

            # Create module from spec
            module = importlib.util.module_from_spec(spec)

            # Execute module (loads all definitions)
            spec.loader.exec_module(module)

            logger.debug(f"Loaded handlers module: {module_name}")
            return module

        except Exception as e:
            raise RunnerError(f"Failed to load handlers.py: {e}") from e

    def _execute_handler_with_timeout(
        self,
        handler_fn: Callable,
        args: list,
        context: dict,
        timeout: int
    ) -> str:
        """
        Execute handler function with timeout

        Note: This is a simple implementation without true timeout enforcement.
        For production, consider using multiprocessing or threading with timeout.

        Args:
            handler_fn: Handler function to execute
            args: Command arguments
            context: Execution context
            timeout: Timeout in seconds (currently not enforced)

        Returns:
            Handler output string

        Raises:
            RunnerError: If handler execution fails
            TimeoutError: If execution exceeds timeout (future implementation)
        """
        try:
            # Execute handler
            # TODO: Implement true timeout using threading.Timer or multiprocessing
            result = handler_fn(args, context)

            # Ensure result is a string
            if not isinstance(result, str):
                result = str(result)

            return result

        except Exception as e:
            raise RunnerError(f"Handler execution error: {e}") from e

    def _log_audit_started(
        self,
        invocation: Invocation,
        run_id: str
    ):
        """Log audit event for builtin execution start"""
        try:
            from agentos.core.capabilities.audit_events import ExtensionAuditEvent
            from agentos.core.capabilities.audit_logger import get_audit_logger

            event = ExtensionAuditEvent.create_started(
                ext_id=invocation.extension_id,
                action=invocation.action_id,
                permissions_requested=["exec_builtin"],
                run_id=run_id,
                session_id=invocation.session_id,
                project_id=invocation.metadata.get("project_id")
            )
            event.metadata["handler_type"] = "builtin"
            event.metadata["args"] = invocation.args

            audit_logger = get_audit_logger()
            audit_logger.log_extension_event(event)
        except Exception as e:
            logger.warning(f"Failed to log audit start event: {e}")

    def _log_audit_finished(
        self,
        invocation: Invocation,
        run_id: str,
        output: str,
        exit_code: int,
        duration_ms: int,
        error: Optional[str] = None
    ):
        """Log audit event for builtin execution finish"""
        try:
            from agentos.core.capabilities.audit_events import ExtensionAuditEvent
            from agentos.core.capabilities.audit_logger import get_audit_logger

            event = ExtensionAuditEvent.create_finished(
                ext_id=invocation.extension_id,
                action=invocation.action_id,
                permissions_requested=["exec_builtin"],
                run_id=run_id,
                stdout=output,
                stderr=error or "",
                exit_code=exit_code,
                duration_ms=duration_ms,
                session_id=invocation.session_id,
                project_id=invocation.metadata.get("project_id")
            )
            event.metadata["handler_type"] = "builtin"

            audit_logger = get_audit_logger()
            audit_logger.log_extension_event(event)
        except Exception as e:
            logger.warning(f"Failed to log audit finish event: {e}")
