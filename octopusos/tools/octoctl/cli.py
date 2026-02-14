from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode

import click
import requests


def _origin() -> str:
    return (os.getenv("OCTOPUS_MANAGER_ORIGIN", "").strip() or "http://127.0.0.1:6110").rstrip("/")


def _headers() -> dict[str, str]:
    return {"X-OctopusOS-Source": "cli"}


def _get(path: str, *, params: dict | None = None) -> dict:
    url = _origin() + path
    r = requests.get(url, headers=_headers(), params=params, timeout=4.0)
    r.raise_for_status()
    return r.json()


def _post(path: str) -> dict:
    url = _origin() + path
    r = requests.post(url, headers=_headers(), timeout=12.0)
    r.raise_for_status()
    return r.json()


@click.group()
def cli() -> None:
    """Control OctopusOS Manager (local-only)."""


@cli.command("status")
def status_cmd() -> None:
    click.echo(json.dumps(_get("/control/status"), ensure_ascii=False, indent=2))


@cli.command("start")
def start_cmd() -> None:
    click.echo(json.dumps(_post("/control/start"), ensure_ascii=False, indent=2))


@cli.command("stop")
def stop_cmd() -> None:
    click.echo(json.dumps(_post("/control/stop"), ensure_ascii=False, indent=2))


@cli.command("restart")
def restart_cmd() -> None:
    click.echo(json.dumps(_post("/control/restart"), ensure_ascii=False, indent=2))


@cli.command("logs")
@click.option("--service", type=click.Choice(["backend", "frontend", "manager"]), default="backend")
@click.option("--tail", type=int, default=200)
def logs_cmd(service: str, tail: int) -> None:
    click.echo(json.dumps(_get("/control/logs", params={"service": service, "tail": tail}), ensure_ascii=False, indent=2))


def main() -> None:
    try:
        cli(standalone_mode=True)
    except requests.HTTPError as exc:
        click.echo(f"HTTP error: {exc}", err=True)
        sys.exit(2)
    except requests.RequestException as exc:
        base = _origin()
        click.echo(
            "\n".join(
                [
                    f"Manager not reachable at {base}.",
                    "Start it with: octopus-manager",
                    "Or: open Tray -> Start (if installed).",
                    f"Underlying error: {exc}",
                ]
            ),
            err=True,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
