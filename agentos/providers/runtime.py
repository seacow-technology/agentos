"""
Provider Runtime Manager

Handles lifecycle management for local model providers:
- Start/stop processes (Ollama, llama.cpp server)
- PID tracking and process monitoring
- Runtime state persistence (~/.agentos/runtime/providers.json)

Sprint B Task #5 implementation
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

from agentos.core.utils.process import terminate_process, kill_process, is_process_running

logger = logging.getLogger(__name__)


@dataclass
class ProcessRuntime:
    """Runtime information for a managed process"""
    pid: int
    command: str
    started_at: str
    endpoint: str


class RuntimeStateManager:
    """
    Manages runtime state for local model provider processes

    Stores PID and metadata in ~/.agentos/runtime/providers.json
    """

    def __init__(self, state_file: Optional[Path] = None):
        if state_file is None:
            # Default to ~/.agentos/runtime/providers.json
            home = Path.home()
            runtime_dir = home / ".agentos" / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            state_file = runtime_dir / "providers.json"

        self.state_file = state_file
        self._state: Dict[str, ProcessRuntime] = {}
        self._load()

    def _load(self):
        """Load state from disk"""
        if not self.state_file.exists():
            self._state = {}
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._state = {
                    k: ProcessRuntime(**v) for k, v in data.items()
                }
            logger.debug(f"Loaded runtime state: {len(self._state)} processes")
        except Exception as e:
            logger.error(f"Failed to load runtime state: {e}")
            self._state = {}

    def _save(self):
        """Save state to disk"""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                data = {k: asdict(v) for k, v in self._state.items()}
                json.dump(data, f, indent=2)
            logger.debug(f"Saved runtime state: {len(self._state)} processes")
        except Exception as e:
            logger.error(f"Failed to save runtime state: {e}")

    def get(self, provider_id: str) -> Optional[ProcessRuntime]:
        """Get runtime info for a provider"""
        return self._state.get(provider_id)

    def set(self, provider_id: str, runtime: ProcessRuntime):
        """Set runtime info for a provider"""
        self._state[provider_id] = runtime
        self._save()

    def remove(self, provider_id: str):
        """Remove runtime info for a provider"""
        if provider_id in self._state:
            del self._state[provider_id]
            self._save()

    def is_running(self, provider_id: str) -> bool:
        """Check if a provider process is actually running"""
        runtime = self.get(provider_id)
        if not runtime:
            return False

        if is_process_running(runtime.pid):
            return True
        else:
            # Process doesn't exist, clean up stale state
            logger.warning(f"Stale PID {runtime.pid} for {provider_id}, cleaning up")
            self.remove(provider_id)
            return False


class OllamaRuntimeManager:
    """
    Manages Ollama server lifecycle

    Provides start/stop/status operations with PID tracking
    """

    PROVIDER_ID = "ollama"
    DEFAULT_ENDPOINT = "http://127.0.0.1:11434"

    def __init__(self, state_manager: Optional[RuntimeStateManager] = None):
        self.state = state_manager or RuntimeStateManager()

    async def start(self) -> Dict[str, any]:
        """
        Start Ollama server

        Returns:
            Dict with status, pid, message
        """
        from datetime import datetime, timezone

        # Check if already running
        if self.state.is_running(self.PROVIDER_ID):
            runtime = self.state.get(self.PROVIDER_ID)
            return {
                "status": "already_running",
                "pid": runtime.pid,
                "message": f"Ollama is already running (PID: {runtime.pid})",
            }

        # Check if ollama CLI exists (跨平台)
        import shutil
        if not shutil.which("ollama"):
            return {
                "status": "error",
                "message": "Ollama CLI not found. Install from: https://ollama.ai/download",
            }

        # Start Ollama server
        try:
            logger.info("Starting Ollama server...")
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )

            # Store runtime info
            runtime = ProcessRuntime(
                pid=process.pid,
                command="ollama serve",
                started_at=datetime.now(timezone.utc).isoformat(),
                endpoint=self.DEFAULT_ENDPOINT,
            )
            self.state.set(self.PROVIDER_ID, runtime)

            logger.info(f"Ollama server started (PID: {process.pid})")
            return {
                "status": "started",
                "pid": process.pid,
                "endpoint": self.DEFAULT_ENDPOINT,
                "message": "Ollama server started successfully",
            }

        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            return {
                "status": "error",
                "message": f"Failed to start Ollama: {str(e)}",
            }

    async def stop(self, force: bool = False) -> Dict[str, any]:
        """
        Stop Ollama server

        Args:
            force: If True, use SIGKILL immediately

        Returns:
            Dict with status and message
        """
        runtime = self.state.get(self.PROVIDER_ID)
        if not runtime:
            return {
                "status": "not_running",
                "message": "Ollama is not running (no PID tracked)",
            }

        # Check if process still exists
        if not self.state.is_running(self.PROVIDER_ID):
            return {
                "status": "not_running",
                "message": "Ollama is not running (PID not found)",
            }

        pid = runtime.pid

        try:
            if force:
                # Force kill immediately
                logger.info(f"Force killing Ollama (PID: {pid})")
                kill_process(pid)
                self.state.remove(self.PROVIDER_ID)
                return {
                    "status": "stopped",
                    "message": f"Ollama force stopped (PID: {pid})",
                }

            # Graceful shutdown: terminate with 2s timeout
            logger.info(f"Stopping Ollama gracefully (PID: {pid})")
            if terminate_process(pid, timeout=2.0):
                self.state.remove(self.PROVIDER_ID)
                logger.info("Ollama stopped gracefully")
                return {
                    "status": "stopped",
                    "message": f"Ollama stopped gracefully (PID: {pid})",
                }
            else:
                # Process already terminated
                self.state.remove(self.PROVIDER_ID)
                return {
                    "status": "stopped",
                    "message": f"Ollama stopped (PID: {pid})",
                }

        except Exception as e:
            logger.error(f"Failed to stop Ollama: {e}")
            return {
                "status": "error",
                "message": f"Failed to stop Ollama: {str(e)}",
            }

    async def restart(self) -> Dict[str, any]:
        """
        Restart Ollama server

        Returns:
            Dict with status and message
        """
        logger.info("Restarting Ollama...")

        # Stop if running
        if self.state.is_running(self.PROVIDER_ID):
            stop_result = await self.stop()
            if stop_result["status"] not in ["stopped", "not_running"]:
                return {
                    "status": "error",
                    "message": f"Failed to stop Ollama: {stop_result['message']}",
                }

        # Start
        start_result = await self.start()
        if start_result["status"] == "started":
            return {
                "status": "restarted",
                "pid": start_result["pid"],
                "message": "Ollama restarted successfully",
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to start Ollama: {start_result['message']}",
            }

    def get_runtime(self) -> Optional[Dict[str, any]]:
        """
        Get current runtime info

        Returns:
            Dict with runtime info or None if not running
        """
        if not self.state.is_running(self.PROVIDER_ID):
            return None

        runtime = self.state.get(self.PROVIDER_ID)
        if not runtime:
            return None

        return {
            "pid": runtime.pid,
            "command": runtime.command,
            "started_at": runtime.started_at,
            "endpoint": runtime.endpoint,
            "is_running": True,
        }
