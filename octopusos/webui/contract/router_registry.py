"""Router registry for contract/runtime app mounting."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Iterable, List

from fastapi import APIRouter


@dataclass(frozen=True)
class RouterRegistration:
    module: str
    attr: str = "router"
    include_prefix: str | None = None
    optional: bool = False


# Single explicit mount list used by both runtime app and contract app.
# All API routers must be registered here.
ROUTER_REGISTRY: tuple[RouterRegistration, ...] = (
    RouterRegistration("octopusos.webui.api.admin_token"),
    RouterRegistration("octopusos.webui.api.frontdesk"),
    RouterRegistration("octopusos.webui.api.agents"),
    RouterRegistration("octopusos.webui.api.dispatch"),
    RouterRegistration("octopusos.webui.api.sessions"),
    RouterRegistration("octopusos.webui.api.work"),
    RouterRegistration("octopusos.webui.api.providers"),
    RouterRegistration("octopusos.webui.api.projects"),
    # Must be mounted before /api/tasks/{task_id} to avoid shadowing /api/tasks/items.
    RouterRegistration("octopusos.webui.api.exec_tasks"),
    RouterRegistration("octopusos.webui.api.tasks"),
    RouterRegistration("octopusos.webui.api.repos"),
    RouterRegistration("octopusos.webui.api.calls"),
    RouterRegistration("octopusos.webui.api.channels", optional=True),
    RouterRegistration("octopusos.webui.api.channels_email", optional=True),
    RouterRegistration("octopusos.webui.api.enterprise_im", optional=True),
    RouterRegistration("octopusos.webui.api.networkos", optional=True),
    RouterRegistration("octopusos.webui.api.device_binding"),
    RouterRegistration("octopusos.webui.api.mobile_chat"),
    RouterRegistration("octopusos.webui.api.compat_models"),
    RouterRegistration("octopusos.webui.api.compat_v031"),
    RouterRegistration("octopusos.webui.api.compat_extensions"),
    RouterRegistration("octopusos.webui.api.compat_content"),
    RouterRegistration("octopusos.webui.api.mcp_marketplace", optional=True),
    RouterRegistration("octopusos.webui.api.mcp_servers"),
    RouterRegistration("octopusos.webui.api.mcp_email", optional=True),
    RouterRegistration("octopusos.webui.api.mcp_email_oauth", optional=True),
    RouterRegistration("octopusos.webui.api.compat_bulk"),
    RouterRegistration("octopusos.webui.api.external_facts_replay"),
    RouterRegistration("octopusos.webui.api.external_facts_policy"),
    RouterRegistration("octopusos.webui.api.external_facts_providers"),
    RouterRegistration("octopusos.webui.api.external_facts_bindings"),
    RouterRegistration("octopusos.webui.api.external_facts_registry"),
    RouterRegistration("octopusos.webui.api.external_facts_schema"),
    RouterRegistration("octopusos.webui.api.connectors"),
    RouterRegistration("octopusos.webui.api.memory"),
    RouterRegistration("octopusos.webui.api.growth"),
    RouterRegistration("octopusos.webui.api.inbox"),
    RouterRegistration("octopusos.webui.api.work_items"),
    RouterRegistration("octopusos.webui.api.transparency"),
    RouterRegistration("octopusos.webui.api.changelog"),
    RouterRegistration("octopusos.webui.api.streams"),
    RouterRegistration("octopusos.webui.api.preview"),
    RouterRegistration("octopusos.webui.api.daemon_control"),
    RouterRegistration("octopusos.webui.api.desktop_runtime"),
    RouterRegistration("octopusos.webui.api.mode_monitoring"),
    RouterRegistration("octopusos.webui.api.voice"),
    RouterRegistration("octopusos.webui.api.voice_twilio"),
    # knowledge router defines relative paths (/sources, /jobs), so mount under /api/knowledge.
    RouterRegistration("octopusos.webui.api.knowledge", include_prefix="/api/knowledge"),
)

CONTRACT_ONLY_ROUTER_REGISTRY: tuple[RouterRegistration, ...] = (
    # OpenAPI declaration-only router to keep contract snapshot
    # aligned with runtime config endpoints.
    RouterRegistration("octopusos.webui.contract.routers.config_contract"),
)


def _load_module(module_path: str) -> ModuleType:
    return import_module(module_path)


def _get_router(mod: ModuleType, attr: str) -> APIRouter:
    router = getattr(mod, attr, None)
    if not isinstance(router, APIRouter):
        raise TypeError(f"{mod.__name__}.{attr} is not an APIRouter")
    return router


def _is_missing_split_dependency(exc: ModuleNotFoundError) -> bool:
    missing_name = (getattr(exc, "name", "") or "").strip()
    return (
        missing_name.startswith("octopusos.networkos")
        or missing_name.startswith("octopusos.communicationos")
        or missing_name == "networkos"
        or missing_name == "communicationos"
    )


def iter_registered_routers(
    include_contract_only: bool = False,
) -> Iterable[tuple[RouterRegistration, APIRouter]]:
    entries = ROUTER_REGISTRY + (CONTRACT_ONLY_ROUTER_REGISTRY if include_contract_only else ())
    for entry in entries:
        try:
            module = _load_module(entry.module)
        except ModuleNotFoundError as exc:
            if entry.optional and _is_missing_split_dependency(exc):
                continue
            raise
        yield entry, _get_router(module, entry.attr)


def mounted_module_paths() -> set[str]:
    return {entry.module for entry in ROUTER_REGISTRY}


def discover_api_router_modules() -> set[str]:
    """Discover all api modules that expose a top-level APIRouter named 'router'."""
    api_dir = Path(__file__).resolve().parents[1] / "api"
    discovered: set[str] = set()
    for py in api_dir.glob("*.py"):
        if py.name.startswith("_") or py.stem in {
            "__init__",
            "compat_state",
            "providers_errors",
            "providers_models",
            "providers_lifecycle",
            "validation",
        }:
            continue
        module_path = f"octopusos.webui.api.{py.stem}"
        try:
            mod = _load_module(module_path)
        except ModuleNotFoundError as exc:
            if _is_missing_split_dependency(exc):
                continue
            raise
        if isinstance(getattr(mod, "router", None), APIRouter):
            discovered.add(module_path)
    return discovered


def registry_consistency_errors() -> List[str]:
    discovered = discover_api_router_modules()
    mounted = mounted_module_paths()
    missing = sorted(discovered - mounted)
    extra = sorted(mounted - discovered)

    errors: List[str] = []
    if missing:
        errors.append(f"Routers discovered but not registered: {missing}")
    if extra:
        errors.append(f"Routers registered but no APIRouter discovered: {extra}")
    return errors
