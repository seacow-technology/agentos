from octopusos.core.chat.tool_dispatch.azure_mcp_dispatch import (
    _build_request_server_config,
    _extract_location,
)
from octopusos.core.mcp.config import MCPServerConfig


def _server_config() -> MCPServerConfig:
    return MCPServerConfig(
        id="mcp_azure_default",
        enabled=True,
        transport="stdio",
        command=["azure-mcp"],
        env={
            "OCTOPUSOS_MCP_PACKAGE_ID": "azure.mcp",
            "AZURE_SUBSCRIPTION": "default",
            "AZURE_LOCATION": "eastus",
        },
    )


def test_extract_location_from_code() -> None:
    assert _extract_location("列出 australiaeast 的 Azure VM") == "australiaeast"


def test_extract_location_from_aliases() -> None:
    assert _extract_location("查询悉尼的 Azure 虚拟机") == "australiaeast"
    assert _extract_location("show vm in singapore") == "southeastasia"
    assert _extract_location("show vm in london") == "uksouth"


def test_build_request_server_config_overrides_location_per_request() -> None:
    base = _server_config()
    request_config, inferred_location = _build_request_server_config(base, "show azure vms in sydney")

    assert inferred_location == "australiaeast"
    assert request_config.env.get("AZURE_LOCATION") == "australiaeast"
    assert base.env.get("AZURE_LOCATION") == "eastus"
