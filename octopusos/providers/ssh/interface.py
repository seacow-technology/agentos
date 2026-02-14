"""SSH/SFTP provider interface.

Providers do execution only:
- no HTTPException
- no audit logging
- no gate decisions

Governance (gates, skills/capabilities, audit) lives in API layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    error_code: Optional[str] = None


@dataclass(frozen=True)
class SftpListItem:
    name: str
    type: str = "file"
    size: Optional[int] = None


@dataclass(frozen=True)
class SftpTransferResult:
    bytes_total: Optional[int]
    bytes_done: int
    duration_ms: int
    error_code: Optional[str] = None


class ISshProvider(Protocol):
    def exec(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        command: str,
        timeout_ms: int,
    ) -> ExecResult: ...

    def sftp_list(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        path: str,
        timeout_ms: int,
    ) -> list[SftpListItem]: ...

    def sftp_download(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        remote_path: str,
        timeout_ms: int,
    ) -> tuple[str, SftpTransferResult]: ...

    def sftp_upload(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        remote_path: str,
        content: bytes,
        timeout_ms: int,
    ) -> SftpTransferResult: ...

    def sftp_remove(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        remote_path: str,
        timeout_ms: int,
    ) -> SftpTransferResult: ...

