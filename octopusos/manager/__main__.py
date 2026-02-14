from __future__ import annotations

import os
import argparse

import uvicorn

from .api import create_app
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="octopus-manager", description="OctopusOS local manager control API")
    parser.add_argument("--host", default=None, help="bind host (default: from config)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: from config)")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repo root for managing the WebUI frontend dev server (default: $OCTOPUSOS_REPO_ROOT or cwd)",
    )
    args = parser.parse_args()

    repo_root = (
        (args.repo_root or "").strip()
        or os.getenv("OCTOPUSOS_REPO_ROOT", "").strip()
        or os.getcwd()
    )

    cfg = load_config(repo_root=repo_root)
    host = str(args.host or cfg.host)
    port = int(args.port or cfg.port)

    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
