from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import ensure_manager_dirs


@dataclass(frozen=True)
class ManagerConfig:
    mode: str
    host: str
    port: int
    webui_host: str
    webui_preferred_port: int
    start_frontend: bool
    frontend_host: str
    frontend_port: int | None
    frontend_cmd: list[str]
    repo_root: str


def _default_cfg(repo_root: str) -> dict[str, Any]:
    # Conservative defaults: manage backend daemon; frontend dev server is opt-in.
    return {
        "mode": "PROBE",
        "manager": {"host": "127.0.0.1", "port": 6110},
        "webui": {"host": "127.0.0.1", "preferred_port": 8080},
        "frontend": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": None,
            "cmd": ["npm", "run", "dev", "--", "--host", "{host}", "--port", "{port}"],
        },
        "repo_root": repo_root,
    }


def config_path() -> Path:
    paths = ensure_manager_dirs()
    return paths.data_dir / "config.json"


def load_config(*, repo_root: str) -> ManagerConfig:
    cfg_file = config_path()
    if not cfg_file.exists():
        cfg_file.write_text(json.dumps(_default_cfg(repo_root), indent=2), encoding="utf-8")

    raw = json.loads(cfg_file.read_text(encoding="utf-8"))
    mode = str(raw.get("mode") or "PROBE").strip().upper()
    if mode not in {"PROBE", "REAL"}:
        mode = "PROBE"
    mgr = raw.get("manager", {}) or {}
    webui = raw.get("webui", {}) or {}
    fe = raw.get("frontend", {}) or {}

    host = str(mgr.get("host") or "127.0.0.1")
    port = int(mgr.get("port") or 6110)

    webui_host = str(webui.get("host") or "127.0.0.1")
    webui_preferred_port = int(webui.get("preferred_port") or 8080)

    start_frontend = bool(fe.get("enabled") or False)
    frontend_host = str(fe.get("host") or webui_host)
    frontend_port = fe.get("port")
    frontend_port = int(frontend_port) if isinstance(frontend_port, int) else None
    frontend_cmd = fe.get("cmd") or ["npm", "run", "dev", "--", "--host", "{host}", "--port", "{port}"]
    if not isinstance(frontend_cmd, list) or not all(isinstance(x, str) for x in frontend_cmd):
        raise ValueError("frontend.cmd must be a list of strings")

    rr = str(raw.get("repo_root") or repo_root)

    return ManagerConfig(
        mode=mode,
        host=host,
        port=port,
        webui_host=webui_host,
        webui_preferred_port=webui_preferred_port,
        start_frontend=start_frontend,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        frontend_cmd=list(frontend_cmd),
        repo_root=rr,
    )
