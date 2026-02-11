#!/usr/bin/env python3
"""Hard gate: local echo MCP server must support list_tools + call_tool."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from octopusos.core.mcp.client import MCPClient
from octopusos.core.mcp.config import MCPServerConfig


async def _run() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "servers" / "echo-math-mcp" / "index.js"
    if not server_path.exists():
        raise RuntimeError(f"echo server not found: {server_path}")

    cfg = MCPServerConfig(
        id="echo-smoke",
        enabled=True,
        transport="stdio",
        command=["node", str(server_path)],
        allow_tools=[],
        deny_side_effect_tags=[],
        env={"OCTOPUSOS_MCP_PACKAGE_ID": "octopusos.official/echo-math"},
        timeout_ms=30000,
    )

    client = MCPClient(cfg)
    try:
        await client.connect()
        tools = await client.list_tools()
        tool_names = [str(t.get("name") or "") for t in tools]
        if "echo" not in tool_names:
            raise RuntimeError(f"echo tool missing, tools={tool_names}")
        echo_schema = next((t for t in tools if str(t.get("name") or "") == "echo"), {})
        input_schema = echo_schema.get("inputSchema") if isinstance(echo_schema, dict) else {}
        properties = input_schema.get("properties") if isinstance(input_schema, dict) else {}
        required = input_schema.get("required") if isinstance(input_schema, dict) else []
        if "text" in properties:
            args = {"text": "echo-smoke"}
        elif "message" in properties:
            args = {"message": "echo-smoke"}
        elif isinstance(required, list) and len(required) == 1:
            args = {str(required[0]): "echo-smoke"}
        else:
            args = {"text": "echo-smoke"}
        result = await client.call_tool("echo", args)
        content = str(result)
        if "echo-smoke" not in content:
            raise RuntimeError(f"echo result mismatch: {result}")
        return {
            "ok": True,
            "tool_names": tool_names,
            "echo_result": result,
            "server": str(server_path),
        }
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def main() -> int:
    report = asyncio.run(_run())
    out = Path("reports/echo_mcp_smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
