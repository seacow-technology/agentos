from __future__ import annotations

import os
import subprocess
import tempfile
import time
from typing import Optional

from octopusos.webui.api._db_bridgeos import ensure_bridgeos_schema
from octopusos.webui.api._secret_store import decrypt_secret

from .interface import ExecResult, SftpListItem, SftpTransferResult


def _classify_ssh_error(*, exit_code: int, stderr: str, timed_out: bool) -> Optional[str]:
    if timed_out:
        return "SSH_TIMEOUT"
    if exit_code == 0:
        return None
    s = (stderr or "").lower()
    if "permission denied" in s:
        return "SSH_AUTH_FAILED"
    if "connection timed out" in s or "operation timed out" in s:
        return "SSH_TIMEOUT"
    if "could not resolve hostname" in s:
        return "SSH_HOST_UNREACHABLE"
    if "no route to host" in s or "connection refused" in s:
        return "SSH_HOST_UNREACHABLE"
    if exit_code == 255:
        return "SSH_HOST_UNREACHABLE"
    return "SSH_EXEC_FAILED"


def _parse_secret_id(auth_ref: str) -> Optional[str]:
    s = (auth_ref or "").strip()
    if s.startswith("secret_ref://keychain/"):
        return s.split("secret_ref://keychain/", 1)[1].strip() or None
    return None


def _resolve_private_key_pem(conn, auth_ref: Optional[str]) -> Optional[str]:
    if not auth_ref:
        return None
    secret_id = _parse_secret_id(auth_ref)
    if not secret_id:
        return None
    ensure_bridgeos_schema(conn)
    row = conn.execute(
        "SELECT kind, encrypted_blob FROM secrets WHERE secret_id = ?",
        (secret_id,),
    ).fetchone()
    if not row:
        return None
    kind = str(row["kind"] or "")
    if kind not in {"ssh_private_key", "ssh_key", "ssh_private_key_pem"}:
        return None
    blob = row["encrypted_blob"]
    if not blob:
        return None
    return decrypt_secret(str(blob))


