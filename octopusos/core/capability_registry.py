"""
Capability Registry - Unified capability and runtime preset management

This module provides a centralized registry for system capabilities (Code Assets, Preview, etc.)
and their associated runtime presets (e.g., three-webgl-umd, chartjs-umd).

Key Features:
- Capability metadata with risk levels and audit requirements
- Runtime presets with dependency management
- Auto-injection rules for smart dependency loading
- CSP and sandbox policy configuration

Design Philosophy:
- Declarative: All capabilities and presets defined as data structures
- Extensible: Easy to add new capabilities and presets
- Auditable: Built-in audit event tracking
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import re


class CapabilityKind(Enum):
    """Capability categories"""
    CODE_ASSET = "code_asset"  # Snippet CRUD operations
    PREVIEW = "preview"  # Preview runtime environment
    TASK_MATERIALIZATION = "task_materialization"  # Snippet → Task conversion


class RiskLevel(Enum):
    """Risk level for capability operations"""
    LOW = "low"  # Read-only, no side effects
    MEDIUM = "medium"  # Modifies data but isolated
    HIGH = "high"  # Can execute code or affect system


@dataclass
class RuntimeDependency:
    """External dependency for preview runtime"""
    id: str  # Unique identifier
    url: str  # CDN URL
    type: str  # script | style
    integrity: Optional[str] = None  # SRI hash for security
    order: int = 0  # Load order (lower = earlier)
    condition: Optional[str] = None  # Auto-inject condition (keyword in code)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "id": self.id,
            "url": self.url,
            "type": self.type,
            "order": self.order,
        }
        if self.integrity:
            result["integrity"] = self.integrity
        if self.condition:
            result["condition"] = self.condition
        return result


@dataclass
class RuntimePreset:
    """
    Runtime preset definition for Preview capability

    A preset defines a complete runtime environment with:
    - Core dependencies (always loaded)
    - Optional dependencies (loaded on-demand based on code content)
    - Security policies (CSP, sandbox)
    """
    id: str  # e.g., "three-webgl-umd"
    name: str  # Human-readable name
    description: str  # What this preset is for
    dependencies: List[RuntimeDependency]  # All available dependencies
    sandbox_policy: Dict[str, Any]  # iframe sandbox attributes
    auto_inject_rules: Dict[str, List[str]] = field(default_factory=dict)  # {pattern: [dep_ids]}
    csp_rules: Optional[str] = None  # Content Security Policy

    def get_core_deps(self) -> List[RuntimeDependency]:
        """Get core dependencies (no condition)"""
        return [dep for dep in self.dependencies if dep.condition is None]

    def get_optional_deps(self) -> List[RuntimeDependency]:
        """Get optional dependencies (with condition)"""
        return [dep for dep in self.dependencies if dep.condition is not None]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "sandbox_policy": self.sandbox_policy,
            "auto_inject_rules": self.auto_inject_rules,
            "csp_rules": self.csp_rules,
        }


@dataclass
class Capability:
    """
    Base capability definition

    A capability represents a system feature with specific security and audit requirements.
    Examples: Snippet CRUD, Preview Runtime, Task Materialization
    """
    capability_id: str  # Unique identifier
    kind: CapabilityKind  # Capability category
    name: str  # Human-readable name
    description: str  # What this capability does
    risk_level: RiskLevel  # Security risk assessment
    requires_admin_token: bool  # Whether admin privileges required
    audit_events: List[str]  # Event types to audit
    presets: Optional[List[RuntimePreset]] = None  # For Preview capability

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "capability_id": self.capability_id,
            "kind": self.kind.value,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "requires_admin_token": self.requires_admin_token,
            "audit_events": self.audit_events,
        }
        if self.presets:
            result["presets"] = [preset.to_dict() for preset in self.presets]
        return result


class CapabilityRegistry:
    """
    Capability Registry - Central management for system capabilities

    Usage:
        registry = CapabilityRegistry()
        capability = registry.get("preview")
        preset = registry.get_preset("preview", "three-webgl-umd")
        deps = registry.detect_required_deps(preset, code)
    """

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default capabilities and presets"""
        # Register Code Asset capability
        self.register(Capability(
            capability_id="code_asset",
            kind=CapabilityKind.CODE_ASSET,
            name="Code Asset Management",
            description="CRUD operations for code snippets library",
            risk_level=RiskLevel.MEDIUM,
            requires_admin_token=False,
            audit_events=[
                "SNIPPET_CREATED",
                "SNIPPET_UPDATED",
                "SNIPPET_DELETED",
                "SNIPPET_USED_IN_TASK",
            ],
        ))

        # Register Task Materialization capability
        self.register(Capability(
            capability_id="task_materialization",
            kind=CapabilityKind.TASK_MATERIALIZATION,
            name="Task Materialization",
            description="Convert code snippets to executable tasks",
            risk_level=RiskLevel.HIGH,
            requires_admin_token=False,
            audit_events=[
                "TASK_MATERIALIZED_FROM_SNIPPET",
            ],
        ))

        # Register Preview capability with presets
        self.register(Capability(
            capability_id="preview",
            kind=CapabilityKind.PREVIEW,
            name="Preview Runtime",
            description="Secure iframe-based code preview with runtime presets",
            risk_level=RiskLevel.MEDIUM,
            requires_admin_token=False,
            audit_events=[
                "PREVIEW_SESSION_CREATED",
                "PREVIEW_SESSION_OPENED",
                "PREVIEW_SESSION_EXPIRED",
                "PREVIEW_RUNTIME_SELECTED",
                "PREVIEW_DEP_INJECTED",
            ],
            presets=[
                self._create_html_basic_preset(),
                self._create_three_webgl_preset(),
                self._create_chartjs_preset(),
                self._create_d3_preset(),
            ],
        ))

    def _create_html_basic_preset(self) -> RuntimePreset:
        """Create html-basic preset - pure HTML/CSS/JS with minimal restrictions"""
        return RuntimePreset(
            id="html-basic",
            name="HTML Basic",
            description="Pure HTML/CSS/JS environment with no external dependencies",
            dependencies=[],  # No injected dependencies
            sandbox_policy={
                "allow": [
                    "scripts",  # Allow JavaScript execution
                ],
                "csp": "default-src 'self' 'unsafe-inline' 'unsafe-eval';",
            },
            auto_inject_rules={},
            csp_rules="default-src 'self' 'unsafe-inline' 'unsafe-eval';",
        )

    def _create_three_webgl_preset(self) -> RuntimePreset:
        """
        Create three-webgl-umd preset - Three.js WebGL environment

        This is the P0 priority preset with smart dependency injection:
        - Core Three.js library always loaded
        - Optional modules loaded based on code content
        """
        return RuntimePreset(
            id="three-webgl-umd",
            name="Three.js WebGL (UMD)",
            description="Three.js r169 with WebGL support and optional loaders",
            dependencies=[
                # Core Three.js (always loaded)
                RuntimeDependency(
                    id="three-core",
                    url="https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.min.js",
                    type="script",
                    order=0,
                ),
                # Optional: FontLoader (loaded if code mentions FontLoader)
                RuntimeDependency(
                    id="three-fontloader",
                    url="https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/loaders/FontLoader.js",
                    type="script",
                    order=1,
                    condition="FontLoader",
                ),
                # Optional: OrbitControls
                RuntimeDependency(
                    id="three-orbit-controls",
                    url="https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/controls/OrbitControls.js",
                    type="script",
                    order=1,
                    condition="OrbitControls",
                ),
                # Optional: GLTFLoader
                RuntimeDependency(
                    id="three-gltf-loader",
                    url="https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/loaders/GLTFLoader.js",
                    type="script",
                    order=1,
                    condition="GLTFLoader",
                ),
                # Optional: TextGeometry
                RuntimeDependency(
                    id="three-text-geometry",
                    url="https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/geometries/TextGeometry.js",
                    type="script",
                    order=2,
                    condition="TextGeometry",
                ),
            ],
            sandbox_policy={
                "allow": [
                    "scripts",
                    "same-origin",  # Required for WebGL
                ],
                "csp": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline';",
            },
            auto_inject_rules={
                # Pattern: [dep_ids to inject]
                "FontLoader": ["three-fontloader"],
                "OrbitControls": ["three-orbit-controls"],
                "GLTFLoader": ["three-gltf-loader"],
                "TextGeometry": ["three-text-geometry"],
            },
            csp_rules="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline';",
        )

    def _create_chartjs_preset(self) -> RuntimePreset:
        """Create chartjs-umd preset - Chart.js environment"""
        return RuntimePreset(
            id="chartjs-umd",
            name="Chart.js (UMD)",
            description="Chart.js library for data visualization",
            dependencies=[
                RuntimeDependency(
                    id="chartjs-core",
                    url="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js",
                    type="script",
                    order=0,
                ),
            ],
            sandbox_policy={
                "allow": [
                    "scripts",
                ],
                "csp": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';",
            },
            auto_inject_rules={},
            csp_rules="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';",
        )

    def _create_d3_preset(self) -> RuntimePreset:
        """Create d3-umd preset - D3.js environment"""
        return RuntimePreset(
            id="d3-umd",
            name="D3.js (UMD)",
            description="D3.js library for data-driven visualizations",
            dependencies=[
                RuntimeDependency(
                    id="d3-core",
                    url="https://cdn.jsdelivr.net/npm/d3@7.8.5/dist/d3.min.js",
                    type="script",
                    order=0,
                ),
            ],
            sandbox_policy={
                "allow": [
                    "scripts",
                ],
                "csp": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';",
            },
            auto_inject_rules={},
            csp_rules="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';",
        )

    def register(self, capability: Capability):
        """
        Register a capability

        Args:
            capability: Capability to register

        Raises:
            ValueError: If capability_id already exists
        """
        if capability.capability_id in self._capabilities:
            raise ValueError(f"Capability already registered: {capability.capability_id}")

        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> Optional[Capability]:
        """
        Get capability by ID

        Args:
            capability_id: Capability identifier

        Returns:
            Capability if found, None otherwise
        """
        return self._capabilities.get(capability_id)

    def list_all(self) -> List[Capability]:
        """Get all registered capabilities"""
        return list(self._capabilities.values())

    def get_preset(self, capability_id: str, preset_id: str) -> Optional[RuntimePreset]:
        """
        Get preset for a capability

        Args:
            capability_id: Capability identifier
            preset_id: Preset identifier

        Returns:
            RuntimePreset if found, None otherwise
        """
        capability = self.get(capability_id)
        if not capability or not capability.presets:
            return None

        for preset in capability.presets:
            if preset.id == preset_id:
                return preset

        return None

    def detect_required_deps(self, preset: RuntimePreset, code: str) -> List[RuntimeDependency]:
        """
        Detect which dependencies to inject based on code content

        This implements smart dependency loading:
        1. Always include core dependencies (no condition)
        2. Scan code for keywords matching auto_inject_rules
        3. Include optional dependencies that match

        Args:
            preset: Runtime preset
            code: User code to analyze

        Returns:
            List of dependencies to inject, sorted by order

        Example:
            >>> preset = registry.get_preset("preview", "three-webgl-umd")
            >>> code = "const controls = new THREE.OrbitControls(camera);"
            >>> deps = registry.detect_required_deps(preset, code)
            >>> # Returns: [three-core, three-orbit-controls]
        """
        required_deps = []

        # Step 1: Add all core dependencies (always loaded)
        required_deps.extend(preset.get_core_deps())

        # Step 2: Detect optional dependencies based on code content
        for pattern, dep_ids in preset.auto_inject_rules.items():
            # Check if pattern appears in code
            if re.search(r'\b' + re.escape(pattern) + r'\b', code, re.IGNORECASE):
                # Find and add matching dependencies
                for dep in preset.dependencies:
                    if dep.id in dep_ids and dep not in required_deps:
                        required_deps.append(dep)

        # Step 3: Sort by order
        required_deps.sort(key=lambda d: d.order)

        return required_deps


# Global registry instance (singleton)
_registry_instance: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """
    Get the global capability registry instance

    Returns:
        Global CapabilityRegistry singleton
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = CapabilityRegistry()
    return _registry_instance
