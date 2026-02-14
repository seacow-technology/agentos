from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request

from .config import load_config
from .supervisor import ManagerSupervisor
from octopusos import __version__ as octopusos_version


def _repo_root() -> str:
    # Best-effort: this file lives at os/octopusos/manager/api.py
    return str(Path(__file__).resolve().parents[3])


def _source_from_headers(x_octopusos_source: str | None) -> str:
    raw = (x_octopusos_source or "").strip().lower()
    return raw if raw in {"tray", "cli", "web"} else "unknown"


def create_app() -> FastAPI:
    cfg = load_config(repo_root=_repo_root())
    sup = ManagerSupervisor(cfg)

    app = FastAPI(title="OctopusOS Manager Control API")

    @app.get("/control/health")
    def health() -> dict:
        return {
            "ok": True,
            "api_version": "v1",
            "pid": os.getpid(),
            "octopusos_version": octopusos_version,
            "mode": cfg.mode,
            "data_dir": str(sup.paths.data_dir),
            "build": {
                "git_sha": os.getenv("GIT_SHA") or os.getenv("GITHUB_SHA"),
            },
        }

    @app.get("/control/status")
    def status(request: Request) -> dict:
        payload = sup.status()
        try:
            payload.setdefault("manager", {})
            payload["manager"]["origin"] = str(request.base_url).rstrip("/")
        except Exception:
            pass
        return payload

    @app.post("/control/start")
    def start(request: Request, x_octopusos_source: str | None = Header(default=None)) -> dict:
        source = _source_from_headers(x_octopusos_source)
        result = sup.start_all(source=source)
        if result.get("status_code") == 409:
            raise HTTPException(status_code=409, detail="operation_in_progress")
        return result

    @app.post("/control/stop")
    def stop(request: Request, x_octopusos_source: str | None = Header(default=None)) -> dict:
        source = _source_from_headers(x_octopusos_source)
        result = sup.stop_all(source=source)
        if result.get("status_code") == 409:
            raise HTTPException(status_code=409, detail="operation_in_progress")
        return result

    @app.post("/control/restart")
    def restart(request: Request, x_octopusos_source: str | None = Header(default=None)) -> dict:
        source = _source_from_headers(x_octopusos_source)
        result = sup.restart_all(source=source)
        if result.get("status_code") == 409:
            raise HTTPException(status_code=409, detail="operation_in_progress")
        return result

    @app.get("/control/logs")
    def logs(
        service: str = Query(default="backend"),
        tail: int = Query(default=200, ge=1, le=5000),
    ) -> dict:
        return sup.tail_logs(service=service, tail=tail)

    return app


app = create_app()
