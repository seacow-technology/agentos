"""Tool dispatch helpers for chat engine."""

from octopusos.core.chat.tool_dispatch.aws_mcp_dispatch import try_handle_aws_via_mcp
from octopusos.core.chat.tool_dispatch.azure_mcp_dispatch import try_handle_azure_via_mcp
from octopusos.core.chat.tool_dispatch.dbops_skill_dispatch import try_handle_dbops_via_skillos

__all__ = ["try_handle_aws_via_mcp", "try_handle_azure_via_mcp", "try_handle_dbops_via_skillos"]
