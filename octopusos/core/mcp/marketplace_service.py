"""Marketplace service for MCP catalog, attach, and uninstall."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from octopusos.core.capabilities.audit import emit_audit_event
from octopusos.core.mcp.config import MCPConfigManager, MCPServerConfig
from octopusos.core.mcp.marketplace_registry import MCPMarketplaceRegistry


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_component(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return normalized or "default"


def _make_server_id(package_id: str, profile: str) -> str:
    return f"mcp_{_sanitize_component(package_id)}_{_sanitize_component(profile)}"


def _extract_command(
    connection_template: Dict[str, Any],
    *,
    profile: str,
    region: Optional[str],
) -> List[str]:
    command_value = connection_template.get("command")
    args = connection_template.get("args") or []

    if isinstance(command_value, list):
        cmd = [str(item) for item in command_value if str(item).strip()]
    elif isinstance(command_value, str) and command_value.strip():
        cmd = [command_value.strip()]
    else:
        raise ValueError("connection_template.command is required")

    rendered_args: List[str] = []
    for item in args:
        rendered = _render_env_template(item, profile=profile, region=region)
        if rendered is not None:
            rendered_args.append(rendered)

    cmd.extend(rendered_args)
    if not cmd:
        raise ValueError("MCP command cannot be empty")
    return cmd


def _catalog_requires(package_id: str) -> List[str]:
    if package_id == "aws.mcp":
        return ["aws-cli"]
    if package_id == "azure.mcp":
        return ["azure-cli"]
    if package_id == "cloudflare.mcp":
        return ["wrangler-auth"]
    return []


def _apply_cloud_attach_env(
    *,
    package_id: str,
    env: Dict[str, str],
    profile: str,
    region: Optional[str],
) -> None:
    if package_id == "aws.mcp":
        env["AWS_PROFILE"] = profile
        if region:
            env["AWS_REGION"] = region
        else:
            env.pop("AWS_REGION", None)
        return

    if package_id == "azure.mcp":
        env["AZURE_SUBSCRIPTION"] = profile
        if region:
            env["AZURE_LOCATION"] = region
        else:
            env.pop("AZURE_LOCATION", None)
        return

    if package_id == "cloudflare.mcp":
        env["CLOUDFLARE_ACCOUNT_ID"] = profile
        return


def _render_env_template(value: Any, *, profile: str, region: Optional[str]) -> Optional[str]:
    """Render known env placeholders and drop unresolved optional region placeholders."""
    raw = str(value)
    rendered = raw.replace("{{profile}}", profile)
    if "{{region}}" in rendered:
        if region:
            rendered = rendered.replace("{{region}}", region)
        else:
            rendered = rendered.replace("{{region}}", "").strip()
    if not rendered:
        return None
    return rendered


def _package_to_summary(package, config_manager: MCPConfigManager) -> Dict[str, Any]:
    connected = False
    for server in config_manager.list_servers():
        if server.env.get("OCTOPUSOS_MCP_PACKAGE_ID") == package.package_id:
            connected = True
            break

    return {
        "package_id": package.package_id,
        "name": package.name,
        "version": package.version,
        "author": package.author,
        "description": package.description,
        "tools_count": len(package.tools),
        "transport": package.transport.value,
        "recommended_trust_tier": package.recommended_trust_tier,
        "requires_admin_token": package.requires_admin_token,
        "is_connected": connected,
        "tags": package.tags,
        "declared_side_effects": [effect.value for effect in package.declared_side_effects],
    }


def list_catalog(
    *,
    connected_only: bool = False,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    registry: Optional[MCPMarketplaceRegistry] = None,
    config_manager: Optional[MCPConfigManager] = None,
) -> Dict[str, Any]:
    market = registry or MCPMarketplaceRegistry()
    manager = config_manager or MCPConfigManager()

    if search:
        packages = market.search_packages(search)
    else:
        packages = market.list_packages(connected_only=False, tag=tag)

    items = [_package_to_summary(pkg, manager) for pkg in packages]
    if connected_only:
        items = [item for item in items if item["is_connected"]]

    catalog_items = [
        {
            "package_id": item["package_id"],
            "display_name": item["name"],
            "description": item["description"],
            "trust_tier": item["recommended_trust_tier"],
            "declared_side_effects": item["declared_side_effects"],
            "requires": _catalog_requires(item["package_id"]),
        }
        for item in items
    ]
    return {"packages": items, "catalog": catalog_items, "total": len(items)}


def get_package_detail(
    package_id: str,
    *,
    registry: Optional[MCPMarketplaceRegistry] = None,
) -> Dict[str, Any]:
    market = registry or MCPMarketplaceRegistry()
    package = market.get_package(package_id)
    if not package:
        raise KeyError(f"Package not found: {package_id}")
    return package.model_dump()


def get_governance_preview(
    package_id: str,
    *,
    registry: Optional[MCPMarketplaceRegistry] = None,
) -> Dict[str, Any]:
    market = registry or MCPMarketplaceRegistry()
    preview = market.generate_governance_preview(package_id)
    if not preview:
        raise KeyError(f"Package not found: {package_id}")
    return preview.model_dump()


def attach_package(
    *,
    package_id: str,
    profile: str = "default",
    region: Optional[str] = None,
    custom_config: Optional[Dict[str, Any]] = None,
    override_trust_tier: Optional[str] = None,
    registry: Optional[MCPMarketplaceRegistry] = None,
    config_manager: Optional[MCPConfigManager] = None,
) -> Dict[str, Any]:
    market = registry or MCPMarketplaceRegistry()
    manager = config_manager or MCPConfigManager()

    package = market.get_package(package_id)
    if not package:
        raise KeyError(f"Package not found: {package_id}")

    server_id = _make_server_id(package_id, profile)
    if manager.get_server_config(server_id):
        raise ValueError(f"Package already attached for profile '{profile}': {package_id}")

    connection = dict(package.connection_template)
    if custom_config:
        connection.update(custom_config)

    command = _extract_command(connection, profile=profile, region=region)
    env: Dict[str, str] = {}
    for key, value in (connection.get("env") or {}).items():
        rendered = _render_env_template(value, profile=profile, region=region)
        if rendered is not None:
            env[str(key)] = rendered
    _apply_cloud_attach_env(package_id=package_id, env=env, profile=profile, region=region)
    env["OCTOPUSOS_MCP_PACKAGE_ID"] = package_id
    env["OCTOPUSOS_MCP_ATTACHED_AT"] = _utc_iso()

    server_config = MCPServerConfig(
        id=server_id,
        enabled=False,
        transport=package.transport.value,
        command=command,
        allow_tools=[],
        deny_side_effect_tags=[],
        env=env,
        timeout_ms=30000,
    )
    manager.add_server(server_config)

    applied_trust = override_trust_tier or package.recommended_trust_tier
    warnings: List[str] = []
    if override_trust_tier and override_trust_tier != package.recommended_trust_tier:
        warnings.append(
            f"Trust tier override: {package.recommended_trust_tier} -> {override_trust_tier}."
        )
    if package.declared_side_effects:
        warnings.append("Package declares side effects; review policy gates before enable.")

    audit_id = emit_audit_event(
        event_type="mcp_attached",
        details={
            "package_id": package_id,
            "server_id": server_id,
            "enabled": False,
            "profile": profile,
            "region": region,
            "trust_tier": applied_trust,
        },
    )

    return {
        "server_id": server_id,
        "server_id_reason": f"package={package_id}, profile={profile}",
        "enabled": False,
        "audit_id": audit_id,
        "warnings": warnings,
        "next_steps": [
            f"Call POST /api/mcp/servers/{server_id}/preflight then /enable",
        ],
        "status": "attached",
        "trust_tier": applied_trust,
    }


def uninstall_package(
    package_id: str,
    *,
    config_manager: Optional[MCPConfigManager] = None,
) -> Dict[str, Any]:
    manager = config_manager or MCPConfigManager()
    removed_ids: List[str] = []
    for server in manager.list_servers():
        if server.env.get("OCTOPUSOS_MCP_PACKAGE_ID") == package_id:
            if manager.remove_server(server.id):
                removed_ids.append(server.id)

    audit_id = emit_audit_event(
        event_type="mcp_uninstall",
        details={"package_id": package_id, "removed_server_ids": removed_ids},
    )
    return {"removed_server_ids": removed_ids, "audit_id": audit_id}
