"""
跨平台进程管理工具

提供统一的进程操作接口,兼容 Windows、Linux 和 macOS。

Functions:
    - terminate_process: 终止进程 (SIGTERM on Unix, taskkill on Windows)
    - kill_process: 强制终止进程 (SIGKILL on Unix, taskkill /F on Windows)
    - is_process_running: 检查进程是否运行
"""

import platform
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessError(Exception):
    """进程操作异常"""
    pass


def terminate_process(pid: int, timeout: float = 2.0) -> bool:
    """
    优雅地终止进程 (跨平台)

    Unix: 发送 SIGTERM, 等待 timeout 秒, 超时则 SIGKILL
    Windows: 使用 taskkill, 超时则 taskkill /F

    Args:
        pid: 进程 ID
        timeout: 等待进程退出的超时时间(秒)

    Returns:
        True: 进程成功终止
        False: 进程不存在或已终止

    Raises:
        ProcessError: 终止失败
    """
    if not is_process_running(pid):
        logger.debug(f"Process {pid} is not running")
        return False

    system = platform.system()

    try:
        if system == "Windows":
            return _terminate_process_windows(pid, timeout)
        else:
            return _terminate_process_unix(pid, timeout)
    except Exception as e:
        logger.error(f"Failed to terminate process {pid}: {e}")
        raise ProcessError(f"Failed to terminate process {pid}: {e}") from e


def kill_process(pid: int) -> bool:
    """
    强制终止进程 (跨平台)

    Unix: 发送 SIGKILL
    Windows: 使用 taskkill /F

    Args:
        pid: 进程 ID

    Returns:
        True: 进程成功终止
        False: 进程不存在或已终止

    Raises:
        ProcessError: 终止失败
    """
    if not is_process_running(pid):
        logger.debug(f"Process {pid} is not running")
        return False

    system = platform.system()

    try:
        if system == "Windows":
            return _kill_process_windows(pid)
        else:
            return _kill_process_unix(pid)
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {e}")
        raise ProcessError(f"Failed to kill process {pid}: {e}") from e


def is_process_running(pid: int) -> bool:
    """
    检查进程是否运行 (跨平台)

    Args:
        pid: 进程 ID

    Returns:
        True: 进程Running
        False: 进程不存在
    """
    system = platform.system()

    try:
        if system == "Windows":
            return _is_process_running_windows(pid)
        else:
            return _is_process_running_unix(pid)
    except Exception as e:
        logger.warning(f"Failed to check process {pid}: {e}")
        return False


# ============================================
# Unix/Linux/macOS 实现
# ============================================

def _terminate_process_unix(pid: int, timeout: float) -> bool:
    """Unix 平台优雅终止进程"""
    import signal
    import time
    import os

    try:
        # 发送 SIGTERM
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent SIGTERM to process {pid}")

        # 等待进程退出
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not is_process_running(pid):
                logger.info(f"Process {pid} terminated gracefully")
                return True
            time.sleep(0.1)

        # 超时,强制 SIGKILL
        logger.warning(f"Process {pid} did not terminate after {timeout}s, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)

        # 等待 SIGKILL 生效,轮询确认进程已终止
        kill_start = time.time()
        while time.time() - kill_start < 1.0:  # 给 SIGKILL 最多 1 秒时间
            if not is_process_running(pid):
                logger.info(f"Process {pid} force killed")
                return True
            time.sleep(0.05)

        return True

    except ProcessLookupError:
        # 进程已不存在
        return False
    except PermissionError as e:
        raise ProcessError(f"Permission denied to terminate process {pid}") from e


def _kill_process_unix(pid: int) -> bool:
    """Unix 平台强制终止进程"""
    import signal
    import os
    import time

    try:
        os.kill(pid, signal.SIGKILL)
        logger.info(f"Sent SIGKILL to process {pid}")

        # 等待 SIGKILL 生效,轮询确认进程已终止
        start_time = time.time()
        while time.time() - start_time < 1.0:  # 给 SIGKILL 最多 1 秒时间
            if not is_process_running(pid):
                logger.info(f"Process {pid} killed")
                return True
            time.sleep(0.05)

        return True
    except ProcessLookupError:
        return False
    except PermissionError as e:
        raise ProcessError(f"Permission denied to kill process {pid}") from e


def _is_process_running_unix(pid: int) -> bool:
    """Unix 平台检查进程存在"""
    import os

    # 验证 PID 有效性
    if pid < 0:
        return False

    try:
        # 发送信号 0 不会杀死进程,只检查是否存在
        os.kill(pid, 0)

        # 进程存在,但需要排除僵尸进程 (zombie)
        # 僵尸进程已死亡,只是等待父进程回收
        try:
            import psutil
            proc = psutil.Process(pid)
            # 如果是僵尸进程,视为不运行
            if proc.status() == psutil.STATUS_ZOMBIE:
                logger.debug(f"Process {pid} is zombie (not running)")
                return False
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied):
            # 如果 psutil 不Available或无法访问进程信息,回退到基本检查
            pass

        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在但无权限,视为Running
        return True


# ============================================
# Windows 实现
# ============================================

def _terminate_process_windows(pid: int, timeout: float) -> bool:
    """Windows 平台优雅终止进程"""
    import time

    try:
        # Windows: 先尝试普通 taskkill (类似 SIGTERM)
        result = subprocess.run(
            ["taskkill", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.info(f"Sent taskkill to process {pid}")

            # 等待进程退出
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not is_process_running(pid):
                    logger.info(f"Process {pid} terminated gracefully")
                    return True
                time.sleep(0.1)

        # 超时或失败,强制终止
        logger.warning(f"Process {pid} did not terminate, using /F flag")
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        raise ProcessError(f"taskkill command timed out for process {pid}")
    except FileNotFoundError:
        raise ProcessError("taskkill command not found (not a Windows system?)")


def _kill_process_windows(pid: int) -> bool:
    """Windows 平台强制终止进程"""
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.info(f"Force killed process {pid}")
            return True
        else:
            # 错误代码 128: 进程不存在
            if "not found" in result.stderr.lower():
                return False
            raise ProcessError(f"taskkill failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise ProcessError(f"taskkill command timed out for process {pid}")
    except FileNotFoundError:
        raise ProcessError("taskkill command not found (not a Windows system?)")


def _is_process_running_windows(pid: int) -> bool:
    """Windows 平台检查进程存在"""
    try:
        # Windows: 使用 tasklist 查询进程
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=2
        )

        # 如果输出包含 PID, 则进程存在
        return str(pid) in result.stdout

    except (subprocess.TimeoutExpired, FileNotFoundError):
        # 回退方案: 尝试 taskkill 查询 (不实际终止)
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=2
            )
            # 如果返回错误 128, 则进程不存在
            return "not found" not in result.stderr.lower()
        except:
            return False
