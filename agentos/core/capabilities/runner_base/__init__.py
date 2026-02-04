"""
Capability Runner System

This module provides the execution framework for extension capabilities,
including the base runner abstraction and concrete implementations.
"""

from .base import (
    Runner,
    Invocation,
    RunResult,
    RunnerError,
    ValidationError,
    TimeoutError as RunnerTimeoutError,
)
from .builtin import BuiltinRunner
from .simulated import SimulatedRunner
from .shell import ShellRunner
from .shell_config import ShellConfig
from .command_template import CommandTemplate, CommandTemplateError

# Backward compatibility alias
MockRunner = SimulatedRunner

__all__ = [
    "Runner",
    "Invocation",
    "RunResult",
    "RunnerError",
    "ValidationError",
    "RunnerTimeoutError",
    "BuiltinRunner",
    "SimulatedRunner",
    "MockRunner",  # Backward compatibility alias
    "ShellRunner",
    "ShellConfig",
    "CommandTemplate",
    "CommandTemplateError",
    "get_runner",
]


def get_runner(runner_type: str, **kwargs) -> Runner:
    """
    Factory function to get runner instance by type

    Args:
        runner_type: Runner type identifier
            - "builtin" or "exec.python_handler" -> BuiltinRunner
            - "simulated" or "mock" -> SimulatedRunner (mock is deprecated alias)
            - "shell" or "exec.shell" -> ShellRunner
        **kwargs: Additional arguments passed to runner constructor

    Returns:
        Runner instance

    Raises:
        ValueError: If runner type is not supported

    Examples:
        # Get builtin runner
        runner = get_runner("builtin")

        # Get builtin runner with custom timeout
        runner = get_runner("builtin", default_timeout=60)

        # Get simulated runner
        runner = get_runner("simulated", delay_per_stage=1.0)

        # Get shell runner
        runner = get_runner("shell", config=shell_config)
    """
    # Normalize runner type
    runner_type_lower = runner_type.lower()

    # Map runner types to implementations
    if runner_type_lower in ("builtin", "exec.python_handler", "default"):
        return BuiltinRunner(**kwargs)
    elif runner_type_lower in ("simulated", "mock"):  # "mock" is deprecated alias
        return SimulatedRunner(**kwargs)
    elif runner_type_lower in ("shell", "exec.shell"):
        return ShellRunner(**kwargs)
    else:
        raise ValueError(
            f"Unknown runner type: {runner_type}. "
            f"Supported types: builtin, simulated, shell"
        )
