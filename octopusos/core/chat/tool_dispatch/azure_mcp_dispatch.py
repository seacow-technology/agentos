"""Azure MCP dispatch for chat queries."""

from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from octopusos.core.mcp.client import MCPClient
from octopusos.core.mcp.config import MCPConfigManager, MCPServerConfig

AZURE_KEYWORDS = (
    "azure",
    "az",
    "vm",
    "vms",
    "virtual machine",
    "resource group",
    "subscription",
    "cost",
    "billing",
    "usage",
    "账单",
    "费用",
    "成本",
    "虚拟机",
)

AZURE_LOCATION_CODE_RE = re.compile(r"\b[a-z]+(?:[a-z0-9]+)?\d?\b", re.IGNORECASE)
AZURE_LOCATION_ALIASES: Dict[str, str] = {
    "sydney": "australiaeast",
    "悉尼": "australiaeast",
    "singapore": "southeastasia",
    "新加坡": "southeastasia",
    "tokyo": "japaneast",
    "东京": "japaneast",
    "japan": "japaneast",
    "frankfurt": "germanywestcentral",
    "法兰克福": "germanywestcentral",
    "london": "uksouth",
    "伦敦": "uksouth",
    "virginia": "eastus",
    "us east": "eastus",
    "east us": "eastus",
    "west us": "westus",
}
AZURE_LOCATION_PREFIXES = (
    "eastus",
    "westus",
    "centralus",
    "northcentralus",
    "southcentralus",
    "westeurope",
    "northeurope",
    "uksouth",
    "ukwest",
    "australia",
    "japan",
    "korea",
    "canada",
    "southeastasia",
    "eastasia",
    "germany",
    "switzerland",
    "france",
    "norway",
    "sweden",
    "italy",
    "spain",
    "qatar",
    "uae",
    "brazil",
    "southafrica",
)

INTENT_TOOL_CANDIDATES: Dict[str, List[str]] = {
    "vm_instances": [
        "azure_vm_list_instances",
        "azure_compute_list_virtual_machines",
        "azure_vm_list",
        "list_virtual_machines",
        "vm_list",
    ],
    "vm_status_health": [
        "azure_vm_list_instance_status",
        "azure_compute_list_virtual_machines_instance_view",
        "azure_vm_get_status",
        "vm_instance_view",
    ],
    "cost_usage": [
        "azure_cost_get_cost_and_usage",
        "azure_cost_management_query_usage",
        "azure_billing_get_usage",
    ],
    "cost_explain": [
        "azure_cost_get_cost_breakdown",
        "azure_cost_management_query_breakdown",
        "azure_billing_get_cost_breakdown",
    ],
    "service_enablement": [
        "azure_resource_list_providers",
        "azure_subscription_list_locations",
        "azure_subscription_get_capabilities",
    ],
}
GENERIC_QUERY_TOOLS = ("query", "ask", "natural_language_query", "prompt", "chat", "azure_query", "suggest_azure_commands")


def _is_english_query(text: str) -> bool:
    source = text or ""
    latin = len(re.findall(r"[A-Za-z]", source))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", source))
    if cjk > 0:
        return False
    return latin >= 6


def _t(is_en: bool, zh: str, en: str) -> str:
    return en if is_en else zh


def _is_azure_query(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in AZURE_KEYWORDS)


def _is_high_risk_azure_intent(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("create", "delete", "remove", "terminate", "restart", "stop", "start", "创建", "删除", "重启", "停止", "启动"))


def _find_enabled_azure_server(manager: MCPConfigManager) -> Optional[MCPServerConfig]:
    for server in manager.get_enabled_servers():
        if (server.env or {}).get("OCTOPUSOS_MCP_PACKAGE_ID") == "azure.mcp":
            return server
    return None


