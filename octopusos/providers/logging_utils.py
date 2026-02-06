"""
Provider Structured Logging Utilities

Provides structured logging for all provider operations with comprehensive
context including provider ID, action, platform, timing, and error tracking.

This module implements Task #14 (P0.1) from PROVIDERS_FIX_CHECKLIST_V2.md:
- Structured logs with timestamp, provider, action, platform, resolved_exe, pid, exit_code, elapsed_ms, error_code
- Log file: ~/.agentos/logs/providers.log
- Configurable log levels

Sprint B+ Provider Architecture Refactor
Phase 3.4: API Call Chain Diagnosis & Log Enhancement
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextvars import ContextVar

from agentos.providers import platform_utils

# Context variable for operation timing
_operation_start_time: ContextVar[Optional[float]] = ContextVar('operation_start_time', default=None)


class ProviderStructuredLogger:
    """
    Structured logger for provider operations

    Features:
    - Automatic timing of operations
    - Platform detection
    - Structured JSON-like log entries
    - Dedicated log file for providers
    - Context-aware logging (provider, action, etc.)
    """

    def __init__(self, logger_name: str = "agentos.providers"):
        """
        Initialize structured logger

        Args:
            logger_name: Logger name (default: "agentos.providers")
        """
        self.logger = logging.getLogger(logger_name)
        self._ensure_provider_log_file()

    def _ensure_provider_log_file(self):
        """Ensure providers.log file exists and is configured"""
        log_dir = platform_utils.get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        providers_log_file = log_dir / "providers.log"

        # Check if file handler already exists
        has_file_handler = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == str(providers_log_file)
            for h in self.logger.handlers
        )

        if not has_file_handler:
            # Create file handler with UTF-8 encoding
            file_handler = logging.FileHandler(
                providers_log_file,
                mode='a',
                encoding='utf-8'
            )

            # Use detailed format for file logs
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)

            self.logger.addHandler(file_handler)

    def _format_structured_log(
        self,
        provider: str,
        action: str,
        platform: Optional[str] = None,
        resolved_exe: Optional[str] = None,
        pid: Optional[int] = None,
        exit_code: Optional[int] = None,
        elapsed_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        **extra_fields
    ) -> str:
        """
        Format structured log entry

        Args:
            provider: Provider ID (ollama, llamacpp, lmstudio)
            action: Action performed (start, stop, restart, detect, validate)
            platform: Platform (windows, macos, linux)
            resolved_exe: Path to the executable used
            pid: Process ID
            exit_code: Exit code of the process
            elapsed_ms: Operation duration in milliseconds
            error_code: Error code if operation failed
            message: Additional message
            **extra_fields: Additional fields to include

        Returns:
            str: Formatted log message
        """
        # Build structured log entry
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "action": action,
        }

        # Add optional fields
        if platform:
            log_data["platform"] = platform
        if resolved_exe:
            log_data["resolved_exe"] = resolved_exe
        if pid is not None:
            log_data["pid"] = pid
        if exit_code is not None:
            log_data["exit_code"] = exit_code
        if elapsed_ms is not None:
            log_data["elapsed_ms"] = round(elapsed_ms, 2)
        if error_code:
            log_data["error_code"] = error_code
        if message:
            log_data["message"] = message

        # Add extra fields
        log_data.update(extra_fields)

        # Format as key=value pairs for easy parsing
        log_parts = []
        for key, value in log_data.items():
            if isinstance(value, str):
                # Quote strings with spaces
                if ' ' in value:
                    log_parts.append(f'{key}="{value}"')
                else:
                    log_parts.append(f'{key}={value}')
            else:
                log_parts.append(f'{key}={value}')

        return ' '.join(log_parts)

    def log_operation(
        self,
        level: int,
        provider: str,
        action: str,
        platform: Optional[str] = None,
        resolved_exe: Optional[str] = None,
        pid: Optional[int] = None,
        exit_code: Optional[int] = None,
        elapsed_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        **extra_fields
    ):
        """
        Log a provider operation with structured data

        Args:
            level: Logging level (logging.INFO, logging.ERROR, etc.)
            provider: Provider ID
            action: Action performed
            platform: Platform name
            resolved_exe: Executable path
            pid: Process ID
            exit_code: Exit code
            elapsed_ms: Duration in milliseconds
            error_code: Error code
            message: Additional message
            **extra_fields: Additional fields
        """
        # Auto-detect platform if not provided
        if platform is None:
            platform = platform_utils.get_platform()

        structured_msg = self._format_structured_log(
            provider=provider,
            action=action,
            platform=platform,
            resolved_exe=resolved_exe,
            pid=pid,
            exit_code=exit_code,
            elapsed_ms=elapsed_ms,
            error_code=error_code,
            message=message,
            **extra_fields
        )

        self.logger.log(level, structured_msg)

    def log_start(
        self,
        provider: str,
        resolved_exe: Optional[str] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log provider start operation"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="start",
            resolved_exe=resolved_exe,
            message=f"Starting {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_start_success(
        self,
        provider: str,
        pid: int,
        resolved_exe: Optional[str] = None,
        elapsed_ms: Optional[float] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log successful provider start"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="start",
            resolved_exe=resolved_exe,
            pid=pid,
            elapsed_ms=elapsed_ms,
            message=f"Successfully started {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_start_failure(
        self,
        provider: str,
        error_code: str,
        resolved_exe: Optional[str] = None,
        elapsed_ms: Optional[float] = None,
        exit_code: Optional[int] = None,
        message: Optional[str] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log failed provider start"""
        self.log_operation(
            level=logging.ERROR,
            provider=provider,
            action="start",
            resolved_exe=resolved_exe,
            error_code=error_code,
            elapsed_ms=elapsed_ms,
            exit_code=exit_code,
            message=message or f"Failed to start {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_stop(
        self,
        provider: str,
        pid: Optional[int] = None,
        force: bool = False,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log provider stop operation"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="stop",
            pid=pid,
            message=f"Stopping {provider}",
            force=force,
            instance_key=instance_key,
            **extra
        )

    def log_stop_success(
        self,
        provider: str,
        pid: Optional[int] = None,
        elapsed_ms: Optional[float] = None,
        exit_code: Optional[int] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log successful provider stop"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="stop",
            pid=pid,
            elapsed_ms=elapsed_ms,
            exit_code=exit_code,
            message=f"Successfully stopped {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_stop_failure(
        self,
        provider: str,
        error_code: str,
        pid: Optional[int] = None,
        elapsed_ms: Optional[float] = None,
        message: Optional[str] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log failed provider stop"""
        self.log_operation(
            level=logging.ERROR,
            provider=provider,
            action="stop",
            pid=pid,
            error_code=error_code,
            elapsed_ms=elapsed_ms,
            message=message or f"Failed to stop {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_restart(
        self,
        provider: str,
        old_pid: Optional[int] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log provider restart operation"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="restart",
            pid=old_pid,
            message=f"Restarting {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_restart_success(
        self,
        provider: str,
        old_pid: Optional[int],
        new_pid: int,
        elapsed_ms: Optional[float] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log successful provider restart"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="restart",
            pid=new_pid,
            elapsed_ms=elapsed_ms,
            message=f"Successfully restarted {provider}",
            old_pid=old_pid,
            instance_key=instance_key,
            **extra
        )

    def log_restart_failure(
        self,
        provider: str,
        error_code: str,
        old_pid: Optional[int] = None,
        elapsed_ms: Optional[float] = None,
        message: Optional[str] = None,
        instance_key: Optional[str] = None,
        **extra
    ):
        """Log failed provider restart"""
        self.log_operation(
            level=logging.ERROR,
            provider=provider,
            action="restart",
            pid=old_pid,
            error_code=error_code,
            elapsed_ms=elapsed_ms,
            message=message or f"Failed to restart {provider}",
            instance_key=instance_key,
            **extra
        )

    def log_detect(
        self,
        provider: str,
        resolved_exe: Optional[str] = None,
        searched_paths: Optional[list] = None,
        **extra
    ):
        """Log executable detection"""
        self.log_operation(
            level=logging.INFO,
            provider=provider,
            action="detect",
            resolved_exe=resolved_exe,
            message=f"Detecting {provider} executable",
            searched_paths=searched_paths,
            **extra
        )

    def log_validate(
        self,
        provider: str,
        path: str,
        is_valid: bool,
        version: Optional[str] = None,
        error_message: Optional[str] = None,
        **extra
    ):
        """Log executable validation"""
        level = logging.INFO if is_valid else logging.WARNING
        self.log_operation(
            level=level,
            provider=provider,
            action="validate",
            resolved_exe=path if is_valid else None,
            message=error_message if not is_valid else f"Validated {provider} executable",
            is_valid=is_valid,
            version=version,
            **extra
        )


# Timing context manager for operations
class OperationTimer:
    """
    Context manager for timing operations

    Usage:
        with OperationTimer() as timer:
            # perform operation
            pass

        elapsed_ms = timer.elapsed_ms()
    """

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        _operation_start_time.set(self.start_time)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        _operation_start_time.set(None)
        return False

    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        if self.start_time is None:
            return 0.0

        end = self.end_time if self.end_time is not None else time.perf_counter()
        return (end - self.start_time) * 1000.0


# Global logger instance
_provider_logger: Optional[ProviderStructuredLogger] = None


def get_provider_logger() -> ProviderStructuredLogger:
    """Get the global provider structured logger instance"""
    global _provider_logger
    if _provider_logger is None:
        _provider_logger = ProviderStructuredLogger()
    return _provider_logger


# Convenience functions
def log_provider_operation(
    provider: str,
    action: str,
    level: int = logging.INFO,
    **kwargs
):
    """
    Convenience function to log a provider operation

    Args:
        provider: Provider ID
        action: Action performed
        level: Logging level
        **kwargs: Additional fields (pid, error_code, elapsed_ms, etc.)
    """
    logger = get_provider_logger()
    logger.log_operation(level, provider, action, **kwargs)
