"""Sandbox Isolation System for Extension Execution

Phase D1: Container/WASM-level sandbox isolation for HIGH risk extensions.

This module provides runtime isolation to ensure HIGH risk extensions cannot
access host resources without explicit authorization.

Core Components:
- ISandbox: Abstract interface for sandbox implementations
- DockerSandbox: Docker container-based isolation (primary implementation)
- SandboxConfig: Configuration for sandbox execution

Red Lines:
1. HIGH risk extensions MUST run in sandbox
2. Sandbox failure = execution blocked (no fallback)
3. Default deny-by-default approach

Created: 2026-02-02
Phase: D'
"""

from agentos.core.capabilities.sandbox.interface import ISandbox
from agentos.core.capabilities.sandbox.docker_sandbox import DockerSandbox
from agentos.core.capabilities.sandbox.config import (
    SandboxConfig,
    HIGH_RISK_CONFIG,
    MEDIUM_RISK_CONFIG,
    LOW_RISK_CONFIG
)
from agentos.core.capabilities.sandbox.exceptions import (
    SandboxError,
    SandboxUnavailableError,
    SandboxTimeoutError,
    SandboxResourceError
)

__all__ = [
    'ISandbox',
    'DockerSandbox',
    'SandboxConfig',
    'HIGH_RISK_CONFIG',
    'MEDIUM_RISK_CONFIG',
    'LOW_RISK_CONFIG',
    'SandboxError',
    'SandboxUnavailableError',
    'SandboxTimeoutError',
    'SandboxResourceError',
]
