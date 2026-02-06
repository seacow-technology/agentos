"""
MCP Marketplace Registry Manager

This module manages the local MCP Marketplace registry, which stores metadata
about available MCP packages. The registry provides:

- Loading MCP Package declarations from YAML
- Search and filtering capabilities
- Governance preview generation (risk assessment before connection)

What this module does NOT do:
- Execute MCP tools
- Modify governance policies
- Make permission decisions

The registry is a read-only metadata source. All governance decisions are made
by the policy engine at runtime based on the current policies and trust tiers.
"""

import yaml
from pathlib import Path
from typing import List, Optional
import logging

from agentos.core.mcp.marketplace_models import (
    MCPPackage,
    MCPGovernancePreview,
    MCPTransportType
)
from agentos.core.capabilities.trust_tier_defaults import TRUST_TIER_QUOTA_DEFAULTS

logger = logging.getLogger(__name__)


class MCPMarketplaceRegistry:
    """MCP Marketplace Local Registry

    Responsibilities:
    - Load local MCP Package declarations
    - Provide search and filtering
    - Generate governance previews

    Not Responsible For:
    - Executing MCP tools
    - Modifying governance policies
    - Calling MCP tools
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """
        Initialize the registry

        Args:
            registry_path: Path to registry YAML file. If None, uses default path
                          (project_root/data/mcp_registry.yaml)
        """
        if registry_path is None:
            # Default location: project root's data/mcp_registry.yaml
            registry_path = Path(__file__).parent.parent.parent.parent / "data" / "mcp_registry.yaml"

        self.registry_path = registry_path
        self.packages: List[MCPPackage] = []

        self._load_registry()

    def _load_registry(self):
        """Load registry from YAML file"""
        if not self.registry_path.exists():
            logger.warning(f"MCP registry not found: {self.registry_path}")
            return

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data or 'packages' not in data:
                logger.warning("Invalid registry format: missing 'packages' key")
                return

            for pkg_data in data['packages']:
                try:
                    package = MCPPackage(**pkg_data)
                    self.packages.append(package)
                except Exception as e:
                    logger.error(
                        f"Failed to parse package {pkg_data.get('package_id', 'unknown')}: {e}",
                        exc_info=True
                    )

            logger.info(f"Loaded {len(self.packages)} packages from registry")

        except Exception as e:
            logger.error(f"Failed to load registry from {self.registry_path}: {e}", exc_info=True)

    def list_packages(
        self,
        connected_only: bool = False,
        tag: Optional[str] = None
    ) -> List[MCPPackage]:
        """List all packages with optional filtering

        Args:
            connected_only: If True, only return connected packages
            tag: If provided, only return packages with this tag

        Returns:
            List of MCPPackage objects matching the filters
        """
        packages = self.packages

        if connected_only:
            packages = [p for p in packages if p.is_connected]

        if tag:
            packages = [p for p in packages if tag in p.tags]

        return packages

    def get_package(self, package_id: str) -> Optional[MCPPackage]:
        """Get a single package by ID

        Args:
            package_id: Package identifier

        Returns:
            MCPPackage if found, None otherwise
        """
        for pkg in self.packages:
            if pkg.package_id == package_id:
                return pkg
        return None

    def generate_governance_preview(self, package_id: str) -> Optional[MCPGovernancePreview]:
        """Generate governance preview (pre-connection risk assessment)

        This shows "what would happen if we connect this MCP" without making decisions.
        The preview helps users understand the governance implications before connecting.

        Inference Logic:
        - Trust Tier: Based on transport type (stdio=T1, http/https=T3, etc.)
        - Risk Level: Based on trust tier (T0=LOW, T1=MEDIUM, T2=HIGH, T3=CRITICAL)
        - Quota: Default quota for the inferred trust tier
        - Admin Token: Required for T3, or T2 with side effects
        - Gate Warnings: Predictions based on package characteristics

        Args:
            package_id: Package identifier

        Returns:
            MCPGovernancePreview if package found, None otherwise
        """
        package = self.get_package(package_id)
        if not package:
            return None

        # Infer Trust Tier based on transport
        tier_map = {
            MCPTransportType.STDIO: "T1",
            MCPTransportType.HTTP: "T3",
            MCPTransportType.HTTPS: "T3",
            MCPTransportType.TCP: "T2",
            MCPTransportType.SSH: "T2"
        }
        inferred_tier = tier_map.get(package.transport, "T3")

        # Infer risk level based on trust tier
        risk_map = {
            "T0": "LOW",
            "T1": "MEDIUM",
            "T2": "HIGH",
            "T3": "CRITICAL"
        }
        risk_level = risk_map[inferred_tier]

        # Get default quota for the trust tier
        # Map T0-T3 to TrustTier enum values for lookup
        from agentos.core.capabilities.capability_models import TrustTier
        tier_enum_map = {
            "T0": TrustTier.T0,
            "T1": TrustTier.T1,
            "T2": TrustTier.T2,
            "T3": TrustTier.T3
        }
        tier_enum = tier_enum_map.get(inferred_tier, TrustTier.T1)
        default_quota = TRUST_TIER_QUOTA_DEFAULTS.get(tier_enum, {})

        # Determine admin token requirements
        requires_admin_for = []
        if package.declared_side_effects:
            requires_admin_for.append("side_effects")
        if inferred_tier == "T3":
            requires_admin_for.append("all_calls")

        # Generate gate warnings
        gate_warnings = []
        if not package.declared_side_effects:
            gate_warnings.append("No side effects declared - may be blocked by Policy Gate")
        if len(package.tools) > 10:
            gate_warnings.append("Large tool set - may hit quota limits faster")
        if inferred_tier in ["T2", "T3"]:
            gate_warnings.append(f"Trust Tier {inferred_tier} - requires careful approval")

        # Determine audit level
        audit_level = "enhanced" if inferred_tier in ["T2", "T3"] else "standard"

        return MCPGovernancePreview(
            package_id=package_id,
            inferred_trust_tier=inferred_tier,
            inferred_risk_level=risk_level,
            default_quota=default_quota,
            requires_admin_token_for=requires_admin_for,
            gate_warnings=gate_warnings,
            audit_level=audit_level
        )

    def search_packages(self, query: str) -> List[MCPPackage]:
        """Search packages by query string

        Searches in:
        - Package name
        - Description
        - Tags

        Args:
            query: Search query string

        Returns:
            List of matching MCPPackage objects
        """
        query_lower = query.lower()
        results = []

        for pkg in self.packages:
            if (query_lower in pkg.name.lower() or
                query_lower in pkg.description.lower() or
                any(query_lower in tag.lower() for tag in pkg.tags)):
                results.append(pkg)

        return results

    def reload(self):
        """Reload registry from disk

        Useful for refreshing the registry after external updates.
        """
        logger.info("Reloading MCP registry")
        self.packages.clear()
        self._load_registry()
