from octopusos.core.chat.tool_dispatch import azure_mcp_dispatch
from octopusos.core.mcp.config import MCPServerConfig


class _FakeManager:
    def __init__(self, servers):
        self._servers = servers

    def get_enabled_servers(self):
        return self._servers


def _azure_server() -> MCPServerConfig:
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


def test_requires_location_before_any_azure_operation(monkeypatch) -> None:
    monkeypatch.setattr(azure_mcp_dispatch, "MCPConfigManager", lambda: _FakeManager([_azure_server()]))

    called = {"value": False}

    def _never_call(_):
        called["value"] = True
        return {"ok": True}

    monkeypatch.setattr(azure_mcp_dispatch, "_run_async", _never_call)

    result = azure_mcp_dispatch.try_handle_azure_via_mcp("列出我的 Azure VM")
    assert result is not None
    assert result.get("handled") is True
    assert result.get("blocked") is True
    assert result.get("needs_location") is True
    assert called["value"] is False
