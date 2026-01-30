"""
Shell Runner Implementation

Executes shell commands with strict security controls:
- Manifest allowlist validation
- Parameter tokenization (no injection)
- Timeout enforcement
- Output truncation
- Working directory isolation
- Environment variable whitelisting

Part of PR-E4: ShellRunner
"""

import logging
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from .base import Runner, Invocation, RunResult, ProgressCallback, RunnerError, ValidationError, TimeoutError as RunnerTimeoutError
from .shell_config import ShellConfig
from .command_template import CommandTemplate, CommandTemplateError

logger = logging.getLogger(__name__)


class ShellRunner(Runner):
    """
    Shell command runner with security controls

    Executes shell commands from extensions with strict security boundaries:
    - Only commands declared in manifest are allowed
    - Parameters are safely tokenized (no shell injection)
    - Execution timeout enforced
    - Output size limited
    - Working directory isolated
    - Environment variables whitelisted

    Example:
        >>> config = ShellConfig(
        ...     allowed_commands=["echo {message}"],
        ...     work_dir=Path("/tmp/ext"),
        ...     timeout_sec=30
        ... )
        >>> runner = ShellRunner(config)
        >>> invocation = Invocation(
        ...     extension_id="tools.test",
        ...     action_id="hello",
        ...     session_id="sess_123",
        ...     args=["World"]
        ... )
        >>> result = runner.run(invocation)
    """

    def __init__(
        self,
        config: Optional[ShellConfig] = None,
        extensions_dir: Optional[Path] = None
    ):
        """
        Initialize shell runner

        Args:
            config: Shell configuration (optional, can be loaded per-invocation)
            extensions_dir: Directory where extensions are installed
        """
        self.config = config

        if extensions_dir is None:
            extensions_dir = Path.home() / ".agentos" / "extensions"
        self.extensions_dir = Path(extensions_dir)

        logger.info(f"ShellRunner initialized (extensions_dir={self.extensions_dir})")

    @property
    def runner_type(self) -> str:
        return "shell"

    def run(
        self,
        invocation: Invocation,
        progress_cb: Optional[ProgressCallback] = None,
        declared_permissions: Optional[list] = None
    ) -> RunResult:
        """
        Execute a shell command from extension

        Progress stages:
        - VALIDATING (5%): Validate extension and command
        - LOADING (15%): Load configuration and parse command
        - EXECUTING (60%): Execute shell command
        - FINALIZING (90%): Process results
        - DONE (100%): Complete

        Args:
            invocation: The invocation request
            progress_cb: Optional progress callback
            declared_permissions: Permissions declared in manifest (should include exec_shell)

        Returns:
            RunResult with execution status and output

        Raises:
            ValidationError: If command is not allowed or invalid
            RunnerError: If execution fails
            RunnerTimeoutError: If execution exceeds timeout
            PermissionError: If exec_shell permission not granted
        """
        started_at = datetime.now()
        run_id = f"shell_{uuid.uuid4().hex[:8]}"

        try:
            # Stage 1: VALIDATING (5%)
            if progress_cb:
                progress_cb("VALIDATING", 5, "Validating shell command")

            # Check permissions
            if declared_permissions is None:
                declared_permissions = []

            if "exec_shell" not in declared_permissions:
                raise PermissionError(
                    f"Permission 'exec_shell' required but not declared in manifest. "
                    f"Declared permissions: {declared_permissions}"
                )

            # Load extension configuration if not provided
            if self.config is None:
                config = self._load_extension_config(invocation.extension_id)
            else:
                config = self.config

            # Get command template from invocation metadata or action_id
            command_template_str = invocation.metadata.get("command_template")
            if not command_template_str:
                # Fallback: try to infer from action_id (for testing)
                # In production, command_template should be in metadata
                raise ValidationError(
                    "No command_template provided in invocation metadata. "
                    "ShellRunner requires explicit command template."
                )

            # Stage 2: LOADING (15%)
            if progress_cb:
                progress_cb("LOADING", 15, f"Parsing command template")

            # Validate command is allowed
            if not config.is_command_allowed(command_template_str):
                available_cmds = "\n".join(config.allowed_commands)
                raise ValidationError(
                    f"Command not allowed by manifest: {command_template_str}\n"
                    f"Allowed commands:\n{available_cmds}"
                )

            # Parse command template
            try:
                template = CommandTemplate(command_template_str)
            except CommandTemplateError as e:
                raise ValidationError(f"Invalid command template: {e}")

            # Build arguments from invocation
            template_args = self._build_template_args(invocation, template)

            # Render command to argv
            try:
                argv = template.render(template_args)
            except CommandTemplateError as e:
                raise ValidationError(f"Failed to render command: {e}")

            # Stage 3: EXECUTING (60%)
            if progress_cb:
                progress_cb("EXECUTING", 60, f"Executing: {argv[0]}")

            # Log audit event for shell execution start
            self._log_audit_started(
                invocation=invocation,
                command=argv,
                run_id=run_id
            )

            # Execute command
            result = self._execute_command(
                argv=argv,
                config=config,
                timeout=invocation.timeout or config.timeout_sec
            )

            # Stage 4: FINALIZING (90%)
            if progress_cb:
                progress_cb("FINALIZING", 90, "Processing command output")

            # Truncate output if needed
            stdout = result["stdout"]
            stderr = result["stderr"]
            truncated = False

            if len(stdout) > config.max_output_size:
                stdout = stdout[:config.max_output_size]
                truncated = True

            if len(stderr) > config.max_output_size:
                stderr = stderr[:config.max_output_size]
                truncated = True

            # Build output
            output = stdout if stdout else stderr
            if truncated:
                output += f"\n\n[Output truncated to {config.max_output_size} bytes]"

            # Stage 5: DONE (100%)
            if progress_cb:
                progress_cb("DONE", 100, "Shell command complete")

            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit event for shell execution finish
            self._log_audit_finished(
                invocation=invocation,
                run_id=run_id,
                stdout=stdout,
                stderr=stderr,
                exit_code=result["exit_code"],
                duration_ms=duration_ms
            )

            success = result["exit_code"] == 0

            return RunResult(
                success=success,
                output=output,
                error=stderr if not success else None,
                exit_code=result["exit_code"],
                duration_ms=duration_ms,
                metadata={
                    "extension_id": invocation.extension_id,
                    "action_id": invocation.action_id,
                    "runner_type": self.runner_type,
                    "command": " ".join(argv),
                    "truncated": truncated,
                    "run_id": run_id
                },
                started_at=started_at,
                completed_at=completed_at
            )

        except PermissionError as e:
            # Permission denied
            logger.warning(f"Permission denied for shell execution: {e}")
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Log audit denial
            self._log_audit_denied(
                invocation=invocation,
                reason=str(e)
            )

            return RunResult(
                success=False,
                output="",
                error=f"Permission denied: {e}",
                exit_code=126,  # Permission denied exit code
                duration_ms=duration_ms,
                metadata={"error_type": "permission_denied"},
                started_at=started_at,
                completed_at=completed_at
            )

        except ValidationError as e:
            # Validation errors
            logger.warning(f"Validation error: {e}")
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            return RunResult(
                success=False,
                output="",
                error=str(e),
                exit_code=1,
                duration_ms=duration_ms,
                metadata={"error_type": "validation"},
                started_at=started_at,
                completed_at=completed_at
            )

        except RunnerTimeoutError as e:
            # Timeout errors
            logger.error(f"Shell command timeout: {e}")
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            return RunResult(
                success=False,
                output="",
                error=str(e),
                exit_code=124,  # Timeout exit code
                duration_ms=duration_ms,
                metadata={"error_type": "timeout"},
                started_at=started_at,
                completed_at=completed_at
            )

        except Exception as e:
            # Unexpected errors
            logger.error(f"Shell command execution failed: {e}", exc_info=True)
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            return RunResult(
                success=False,
                output="",
                error=f"Shell execution failed: {str(e)}",
                exit_code=1,
                duration_ms=duration_ms,
                metadata={"error_type": "execution"},
                started_at=started_at,
                completed_at=completed_at
            )

    def _load_extension_config(self, extension_id: str) -> ShellConfig:
        """
        Load shell configuration from extension manifest

        Args:
            extension_id: Extension ID

        Returns:
            ShellConfig instance

        Raises:
            ValidationError: If manifest is invalid or not found
        """
        import json

        extension_dir = self.extensions_dir / extension_id
        manifest_path = extension_dir / "manifest.json"

        if not manifest_path.exists():
            raise ValidationError(f"Manifest not found for extension: {extension_id}")

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            raise ValidationError(f"Failed to load manifest for {extension_id}: {e}")

        try:
            config = ShellConfig.from_manifest(
                manifest=manifest,
                work_dir=extension_dir,
                extension_id=extension_id
            )
            return config
        except Exception as e:
            raise ValidationError(f"Failed to parse shell config from manifest: {e}")

    def _build_template_args(
        self,
        invocation: Invocation,
        template: CommandTemplate
    ) -> Dict[str, str]:
        """
        Build template arguments from invocation

        Maps invocation args to template parameters.

        Args:
            invocation: Invocation request
            template: Command template

        Returns:
            Dictionary of parameter values

        Raises:
            ValidationError: If required parameters missing
        """
        # Map positional args to template params
        template_args = {}

        for i, param in enumerate(template.params):
            if i < len(invocation.args):
                template_args[param] = invocation.args[i]
            elif param in invocation.flags:
                template_args[param] = str(invocation.flags[param])
            else:
                # Check metadata
                if param in invocation.metadata:
                    template_args[param] = str(invocation.metadata[param])

        return template_args

    def _execute_command(
        self,
        argv: List[str],
        config: ShellConfig,
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute shell command using subprocess

        Args:
            argv: Command arguments
            config: Shell configuration
            timeout: Timeout in seconds

        Returns:
            Dict with stdout, stderr, exit_code

        Raises:
            RunnerTimeoutError: If command times out
            RunnerError: If execution fails
        """
        try:
            # Prepare environment
            env = config.get_env_dict()

            # Execute command
            logger.debug(f"Executing command: {argv}")
            logger.debug(f"Working directory: {config.work_dir}")
            logger.debug(f"Timeout: {timeout}s")

            result = subprocess.run(
                argv,
                cwd=str(config.work_dir),
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired as e:
            raise RunnerTimeoutError(
                f"Command timed out after {timeout}s: {' '.join(argv)}"
            )
        except FileNotFoundError as e:
            raise RunnerError(
                f"Command not found: {argv[0]}. Make sure it's installed and in PATH."
            )
        except Exception as e:
            raise RunnerError(f"Failed to execute command: {e}")

    def _log_audit_started(
        self,
        invocation: Invocation,
        command: List[str],
        run_id: str
    ):
        """Log audit event for shell execution start"""
        try:
            from agentos.core.capabilities.audit_events import ExtensionAuditEvent
            from agentos.core.capabilities.audit_logger import get_audit_logger

            event = ExtensionAuditEvent.create_started(
                ext_id=invocation.extension_id,
                action=invocation.action_id,
                permissions_requested=["exec_shell"],
                run_id=run_id,
                session_id=invocation.session_id,
                project_id=invocation.metadata.get("project_id")
            )
            event.metadata["command"] = " ".join(command)

            audit_logger = get_audit_logger()
            audit_logger.log_extension_event(event)
        except Exception as e:
            logger.warning(f"Failed to log audit start event: {e}")

    def _log_audit_finished(
        self,
        invocation: Invocation,
        run_id: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: int
    ):
        """Log audit event for shell execution finish"""
        try:
            from agentos.core.capabilities.audit_events import ExtensionAuditEvent
            from agentos.core.capabilities.audit_logger import get_audit_logger

            event = ExtensionAuditEvent.create_finished(
                ext_id=invocation.extension_id,
                action=invocation.action_id,
                permissions_requested=["exec_shell"],
                run_id=run_id,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
                session_id=invocation.session_id,
                project_id=invocation.metadata.get("project_id")
            )

            audit_logger = get_audit_logger()
            audit_logger.log_extension_event(event)
        except Exception as e:
            logger.warning(f"Failed to log audit finish event: {e}")

    def _log_audit_denied(self, invocation: Invocation, reason: str):
        """Log audit event for shell execution denial"""
        try:
            from agentos.core.capabilities.audit_events import ExtensionAuditEvent
            from agentos.core.capabilities.audit_logger import get_audit_logger

            event = ExtensionAuditEvent.create_denied(
                ext_id=invocation.extension_id,
                action=invocation.action_id,
                permissions_requested=["exec_shell"],
                reason_code="PERMISSION_DENIED",
                session_id=invocation.session_id,
                project_id=invocation.metadata.get("project_id")
            )
            event.metadata["reason"] = reason

            audit_logger = get_audit_logger()
            audit_logger.log_extension_event(event)
        except Exception as e:
            logger.warning(f"Failed to log audit denial event: {e}")
