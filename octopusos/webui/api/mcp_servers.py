"""MCP server management APIs."""

from __future__ import annotations

import configparser
import concurrent.futures
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from octopusos.core.capabilities.registry import CapabilityRegistry
from octopusos.core.extensions.registry import ExtensionRegistry
from octopusos.core.mcp.config import MCPConfigManager
from octopusos.core.mcp.preflight_runner import run_preflight_for_server
from octopusos.core.runtime.dependency_installer import ensure_aws_cli_if_needed

router = APIRouter(prefix="/api", tags=["mcp-servers"])

MICROSOFT_MCP_PACKAGES = {
    "microsoft.teams.mcp",
    "microsoft.mail.mcp",
    "microsoft.calendar.mcp",
    "microsoft.odspremoteserver.mcp",
    "microsoft.sharepointlisttools.mcp",
    "microsoft.word.mcp",
}


class EnableRequest(BaseModel):
    auto_install: bool = Field(default=True)
    confirm_actions: bool = Field(default=True)


class ConfigureRequest(BaseModel):
    profile: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    tenant_id: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None)
    bot_app_id: Optional[str] = Field(default=None)


def _refresh_capabilities() -> None:
    # Best-effort refresh so newly enabled MCP tools become discoverable immediately.
    registry = CapabilityRegistry(ExtensionRegistry())
    registry.refresh()


def _mask_env(env: Dict[str, str]) -> Dict[str, str]:
    masked: Dict[str, str] = {}
    for key, value in env.items():
        upper = key.upper()
        if any(token in upper for token in ("TOKEN", "SECRET", "KEY", "PASSWORD")):
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


def _server_payload(server) -> Dict[str, Any]:
    env = dict(server.env or {})
    package_id = env.get("OCTOPUSOS_MCP_PACKAGE_ID")
    aws_profile = env.get("AWS_PROFILE")
    aws_region = env.get("AWS_REGION")
    azure_subscription = env.get("AZURE_SUBSCRIPTION")
    azure_location = env.get("AZURE_LOCATION")
    teams_tenant_id = env.get("TEAMS_TENANT_ID")
    teams_client_id = env.get("TEAMS_CLIENT_ID")
    teams_bot_app_id = env.get("TEAMS_BOT_APP_ID")
    teams_has_client_secret = bool(env.get("TEAMS_CLIENT_SECRET"))
    microsoft_tenant_id = teams_tenant_id
    microsoft_client_id = teams_client_id
    microsoft_bot_app_id = teams_bot_app_id
    microsoft_has_client_secret = teams_has_client_secret

    cloud_profile = aws_profile
    cloud_region = aws_region
    if package_id == "azure.mcp":
        cloud_profile = azure_subscription
        cloud_region = azure_location

    return {
        "server_id": server.id,
        "enabled": server.enabled,
        "type": server.transport,
        "command": server.command[0] if server.command else "",
        "args": server.command[1:] if len(server.command) > 1 else [],
        "package_id": package_id,
        "aws_profile": aws_profile,
        "aws_region": aws_region,
        "azure_subscription": azure_subscription,
        "azure_location": azure_location,
        "teams_tenant_id": teams_tenant_id,
        "teams_client_id": teams_client_id,
        "teams_bot_app_id": teams_bot_app_id,
        "teams_has_client_secret": teams_has_client_secret,
        "microsoft_tenant_id": microsoft_tenant_id,
        "microsoft_client_id": microsoft_client_id,
        "microsoft_bot_app_id": microsoft_bot_app_id,
        "microsoft_has_client_secret": microsoft_has_client_secret,
        "cloud_profile": cloud_profile,
        "cloud_region": cloud_region,
        "env_summary": _mask_env(env),
    }


@router.get("/mcp/servers")
def list_mcp_servers() -> Dict[str, Any]:
    manager = MCPConfigManager()
    servers = [_server_payload(server) for server in manager.list_servers()]
    return {"servers": servers, "total": len(servers), "source": "real"}


@router.get("/mcp/servers/{server_id}")
def get_mcp_server(server_id: str) -> Dict[str, Any]:
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server not found")
    return {"server": _server_payload(server), "source": "real"}


