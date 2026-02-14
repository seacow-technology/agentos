from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

from .interface import ExecResult, SftpListItem, SftpTransferResult


class ProbeSshProvider:
    """Deterministic, no-network provider for CI/probe-only mode."""

    def exec(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        command: str,
        timeout_ms: int,
    ) -> ExecResult:
        started = time.time()
        out = f"[probe] {command}\n"
        return ExecResult(exit_code=0, stdout=out, stderr="", duration_ms=int((time.time() - started) * 1000))

    def sftp_list(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        path: str,
        timeout_ms: int,
    ) -> list[SftpListItem]:
        return [
            SftpListItem(name=".", type="dir", size=0),
            SftpListItem(name="..", type="dir", size=0),
            SftpListItem(name="README.txt", type="file", size=24),
            SftpListItem(name="notes.log", type="file", size=64),
        ]

    def sftp_download(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        remote_path: str,
        timeout_ms: int,
    ) -> tuple[str, SftpTransferResult]:
        started = time.time()
        content = f"[probe] download {remote_path}\n".encode("utf-8")
        fd, tmp = tempfile.mkstemp(prefix="octo-sftp-probe-", suffix=".bin")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(content)
        return tmp, SftpTransferResult(
            bytes_total=len(content),
            bytes_done=len(content),
            duration_ms=int((time.time() - started) * 1000),
        )

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
    ) -> SftpTransferResult:
        started = time.time()
        return SftpTransferResult(
            bytes_total=len(content),
            bytes_done=len(content),
            duration_ms=int((time.time() - started) * 1000),
        )

    def sftp_remove(
        self,
        *,
        hostname: str,
        port: int,
        username: Optional[str],
        auth_ref: Optional[str],
        remote_path: str,
        timeout_ms: int,
    ) -> SftpTransferResult:
        started = time.time()
        return SftpTransferResult(bytes_total=None, bytes_done=0, duration_ms=int((time.time() - started) * 1000))