class SystemSshProvider:
    def _maybe_key_args(self, auth_ref: Optional[str]) -> tuple[list[str], Optional[str]]:
        """Resolve a keychain-backed private key and prepare OpenSSH-style args.

        Returns (key_args, key_tmp_path). Caller must delete key_tmp_path if not None.
        """
        key_tmp: Optional[str] = None
        key_args: list[str] = []
        if not auth_ref:
            return key_args, key_tmp
        try:
            from octopusos.webui.api._db_bridgeos import connect_bridgeos

            conn = connect_bridgeos()
            try:
                pem = _resolve_private_key_pem(conn, auth_ref)
            finally:
                conn.close()
            if not pem:
                return key_args, key_tmp
            fd, key_tmp = tempfile.mkstemp(prefix="octo-ssh-key-", suffix=".pem")
            os.close(fd)
            with open(key_tmp, "w", encoding="utf-8") as f:
                f.write(pem)
            os.chmod(key_tmp, 0o600)
            key_args = ["-i", key_tmp, "-o", "IdentitiesOnly=yes"]
        except Exception:
            key_tmp = None
            key_args = []
        return key_args, key_tmp

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
        user_host = f"{username}@{hostname}" if username else hostname
        key_args, key_tmp = self._maybe_key_args(auth_ref)

        args = [
            "ssh",
            "-p",
            str(int(port)),
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={max(1, int(timeout_ms / 1000))}",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            *key_args,
            user_host,
            command,
        ]
        try:
            cp = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, timeout_ms / 1000.0),
            )
            err_code = _classify_ssh_error(exit_code=int(cp.returncode), stderr=cp.stderr or "", timed_out=False)
            return ExecResult(
                exit_code=int(cp.returncode),
                stdout=cp.stdout or "",
                stderr=cp.stderr or "",
                duration_ms=int((time.time() - started) * 1000),
                error_code=err_code,
            )
        except subprocess.TimeoutExpired as e:
            return ExecResult(
                exit_code=124,
                stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
                stderr=(e.stderr or "") if isinstance(e.stderr, str) else "",
                duration_ms=int((time.time() - started) * 1000),
                error_code=_classify_ssh_error(exit_code=124, stderr=str(e.stderr or ""), timed_out=True),
            )
        finally:
            if key_tmp:
                try:
                    os.remove(key_tmp)
                except Exception:
                    pass

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
        user_host = f"{username}@{hostname}" if username else hostname
        batch = f"ls -1 {path}\n"
        key_args, key_tmp = self._maybe_key_args(auth_ref)
        args = [
            "sftp",
            "-P",
            str(int(port)),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            *key_args,
            user_host,
        ]
        try:
            cp = subprocess.run(
                args,
                input=batch,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, timeout_ms / 1000.0),
            )
            if cp.returncode != 0:
                raise RuntimeError((cp.stderr or cp.stdout or "sftp list failed")[:200])
            items: list[SftpListItem] = []
            for line in (cp.stdout or "").splitlines():
                name = line.strip()
                if not name or name.startswith("sftp>"):
                    continue
                items.append(SftpListItem(name=name, type="file"))
            return items
        finally:
            if key_tmp:
                try:
                    os.remove(key_tmp)
                except Exception:
                    pass

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
        user_host = f"{username}@{hostname}" if username else hostname
        fd, tmp = tempfile.mkstemp(prefix="octo-scp-dl-", suffix=".bin")
        os.close(fd)
        key_args, key_tmp = self._maybe_key_args(auth_ref)
        args = [
            "scp",
            "-P",
            str(int(port)),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            *key_args,
            f"{user_host}:{remote_path}",
            tmp,
        ]
        try:
            cp = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, timeout_ms / 1000.0),
            )
            if cp.returncode != 0:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                raise RuntimeError((cp.stderr or cp.stdout or "scp download failed")[:200])
            size = os.path.getsize(tmp)
            return tmp, SftpTransferResult(
                bytes_total=size,
                bytes_done=size,
                duration_ms=int((time.time() - started) * 1000),
            )
        finally:
            if key_tmp:
                try:
                    os.remove(key_tmp)
                except Exception:
                    pass

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
        user_host = f"{username}@{hostname}" if username else hostname
        fd, tmp = tempfile.mkstemp(prefix="octo-scp-ul-", suffix=".bin")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(content)
        key_args, key_tmp = self._maybe_key_args(auth_ref)
        try:
            args = [
                "scp",
                "-P",
                str(int(port)),
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                *key_args,
                tmp,
                f"{user_host}:{remote_path}",
            ]
            cp = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, timeout_ms / 1000.0),
            )
            if cp.returncode != 0:
                raise RuntimeError((cp.stderr or cp.stdout or "scp upload failed")[:200])
            size = len(content)
            return SftpTransferResult(
                bytes_total=size,
                bytes_done=size,
                duration_ms=int((time.time() - started) * 1000),
            )
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
            if key_tmp:
                try:
                    os.remove(key_tmp)
                except Exception:
                    pass

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
        user_host = f"{username}@{hostname}" if username else hostname
        if "\n" in remote_path or "\r" in remote_path:
            raise RuntimeError("invalid remote_path")
        batch = f"rm {remote_path}\n"
        key_args, key_tmp = self._maybe_key_args(auth_ref)
        args = [
            "sftp",
            "-P",
            str(int(port)),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            *key_args,
            user_host,
        ]
        try:
            cp = subprocess.run(
                args,
                input=batch,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, timeout_ms / 1000.0),
            )
            if cp.returncode != 0:
                raise RuntimeError((cp.stderr or cp.stdout or "sftp remove failed")[:200])
            return SftpTransferResult(
                bytes_total=None,
                bytes_done=0,
                duration_ms=int((time.time() - started) * 1000),
            )
        finally:
            if key_tmp:
                try:
                    os.remove(key_tmp)
                except Exception:
                    pass

