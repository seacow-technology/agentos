"""
MCP Marketplace APIs - Backend Interface

Provides 4 API endpoints to support Discover, Inspect, Approve, Attach flow:

1. GET /api/mcp/marketplace/packages - List all packages (Discover)
2. GET /api/mcp/marketplace/packages/{package_id} - Get package details (Inspect)
3. GET /api/mcp/marketplace/governance-preview/{package_id} - Generate governance preview
4. POST /api/mcp/marketplace/attach - Attach MCP to local AgentOS (Attach)

Core Principles (RED LINES):
- API cannot execute MCP
- API cannot bypass Gate
- API cannot silent enable high-risk capabilities
- Attach API must have complete audit
- All APIs follow permission model
"""

import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.core.mcp.marketplace_registry import MCPMarketplaceRegistry
from agentos.core.mcp.config import MCPServerConfig
from agentos.core.capabilities.audit import emit_audit_event
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)
router = APIRouter()

# Global registry instance (lazy initialized)
_marketplace_registry: Optional[MCPMarketplaceRegistry] = None


def get_marketplace_registry() -> MCPMarketplaceRegistry:
    """Get or create marketplace registry instance"""
    global _marketplace_registry
    if _marketplace_registry is None:
        _marketplace_registry = MCPMarketplaceRegistry()
        logger.info("MCPMarketplaceRegistry initialized")
    return _marketplace_registry


# ============================================
# Response Models
# ============================================

class MCPPackageSummary(BaseModel):
    """Package summary for list view"""
    package_id: str
    name: str
    version: str
    author: str
    description: str
    tools_count: int
    transport: str
    recommended_trust_tier: str
    requires_admin_token: bool
    is_connected: bool
    tags: List[str]


class PackageListResponse(BaseModel):
    """Package list response"""
    packages: List[MCPPackageSummary]
    total: int


class AttachRequest(BaseModel):
    """MCP package attach request"""
    package_id: str = Field(description="Package ID to attach")
    override_trust_tier: Optional[str] = Field(None, description="Override trust tier (T0-T3)")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Custom connection config")


# ============================================
# API Endpoints
# ============================================

