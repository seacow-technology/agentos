"""Router priority contract validation helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Set


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "router_priority_contract.v1.schema.json"
CONTRACT_PATH = Path(__file__).with_name("router_priority_contract.v1.json")

ENGINE_ROUTER_SPEC: List[Dict[str, Any]] = [
    {"group_id": "tool_intent", "fn": "detect_tool_intent"},
    {"group_id": "company_research", "fn": "parse_company_research_request"},
    {"group_id": "dbops_skill_dispatch", "fn": "try_handle_dbops_via_skillos"},
    {"group_id": "aws_azure_fastpath", "fn": "try_handle_aws_via_mcp"},
    {"group_id": "aws_azure_fastpath", "fn": "try_handle_azure_via_mcp"},
    {"group_id": "external_facts_stock", "fn": "detect_stock_query"},
    {"group_id": "external_facts_any", "fn": "resolve_external_fact_request"},
]


class RouterPriorityContractError(RuntimeError):
    pass


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_router_priority_contract() -> Dict[str, Any]:
    return _load_json(CONTRACT_PATH)


@lru_cache(maxsize=1)
def load_router_priority_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_PATH)


def validate_router_priority_contract(contract: Dict[str, Any], schema: Dict[str, Any]) -> None:
    try:
        import jsonschema
        jsonschema.validate(instance=contract, schema=schema)
    except Exception as exc:
        # Keep runtime robust even if jsonschema is missing in lightweight envs.
        if exc.__class__.__name__ != "ModuleNotFoundError":
            raise RouterPriorityContractError(f"contract schema validation failed: {exc}") from exc

    group_ids = [g["group_id"] for g in contract.get("groups", [])]
    duplicates = sorted({gid for gid in group_ids if group_ids.count(gid) > 1})
    if duplicates:
        raise RouterPriorityContractError(f"duplicate group_id in contract: {duplicates}")

    group_set = set(group_ids)
    for rule in contract.get("hard_rules", []):
        before = str(rule.get("before") or "")
        after = str(rule.get("after") or "")
        if before not in group_set or after not in group_set:
            raise RouterPriorityContractError(
                f"hard_rules reference unknown group: before={before}, after={after}"
            )

    stopwords = {str(v).lower() for v in contract.get("reserved_tokens", {}).get("stock_symbol_stopwords", [])}
    if "echo" not in stopwords:
        raise RouterPriorityContractError("reserved_tokens.stock_symbol_stopwords must include 'echo'")


def validate_router_implementation_against_contract(
    engine_router_spec: List[Dict[str, Any]],
    contract: Dict[str, Any],
) -> None:
    groups = contract.get("groups", [])
    priority_map = {str(g["group_id"]): int(g["priority"]) for g in groups}
    required_groups = {str(g["group_id"]) for g in groups if bool(g.get("required"))}

    present_groups = [str(item.get("group_id") or "") for item in engine_router_spec]
    present_set = set(present_groups)

    missing_required = sorted(required_groups - present_set)
    if missing_required:
        raise RouterPriorityContractError(f"missing required router groups: {missing_required}")

    ordered_unique: List[str] = []
    seen: Set[str] = set()
    for gid in present_groups:
        if gid and gid not in seen:
            ordered_unique.append(gid)
            seen.add(gid)

    priorities = [priority_map.get(gid, 9999) for gid in ordered_unique]
    if priorities != sorted(priorities):
        paired = list(zip(ordered_unique, priorities))
        raise RouterPriorityContractError(
            "router implementation order does not follow contract priority: " + str(paired)
        )

    position = {gid: idx for idx, gid in enumerate(ordered_unique)}
    for rule in contract.get("hard_rules", []):
        before = str(rule["before"])
        after = str(rule["after"])
        if position.get(before, 10**6) >= position.get(after, -1):
            raise RouterPriorityContractError(
                f"hard rule violated: '{before}' must be before '{after}', order={ordered_unique}"
            )


def validate_router_priority_contract_runtime() -> Dict[str, Any]:
    contract = load_router_priority_contract()
    schema = load_router_priority_schema()
    validate_router_priority_contract(contract, schema)
    validate_router_implementation_against_contract(ENGINE_ROUTER_SPEC, contract)
    return contract


@lru_cache(maxsize=1)
def reserved_stock_symbol_stopwords() -> List[str]:
    contract = load_router_priority_contract()
    values = contract.get("reserved_tokens", {}).get("stock_symbol_stopwords", [])
    return [str(v).lower() for v in values if str(v).strip()]
