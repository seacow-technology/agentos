from __future__ import annotations

import os
from contextlib import contextmanager

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

from .paths import ensure_manager_dirs


class OperationInProgress(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if psutil is not None:
        try:
            return psutil.pid_exists(pid)
        except Exception:
            pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@contextmanager
def manager_lock():
    paths = ensure_manager_dirs()
    lock_file = paths.lock_file

    # Stale lock cleanup.
    if lock_file.exists():
        try:
            stale_pid = int(lock_file.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            stale_pid = 0
        if stale_pid and _pid_alive(stale_pid):
            raise OperationInProgress("operation_in_progress")
        lock_file.unlink(missing_ok=True)

    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:  # pragma: no cover - race
        raise OperationInProgress("operation_in_progress") from exc
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        lock_file.unlink(missing_ok=True)

