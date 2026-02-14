from __future__ import annotations

from .interface import ExecResult, ISshProvider, SftpListItem, SftpTransferResult


class McpSshProvider:
    """Placeholder for an MCP-backed SSH/SFTP provider.

    The API layer should not change when this is implemented; only the factory
    selection should be updated.
    """

    def exec(self, *, hostname: str, port: int, username, auth_ref, command: str, timeout_ms: int) -> ExecResult:
        raise NotImplementedError("MCP SSH provider is not implemented yet")

    def sftp_list(self, *, hostname: str, port: int, username, auth_ref, path: str, timeout_ms: int) -> list[SftpListItem]:
        raise NotImplementedError("MCP SSH provider is not implemented yet")

    def sftp_download(self, *, hostname: str, port: int, username, auth_ref, remote_path: str, timeout_ms: int) -> tuple[str, SftpTransferResult]:
        raise NotImplementedError("MCP SSH provider is not implemented yet")

    def sftp_upload(self, *, hostname: str, port: int, username, auth_ref, remote_path: str, content: bytes, timeout_ms: int) -> SftpTransferResult:
        raise NotImplementedError("MCP SSH provider is not implemented yet")

    def sftp_remove(self, *, hostname: str, port: int, username, auth_ref, remote_path: str, timeout_ms: int) -> SftpTransferResult:
        raise NotImplementedError("MCP SSH provider is not implemented yet")

