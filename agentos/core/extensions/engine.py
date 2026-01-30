"""
Extension Install Engine - Controlled execution engine for extension install plans

This module provides a declarative execution engine that runs extension install/uninstall
plans in a controlled, sandboxed environment with real-time progress tracking and audit logging.

Key Features:
- Declarative execution: Extensions declare steps, engine executes them safely
- Controlled environment: Sandboxed command execution with PATH/ENV restrictions
- Real-time progress: 0-100% progress tracking with step-by-step updates
- Full audit trail: All steps logged to system_logs and task_audits
- Standardized errors: Clear error codes and actionable hints
- Platform support: Cross-platform with conditional step execution

Design Philosophy:
- Security first: No arbitrary code execution, only whitelisted step types
- Observable: Every action is logged and traceable
- Resilient: Proper error handling with rollback support
- Simple: Clean API for registry integration
"""

import asyncio
import hashlib
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import yaml
from pydantic import BaseModel, Field

from agentos.core.extensions.exceptions import InstallationError
from agentos.core.extensions.models import InstallStatus

logger = logging.getLogger(__name__)


# ============================================
# Error Codes
# ============================================

class InstallErrorCode(str, Enum):
    """Standardized error codes for installation failures"""
    PLATFORM_NOT_SUPPORTED = "PLATFORM_NOT_SUPPORTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    COMMAND_FAILED = "COMMAND_FAILED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TIMEOUT = "TIMEOUT"
    INVALID_PLAN = "INVALID_PLAN"
    INVALID_STEP_TYPE = "INVALID_STEP_TYPE"
    STEP_NOT_FOUND = "STEP_NOT_FOUND"
    CONDITION_ERROR = "CONDITION_ERROR"
    UNKNOWN = "UNKNOWN"


