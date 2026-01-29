"""
Ollama Controller - Start/Stop Ollama Server

Sprint B Task #5: Ollama lifecycle management

Scope:
- Start/Stop Ollama (local only)
- Idempotent operations
- PID tracking via file
- Event emission on state change

Not in scope:
- Installation
- Model downloads
- Port management
- Multi-instance
- Authentication
"""

import os
import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx

from agentos.core.utils.process import terminate_process, kill_process, is_process_running

logger = logging.getLogger(__name__)


@dataclass
class ControlResult:
    """Result of start/stop operation"""
    ok: bool
    provider: str = "ollama"
    action: str = ""  # "start" | "stop"
    state: str = ""  # ProviderState value
    pid: Optional[int] = None
    message: str = ""
    error: Optional[Dict[str, str]] = None


class OllamaController:
    """
    Controller for Ollama server lifecycle

    Architecture:
    - PID tracking via ~/.agentos/ollama.pid
    - Idempotent start/stop
    - Event emission via EventBus
    """

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        store_dir: str = None,
    ):
        self.endpoint = endpoint
        self.store_dir = Path(store_dir or Path.home() / ".agentos")
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.pid_file = self.store_dir / "ollama.pid"
        self.log_file = self.store_dir / "ollama.log"

    def is_running(self) -> bool:
        """
        Check if Ollama is running via probe

        Returns True if endpoint responds to /api/tags
        """
        try:
            with httpx.Client(timeout=1.5) as client:
                response = client.get(f"{self.endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def get_pid(self) -> Optional[int]:
        """Get PID from tracking file (if exists and valid)"""
        if not self.pid_file.exists():
            return None

        try:
            pid = int(self.pid_file.read_text().strip())

            # Verify PID is still valid
            if is_process_running(pid):
                return pid
            else:
                # PID no longer exists, clean up stale file
                self.pid_file.unlink(missing_ok=True)
                return None

        except Exception as e:
            logger.warning(f"Failed to read PID file: {e}")
            return None

    def _save_pid(self, pid: int):
        """Save PID to tracking file"""
        try:
            self.pid_file.write_text(str(pid))
            logger.info(f"Saved Ollama PID: {pid}")
        except Exception as e:
            logger.error(f"Failed to save PID: {e}")

    def _clear_pid(self):
        """Remove PID tracking file"""
        try:
            self.pid_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to clear PID file: {e}")

    def start(self) -> ControlResult:
        """
        Start Ollama server (idempotent)

        Process:
        1. Check if already running (probe)
        2. If running → return READY (idempotent)
        3. If not running → spawn subprocess
        4. Wait up to 3s for READY (poll 5 times)
        5. Emit provider.status_changed event
        """
        logger.info("Starting Ollama server...")

        # Step 1: Check if already running (idempotent)
        if self.is_running():
            pid = self.get_pid()
            logger.info(f"Ollama already running (PID: {pid})")

            # Emit event
            self._emit_status_event("READY", pid)

            return ControlResult(
                ok=True,
                action="start",
                state="READY",
                pid=pid,
                message="Ollama already running",
            )

        # Step 2: Spawn subprocess
        try:
            # Open log file for stdout/stderr
            log_handle = open(self.log_file, "a", buffering=1, encoding="utf-8")

            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from parent
            )

            pid = process.pid
            self._save_pid(pid)

            logger.info(f"Ollama process started: PID {pid}")

        except FileNotFoundError:
            error_msg = "Ollama CLI not found. Please install Ollama first."
            logger.error(error_msg)

            return ControlResult(
                ok=False,
                action="start",
                state="DISCONNECTED",
                message=error_msg,
                error={
                    "code": "cli_not_found",
                    "message": error_msg,
                    "hint": "Install Ollama from https://ollama.com/download",
                },
            )

        except Exception as e:
            error_msg = f"Failed to start Ollama: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return ControlResult(
                ok=False,
                action="start",
                state="ERROR",
                message=error_msg,
                error={
                    "code": "start_failed",
                    "message": error_msg,
                    "hint": f"Check logs at {self.log_file}",
                },
            )

        # Step 3: Wait for READY (poll up to 3s)
        max_attempts = 6
        for attempt in range(max_attempts):
            time.sleep(0.5)

            if self.is_running():
                logger.info(f"Ollama is READY (took {(attempt + 1) * 0.5}s)")

                # Emit event
                self._emit_status_event("READY", pid)

                return ControlResult(
                    ok=True,
                    action="start",
                    state="READY",
                    pid=pid,
                    message=f"Ollama started successfully (PID: {pid})",
                )

        # Timeout: process started but endpoint not ready
        logger.warning(f"Ollama started but endpoint not ready after 3s")

        # Emit DEGRADED event
        self._emit_status_event("DEGRADED", pid)

        return ControlResult(
            ok=False,
            action="start",
            state="DEGRADED",
            pid=pid,
            message="Ollama process started but endpoint not responding",
            error={
                "code": "start_timeout",
                "message": "Ollama started but not ready after 3s",
                "hint": f"Check logs at {self.log_file}",
            },
        )

    def stop(self) -> ControlResult:
        """
        Stop Ollama server (idempotent)

        Process:
        1. Check if running (probe)
        2. If not running → return DISCONNECTED (idempotent)
        3. If running → get PID, send SIGTERM
        4. Wait 1s, check if stopped
        5. If still running → SIGKILL
        6. Emit provider.status_changed event
        """
        logger.info("Stopping Ollama server...")

        # Step 1: Check if already stopped (idempotent)
        if not self.is_running():
            logger.info("Ollama already stopped")

            # Clean up PID file
            self._clear_pid()

            # Emit event
            self._emit_status_event("DISCONNECTED", None)

            return ControlResult(
                ok=True,
                action="stop",
                state="DISCONNECTED",
                pid=None,
                message="Ollama already stopped",
            )

        # Step 2: Get PID
        pid = self.get_pid()

        if pid is None:
            # Running but no PID tracked (external process)
            logger.warning("Ollama is running but PID not tracked (external process?)")

            return ControlResult(
                ok=False,
                action="stop",
                state="ERROR",
                message="Ollama is running but PID not tracked",
                error={
                    "code": "pid_not_tracked",
                    "message": "Cannot stop Ollama: PID not tracked",
                    "hint": "Ollama may have been started externally. Stop it manually.",
                },
            )

        # Step 3: Terminate process
        try:
            logger.info(f"Terminating Ollama process (PID {pid})")

            # Try graceful termination with 5s timeout (Ollama may need time to cleanup)
            if terminate_process(pid, timeout=5.0):
                logger.info("Ollama stopped gracefully")
                self._clear_pid()

                # Emit event
                self._emit_status_event("DISCONNECTED", None)

                return ControlResult(
                    ok=True,
                    action="stop",
                    state="DISCONNECTED",
                    pid=None,
                    message="Ollama stopped successfully",
                )
            else:
                # Process was not running or already terminated
                logger.info("Ollama process already stopped")
                self._clear_pid()

                # Emit event
                self._emit_status_event("DISCONNECTED", None)

                return ControlResult(
                    ok=True,
                    action="stop",
                    state="DISCONNECTED",
                    pid=None,
                    message="Ollama stopped",
                )

        except ProcessLookupError:
            # Process already dead
            logger.info(f"Process {pid} already terminated")
            self._clear_pid()

            # Emit event
            self._emit_status_event("DISCONNECTED", None)

            return ControlResult(
                ok=True,
                action="stop",
                state="DISCONNECTED",
                pid=None,
                message="Ollama process already terminated",
            )

        except Exception as e:
            error_msg = f"Failed to stop Ollama: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return ControlResult(
                ok=False,
                action="stop",
                state="ERROR",
                message=error_msg,
                error={
                    "code": "stop_failed",
                    "message": error_msg,
                    "hint": f"Try stopping manually: kill {pid}",
                },
            )

    def _emit_status_event(self, state: str, pid: Optional[int]):
        """
        Emit provider.status_changed event

        Sprint B Task #4: Event integration
        """
        try:
            from agentos.core.events import Event, get_event_bus

            event = Event.provider_status_changed(
                provider_id="ollama",
                state=state,
                details={
                    "endpoint": self.endpoint,
                    "pid": pid,
                    "action": "control",  # Distinguish from probe
                },
            )

            get_event_bus().emit(event)
            logger.debug(f"Emitted provider.status_changed: {state}")

        except Exception as e:
            logger.warning(f"Failed to emit status event: {e}")
