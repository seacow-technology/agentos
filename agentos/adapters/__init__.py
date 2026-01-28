"""Adapters module"""

from agentos.adapters.base import BaseAdapter
from agentos.adapters.dotnet import DotnetAdapter
from agentos.adapters.vite_react import ViteReactAdapter

# Registry of all adapters
_ADAPTERS = [
    ViteReactAdapter(),
    DotnetAdapter(),
]


def get_adapters() -> list[BaseAdapter]:
    """Get list of all registered adapters"""
    return _ADAPTERS


__all__ = ["BaseAdapter", "ViteReactAdapter", "DotnetAdapter", "get_adapters"]