@router.get("/packages", response_model=PackageListResponse)
async def list_mcp_packages(
    connected_only: bool = Query(False, description="Only show connected packages"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search query")
):
    """
    List all MCP packages (Discover)

    Query Parameters:
    - connected_only: bool - Only show already attached packages
    - tag: str - Filter packages by tag
    - search: str - Search in name, description, tags

    Returns:
        PackageListResponse with packages list and total count
    """
    try:
        registry = get_marketplace_registry()

        # Get packages
        if search:
            packages = registry.search_packages(search)
        else:
            packages = registry.list_packages(
                connected_only=connected_only,
                tag=tag
            )

        # Convert to summaries
        summaries = []
        for pkg in packages:
            summaries.append(MCPPackageSummary(
                package_id=pkg.package_id,
                name=pkg.name,
                version=pkg.version,
                author=pkg.author,
                description=pkg.description,
                tools_count=len(pkg.tools),
                transport=pkg.transport.value,
                recommended_trust_tier=pkg.recommended_trust_tier,
                requires_admin_token=pkg.requires_admin_token,
                is_connected=pkg.is_connected,
                tags=pkg.tags
            ))

        logger.info(f"Listed {len(summaries)} MCP packages")
        return PackageListResponse(
            packages=summaries,
            total=len(summaries)
        )

    except Exception as e:
        logger.error(f"Failed to list packages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages/{package_id:path}")
async def get_mcp_package(package_id: str):
    """
    Get MCP package details (Inspect)

    Path Parameters:
    - package_id: Package identifier (e.g., "agentos.official/echo-math")

    Returns:
        Complete package details including tools, side effects, and metadata
    """
    try:
        registry = get_marketplace_registry()
        package = registry.get_package(package_id)

        if not package:
            raise HTTPException(
                status_code=404,
                detail=f"Package not found: {package_id}"
            )

        logger.info(f"Retrieved package details: {package_id}")
        return {
            "ok": True,
            "data": package.model_dump()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get package {package_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance-preview/{package_id:path}")
async def get_governance_preview(package_id: str):
    """
    Generate governance preview (pre-attach risk assessment)

    Path Parameters:
    - package_id: Package identifier

    Returns:
        Governance preview with:
        - Inferred trust tier and risk level
        - Default quota settings
        - Admin token requirements
        - Gate warnings
        - Audit level
    """
    try:
        registry = get_marketplace_registry()
        preview = registry.generate_governance_preview(package_id)

        if not preview:
            raise HTTPException(
                status_code=404,
                detail=f"Package not found: {package_id}"
            )

        logger.info(f"Generated governance preview for: {package_id}")
        return {
            "ok": True,
            "data": preview.model_dump()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate preview for {package_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attach")
async def attach_mcp_package(request: AttachRequest):
    """
    Attach MCP package to local AgentOS (Attach)

    IMPORTANT:
    - Attach后MCP默认disabled
    - 需要显式enable才能使用
    - 如果有side effects,需要admin token

    Core Logic:
    1. Verify package_id exists
    2. Generate MCP server config (disabled by default)
    3. Write audit: capability_attached
    4. Do NOT auto-enable (requires explicit enable)
    5. Return attachment status

    Request Body:
    - package_id: Package to attach
    - override_trust_tier: Optional trust tier override (T0-T3)
    - custom_config: Optional custom connection config

    Returns:
        Attachment result with:
        - server_id: Generated server ID
        - status: "attached"
        - enabled: false (always)
        - trust_tier: Applied trust tier
        - audit_id: Audit event ID
        - warnings: List of warnings
        - next_steps: User guidance
    """
    try:
        registry = get_marketplace_registry()
        package = registry.get_package(request.package_id)

        if not package:
            raise HTTPException(
                status_code=404,
                detail=f"Package not found: {request.package_id}"
            )

        if package.is_connected:
            raise HTTPException(
                status_code=400,
                detail=f"Package already connected: {request.package_id}"
            )

        # Generate server_id from package_id (take last part)
        server_id = request.package_id.split("/")[-1]

        # Determine trust tier
        trust_tier = request.override_trust_tier or package.recommended_trust_tier

        # Check override warning
        warnings = []
        if request.override_trust_tier and request.override_trust_tier != package.recommended_trust_tier:
            warnings.append(
                f"⚠️ Trust Tier overridden: {package.recommended_trust_tier} → {request.override_trust_tier}"
            )

        # Prepare connection config
        config_data = request.custom_config or package.connection_template

        # Ensure MCP config directory exists
        mcp_config_dir = Path.home() / ".agentos" / "mcp"
        mcp_config_dir.mkdir(parents=True, exist_ok=True)

        # Write server config file
        config_file = mcp_config_dir / f"{server_id}.yaml"
        config_content = {
            "server_id": server_id,
            "name": package.name,
            "transport": package.transport.value,
            "enabled": False,  # CRITICAL: Default disabled
            "trust_tier": trust_tier,
            "config": config_data,
            "metadata": {
                "package_id": request.package_id,
                "version": package.version,
                "attached_at": iso_z(datetime.now())
            }
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_content, f, default_flow_style=False)

        logger.info(f"MCP server config written: {config_file}")

        # Write audit event
        audit_id = emit_audit_event(
            event_type="mcp_attached",
            details={
                "package_id": request.package_id,
                "server_id": server_id,
                "trust_tier": trust_tier,
                "transport": package.transport.value,
                "requires_admin_token": package.requires_admin_token,
                "declared_side_effects": [str(e.value) for e in package.declared_side_effects],
                "enabled": False,  # Emphasize disabled state
                "attached_at": iso_z(datetime.now())
            }
        )

        logger.info(f"Audit event emitted: {audit_id}")

        # Update package status (in-memory only, not persisted)
        package.is_connected = True
        package.connected_at = iso_z(datetime.now())

        # Add standard warnings
        warnings.append("MCP is attached but not enabled. Use CLI to enable.")

        if package.declared_side_effects:
            warnings.append("This MCP declares side effects. Admin token may be required.")

        if trust_tier in ["T2", "T3"]:
            warnings.append(f"Trust Tier {trust_tier} - requires careful approval before enabling.")

        # Build next steps
        next_steps = [
            "Review the MCP in Capabilities → MCP",
            f"Enable using: agentos mcp enable {server_id}",
        ]

        if package.requires_admin_token:
            next_steps.append("Configure admin token for sensitive operations")

        logger.info(f"MCP package attached successfully: {request.package_id} → {server_id}")

        return {
            "ok": True,
            "data": {
                "server_id": server_id,
                "status": "attached",
                "enabled": False,
                "trust_tier": trust_tier,
                "audit_id": audit_id,
                "warnings": warnings,
                "next_steps": next_steps
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to attach package {request.package_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
