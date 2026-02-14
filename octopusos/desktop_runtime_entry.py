"""
Desktop runtime entrypoint for Electron "all-in-one" builds.

Why this exists:
- The regular `octopusos webui start` CLI uses the daemon service which spawns
  `sys.executable -m uvicorn ...`. In a PyInstaller onefile binary, `sys.executable`
  points back to this binary (not a Python interpreter), so `-m` breaks.
- Electron needs a single foreground process that binds a specific host/port and
  logs to stderr (captured by the desktop shell).
"""

from __future__ import annotations

import argparse
import os
import sys


def _parse_args(argv: list[str]) -> argparse.Namespace:
    # Compat: accept old shape `octopusos-runtime webui start ...` used by earlier Electron builds.
    compat_argv = list(argv)
    if len(compat_argv) >= 2 and compat_argv[0] == "webui" and compat_argv[1] == "start":
        compat_argv = compat_argv[2:]

    p = argparse.ArgumentParser(prog="octopusos-runtime", add_help=True)
    p.add_argument("--host", default=os.getenv("OCTOPUSOS_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("OCTOPUSOS_PORT", "8080")))
    # Electron passes these today; keep them as no-ops for compatibility.
    p.add_argument("--backend-only", action="store_true")
    p.add_argument("--with-frontend", action="store_true")
    p.add_argument("--foreground", action="store_true")
    p.add_argument("--open", action="store_true")
    return p.parse_args(compat_argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(list(argv) if argv is not None else sys.argv[1:])

    # Import late so PyInstaller can collect it from the installed environment.
    import uvicorn  # type: ignore

    # Import the FastAPI app directly so PyInstaller includes the whole webui package.
    # Using "octopusos.webui.app:app" as a string can lead to missing modules in the bundle.
    from octopusos.webui.app import app as fastapi_app  # noqa: WPS433

    # uvicorn.run blocks in-process (no sys.executable subprocess).
    uvicorn.run(
        fastapi_app,
        host=str(ns.host),
        port=int(ns.port),
        log_level=os.getenv("OCTOPUSOS_LOG_LEVEL", "info"),
        # Keep behavior stable across platforms.
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
