"""Command handlers for different command categories."""

from .history_handlers import register_history_commands
from .kb_handlers import register_kb_commands
from .mem_handlers import register_memory_commands

__all__ = [
    "register_kb_commands",
    "register_memory_commands",
    "register_history_commands",
]
