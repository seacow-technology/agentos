from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from octopusos.daemon import service as webui_daemon

from .config import ManagerConfig
from .lock import OperationInProgress, manager_lock
from .paths import ensure_manager_dirs


def _now_ts() -> int:
    return int(time.time())


def _pick_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@dataclass(frozen=True)
class ServiceSnapshot:
    name: str
    state: str
    pid: int | None
    url: str | None
    port: int | None
    last_error: str | None


class ManagerSupervisor:
    def __init__(self, cfg: ManagerConfig):
        self.cfg = cfg
        self.paths = ensure_manager_dirs()

    def _event(self, event: str, *, source: str, details: dict[str, Any] | None = None) -> None:
        payload = {
            "ts": _now_ts(),
            "event": event,
            "source": source,
            "details": details or {},
        }
        self.paths.events_file.parent.mkdir(parents=True, exist_ok=True)
        with self.paths.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now_ts()
        self.paths.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_state(self) -> dict[str, Any]:
        if not self.paths.state_file.exists():
            return {}
        try:
            return json.loads(self.paths.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _with_webui_data_dir(self):
        # Ensure the webui daemon runtime dir is isolated from dev CLI by setting OCTOPUSOS_DATA_DIR.
        # This is process-wide, but the manager is intended to be the only owner of its process.
        class _EnvCtx:
            def __init__(self, key: str, value: str):
                self.key = key
                self.value = value
                self.prev = None

            def __enter__(self):
                self.prev = os.environ.get(self.key)
                os.environ[self.key] = self.value

            def __exit__(self, exc_type, exc, tb):
                if self.prev is None:
                    os.environ.pop(self.key, None)
                else:
                    os.environ[self.key] = self.prev

        return _EnvCtx("OCTOPUSOS_DATA_DIR", str(self.paths.data_dir))

    def backend_status(self) -> ServiceSnapshot:
        with self._with_webui_data_dir():
            st = webui_daemon.read_status()
        return ServiceSnapshot(
            name="backend",
            state="RUNNING" if st.running else "STOPPED",
            pid=st.pid,
            url=st.url if st.running else None,
            port=st.port if st.running else st.port,
            last_error=st.last_error,
        )

    def frontend_status(self) -> ServiceSnapshot:
        pid = None
        if self.paths.frontend_pid_file.exists():
            try:
                pid = int(self.paths.frontend_pid_file.read_text(encoding="utf-8").strip())
            except Exception:
                pid = None

        if pid and _is_pid_running(pid):
            st = self._read_state()
            url = ((st.get("services") or {}).get("frontend") or {}).get("url")
            port = ((st.get("services") or {}).get("frontend") or {}).get("port")
            return ServiceSnapshot(
                name="frontend",
                state="RUNNING",
                pid=pid,
                url=url if isinstance(url, str) else None,
                port=int(port) if isinstance(port, int) else None,
                last_error=None,
            )

        self.paths.frontend_pid_file.unlink(missing_ok=True)
        return ServiceSnapshot(name="frontend", state="STOPPED", pid=None, url=None, port=None, last_error=None)

    def status(self) -> dict[str, Any]:
        backend = self.backend_status()
        frontend = self.frontend_status()

        if backend.state == "RUNNING" and (frontend.state in {"RUNNING", "STOPPED"}):
            overall = "RUNNING" if (not self.cfg.start_frontend or frontend.state == "RUNNING" or frontend.state == "STOPPED") else "DEGRADED"
        else:
            overall = "STOPPED" if backend.state == "STOPPED" and frontend.state == "STOPPED" else "DEGRADED"

        # Prefer frontend URL for "open web" if present; otherwise backend URL.
        return {
            "ok": True,
            "overall": {"state": overall, "updated_at": _now_ts()},
            "manager": {
                "origin": f"http://{self.cfg.host}:{self.cfg.port}",
                "mode": self.cfg.mode,
                "data_dir": str(self.paths.data_dir),
                "state_file": str(self.paths.state_file),
                "events_file": str(self.paths.events_file),
            },
            "services": {
                "backend": backend.__dict__,
                "frontend": frontend.__dict__,
            },
        }

    def _write_status_state(self, *, backend: ServiceSnapshot, frontend: ServiceSnapshot, overall_state: str) -> None:
        self._write_state(
            {
                "overall": {"state": overall_state},
                "services": {
                    "backend": backend.__dict__,
                    "frontend": frontend.__dict__,
                },
            }
        )

    def start_all(self, *, source: str) -> dict[str, Any]:
        try:
            with manager_lock():
                self._event("start.requested", source=source)
                self._write_state({"overall": {"state": "STARTING"}, "services": {}})

                with self._with_webui_data_dir():
                    result = webui_daemon.start_webui(
                        host=self.cfg.webui_host,
                        preferred_port=self.cfg.webui_preferred_port,
                        foreground=False,
                        open_browser=False,
                    )

                backend = self.backend_status()
                if not result.ok or backend.state != "RUNNING":
                    backend = ServiceSnapshot(
                        name="backend",
                        state="FAILED",
                        pid=result.status.pid,
                        url=None,
                        port=result.status.port,
                        last_error=result.message,
                    )
                    frontend = self.frontend_status()
                    self._write_status_state(backend=backend, frontend=frontend, overall_state="FAILED")
                    self._event("start.failed", source=source, details={"message": result.message})
                    return self.status()

                frontend = self.frontend_status()
                if self.cfg.start_frontend:
                    frontend = self._start_frontend(source=source, backend_url=backend.url or "")

                self._write_status_state(backend=backend, frontend=frontend, overall_state="RUNNING")
                self._event("start.ok", source=source, details={"backend_url": backend.url, "frontend_url": frontend.url})
                return self.status()
        except OperationInProgress:
            return {"ok": False, "error": "operation_in_progress", "status_code": 409}

    def stop_all(self, *, source: str) -> dict[str, Any]:
        try:
            with manager_lock():
                self._event("stop.requested", source=source)
                self._write_state({"overall": {"state": "STOPPING"}, "services": {}})

                self._stop_frontend(source=source)
                with self._with_webui_data_dir():
                    ok, msg = webui_daemon.stop_webui()

                backend = self.backend_status()
                frontend = self.frontend_status()
                overall = "STOPPED" if ok else "DEGRADED"
                self._write_status_state(backend=backend, frontend=frontend, overall_state=overall)
                self._event("stop.ok" if ok else "stop.failed", source=source, details={"message": msg})
                return self.status()
        except OperationInProgress:
            return {"ok": False, "error": "operation_in_progress", "status_code": 409}

    def restart_all(self, *, source: str) -> dict[str, Any]:
        # Keep the lock boundaries simple: stop then start, each with lock.
        self.stop_all(source=source)
        return self.start_all(source=source)

    def tail_logs(self, *, service: str, tail: int) -> dict[str, Any]:
        tail = max(1, min(int(tail), 5000))
        if service == "backend":
            with self._with_webui_data_dir():
                content = webui_daemon.tail_logs(lines=tail)
                st = webui_daemon.read_status()
            return {"ok": True, "service": "backend", "log_file": str(st.log_file), "lines": content.splitlines()}
        if service == "frontend":
            if not self.paths.frontend_log_file.exists():
                return {"ok": True, "service": "frontend", "log_file": str(self.paths.frontend_log_file), "lines": []}
            lines = self.paths.frontend_log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
            return {"ok": True, "service": "frontend", "log_file": str(self.paths.frontend_log_file), "lines": lines}
        if service == "manager":
            # Manager itself currently logs to stdout/stderr; return state/event tail instead.
            events = []
            if self.paths.events_file.exists():
                raw = self.paths.events_file.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
                events = raw
            return {"ok": True, "service": "manager", "events": events}
        return {"ok": False, "error": f"unknown service: {service}"}

    def _start_frontend(self, *, source: str, backend_url: str) -> ServiceSnapshot:
        host = self.cfg.frontend_host
        port = self.cfg.frontend_port or _pick_free_port(host)

        public_origin = f"http://{host}:{port}"
        repo_root = Path(self.cfg.repo_root).resolve()

        # Ensure WebUI v2 frontend can resolve its runtime-config.json.
        runtime_file = repo_root / "apps" / "webui" / "public" / "runtime" / "runtime-config.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(json.dumps({"public_origin": public_origin}), encoding="utf-8")

        env = os.environ.copy()
        env["OCTOPUS_BACKEND_ORIGIN"] = backend_url
        env["OCTOPUS_PUBLIC_ORIGIN"] = public_origin

        cmd = [p.format(host=host, port=str(port)) for p in self.cfg.frontend_cmd]

        self.paths.frontend_log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = self.paths.frontend_log_file.open("a", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(repo_root / "apps" / "webui"), stdout=log_handle, stderr=subprocess.STDOUT, env=env)
        self.paths.frontend_pid_file.write_text(str(proc.pid), encoding="utf-8")

        # Optional: wait a bit for frontend to become reachable (best-effort).
        url = public_origin
        ok = False
        try:
            with httpx.Client(timeout=0.6) as client:
                for _ in range(12):
                    try:
                        r = client.get(url)
                        if r.status_code < 500:
                            ok = True
                            break
                    except Exception:
                        time.sleep(0.25)
        except Exception:
            ok = False

        if not ok:
            self._event("frontend.start.degraded", source=source, details={"url": url})
            return ServiceSnapshot(name="frontend", state="DEGRADED", pid=proc.pid, url=url, port=port, last_error="frontend not reachable yet")

        self._event("frontend.start.ok", source=source, details={"url": url})
        return ServiceSnapshot(name="frontend", state="RUNNING", pid=proc.pid, url=url, port=port, last_error=None)

    def _stop_frontend(self, *, source: str) -> None:
        if not self.paths.frontend_pid_file.exists():
            return
        try:
            pid = int(self.paths.frontend_pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            self.paths.frontend_pid_file.unlink(missing_ok=True)
            return

        if not pid or not _is_pid_running(pid):
            self.paths.frontend_pid_file.unlink(missing_ok=True)
            return

        self._event("frontend.stop.requested", source=source, details={"pid": pid})
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            self.paths.frontend_pid_file.unlink(missing_ok=True)
            return

        deadline = time.time() + 8.0
        while time.time() < deadline and _is_pid_running(pid):
            time.sleep(0.15)

        if _is_pid_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

        self.paths.frontend_pid_file.unlink(missing_ok=True)
        self._event("frontend.stop.ok", source=source, details={"pid": pid})
