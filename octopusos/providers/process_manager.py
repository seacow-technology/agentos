"""
Provider Process Manager

Manages lifecycle of locally-launched provider services (e.g., llama-server).

Features:
- Start/stop provider processes
- Port conflict detection
- Process monitoring (PID, stdout/stderr capture)
- Launch command building from config
- Cross-platform process management (Windows/macOS/Linux)

Sprint B+ Provider Architecture Refactor
Phase 1.2: Cross-platform Process Management
"""

import asyncio
import json
import logging
import os
import platform
import psutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, Deque
import socket

from agentos.providers.platform_utils import get_run_dir, get_log_dir
from agentos.core.utils.process import terminate_process, kill_process

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running provider process"""
    pid: int
    command: str
    started_at: float
    stdout_buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=1000))
    stderr_buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=1000))
    returncode: Optional[int] = None


class ProcessManager:
    """
    Manages provider service processes

    Singleton pattern - use get_instance()
    Features:
    - PID file tracking for reboot recovery
    - Process monitoring and output capture
    - Graceful shutdown with reader cleanup
    """

    _instance: Optional["ProcessManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._processes: Dict[str, ProcessInfo] = {}  # instance_key -> ProcessInfo
        self._process_objects: Dict[str, subprocess.Popen] = {}
        self._reader_tasks: Dict[str, list] = {}  # instance_key -> [stdout_task, stderr_task]

        # PID files directory - use cross-platform path from platform_utils
        self.run_dir = get_run_dir()
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Log directory for process output
        self.log_dir = get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Recover processes on init
        self._recover_processes()

    @classmethod
    def get_instance(cls) -> "ProcessManager":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_pidfile_path(self, instance_key: str) -> Path:
        """Get pidfile path for an instance"""
        # Replace : with __ for filesystem safety
        safe_key = instance_key.replace(":", "__")
        return self.run_dir / f"{safe_key}.pid"

    def _write_pidfile(self, instance_key: str, proc_info: ProcessInfo, base_url: str):
        """
        Write pidfile for process tracking with timestamp for validation.

        PID file format includes:
        - pid: Process ID
        - timestamp: ISO format timestamp for verification
        - command: Command line that was used to start the process
        - started_at: Unix timestamp of process start
        - base_url: Service endpoint URL
        - instance_key: Unique identifier for this instance

        Task #16: P0.3 - PID persistence enhancement
        """
        pidfile = self._get_pidfile_path(instance_key)
        try:
            from datetime import datetime
            data = {
                "pid": proc_info.pid,
                "timestamp": datetime.now().isoformat(),
                "command": proc_info.command,
                "started_at": proc_info.started_at,
                "base_url": base_url,
                "instance_key": instance_key,
            }
            with open(pidfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Wrote pidfile: {pidfile}")
        except Exception as e:
            logger.error(f"Failed to write pidfile {pidfile}: {e}")

    def _read_pidfile(self, instance_key: str) -> Optional[Dict[str, Any]]:
        """Read pidfile data"""
        pidfile = self._get_pidfile_path(instance_key)
        if not pidfile.exists():
            return None

        try:
            with open(pidfile, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read pidfile {pidfile}: {e}")
            return None

    def _remove_pidfile(self, instance_key: str):
        """Remove pidfile"""
        pidfile = self._get_pidfile_path(instance_key)
        try:
            if pidfile.exists():
                pidfile.unlink()
                logger.debug(f"Removed pidfile: {pidfile}")
        except Exception as e:
            logger.error(f"Failed to remove pidfile {pidfile}: {e}")

    def save_pid(self, provider: str, instance: str, pid: int):
        """
        Save PID to file with timestamp.

        Task #16: P0.3 - Public API for PID persistence

        Args:
            provider: Provider ID (e.g., "ollama")
            instance: Instance ID (e.g., "default")
            pid: Process ID to save

        Note:
            This is a public interface to _write_pidfile for external use.
            Creates a minimal PID file when process info is not available.
        """
        from datetime import datetime
        instance_key = f"{provider}:{instance}"
        pidfile = self._get_pidfile_path(instance_key)
        try:
            data = {
                "pid": pid,
                "timestamp": datetime.now().isoformat(),
                "instance_key": instance_key,
                "started_at": time.time(),
            }
            with open(pidfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved PID {pid} for {instance_key}")
        except Exception as e:
            logger.error(f"Failed to save PID for {instance_key}: {e}")

    def load_pid(self, provider: str, instance: str) -> Optional[dict]:
        """
        Load PID from file, returning PID info with timestamp.

        Task #16: P0.3 - Public API for PID persistence

        Args:
            provider: Provider ID (e.g., "ollama")
            instance: Instance ID (e.g., "default")

        Returns:
            dict with keys: {"pid": int, "timestamp": str, "started_at": float}
            or None if PID file doesn't exist or is invalid

        Example:
            >>> pm.load_pid("ollama", "default")
            {"pid": 12345, "timestamp": "2026-01-29T10:30:00", "started_at": 1738144200.0}
        """
        instance_key = f"{provider}:{instance}"
        pidfile_data = self._read_pidfile(instance_key)
        if not pidfile_data:
            return None

        # Extract required fields
        pid = pidfile_data.get("pid")
        timestamp = pidfile_data.get("timestamp")
        started_at = pidfile_data.get("started_at")

        if pid is None:
            return None

        return {
            "pid": pid,
            "timestamp": timestamp,
            "started_at": started_at,
        }

    def verify_pid(self, pid_info: dict) -> bool:
        """
        Verify that a PID from PID file is still running.

        Task #16: P0.3 - PID verification utility

        Args:
            pid_info: Dictionary with at least {"pid": int, "timestamp": str}
                     as returned by load_pid()

        Returns:
            bool: True if process is still running, False otherwise

        Example:
            >>> pid_info = pm.load_pid("ollama", "default")
            >>> if pid_info and pm.verify_pid(pid_info):
            ...     print("Process is running")
        """
        pid = pid_info.get("pid")
        if pid is None:
            return False

        return self._is_process_alive(pid)

    def _is_process_alive(self, pid: int) -> bool:
        """
        Check if process with PID is alive using psutil (cross-platform).

        This method replaces platform-specific implementations like:
        - Unix: os.kill(pid, 0)
        - Windows: tasklist /FI "PID eq {pid}"

        Args:
            pid: Process ID to check

        Returns:
            bool: True if process is running, False otherwise

        Note:
            Uses psutil for cross-platform compatibility, handling
            NoSuchProcess and AccessDenied exceptions gracefully.
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _recover_processes(self):
        """Recover processes from pidfiles on startup"""
        if not self.run_dir.exists():
            return

        for pidfile in self.run_dir.glob("*.pid"):
            try:
                with open(pidfile, "r", encoding="utf-8") as f:
                    data = json.load(f)

                instance_key = data.get("instance_key")
                pid = data.get("pid")

                if not instance_key or not pid:
                    pidfile.unlink()
                    continue

                # Check if process is still alive
                if self._is_process_alive(pid):
                    # Recover process info
                    proc_info = ProcessInfo(
                        pid=pid,
                        command=data.get("command", ""),
                        started_at=data.get("started_at", time.time()),
                    )
                    self._processes[instance_key] = proc_info
                    logger.info(
                        f"Recovered process {instance_key} (PID {pid}) from pidfile"
                    )
                else:
                    # Process died, clean up pidfile
                    pidfile.unlink()
                    logger.debug(f"Cleaned up stale pidfile: {pidfile}")

            except Exception as e:
                logger.error(f"Failed to recover from pidfile {pidfile}: {e}")

    def _check_port_available(self, host: str, port: int) -> tuple[bool, Optional[str]]:
        """
        Check if port is available

        Returns: (is_available, occupant_info)
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)

        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                # Port is occupied
                return False, f"Port {port} is already in use"
            else:
                # Port is available
                return True, None
        except socket.error as e:
            logger.warning(f"Socket error checking port {port}: {e}")
            return False, f"Socket error: {e}"
        finally:
            sock.close()

    def _build_command(
        self,
        bin_name: str,
        args: Dict[str, Any],
    ) -> list[str]:
        """
        Build command line from launch config

        Args:
            bin_name: Binary name (e.g., "llama-server")
            args: Dictionary of arguments

        Returns:
            Command as list of strings

        Example:
            args = {
                "model": "/path/to/model.gguf",
                "host": "127.0.0.1",
                "port": 11434,
                "ngl": 99,
                "threads": 8,
                "ctx": 8192,
            }
            -> ["llama-server", "-m", "/path/to/model.gguf", "--host", "127.0.0.1", ...]
        """
        cmd = [bin_name]

        # Map common arg names to llama-server flags
        flag_mapping = {
            "model": "-m",
            "host": "--host",
            "port": "--port",
            "ngl": "-ngl",
            "threads": "-t",
            "ctx": "-c",
            "context": "-c",
            "n_ctx": "-c",
            "n_gpu_layers": "-ngl",
            "n_threads": "-t",
        }

        for key, value in args.items():
            if key == "extra_args":
                # Extra args as a list or string
                if isinstance(value, list):
                    cmd.extend(value)
                elif isinstance(value, str):
                    cmd.extend(value.split())
                continue

            # Map key to flag
            flag = flag_mapping.get(key, f"--{key}")

            # Add to command
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            else:
                cmd.extend([flag, str(value)])

        return cmd

    async def start_process(
        self,
        instance_key: str,
        bin_name: str,
        args: Dict[str, Any],
        check_port: bool = True,
    ) -> tuple[bool, str]:
        """
        Start a provider process

        Args:
            instance_key: Unique key for this instance (e.g., "llamacpp:glm47flash-q8")
            bin_name: Binary name (e.g., "llama-server")
            args: Launch arguments
            check_port: If True, check port availability before starting

        Returns:
            (success, message)
        """
        # Check if already running
        if instance_key in self._processes:
            proc_info = self._processes[instance_key]
            if self.is_process_running(instance_key):
                return False, f"Process already running (PID {proc_info.pid})"

        # Check port availability
        if check_port:
            host = args.get("host", "127.0.0.1")
            port = args.get("port")

            if port:
                is_available, occupant_info = self._check_port_available(host, port)
                if not is_available:
                    return False, occupant_info or "Port already in use"

        # Build command
        try:
            command = self._build_command(bin_name, args)
            command_str = " ".join(command)

            logger.info(f"Starting process {instance_key}: {command_str}")

            # Start process with cross-platform compatibility
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "bufsize": 1,
            }

            # Windows: Use CREATE_NO_WINDOW flag to prevent CMD window popup
            if platform.system() == 'Windows':
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(command, **popen_kwargs)

            # Create process info
            proc_info = ProcessInfo(
                pid=process.pid,
                command=command_str,
                started_at=time.time(),
            )

            self._processes[instance_key] = proc_info
            self._process_objects[instance_key] = process

            # Write pidfile for reboot recovery
            base_url = f"http://{args.get('host', '127.0.0.1')}:{args.get('port', 8080)}"
            self._write_pidfile(instance_key, proc_info, base_url)

            # Start background task to capture output
            asyncio.create_task(self._monitor_process(instance_key))

            return True, f"Process started (PID {process.pid})"

        except FileNotFoundError:
            return False, f"Binary not found: {bin_name}. Install with: brew install llama.cpp"
        except Exception as e:
            logger.error(f"Failed to start process {instance_key}: {e}")
            return False, f"Failed to start: {e}"

    async def stop_process(
        self,
        instance_key: str,
        force: bool = False,
    ) -> tuple[bool, str, Optional[int]]:
        """
        Stop a provider process (cross-platform).

        Task #16: P0.3 - Enhanced with old_pid return and improved verification

        Uses terminate_process() and kill_process() from agentos.core.utils.process,
        which handle platform differences internally:
        - Unix: SIGTERM/SIGKILL
        - Windows: taskkill with appropriate flags

        Args:
            instance_key: Instance key
            force: If True, forcefully kill process immediately (SIGKILL/taskkill /F)
                   If False, attempt graceful termination first (SIGTERM/taskkill)

        Returns:
            tuple[bool, str, Optional[int]]: (success, message, old_pid)
        """
        if instance_key not in self._processes:
            # Check if recovered from pidfile
            pidfile_data = self._read_pidfile(instance_key)
            if pidfile_data:
                pid = pidfile_data.get("pid")
                if pid and self._is_process_alive(pid):
                    # Kill recovered process
                    try:
                        if force:
                            kill_process(pid)
                        else:
                            terminate_process(pid, timeout=2.0)
                        self._remove_pidfile(instance_key)
                        return True, f"Process stopped (PID {pid})", pid
                    except Exception as e:
                        return False, f"Failed to stop recovered process: {e}", pid

            return False, "Process not found or not managed by this manager", None

        process = self._process_objects.get(instance_key)
        proc_info = self._processes[instance_key]
        old_pid = proc_info.pid

        if not process:
            return False, "Process object not found", old_pid

        try:
            if force:
                kill_process(proc_info.pid)
                logger.info(f"Killed process {instance_key} (PID {proc_info.pid})")
            else:
                terminate_process(proc_info.pid, timeout=5.0)
                logger.info(f"Terminated process {instance_key} (PID {proc_info.pid})")

            # Wait for process to exit
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # Process should have been terminated by terminate_process/kill_process
                logger.debug(f"Process {instance_key} cleanup: waiting for subprocess object")
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process {instance_key} subprocess object still exists after termination")

            # Close pipes to signal readers to stop
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

            # Cancel reader tasks
            if instance_key in self._reader_tasks:
                for task in self._reader_tasks[instance_key]:
                    if not task.done():
                        task.cancel()
                del self._reader_tasks[instance_key]

            # Clean up
            proc_info.returncode = process.returncode
            del self._process_objects[instance_key]

            # Remove pidfile
            self._remove_pidfile(instance_key)

            # Verify process is stopped
            stopped = not self._is_process_alive(old_pid)

            return True, f"Process stopped (exit code {process.returncode})", old_pid

        except ProcessLookupError:
            # Clean up pidfile anyway
            self._remove_pidfile(instance_key)
            return False, "Process already terminated", old_pid
        except Exception as e:
            logger.error(f"Failed to stop process {instance_key}: {e}")
            return False, f"Failed to stop: {e}", old_pid

    def is_process_running(self, instance_key: str) -> bool:
        """
        Check if process is running (cross-platform).

        Uses psutil.pid_exists() and psutil.Process.is_running() internally
        instead of platform-specific implementations (os.kill(pid, 0) on Unix
        or tasklist on Windows).

        Args:
            instance_key: Instance key

        Returns:
            bool: True if process is running, False otherwise
        """
        if instance_key not in self._processes:
            # Check pidfile for recovered processes
            pidfile_data = self._read_pidfile(instance_key)
            if pidfile_data:
                pid = pidfile_data.get("pid")
                if pid:
                    return self._is_process_alive(pid)
            return False

        process = self._process_objects.get(instance_key)
        if not process:
            # Might be recovered, check PID
            proc_info = self._processes[instance_key]
            return self._is_process_alive(proc_info.pid)

        return process.poll() is None

    def get_process_info(self, instance_key: str) -> Optional[ProcessInfo]:
        """Get process information"""
        return self._processes.get(instance_key)

    def get_process_output(
        self,
        instance_key: str,
        lines: int = 100,
        stream: str = "stdout",
    ) -> list[str]:
        """
        Get recent process output

        Args:
            instance_key: Instance key
            lines: Number of lines to return
            stream: "stdout" or "stderr"

        Returns:
            List of output lines
        """
        proc_info = self._processes.get(instance_key)
        if not proc_info:
            return []

        buffer = proc_info.stdout_buffer if stream == "stdout" else proc_info.stderr_buffer
        return list(buffer)[-lines:]

    async def _monitor_process(self, instance_key: str):
        """Background task to monitor process and capture output"""
        process = self._process_objects.get(instance_key)
        proc_info = self._processes.get(instance_key)

        if not process or not proc_info:
            return

        reader_tasks = []

        try:
            # Monitor stdout
            if process.stdout:
                async def read_stdout():
                    try:
                        while True:
                            line = await asyncio.get_event_loop().run_in_executor(
                                None, process.stdout.readline
                            )
                            if not line:
                                break
                            proc_info.stdout_buffer.append(line.strip())
                    except Exception as e:
                        logger.debug(f"stdout reader stopped for {instance_key}: {e}")

                stdout_task = asyncio.create_task(read_stdout())
                reader_tasks.append(stdout_task)

            # Monitor stderr
            if process.stderr:
                async def read_stderr():
                    try:
                        while True:
                            line = await asyncio.get_event_loop().run_in_executor(
                                None, process.stderr.readline
                            )
                            if not line:
                                break
                            proc_info.stderr_buffer.append(line.strip())
                    except Exception as e:
                        logger.debug(f"stderr reader stopped for {instance_key}: {e}")

                stderr_task = asyncio.create_task(read_stderr())
                reader_tasks.append(stderr_task)

            # Register reader tasks for cleanup
            self._reader_tasks[instance_key] = reader_tasks

            # Wait for process to exit
            await asyncio.get_event_loop().run_in_executor(None, process.wait)
            proc_info.returncode = process.returncode

            # Remove pidfile when process exits
            self._remove_pidfile(instance_key)

            logger.info(
                f"Process {instance_key} exited with code {process.returncode}"
            )

        except Exception as e:
            logger.error(f"Error monitoring process {instance_key}: {e}")
        finally:
            # Clean up reader tasks
            if instance_key in self._reader_tasks:
                del self._reader_tasks[instance_key]

    def list_all_processes(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all managed processes"""
        result = {}

        for instance_key, proc_info in self._processes.items():
            result[instance_key] = {
                "pid": proc_info.pid,
                "command": proc_info.command,
                "started_at": proc_info.started_at,
                "running": self.is_process_running(instance_key),
                "returncode": proc_info.returncode,
                "uptime_seconds": time.time() - proc_info.started_at
                if self.is_process_running(instance_key)
                else None,
            }

        return result