@router.post("/mcp/servers/refresh")
def refresh_mcp_servers() -> Dict[str, Any]:
    # CapabilityRegistry.refresh() may touch disk / spawn subprocesses; keep this endpoint responsive.
    def _run() -> Dict[str, Any]:
        _refresh_capabilities()
        manager = MCPConfigManager()
        enabled = manager.get_enabled_servers()
        return {
            "message": f"Refreshed {len(enabled)} enabled MCP servers",
            "refreshed_count": len(enabled),
            "source": "real",
        }

    ex: concurrent.futures.ThreadPoolExecutor | None = None
    try:
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        return ex.submit(_run).result(timeout=2.5)
    except Exception:
        # Best-effort: avoid blocking clients; report current enabled servers without refresh.
        manager = MCPConfigManager()
        enabled = manager.get_enabled_servers()
        return {
            "message": f"Refresh timed out; {len(enabled)} enabled MCP servers (no refresh)",
            "refreshed_count": len(enabled),
            "source": "real",
        }
    finally:
        if ex is not None:
            try:
                ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                ex.shutdown(wait=False)


@router.get("/mcp/servers/{server_id}/preflight")
def preflight_mcp_server(server_id: str) -> Dict[str, Any]:
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server not found")
    report = run_preflight_for_server(server)
    payload = report.model_dump()
    payload["server_id"] = server_id
    payload["source"] = "real"
    return payload