def _extract_location(user_text: str) -> Optional[str]:
    text = user_text or ""
    lowered = text.lower()

    for alias in sorted(AZURE_LOCATION_ALIASES.keys(), key=len, reverse=True):
        if alias in lowered:
            return AZURE_LOCATION_ALIASES[alias]

    tokens = re.findall(r"[a-z0-9]+", lowered)
    for token in tokens:
        if any(token.startswith(prefix) for prefix in AZURE_LOCATION_PREFIXES):
            return token

    for m in AZURE_LOCATION_CODE_RE.finditer(lowered):
        token = m.group(0)
        if any(token.startswith(prefix) for prefix in AZURE_LOCATION_PREFIXES):
            return token
    return None


def _build_request_server_config(
    server_config: MCPServerConfig,
    user_text: str,
) -> Tuple[MCPServerConfig, Optional[str]]:
    inferred_location = _extract_location(user_text)
    if not inferred_location:
        return server_config, None

    request_config = server_config.model_copy(deep=True)
    request_env = dict(request_config.env or {})
    request_env["AZURE_LOCATION"] = inferred_location
    request_config.env = request_env
    return request_config, inferred_location


def _query_requires_location(user_text: str) -> bool:
    lowered = (user_text or "").lower()
    return any(token in lowered for token in ("vm", "virtual machine", "instance", "cost", "billing", "usage", "虚拟机", "成本", "费用", "账单"))