# Cross-platform utility functions for external use
# These provide a simpler interface for callers who don't need ProcessManager's full features

def start_process_cross_platform(
    command: list[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
) -> subprocess.Popen:
    """
    Start a process with cross-platform compatibility.

    This is a utility function that handles platform-specific process creation flags.
    For full process management features (monitoring, PID tracking, recovery), use
    ProcessManager instead.

    Args:
        command: Command and arguments as a list
        cwd: Working directory for the process
        env: Environment variables (None means inherit from parent)
        capture_output: If True, capture stdout/stderr to PIPE

    Returns:
        subprocess.Popen: The started process object

    Platform differences handled:
        - Windows: Uses CREATE_NO_WINDOW flag to prevent CMD window popup
        - Unix: Standard Popen with no special flags

    Example:
        >>> proc = start_process_cross_platform(['ollama', 'serve'])
        >>> proc.pid
        12345
    """
    popen_kwargs = {
        "cwd": cwd,
        "env": env,
    }

    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE
        popen_kwargs["text"] = True

    # Windows: Use CREATE_NO_WINDOW flag to prevent CMD window popup
    if platform.system() == 'Windows':
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(command, **popen_kwargs)


def stop_process_cross_platform(
    pid: int,
    timeout: float = 5.0,
    force: bool = False
) -> dict:
    """
    Stop a process with cross-platform compatibility and detailed result.

    Task #16: P0.3 - Enhanced stop logic with verification

    Implementation:
    - Windows: taskkill /PID <pid> /T → wait 5s → taskkill /PID <pid> /T /F
    - macOS/Linux: SIGTERM → wait 5s → SIGKILL
    - Verifies process is stopped using psutil.pid_exists()

    Args:
        pid: Process ID to stop
        timeout: Timeout in seconds for graceful termination (default: 5.0)
        force: If True, skip graceful termination and force kill immediately

    Returns:
        dict: {
            "success": bool,
            "message": str,
            "old_pid": int,
            "stopped": bool  # True if process was verified stopped
        }

    Example:
        >>> result = stop_process_cross_platform(12345)
        >>> result
        {"success": True, "message": "Process stopped", "old_pid": 12345, "stopped": True}
    """
    old_pid = pid

    # Check if process exists before trying to stop
    if not psutil.pid_exists(pid):
        return {
            "success": False,
            "message": f"Process {pid} does not exist",
            "old_pid": old_pid,
            "stopped": True  # Already stopped
        }

    try:
        if force:
            # Force kill immediately
            success = kill_process(pid)
            message = f"Process {pid} force killed" if success else f"Failed to force kill process {pid}"
        else:
            # Graceful termination with timeout
            success = terminate_process(pid, timeout=timeout)
            message = f"Process {pid} terminated gracefully" if success else f"Failed to terminate process {pid}"

        # Verify process is stopped
        stopped = not psutil.pid_exists(pid)

        return {
            "success": success,
            "message": message,
            "old_pid": old_pid,
            "stopped": stopped
        }

    except Exception as e:
        # Check if process is actually stopped despite error
        stopped = not psutil.pid_exists(pid)
        return {
            "success": stopped,  # Success if process is stopped, regardless of exception
            "message": f"Stop completed with exception: {e}",
            "old_pid": old_pid,
            "stopped": stopped
        }


def is_process_running_cross_platform(pid: int) -> bool:
    """
    Check if a process is running (cross-platform).

    Uses psutil.pid_exists() which works on all platforms, replacing
    platform-specific implementations:
    - Unix: os.kill(pid, 0)
    - Windows: tasklist /FI "PID eq {pid}"

    Args:
        pid: Process ID to check

    Returns:
        bool: True if process exists and is running, False otherwise

    Example:
        >>> is_process_running_cross_platform(12345)
        True
        >>> is_process_running_cross_platform(99999)
        False
    """
    return psutil.pid_exists(pid)
