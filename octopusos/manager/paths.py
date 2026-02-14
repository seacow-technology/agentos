from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagerPaths:
    data_dir: Path
    runtime_dir: Path
    log_dir: Path
    lock_file: Path
    state_file: Path
    events_file: Path
    frontend_pid_file: Path
    frontend_log_file: Path


def resolve_manager_data_dir() -> Path:
    # Explicit override for developers and packaging.
    env = os.getenv("OCTOPUS_MANAGER_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".octopusos" / "manager"


def get_manager_paths() -> ManagerPaths:
    data_dir = resolve_manager_data_dir()
    runtime_dir = data_dir / "runtime"
    log_dir = data_dir / "logs"
    return ManagerPaths(
        data_dir=data_dir,
        runtime_dir=runtime_dir,
        log_dir=log_dir,
        lock_file=runtime_dir / "manager.lock",
        state_file=runtime_dir / "state.json",
        events_file=runtime_dir / "events.jsonl",
        frontend_pid_file=runtime_dir / "webui-frontend.pid",
        frontend_log_file=log_dir / "webui-frontend.log",
    )


def ensure_manager_dirs() -> ManagerPaths:
    paths = get_manager_paths()
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    return paths

