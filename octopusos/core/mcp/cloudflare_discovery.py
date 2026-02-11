"""Cloudflare MCP discovery helpers for Network Access setup."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import tomllib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.core.mcp.client import MCPClient
from octopusos.core.mcp.config import MCPConfigManager, MCPServerConfig

_ACCOUNT_RE = re.compile(r"\|\s*[^|]+\s*\|\s*([a-f0-9]{32})\s*\|", re.IGNORECASE)
_ACCOUNT_FALLBACK_RE = re.compile(r"\b[a-f0-9]{32}\b", re.IGNORECASE)
_ACCOUNT_ID_RE = re.compile(r"^[a-f0-9]{32}$", re.IGNORECASE)
_PLACEHOLDER_HOSTNAMES = {
    "example.com",
    "example.net",
    "example.org",
    "test.com",
    "test.net",
    "test.org",
}


@dataclass
class CloudflareMCPDiscoveryResult:
    ok: bool
    account_id: Optional[str] = None
    hostnames: List[str] = field(default_factory=list)
    server_id: Optional[str] = None
    package_id: str = "cloudflare.mcp"
    tools_total: int = 0
    tools_seen: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "account_id": self.account_id,
            "hostnames": self.hostnames,
            "server_id": self.server_id,
            "package_id": self.package_id,
            "tools_total": int(self.tools_total),
            "tools_seen": self.tools_seen,
            "sources": self.sources,
            "warnings": self.warnings,
            "error": self.error,
        }


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _extract_text_blocks(result: Dict[str, Any]) -> List[str]:
    output: List[str] = []
    if not isinstance(result, dict):
        return output

    container = result.get("toolResult")
    if not isinstance(container, dict):
        return output

    content = container.get("content")
    if not isinstance(content, list):
        return output

    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            output.append(text.strip())
    return output


def _parse_json_payload(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_hostnames(payload: Any) -> List[str]:
    hostnames: List[str] = []

    def _append(value: Any) -> None:
        candidate = str(value or "").strip().lower()
        if not candidate:
            return
        if "." not in candidate:
            return
        if "/" in candidate:
            return
        hostnames.append(candidate)

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                _append(item)
                continue
            if not isinstance(item, dict):
                continue
            _append(item.get("name"))
            _append(item.get("hostname"))
            _append(item.get("domain"))
    elif isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, list):
            return _extract_hostnames(result)
        _append(payload.get("name"))
        _append(payload.get("hostname"))
        _append(payload.get("domain"))

    return sorted(set(hostnames))


def _normalize_account_id(value: Any) -> Optional[str]:
    account = str(value or "").strip().lower()
    if not account:
        return None
    if account in {"default", "null", "none", "-", "n/a"}:
        return None
    if not _ACCOUNT_ID_RE.match(account):
        return None
    return account


def _filter_placeholder_hostnames(hostnames: List[str]) -> tuple[List[str], bool]:
    cleaned = [h for h in hostnames if h and h not in _PLACEHOLDER_HOSTNAMES]
    return sorted(set(cleaned)), len(cleaned) != len(hostnames)


def _load_wrangler_oauth_token() -> Optional[str]:
    config_path = Path.home() / ".config/.wrangler/config/default.toml"
    if not config_path.exists():
        return None
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    token = str(data.get("oauth_token") or "").strip()
    return token or None


def _fetch_hostnames_from_cloudflare_api(*, account_id: str, token: str) -> List[str]:
    params = urllib.parse.urlencode({"account.id": account_id, "per_page": "50"})
    url = f"https://api.cloudflare.com/client/v4/zones?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not payload.get("success"):
        return []
    result = payload.get("result")
    if not isinstance(result, list):
        return []
    hostnames: List[str] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        if name and "." in name:
            hostnames.append(name)
    return sorted(set(hostnames))


def _resolve_account_id_from_wrangler() -> Optional[str]:
    try:
        proc = subprocess.run(
            ["npx", "-y", "wrangler", "whoami"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except Exception:
        return None

    text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    match = _ACCOUNT_RE.search(text)
    if match:
        return str(match.group(1)).strip().lower()

    fallback = _ACCOUNT_FALLBACK_RE.search(text)
    if fallback:
        return str(fallback.group(0)).strip().lower()
    return None


def _extract_account_from_server(server: MCPServerConfig) -> Optional[str]:
    env_account = _normalize_account_id((server.env or {}).get("CLOUDFLARE_ACCOUNT_ID"))
    if env_account:
        return env_account
    for part in server.command or []:
        account = _normalize_account_id(part)
        if account:
            return account
    return None


def _find_enabled_cloudflare_server(
    manager: MCPConfigManager,
    *,
    requested_account_id: Optional[str],
) -> Optional[MCPServerConfig]:
    cloudflare_servers: List[MCPServerConfig] = []
    for server in manager.get_enabled_servers():
        if (server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID") == "cloudflare.mcp":
            cloudflare_servers.append(server)

    if not cloudflare_servers:
        return None

    if requested_account_id:
        for server in cloudflare_servers:
            if _extract_account_from_server(server) == requested_account_id:
                return server

    for server in cloudflare_servers:
        if _extract_account_from_server(server):
            return server
    return cloudflare_servers[0]


def _build_runtime_server_config(
    server: MCPServerConfig,
    *,
    account_id: Optional[str],
) -> MCPServerConfig:
    request_config = server.model_copy(deep=True)
    request_env = dict(request_config.env or {})

    account = str(account_id or request_env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if account:
        request_env["CLOUDFLARE_ACCOUNT_ID"] = account
    request_config.env = request_env

    cmd = list(request_config.command or [])
    if account and cmd and "@cloudflare/mcp-server-cloudflare" in " ".join(cmd):
        has_run = "run" in cmd
        has_account_arg = any(str(part or "").strip().lower() == account.lower() for part in cmd)
        if has_run and not has_account_arg:
            cmd.append(account)
            request_config.command = cmd
    return request_config


async def _discover_async(server_config: MCPServerConfig) -> CloudflareMCPDiscoveryResult:
    client = MCPClient(server_config)
    await client.connect()
    try:
        tools = await client.list_tools()
        tool_names = [str(tool.get("name")) for tool in tools if tool.get("name")]

        hostnames: List[str] = []
        used_sources: List[str] = []
        warnings: List[str] = []

        if "zones_list" in tool_names:
            zones_result = await client.call_tool("zones_list", {})
            for text in _extract_text_blocks(zones_result):
                parsed = _parse_json_payload(text)
                if parsed is None:
                    continue
                names = _extract_hostnames(parsed)
                if names:
                    hostnames.extend(names)
                    used_sources.append("zones_list")

        if not hostnames and "domain_list" in tool_names:
            domain_result = await client.call_tool("domain_list", {})
            for text in _extract_text_blocks(domain_result):
                parsed = _parse_json_payload(text)
                if parsed is None:
                    continue
                names = _extract_hostnames(parsed)
                if names:
                    hostnames.extend(names)
                    used_sources.append("domain_list")

        hostnames, filtered_placeholder = _filter_placeholder_hostnames(hostnames)
        if filtered_placeholder:
            warnings.append("placeholder_hostnames_filtered")

        if not hostnames:
            warnings.append("hostname_not_found_from_mcp")

        account_id = _normalize_account_id((server_config.env or {}).get("CLOUDFLARE_ACCOUNT_ID"))
        return CloudflareMCPDiscoveryResult(
            ok=True,
            account_id=account_id,
            hostnames=sorted(set(hostnames)),
            server_id=server_config.id,
            tools_total=len(tool_names),
            tools_seen=sorted(tool_names),
            sources=sorted(set(used_sources)),
            warnings=warnings,
        )
    finally:
        await client.disconnect()


def discover_cloudflare_setup(
    *,
    account_id: Optional[str] = None,
    config_manager: Optional[MCPConfigManager] = None,
) -> CloudflareMCPDiscoveryResult:
    manager = config_manager or MCPConfigManager()
    requested_account_id = _normalize_account_id(account_id)
    server = _find_enabled_cloudflare_server(manager, requested_account_id=requested_account_id)
    if not server:
        return CloudflareMCPDiscoveryResult(ok=False, error="cloudflare_mcp_not_enabled")

    resolved_account_id = requested_account_id or _normalize_account_id(
        (server.env or {}).get("CLOUDFLARE_ACCOUNT_ID")
    )
    if not resolved_account_id:
        resolved_account_id = _normalize_account_id(_resolve_account_id_from_wrangler())
    if not resolved_account_id:
        return CloudflareMCPDiscoveryResult(
            ok=False,
            server_id=server.id,
            error="cloudflare_account_id_required",
        )

    runtime_server = _build_runtime_server_config(server, account_id=resolved_account_id or None)
    if resolved_account_id and runtime_server.env is not None:
        runtime_server.env["CLOUDFLARE_ACCOUNT_ID"] = resolved_account_id

    try:
        result = _run_async(_discover_async(runtime_server))
    except Exception as exc:
        return CloudflareMCPDiscoveryResult(
            ok=False,
            account_id=resolved_account_id,
            server_id=server.id,
            error=f"mcp_discovery_failed:{exc}",
        )

    if resolved_account_id and not result.account_id:
        result.account_id = resolved_account_id

    if not result.hostnames and resolved_account_id:
        token = _load_wrangler_oauth_token()
        if token:
            try:
                api_hostnames = _fetch_hostnames_from_cloudflare_api(
                    account_id=resolved_account_id,
                    token=token,
                )
                api_hostnames, filtered_placeholder = _filter_placeholder_hostnames(api_hostnames)
                if filtered_placeholder:
                    result.warnings.append("placeholder_hostnames_filtered")
                if api_hostnames:
                    result.hostnames = api_hostnames
                    result.sources = sorted(set([*result.sources, "cloudflare_api"]))
                else:
                    result.warnings.append("hostname_not_found_from_cloudflare_api")
            except Exception:
                result.warnings.append("cloudflare_api_fallback_failed")
        else:
            result.warnings.append("wrangler_oauth_token_missing")
    return result
