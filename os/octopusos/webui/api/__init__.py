"""WebUI API package.

Keep package import side effects minimal.
Historically this module eagerly imported many router modules, which could trigger
database access during import-time and crash startup before init had a chance to run.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_ROUTER_EXPORTS = {
    "frontdesk_router": ("octopusos.webui.api.frontdesk", "router"),
    "agents_router": ("octopusos.webui.api.agents", "router"),
    "dispatch_router": ("octopusos.webui.api.dispatch", "router"),
    "sessions_router": ("octopusos.webui.api.sessions", "router"),
    "external_facts_schema_router": ("octopusos.webui.api.external_facts_schema", "router"),
    "external_facts_providers_router": ("octopusos.webui.api.external_facts_providers", "router"),
    "external_facts_bindings_router": ("octopusos.webui.api.external_facts_bindings", "router"),
    "external_facts_registry_router": ("octopusos.webui.api.external_facts_registry", "router"),
    "connectors_router": ("octopusos.webui.api.connectors", "router"),
    "calls_router": ("octopusos.webui.api.calls", "router"),
    "tasks_router": ("octopusos.webui.api.tasks", "router"),
    "repos_router": ("octopusos.webui.api.repos", "router"),
    "growth_router": ("octopusos.webui.api.growth", "router"),
    "inbox_router": ("octopusos.webui.api.inbox", "router"),
}

_MODULE_EXPORTS = {
    "mode_monitoring": "octopusos.webui.api.mode_monitoring",
    "knowledge": "octopusos.webui.api.knowledge",
    "voice": "octopusos.webui.api.voice",
    "voice_twilio": "octopusos.webui.api.voice_twilio",
    "providers_errors": "octopusos.webui.api.providers_errors",
    "providers_models": "octopusos.webui.api.providers_models",
    "providers_lifecycle": "octopusos.webui.api.providers_lifecycle",
}

__all__ = list(_ROUTER_EXPORTS.keys()) + list(_MODULE_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _ROUTER_EXPORTS:
        module_name, attr_name = _ROUTER_EXPORTS[name]
        module = import_module(module_name)
        return getattr(module, attr_name)
    if name in _MODULE_EXPORTS:
        return import_module(_MODULE_EXPORTS[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
