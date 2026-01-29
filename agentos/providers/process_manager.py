"""
Provider Process Manager

Manages lifecycle of locally-launched provider services (e.g., llama-server).

Features:
- Start/stop provider processes
- Port conflict detection
- Process monitoring (PID, stdout/stderr capture)
- Launch command building from config

Sprint B+ Provider Architecture Refactor
"""

import asyncio
import json
import logging
import os
import psutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, Deque
import socket

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

        # PID files directory
        self.run_dir = Path.home() / ".agentos" / "run"
        self.run_dir.mkdir(parents=True, exist_ok=True)

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
        """Write pidfile for process tracking"""
        pidfile = self._get_pidfile_path(instance_key)
        try:
            data = {
                "pid": proc_info.pid,
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

    def _is_process_alive(self, pid: int) -> bool:
        """Check if process with PID is alive using psutil"""
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

            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

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
    ) -> tuple[bool, str]:
        """
        Stop a provider process

        Args:
            instance_key: Instance key
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            (success, message)
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
                        return True, f"Process stopped (PID {pid})"
                    except Exception as e:
                        return False, f"Failed to stop recovered process: {e}"

            return False, "Process not found or not managed by this manager"

        process = self._process_objects.get(instance_key)
        proc_info = self._processes[instance_key]

        if not process:
            return False, "Process object not found"

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

            return True, f"Process stopped (exit code {process.returncode})"

        except ProcessLookupError:
            # Clean up pidfile anyway
            self._remove_pidfile(instance_key)
            return False, "Process already terminated"
        except Exception as e:
            logger.error(f"Failed to stop process {instance_key}: {e}")
            return False, f"Failed to stop: {e}"

    def is_process_running(self, instance_key: str) -> bool:
        """Check if process is running"""
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