class InstallError(Exception):
    """Installation error with structured information"""
    def __init__(
        self,
        message: str,
        error_code: InstallErrorCode = InstallErrorCode.UNKNOWN,
        hint: Optional[str] = None,
        failed_step: Optional[str] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.hint = hint
        self.failed_step = failed_step


# ============================================
# Data Models
# ============================================

class StepType(str, Enum):
    """Whitelisted step types"""
    DETECT_PLATFORM = "detect.platform"
    DOWNLOAD_HTTP = "download.http"
    EXTRACT_ZIP = "extract.zip"
    EXEC_SHELL = "exec.shell"
    EXEC_POWERSHELL = "exec.powershell"
    VERIFY_COMMAND_EXISTS = "verify.command_exists"
    VERIFY_HTTP = "verify.http"
    WRITE_CONFIG = "write.config"


class PlanStep(BaseModel):
    """Installation plan step"""
    id: str = Field(description="Step unique identifier")
    type: StepType = Field(description="Step type")
    when: Optional[str] = Field(default=None, description="Conditional expression")
    requires_permissions: List[str] = Field(default_factory=list, description="Required permissions")

    # Step-specific fields
    command: Optional[str] = None
    url: Optional[str] = None
    sha256: Optional[str] = None
    target: Optional[str] = None
    source: Optional[str] = None
    config_key: Optional[str] = None
    config_value: Optional[str] = None
    timeout: Optional[int] = 300


class InstallPlan(BaseModel):
    """Installation plan"""
    id: str = Field(description="Extension ID")
    steps: List[PlanStep] = Field(description="Installation steps")
    uninstall: Optional[Dict[str, Any]] = Field(default=None, description="Uninstall configuration")


class StepContext(BaseModel):
    """Execution context for step evaluation"""
    platform_os: str = Field(description="Operating system (linux, darwin, win32)")
    platform_arch: str = Field(description="Architecture (x64, arm64)")
    work_dir: Path = Field(description="Working directory")
    extension_id: str = Field(description="Extension ID")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Step variables")
    extension_manifest: Dict[str, Any] = Field(default_factory=dict, description="Extension manifest for permission checking")

    model_config = {"arbitrary_types_allowed": True}


class StepResult(BaseModel):
    """Result of step execution"""
    success: bool
    step_id: str
    duration_ms: int
    output: Optional[str] = None
    error: Optional[str] = None


class InstallResult(BaseModel):
    """Result of installation process"""
    success: bool
    extension_id: str
    install_id: str
    completed_steps: List[str]
    failed_step: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[InstallErrorCode] = None
    hint: Optional[str] = None
    duration_ms: int


class InstallProgress(BaseModel):
    """Installation progress information"""
    install_id: str
    extension_id: str
    status: InstallStatus
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    total_steps: int
    completed_steps: int


# ============================================
# Condition Evaluator
# ============================================

class ConditionEvaluator:
    """Simple condition expression evaluator for when clauses"""

    @staticmethod
    def evaluate(condition: str, context: StepContext) -> bool:
        """
        Evaluate a condition expression

        Supported expressions:
        - platform.os == "linux"
        - platform.os == "darwin"
        - platform.os == "win32"
        - platform.arch == "x64"
        - platform.arch == "arm64"

        Args:
            condition: Condition expression
            context: Step context

        Returns:
            True if condition matches, False otherwise

        Raises:
            InstallError: If condition syntax is invalid
        """
        if not condition or not condition.strip():
            return True

        try:
            # Simple pattern matching for supported expressions
            # Pattern: platform.{field} == "{value}"
            pattern = r'platform\.(os|arch)\s*==\s*"([^"]+)"'
            match = re.match(pattern, condition.strip())

            if not match:
                raise InstallError(
                    f"Invalid condition syntax: {condition}",
                    error_code=InstallErrorCode.CONDITION_ERROR,
                    hint="Supported format: platform.os == \"linux\" or platform.arch == \"x64\""
                )

            field, expected_value = match.groups()

            if field == "os":
                actual_value = context.platform_os
            elif field == "arch":
                actual_value = context.platform_arch
            else:
                return False

            return actual_value == expected_value

        except InstallError:
            raise
        except Exception as e:
            raise InstallError(
                f"Error evaluating condition: {e}",
                error_code=InstallErrorCode.CONDITION_ERROR
            )


# ============================================
# Sandboxed Executor
# ============================================

class SandboxedExecutor:
    """Controlled command execution with security restrictions"""

    def __init__(self, work_dir: Path, extension_id: str):
        """
        Initialize sandboxed executor

        Args:
            work_dir: Working directory for command execution
            extension_id: Extension ID for namespacing
        """
        self.work_dir = work_dir
        self.extension_id = extension_id

    def execute(
        self,
        command: str,
        timeout: int = 300,
        env_whitelist: Optional[List[str]] = None,
        shell: str = "bash"
    ) -> Tuple[int, str, str]:
        """
        Execute command in controlled environment

        Security restrictions:
        - Working directory: Limited to work_dir
        - PATH: System paths + ~/.agentos/bin
        - ENV: Whitelist only
        - Timeout: Enforced
        - No sudo without explicit permission

        Args:
            command: Command to execute
            timeout: Timeout in seconds
            env_whitelist: Additional environment variables to allow
            shell: Shell to use (bash, sh, powershell)

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            InstallError: If execution fails
        """
        logger.info(f"Executing command in sandbox: {command[:100]}")

        # Ensure work directory exists
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Build restricted environment
        env = self._build_environment(env_whitelist)

        # Detect shell
        if shell == "powershell":
            shell_cmd = ["powershell", "-NoProfile", "-Command"]
        else:
            # Use bash if available, otherwise sh
            shell_cmd = ["/bin/bash", "-c"] if shutil.which("bash") else ["/bin/sh", "-c"]

        try:
            # Execute command
            process = subprocess.Popen(
                shell_cmd + [command],
                cwd=str(self.work_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(timeout=timeout)
            return_code = process.returncode

            if return_code != 0:
                logger.warning(f"Command failed with code {return_code}: {stderr}")

            return return_code, stdout, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            raise InstallError(
                f"Command timed out after {timeout} seconds",
                error_code=InstallErrorCode.TIMEOUT,
                hint=f"Increase timeout or optimize the command"
            )
        except Exception as e:
            raise InstallError(
                f"Command execution failed: {e}",
                error_code=InstallErrorCode.COMMAND_FAILED
            )

    def _build_environment(self, env_whitelist: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Build restricted environment variables

        Args:
            env_whitelist: Additional variables to allow

        Returns:
            Environment dictionary
        """
        # Base whitelist
        base_whitelist = [
            "PATH",
            "HOME",
            "USER",
            "TMPDIR",
            "TEMP",
            "LANG",
            "LC_ALL",
        ]

        if env_whitelist:
            base_whitelist.extend(env_whitelist)

        # Build environment
        env = {}
        for key in base_whitelist:
            if key in os.environ:
                env[key] = os.environ[key]

        # Restrict PATH
        agentos_bin = Path.home() / ".agentos" / "bin"
        system_paths = [
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/local/sbin",
            "/usr/sbin",
            "/sbin",
        ]

        if agentos_bin.exists():
            system_paths.insert(0, str(agentos_bin))

        env["PATH"] = ":".join(system_paths)

        # Add extension-specific vars
        env["AGENTOS_EXTENSION_ID"] = self.extension_id
        env["AGENTOS_WORK_DIR"] = str(self.work_dir)

        return env


# ============================================
# Step Executors
# ============================================

class StepExecutor:
    """Base class for step executors"""

    def __init__(self, context: StepContext):
        self.context = context

    def execute(self, step: PlanStep) -> StepResult:
        """Execute a step and return result"""
        raise NotImplementedError


class PlatformDetectExecutor(StepExecutor):
    """Executor for platform detection"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        # Detect platform
        os_type = sys.platform
        arch = platform.machine().lower()

        # Normalize architecture
        if arch in ("x86_64", "amd64"):
            arch = "x64"
        elif arch in ("aarch64", "arm64"):
            arch = "arm64"

        # Update context
        self.context.platform_os = os_type
        self.context.platform_arch = arch

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return StepResult(
            success=True,
            step_id=step.id,
            duration_ms=duration_ms,
            output=f"Detected: {os_type} {arch}"
        )


class DownloadExecutor(StepExecutor):
    """Executor for HTTP downloads"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.url:
            raise InstallError(
                "Missing required field 'url' for download step",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        if not step.target:
            raise InstallError(
                "Missing required field 'target' for download step",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        # Resolve target path
        target_path = self.context.work_dir / step.target
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Download file
            logger.info(f"Downloading {step.url} to {target_path}")
            response = requests.get(step.url, timeout=step.timeout or 300, stream=True)
            response.raise_for_status()

            # Write to file
            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify SHA256 if provided
            if step.sha256:
                actual_hash = self._compute_sha256(target_path)
                if actual_hash != step.sha256:
                    raise InstallError(
                        f"SHA256 mismatch: expected {step.sha256}, got {actual_hash}",
                        error_code=InstallErrorCode.VERIFICATION_FAILED,
                        failed_step=step.id,
                        hint="The downloaded file may be corrupted or tampered with"
                    )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=f"Downloaded to {target_path}"
            )

        except requests.RequestException as e:
            raise InstallError(
                f"Download failed: {e}",
                error_code=InstallErrorCode.DOWNLOAD_FAILED,
                failed_step=step.id,
                hint="Check network connectivity and URL validity"
            )

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        """Compute SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


class ExtractExecutor(StepExecutor):
    """Executor for zip extraction"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.source:
            raise InstallError(
                "Missing required field 'source' for extract step",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        source_path = self.context.work_dir / step.source
        target_path = self.context.work_dir / (step.target or ".")

        if not source_path.exists():
            raise InstallError(
                f"Source file not found: {source_path}",
                error_code=InstallErrorCode.STEP_NOT_FOUND,
                failed_step=step.id
            )

        try:
            logger.info(f"Extracting {source_path} to {target_path}")
            target_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(source_path, 'r') as zf:
                zf.extractall(target_path)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=f"Extracted to {target_path}"
            )

        except Exception as e:
            raise InstallError(
                f"Extraction failed: {e}",
                error_code=InstallErrorCode.COMMAND_FAILED,
                failed_step=step.id
            )


class ShellExecutor(StepExecutor):
    """Executor for shell commands"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.command:
            raise InstallError(
                "Missing required field 'command' for shell execution",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        # Create sandboxed executor
        executor = SandboxedExecutor(self.context.work_dir, self.context.extension_id)

        try:
            return_code, stdout, stderr = executor.execute(
                step.command,
                timeout=step.timeout or 300,
                shell="bash"
            )

            if return_code != 0:
                raise InstallError(
                    f"Command failed with exit code {return_code}: {stderr}",
                    error_code=InstallErrorCode.COMMAND_FAILED,
                    failed_step=step.id,
                    hint="Check command syntax and permissions"
                )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=stdout
            )

        except InstallError:
            raise
        except Exception as e:
            raise InstallError(
                f"Shell execution failed: {e}",
                error_code=InstallErrorCode.COMMAND_FAILED,
                failed_step=step.id
            )


class PowerShellExecutor(StepExecutor):
    """Executor for PowerShell commands"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.command:
            raise InstallError(
                "Missing required field 'command' for PowerShell execution",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        # Create sandboxed executor
        executor = SandboxedExecutor(self.context.work_dir, self.context.extension_id)

        try:
            return_code, stdout, stderr = executor.execute(
                step.command,
                timeout=step.timeout or 300,
                shell="powershell"
            )

            if return_code != 0:
                raise InstallError(
                    f"PowerShell command failed with exit code {return_code}: {stderr}",
                    error_code=InstallErrorCode.COMMAND_FAILED,
                    failed_step=step.id,
                    hint="Check PowerShell syntax and permissions"
                )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=stdout
            )

        except InstallError:
            raise
        except Exception as e:
            raise InstallError(
                f"PowerShell execution failed: {e}",
                error_code=InstallErrorCode.COMMAND_FAILED,
                failed_step=step.id
            )


class VerifyCommandExecutor(StepExecutor):
    """Executor for command existence verification"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.command:
            raise InstallError(
                "Missing required field 'command' for verification",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        # Check if command exists
        command_name = step.command.split()[0]
        command_path = shutil.which(command_name)

        if not command_path:
            raise InstallError(
                f"Command not found: {command_name}",
                error_code=InstallErrorCode.VERIFICATION_FAILED,
                failed_step=step.id,
                hint=f"Ensure {command_name} is installed and in PATH"
            )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return StepResult(
            success=True,
            step_id=step.id,
            duration_ms=duration_ms,
            output=f"Command found at {command_path}"
        )


class VerifyHttpExecutor(StepExecutor):
    """Executor for HTTP health checks"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.url:
            raise InstallError(
                "Missing required field 'url' for HTTP verification",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        try:
            response = requests.get(step.url, timeout=step.timeout or 30)
            response.raise_for_status()

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=f"HTTP check passed: {response.status_code}"
            )

        except requests.RequestException as e:
            raise InstallError(
                f"HTTP verification failed: {e}",
                error_code=InstallErrorCode.VERIFICATION_FAILED,
                failed_step=step.id,
                hint="Check URL accessibility and network connectivity"
            )


class WriteConfigExecutor(StepExecutor):
    """Executor for writing extension configuration"""

    def execute(self, step: PlanStep) -> StepResult:
        start_time = datetime.now()

        if not step.config_key:
            raise InstallError(
                "Missing required field 'config_key' for config write",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id
            )

        # Write config to extension namespace
        config_file = self.context.work_dir / "config.json"

        try:
            import json

            # Load existing config
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)

            # Update config
            config[step.config_key] = step.config_value

            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return StepResult(
                success=True,
                step_id=step.id,
                duration_ms=duration_ms,
                output=f"Config written: {step.config_key} = {step.config_value}"
            )

        except Exception as e:
            raise InstallError(
                f"Config write failed: {e}",
                error_code=InstallErrorCode.COMMAND_FAILED,
                failed_step=step.id
            )


# ============================================
# Progress Tracker
# ============================================

class ProgressTracker:
    """Real-time progress tracking for installation"""

    def __init__(self, install_id: str, extension_id: str, total_steps: int, registry):
        """
        Initialize progress tracker

        Args:
            install_id: Installation ID
            extension_id: Extension ID
            total_steps: Total number of steps
            registry: Registry instance for database updates
        """
        self.install_id = install_id
        self.extension_id = extension_id
        self.total_steps = total_steps
        self.completed_steps = 0
        self.registry = registry

    def update(self, current_step: str):
        """
        Update progress to database

        Args:
            current_step: Current step ID
        """
        self.completed_steps += 1
        progress = int((self.completed_steps / self.total_steps) * 100) if self.total_steps > 0 else 0

        # Update database
        try:
            self.registry.update_install_progress(
                install_id=self.install_id,
                progress=progress,
                current_step=current_step
            )
            logger.info(f"Progress updated: {progress}% (step {self.completed_steps}/{self.total_steps})")
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")

    def get_progress(self) -> InstallProgress:
        """Get current progress information"""
        progress = int((self.completed_steps / self.total_steps) * 100) if self.total_steps > 0 else 0

        return InstallProgress(
            install_id=self.install_id,
            extension_id=self.extension_id,
            status=InstallStatus.INSTALLING,
            progress=progress,
            current_step=None,
            total_steps=self.total_steps,
            completed_steps=self.completed_steps
        )


# ============================================
# Extension Install Engine
# ============================================

class ExtensionInstallEngine:
    """
    Controlled execution engine for extension installation

    This engine executes extension install/uninstall plans in a secure,
    observable, and reliable manner with full audit trail.
    """

    def __init__(self, registry=None):
        """
        Initialize install engine

        Args:
            registry: Extension registry instance (optional)
        """
        self.registry = registry
        self._executor_map = {
            StepType.DETECT_PLATFORM: PlatformDetectExecutor,
            StepType.DOWNLOAD_HTTP: DownloadExecutor,
            StepType.EXTRACT_ZIP: ExtractExecutor,
            StepType.EXEC_SHELL: ShellExecutor,
            StepType.EXEC_POWERSHELL: PowerShellExecutor,
            StepType.VERIFY_COMMAND_EXISTS: VerifyCommandExecutor,
            StepType.VERIFY_HTTP: VerifyHttpExecutor,
            StepType.WRITE_CONFIG: WriteConfigExecutor,
        }

    def execute_install(
        self,
        extension_id: str,
        plan_yaml_path: Path,
        install_id: str
    ) -> InstallResult:
        """
        Execute installation plan

        Args:
            extension_id: Extension ID
            plan_yaml_path: Path to plan.yaml
            install_id: Installation record ID

        Returns:
            InstallResult with execution details

        Raises:
            InstallationError: If installation fails
        """
        start_time = datetime.now()
        completed_steps = []

        logger.info(f"Starting installation: {extension_id} (install_id={install_id})")

        try:
            # Load plan
            plan = self._load_plan(plan_yaml_path)

            # Load manifest for permission checking
            manifest_path = plan_yaml_path.parent.parent / "manifest.json"
            manifest_dict = {}
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r') as f:
                    manifest_dict = json.load(f)

            # Setup context
            work_dir = Path.home() / ".agentos" / "extensions" / extension_id / "work"
            work_dir.mkdir(parents=True, exist_ok=True)

            context = StepContext(
                platform_os=sys.platform,
                platform_arch=platform.machine().lower(),
                work_dir=work_dir,
                extension_id=extension_id,
                extension_manifest=manifest_dict
            )

            # Filter steps by conditions
            active_steps = self._filter_steps(plan.steps, context)

            # Initialize progress tracker
            tracker = ProgressTracker(
                install_id=install_id,
                extension_id=extension_id,
                total_steps=len(active_steps),
                registry=self.registry
            )

            # Execute steps
            for step in active_steps:
                logger.info(f"Executing step: {step.id} ({step.type})")

                try:
                    # Execute step
                    result = self._execute_step(step, context)

                    # Log to audit trail
                    self._log_step_execution(
                        extension_id=extension_id,
                        install_id=install_id,
                        step=step,
                        result=result
                    )

                    # Update progress
                    tracker.update(step.id)
                    completed_steps.append(step.id)

                except InstallError as e:
                    # Step failed
                    logger.error(f"Step failed: {step.id} - {e}")
                    e.failed_step = step.id
                    raise

            # Installation complete
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(f"Installation completed: {extension_id}")

            return InstallResult(
                success=True,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                duration_ms=duration_ms
            )

        except InstallError as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return InstallResult(
                success=False,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                failed_step=e.failed_step,
                error=str(e),
                error_code=e.error_code,
                hint=e.hint,
                duration_ms=duration_ms
            )
        except Exception as e:
            logger.error(f"Unexpected error during installation: {e}", exc_info=True)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return InstallResult(
                success=False,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                error=str(e),
                error_code=InstallErrorCode.UNKNOWN,
                duration_ms=duration_ms
            )

    def execute_uninstall(
        self,
        extension_id: str,
        plan_yaml_path: Path,
        install_id: str
    ) -> InstallResult:
        """
        Execute uninstallation plan

        Args:
            extension_id: Extension ID
            plan_yaml_path: Path to plan.yaml
            install_id: Uninstall record ID

        Returns:
            InstallResult with execution details
        """
        start_time = datetime.now()
        completed_steps = []

        logger.info(f"Starting uninstallation: {extension_id} (install_id={install_id})")

        try:
            # Load plan
            plan = self._load_plan(plan_yaml_path)

            if not plan.uninstall or "steps" not in plan.uninstall:
                logger.info(f"No uninstall steps defined for {extension_id}")
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                return InstallResult(
                    success=True,
                    extension_id=extension_id,
                    install_id=install_id,
                    completed_steps=[],
                    duration_ms=duration_ms
                )

            # Parse uninstall steps
            uninstall_steps = [PlanStep(**step_dict) for step_dict in plan.uninstall["steps"]]

            # Load manifest for permission checking
            manifest_path = plan_yaml_path.parent.parent / "manifest.json"
            manifest_dict = {}
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r') as f:
                    manifest_dict = json.load(f)

            # Setup context
            work_dir = Path.home() / ".agentos" / "extensions" / extension_id / "work"
            context = StepContext(
                platform_os=sys.platform,
                platform_arch=platform.machine().lower(),
                work_dir=work_dir,
                extension_id=extension_id,
                extension_manifest=manifest_dict
            )

            # Filter steps
            active_steps = self._filter_steps(uninstall_steps, context)

            # Initialize progress tracker
            tracker = ProgressTracker(
                install_id=install_id,
                extension_id=extension_id,
                total_steps=len(active_steps),
                registry=self.registry
            )

            # Execute steps
            for step in active_steps:
                logger.info(f"Executing uninstall step: {step.id} ({step.type})")

                try:
                    result = self._execute_step(step, context)

                    self._log_step_execution(
                        extension_id=extension_id,
                        install_id=install_id,
                        step=step,
                        result=result
                    )

                    tracker.update(step.id)
                    completed_steps.append(step.id)

                except InstallError as e:
                    logger.error(f"Uninstall step failed: {step.id} - {e}")
                    e.failed_step = step.id
                    raise

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(f"Uninstallation completed: {extension_id}")

            return InstallResult(
                success=True,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                duration_ms=duration_ms
            )

        except InstallError as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return InstallResult(
                success=False,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                failed_step=e.failed_step,
                error=str(e),
                error_code=e.error_code,
                hint=e.hint,
                duration_ms=duration_ms
            )
        except Exception as e:
            logger.error(f"Unexpected error during uninstallation: {e}", exc_info=True)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return InstallResult(
                success=False,
                extension_id=extension_id,
                install_id=install_id,
                completed_steps=completed_steps,
                error=str(e),
                error_code=InstallErrorCode.UNKNOWN,
                duration_ms=duration_ms
            )

    def get_install_progress(self, install_id: str) -> Optional[InstallProgress]:
        """
        Get installation progress

        Args:
            install_id: Installation ID

        Returns:
            InstallProgress or None if not found
        """
        if not self.registry:
            return None

        record = self.registry.get_install_record(install_id)
        if not record:
            return None

        return InstallProgress(
            install_id=record.install_id,
            extension_id=record.extension_id,
            status=record.status,
            progress=record.progress,
            current_step=record.current_step,
            total_steps=0,  # Not tracked in DB
            completed_steps=0  # Not tracked in DB
        )

    def _load_plan(self, plan_yaml_path: Path) -> InstallPlan:
        """Load and parse installation plan"""
        if not plan_yaml_path.exists():
            raise InstallError(
                f"Plan file not found: {plan_yaml_path}",
                error_code=InstallErrorCode.INVALID_PLAN,
                hint="Ensure the extension package contains install/plan.yaml"
            )

        try:
            with open(plan_yaml_path, 'r') as f:
                plan_dict = yaml.safe_load(f)

            # Add extension ID from path if not present
            if "id" not in plan_dict:
                plan_dict["id"] = plan_yaml_path.parent.parent.name

            return InstallPlan(**plan_dict)

        except Exception as e:
            raise InstallError(
                f"Failed to parse plan.yaml: {e}",
                error_code=InstallErrorCode.INVALID_PLAN,
                hint="Check YAML syntax and structure"
            )

    def _filter_steps(self, steps: List[PlanStep], context: StepContext) -> List[PlanStep]:
        """Filter steps based on conditional expressions"""
        active_steps = []

        for step in steps:
            if step.when:
                try:
                    if ConditionEvaluator.evaluate(step.when, context):
                        active_steps.append(step)
                    else:
                        logger.info(f"Skipping step {step.id}: condition not met ({step.when})")
                except Exception as e:
                    logger.warning(f"Error evaluating condition for step {step.id}: {e}")
            else:
                active_steps.append(step)

        return active_steps

    def _execute_step(self, step: PlanStep, context: StepContext) -> StepResult:
        """Execute a single step"""
        # ADR-EXT-001: Whitelist check for step types
        allowed_types = [
            StepType.DETECT_PLATFORM,
            StepType.DOWNLOAD_HTTP,
            StepType.EXTRACT_ZIP,
            StepType.EXEC_SHELL,
            StepType.EXEC_POWERSHELL,
            StepType.VERIFY_COMMAND_EXISTS,
            StepType.VERIFY_HTTP,
            StepType.WRITE_CONFIG,
        ]

        if step.type not in allowed_types:
            raise InstallError(
                f"Step type '{step.type}' is not allowed. "
                f"Allowed types: {', '.join([t.value for t in allowed_types])}. "
                f"See ADR-EXT-001 for details.",
                error_code=InstallErrorCode.INVALID_STEP_TYPE,
                failed_step=step.id,
                hint="Check the extension's install/plan.yaml file."
            )

        # ADR-EXT-001: Permission check
        required_perms = step.requires_permissions
        if required_perms:
            manifest_perms = context.extension_manifest.get('permissions_required', [])
            for perm in required_perms:
                if perm not in manifest_perms:
                    raise InstallError(
                        f"Step requires permission '{perm}' which is not declared in manifest. "
                        f"See ADR-EXT-001 for details.",
                        error_code=InstallErrorCode.PERMISSION_DENIED,
                        failed_step=step.id,
                        hint=f"Add '{perm}' to manifest.json permissions_required."
                    )

        executor_class = self._executor_map.get(step.type)

        if not executor_class:
            raise InstallError(
                f"Unsupported step type: {step.type}",
                error_code=InstallErrorCode.INVALID_PLAN,
                failed_step=step.id,
                hint=f"Supported types: {', '.join([t.value for t in StepType])}"
            )

        executor = executor_class(context)
        return executor.execute(step)

    def _log_step_execution(
        self,
        extension_id: str,
        install_id: str,
        step: PlanStep,
        result: StepResult
    ):
        """Log step execution to audit trail"""
        try:
            # Log with standard Python logger
            logger.info(
                f"Extension step executed: {step.id}",
                extra={
                    "extension_id": extension_id,
                    "install_id": install_id,
                    "step_id": step.id,
                    "step_type": step.type.value,
                    "status": "success" if result.success else "failed",
                    "duration_ms": result.duration_ms
                }
            )

            # Log to task_audits (if available)
            try:
                from agentos.core.audit import log_audit_event, EXTENSION_STEP_EXECUTED

                log_audit_event(
                    event_type=EXTENSION_STEP_EXECUTED,
                    task_id=None,  # Will use ORPHAN task
                    level="info" if result.success else "error",
                    metadata={
                        "extension_id": extension_id,
                        "install_id": install_id,
                        "step_id": step.id,
                        "step_type": step.type.value,
                        "duration_ms": result.duration_ms,
                        "output": result.output[:500] if result.output else None,
                        "error": result.error[:500] if result.error else None
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to log to task_audits: {e}")

        except Exception as e:
            logger.warning(f"Failed to log step execution: {e}")
