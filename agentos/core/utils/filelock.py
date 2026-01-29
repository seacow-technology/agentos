"""
跨平台文件锁工具

提供统一的文件锁接口,兼容 Windows、Linux 和 macOS。

- Unix/Linux/macOS: 使用 fcntl.flock
- Windows: 使用 msvcrt.locking

Usage:
    from agentos.core.utils.filelock import acquire_lock, release_lock

    file_handle = open("lockfile", "w", encoding="utf-8")
    try:
        acquire_lock(file_handle)
        # ... critical section ...
    finally:
        release_lock(file_handle)
"""

import platform
import logging

logger = logging.getLogger(__name__)


class FileLockError(Exception):
    """文件锁操作异常"""
    pass


class LockAcquisitionError(FileLockError):
    """锁获取失败异常"""
    pass


def acquire_lock(file_handle, non_blocking: bool = True):
    """
    获取文件锁 (跨平台)

    Args:
        file_handle: 打开的文件对象
        non_blocking: 是否非阻塞 (True: 锁被占用时立即失败, False: 等待)

    Raises:
        LockAcquisitionError: 锁已被其他进程持有 (仅 non_blocking=True)
        FileLockError: 其他锁操作失败
    """
    system = platform.system()

    try:
        if system == "Windows":
            _acquire_lock_windows(file_handle, non_blocking)
        else:
            _acquire_lock_unix(file_handle, non_blocking)

        logger.debug(f"Acquired lock on {file_handle.name}")

    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        raise


def release_lock(file_handle):
    """
    释放文件锁 (跨平台)

    Args:
        file_handle: 持有锁的文件对象

    Raises:
        FileLockError: 锁释放失败
    """
    system = platform.system()

    try:
        if system == "Windows":
            _release_lock_windows(file_handle)
        else:
            _release_lock_unix(file_handle)

        logger.debug(f"Released lock on {file_handle.name}")

    except Exception as e:
        logger.error(f"Failed to release lock: {e}")
        raise FileLockError(f"Failed to release lock: {e}") from e


# ============================================
# Unix/Linux/macOS 实现
# ============================================

def _acquire_lock_unix(file_handle, non_blocking: bool):
    """Unix 平台文件锁实现"""
    import fcntl

    try:
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB

        fcntl.flock(file_handle.fileno(), flags)

    except BlockingIOError as e:
        raise LockAcquisitionError(
            f"Lock is held by another process: {file_handle.name}"
        ) from e
    except OSError as e:
        raise FileLockError(f"fcntl.flock failed: {e}") from e


def _release_lock_unix(file_handle):
    """Unix 平台锁释放实现"""
    import fcntl

    try:
        fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
    except OSError as e:
        raise FileLockError(f"fcntl.flock unlock failed: {e}") from e


# ============================================
# Windows 实现
# ============================================

def _acquire_lock_windows(file_handle, non_blocking: bool):
    """Windows 平台文件锁实现"""
    import msvcrt

    try:
        # Windows: msvcrt.locking() 参数
        # LK_NBLCK: 非阻塞锁
        # LK_LOCK: 阻塞锁
        # nbytes: 锁定的字节数 (1 表示锁整个文件)

        mode = msvcrt.LK_NBLCK if non_blocking else msvcrt.LK_LOCK
        msvcrt.locking(file_handle.fileno(), mode, 1)

    except OSError as e:
        # Windows: errno 13 (Permission denied) = 锁被占用
        # Windows: errno 36 (Resource deadlock avoided) = 锁被占用
        if e.errno in (13, 36):
            raise LockAcquisitionError(
                f"Lock is held by another process: {file_handle.name}"
            ) from e
        else:
            raise FileLockError(f"msvcrt.locking failed: {e}") from e


def _release_lock_windows(file_handle):
    """Windows 平台锁释放实现"""
    import msvcrt

    try:
        # LK_UNLCK: 解锁
        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError as e:
        raise FileLockError(f"msvcrt.locking unlock failed: {e}") from e