@router.get("/mcp/aws/profiles")
def list_local_aws_profiles() -> Dict[str, Any]:
    def _pick_default(profiles: list[str]) -> str:
        return "default" if "default" in profiles else (profiles[0] if profiles else "default")

    def _discover_profiles_from_files() -> list[str]:
        aws_dir = Path.home() / ".aws"
        config_path = aws_dir / "config"
        credentials_path = aws_dir / "credentials"
        discovered: set[str] = set()

        config = configparser.ConfigParser()
        for path in (config_path, credentials_path):
            if not path.exists():
                continue
            try:
                config.read(path, encoding="utf-8")
            except Exception:
                continue
            for section in config.sections():
                if section == "default":
                    discovered.add("default")
                elif section.startswith("profile "):
                    discovered.add(section[len("profile "):].strip())
                else:
                    discovered.add(section.strip())
            config.clear()
        return sorted(p for p in discovered if p)

    file_profiles = _discover_profiles_from_files()
    aws_path = shutil.which("aws")
    if not aws_path:
        if file_profiles:
            return {
                "ok": True,
                "profiles": file_profiles,
                "default_profile": _pick_default(file_profiles),
                "source": "files",
                "reason": "aws_cli_missing",
            }
        return {"ok": False, "profiles": [], "default_profile": "default", "reason": "aws_cli_missing"}

    try:
        proc = subprocess.run(
            ["aws", "configure", "list-profiles"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        if file_profiles:
            return {
                "ok": True,
                "profiles": file_profiles,
                "default_profile": _pick_default(file_profiles),
                "source": "files",
                "reason": str(exc),
            }
        return {"ok": False, "profiles": [], "default_profile": "default", "reason": str(exc)}

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if file_profiles:
            return {
                "ok": True,
                "profiles": file_profiles,
                "default_profile": _pick_default(file_profiles),
                "source": "files",
                "reason": detail or "command_failed",
            }
        return {"ok": False, "profiles": [], "default_profile": "default", "reason": detail or "command_failed"}

    cli_profiles = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    profiles = sorted(set(cli_profiles) | set(file_profiles))
    default_profile = _pick_default(profiles)
    return {
        "ok": True,
        "profiles": profiles,
        "default_profile": default_profile,
        "source": "cli+files" if file_profiles else "cli",
    }


@router.post("/mcp/servers/{server_id}/config")
def configure_mcp_server(server_id: str, payload: ConfigureRequest) -> Dict[str, Any]:
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server not found")

    package_id = (server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID")
    if package_id not in {"aws.mcp", "azure.mcp", *MICROSOFT_MCP_PACKAGES}:
        raise HTTPException(
            status_code=400,
            detail=(
                "config update currently supported for aws.mcp, azure.mcp, "
                "microsoft.teams.mcp, microsoft.mail.mcp, microsoft.calendar.mcp, "
                "microsoft.odspremoteserver.mcp, microsoft.sharepointlisttools.mcp, and microsoft.word.mcp"
            ),
        )

    env_patch: Dict[str, str] = {}
    if payload.profile is not None:
        profile = payload.profile.strip()
        if not profile:
            raise HTTPException(status_code=400, detail="profile cannot be empty")
        if package_id == "aws.mcp":
            env_patch["AWS_PROFILE"] = profile
        else:
            env_patch["AZURE_SUBSCRIPTION"] = profile

    if payload.region is not None:
        region = payload.region.strip()
        # empty region is treated as clearing explicit region override.
        if package_id == "aws.mcp":
            env_patch["AWS_REGION"] = region
        elif package_id == "azure.mcp":
            env_patch["AZURE_LOCATION"] = region

    if package_id in MICROSOFT_MCP_PACKAGES:
        if payload.tenant_id is not None:
            env_patch["TEAMS_TENANT_ID"] = payload.tenant_id.strip()
        if payload.client_id is not None:
            env_patch["TEAMS_CLIENT_ID"] = payload.client_id.strip()
        if payload.client_secret is not None:
            env_patch["TEAMS_CLIENT_SECRET"] = payload.client_secret.strip()
        if payload.bot_app_id is not None:
            env_patch["TEAMS_BOT_APP_ID"] = payload.bot_app_id.strip()

    updated = manager.update_server(server_id, {"env": env_patch})
    return {"ok": True, "server": _server_payload(updated), "source": "real"}


def _run_enable(server_id: str, auto_install: bool) -> Dict[str, Any]:
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server not found")

    report = run_preflight_for_server(server)

    if auto_install and not report.ok:
        # Auto-migrate legacy AWS launcher command when possible.
        cmd0 = server.command[0] if server.command else ""
        package_id = (server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID")
        if (
            package_id == "aws.mcp"
            and cmd0 == "aws-mcp"
            and shutil.which("aws-mcp") is None
        ):
            uvx = shutil.which("uvx")
            if not uvx and shutil.which("brew"):
                subprocess.run(
                    ["brew", "install", "uv"],
                    capture_output=True,
                    text=True,
                    timeout=900,
                    check=False,
                )
                uvx = shutil.which("uvx")
            if uvx:
                manager.update_server(
                    server_id,
                    {"command": ["uvx", "awslabs.aws-api-mcp-server@latest"]},
                )
                server = manager.get_server(server_id)
                if server:
                    report = run_preflight_for_server(server)

        did_install, note = ensure_aws_cli_if_needed(report)
        if did_install:
            report = run_preflight_for_server(server)
            report.warnings.append(note)

    if not report.ok:
        raise HTTPException(status_code=409, detail=report.model_dump())

    manager.update_server(server_id, {"enabled": True})
    _refresh_capabilities()
    return {
        "server_id": server_id,
        "enabled": True,
        "preflight": report.model_dump(),
        "source": "real",
    }


@router.post("/mcp/servers/{server_id}/enable")
def enable_mcp_server(server_id: str, req: EnableRequest) -> Dict[str, Any]:
    return _run_enable(server_id, auto_install=req.auto_install)


@router.post("/mcp/servers/{server_id}/connect")
def connect_mcp_server(server_id: str) -> Dict[str, Any]:
    result = _run_enable(server_id, auto_install=True)
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    return {"server": _server_payload(server), "result": result, "source": "real"}


@router.post("/mcp/servers/{server_id}/disable")
def disable_mcp_server(server_id: str) -> Dict[str, Any]:
    manager = MCPConfigManager()
    server = manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server not found")
    manager.update_server(server_id, {"enabled": False})
    _refresh_capabilities()
    return {"server_id": server_id, "enabled": False, "source": "real"}


@router.post("/mcp/servers/{server_id}/disconnect")
def disconnect_mcp_server(server_id: str) -> Dict[str, Any]:
    return disable_mcp_server(server_id)
