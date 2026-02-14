from __future__ import annotations

import os
from functools import lru_cache

from octopusos.core.providers.ssh_provider_registry import resolve_ssh_provider
from octopusos.providers.ssh import ProbeSshProvider, SystemSshProvider
from octopusos.providers.ssh.interface import ISshProvider
from octopusos.providers.ssh.mcp import McpSshProvider


def _env_flag(name: str, default: str) -> bool:
    v = (os.getenv(name) or default).strip().lower()
    return v in {"1", "true", "yes", "on"}


@lru_cache(maxsize=4)
def _probe_provider() -> ISshProvider:
    return ProbeSshProvider()


@lru_cache(maxsize=4)
def _system_provider() -> ISshProvider:
    return SystemSshProvider()

@lru_cache(maxsize=4)
def _mcp_provider() -> ISshProvider:
    # Placeholder provider (methods raise NotImplementedError).
    return McpSshProvider()


def get_ssh_provider(*, allow_real: bool) -> ISshProvider:
    """Provider factory for SSH/SFTP execution.

    Governance decides whether a call is allowed to be real (env gates, per-connection
    probe_only). The provider selection is purely "probe vs system" for now, but this
    is the seam where MCP can be inserted later.
    """
    selection = resolve_ssh_provider()
    selected = (selection.provider or "probe").strip().lower()

    # Global env gate: only allow real execution with explicit opt-in.
    # Many call sites already gate allow_real; keep this as an additional safety net.
    env_real = _env_flag("OCTO_SSH_REAL", "0")
    can_real = bool(allow_real) and bool(env_real) and bool(selection.allow_real)

    if selected == "probe":
        return _probe_provider()
    if selected == "system":
        return _system_provider() if can_real else _probe_provider()
    if selected == "mcp":
        # API layer should gate before reaching provider execution.
        return _mcp_provider() if can_real else _probe_provider()
    return _probe_provider()
