"""DEPRECATED: SSH provider implementation moved to `octopusos.providers.ssh`.

This module is kept as a compatibility shim for any legacy imports in the tree.

New code should use:
- `octopusos.providers.factory.get_ssh_provider(...)`
- `octopusos.providers.ssh.*`
"""

from __future__ import annotations

from octopusos.providers.ssh.interface import ExecResult, ISshProvider, SftpListItem, SftpTransferResult
from octopusos.providers.ssh.probe import ProbeSshProvider
from octopusos.providers.ssh.system import SystemSshProvider

__all__ = [
    "ISshProvider",
    "ExecResult",
    "SftpListItem",
    "SftpTransferResult",
    "ProbeSshProvider",
    "SystemSshProvider",
]