def _pick_tool_and_args(user_text: str, tools: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    lowered = user_text.lower()
    names = {str(tool.get("name")): tool for tool in tools if tool.get("name")}

    def _first(candidates: List[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in names:
                return candidate
        return None

    def _query_tool() -> Optional[str]:
        return _first(list(GENERIC_QUERY_TOOLS))

    def _intent_or_query(candidates: List[str]) -> Tuple[Optional[str], Dict[str, Any]]:
        picked = _first(candidates)
        if picked:
            return picked, {}
        query_tool = _query_tool()
        if query_tool:
            return query_tool, {"query": user_text}
        return None, {}

    if any(token in lowered for token in ("cost", "billing", "费用", "成本", "账单")):
        if any(token in lowered for token in ("explain", "breakdown", "构成", "解释")):
            return _intent_or_query(INTENT_TOOL_CANDIDATES["cost_explain"])
        return _intent_or_query(INTENT_TOOL_CANDIDATES["cost_usage"])
    if any(token in lowered for token in ("service", "provider", "开通", "可用区域")):
        return _intent_or_query(INTENT_TOOL_CANDIDATES["service_enablement"])
    if any(token in lowered for token in ("health", "status", "状态", "健康")):
        return _intent_or_query(INTENT_TOOL_CANDIDATES["vm_status_health"])
    if any(token in lowered for token in ("vm", "virtual machine", "instance", "虚拟机", "实例")):
        return _intent_or_query(INTENT_TOOL_CANDIDATES["vm_instances"])

    query_tool = _query_tool()
    if query_tool:
        return query_tool, {"query": user_text}

    return None, {}


def _build_direct_cli_commands(user_text: str) -> List[str]:
    lowered = (user_text or "").lower()
    commands: List[str] = []

    wants_vm = any(k in lowered for k in ("vm", "virtual machine", "instance", "虚拟机", "实例"))
    wants_status = any(k in lowered for k in ("status", "health", "状态", "健康"))

    if wants_vm and wants_status:
        commands.append("az vm list -d --output json")
        return commands
    if wants_vm:
        commands.append("az vm list --show-details --output json")
        return commands
    if any(k in lowered for k in ("cost", "billing", "费用", "成本", "账单", "usage", "用量")):
        commands.append("az consumption usage list --output json")
        return commands
    if any(k in lowered for k in ("service", "provider", "开通")):
        commands.append("az provider list --query \"[].namespace\" --output json")
        return commands
    return commands


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


async def _call_server_async(server_config: MCPServerConfig, user_text: str) -> Dict[str, Any]:
    client = MCPClient(server_config)
    await client.connect()
    try:
        tools = await client.list_tools()
        selected_name, args = _pick_tool_and_args(user_text, tools)
        if not selected_name:
            return {
                "ok": False,
                "error": "NO_MATCHED_TOOL",
                "tools": [str(tool.get("name", "")) for tool in tools][:20],
            }

        has_call_azure = any(str(tool.get("name")) == "call_azure" for tool in tools)
        if selected_name == "suggest_azure_commands" and has_call_azure:
            commands = _build_direct_cli_commands(user_text)
            if commands:
                exec_result = await client.call_tool("call_azure", {"cli_command": commands[0], "max_results": 50})
                return {
                    "ok": True,
                    "tool": "call_azure",
                    "mode": "direct_template",
                    "suggested_cli_command": commands[0],
                    "result": exec_result,
                }

        result = await client.call_tool(selected_name, args)
        return {"ok": True, "tool": selected_name, "result": result}
    finally:
        await client.disconnect()


def _extract_call_azure_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for chunk in content:
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        try:
            outer = json.loads(text)
        except Exception:
            continue
        if not isinstance(outer, dict):
            continue
        response = outer.get("response")
        if not isinstance(response, dict):
            continue
        json_str = response.get("json")
        if isinstance(json_str, str) and json_str.strip():
            try:
                body = json.loads(json_str)
            except Exception:
                body = None
        else:
            body = None
        return {"outer": outer, "response": response, "body": body}
    return None


def _summarize_result(payload: Dict[str, Any], user_text: str = "") -> str:
    is_en = _is_english_query(user_text)
    if not payload.get("ok"):
        tools = payload.get("tools") or []
        return _t(
            is_en,
            f"Azure MCP 无法匹配到可执行工具。可用工具: {', '.join(tools) if tools else 'none'}",
            f"Azure MCP cannot match an executable tool. Available tools: {', '.join(tools) if tools else 'none'}",
        )

    tool = payload.get("tool")
    result = payload.get("result")
    location = payload.get("location")
    location_hint = f" (location={location})" if location else ""
    if tool == "call_azure":
        parsed = _extract_call_azure_payload(result if isinstance(result, dict) else {})
        if parsed and parsed.get("body") is not None:
            return f"Azure MCP `{tool}` result{location_hint}:\n{parsed['body']}"
    return f"Azure MCP `{tool}` result{location_hint}:\n{result}"


def try_handle_azure_via_mcp(user_text: str, session_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    del session_context  # reserved for future pending-action flows.

    if not _is_azure_query(user_text):
        return None

    manager = MCPConfigManager()
    server = _find_enabled_azure_server(manager)
    if not server:
        return None

    is_en = _is_english_query(user_text)
    if _is_high_risk_azure_intent(user_text):
        return {
            "handled": True,
            "blocked": True,
            "message": _t(
                is_en,
                "检测到高风险 Azure 写操作意图（create/update/delete/start/stop/restart）。Chat 直连执行已被治理拦截。",
                "Detected high-risk Azure write intent (create/update/delete/start/stop/restart). Direct chat execution is blocked by guardrails.",
            ),
        }

    request_server, inferred_location = _build_request_server_config(server, user_text)
    if not inferred_location and _query_requires_location(user_text):
        return {
            "handled": True,
            "blocked": True,
            "needs_location": True,
            "message": _t(
                is_en,
                "请先明确 Azure location（例如 australiaeast、southeastasia、eastus），再执行实例/账单分析。",
                "Please provide an Azure location first (for example: australiaeast, southeastasia, eastus) before VM or billing analysis.",
            ),
        }

    try:
        payload = _run_async(_call_server_async(request_server, user_text))
    except Exception as exc:
        return {
            "handled": True,
            "blocked": False,
            "message": _t(
                is_en,
                f"Azure MCP 调用异常: {str(exc)[:500]}",
                f"Azure MCP execution error: {str(exc)[:500]}",
            ),
        }

    payload["location"] = inferred_location
    summary = _summarize_result(payload, user_text)
    return {
        "handled": True,
        "blocked": bool(not payload.get("ok")),
        "message": summary,
        "raw": payload,
    }

