"""Router Contract+ helpers: graph and route-order snapshot generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from octopusos.core.chat.router_priority_contract import (
    ENGINE_ROUTER_SPEC,
    load_router_priority_contract,
    validate_router_implementation_against_contract,
    validate_router_priority_contract,
    load_router_priority_schema,
)

REPORTS_DIR = Path("reports")
GRAPH_PATH = REPORTS_DIR / "router_graph.mmd"
SNAPSHOT_PATH = REPORTS_DIR / "router_route_order.snapshot.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_router_contract() -> Dict[str, Any]:
    """Load and validate the router priority contract."""
    contract = load_router_priority_contract()
    schema = load_router_priority_schema()
    validate_router_priority_contract(contract, schema)
    return contract


def build_router_spec() -> List[Dict[str, Any]]:
    """Build normalized implementation router spec for reporting/gates."""
    normalized: List[Dict[str, Any]] = []
    for item in ENGINE_ROUTER_SPEC:
        normalized.append(
            {
                "group_id": str(item.get("group_id") or "").strip(),
                "fn": str(item.get("fn") or "").strip(),
                "module": str(item.get("module") or "octopusos.core.chat.engine"),
                "notes": str(item.get("notes") or ""),
            }
        )
    return normalized


def _group_priority_map(contract: Dict[str, Any]) -> Dict[str, int]:
    return {str(group["group_id"]): int(group["priority"]) for group in contract.get("groups", [])}


def generate_mermaid_graph(contract: Dict[str, Any], spec: List[Dict[str, Any]]) -> str:
    """Generate deterministic Mermaid flowchart from contract + implementation spec."""
    priority_map = _group_priority_map(contract)

    ordered_groups: List[str] = []
    seen = set()
    for item in spec:
        gid = str(item.get("group_id") or "").strip()
        if gid and gid not in seen:
            seen.add(gid)
            ordered_groups.append(gid)

    lines: List[str] = [
        "flowchart TD",
    ]

    for gid in ordered_groups:
        priority = priority_map.get(gid, 9999)
        node_label = f"{gid} (P{priority})"
        lines.append(f'  {gid}["{node_label}"]')

    for index in range(len(ordered_groups) - 1):
        lines.append(f"  {ordered_groups[index]} --> {ordered_groups[index + 1]}")

    hard_rules = contract.get("hard_rules", [])
    if hard_rules:
        lines.append("  %% Hard rules")
        for rule in hard_rules:
            before = str(rule.get("before") or "")
            after = str(rule.get("after") or "")
            if before and after:
                lines.append(f"  {before} -. hard_rule .-> {after}")

    contract_hash = _sha256_text(json.dumps(contract, sort_keys=True, ensure_ascii=True))
    lines.append(f"  %% source: router_priority_contract.v1.json sha256={contract_hash[:12]}")

    return "\n".join(lines) + "\n"


def generate_route_order_snapshot(contract: Dict[str, Any], spec: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate deterministic snapshot for route execution order audit."""
    validate_router_implementation_against_contract(spec, contract)

    priority_map = _group_priority_map(contract)
    ordered_rows: List[Dict[str, Any]] = []
    for index, entry in enumerate(spec):
        group_id = str(entry.get("group_id") or "").strip()
        matcher_fn = str(entry.get("fn") or "").strip()
        module = str(entry.get("module") or "octopusos.core.chat.engine")
        ordered_rows.append(
            {
                "index": index,
                "group_id": group_id,
                "priority": int(priority_map.get(group_id, 9999)),
                "matcher_fn": matcher_fn,
                "module": module,
            }
        )

    hard_rules = [
        {"before": str(rule.get("before") or ""), "after": str(rule.get("after") or "")}
        for rule in contract.get("hard_rules", [])
    ]

    contract_hash = _sha256_text(json.dumps(contract, sort_keys=True, ensure_ascii=True))
    spec_hash = _sha256_text(json.dumps(ordered_rows, sort_keys=True, ensure_ascii=True))

    snapshot = {
        "version": 1,
        "contract_version": int(contract.get("version", 0)),
        "contract_hash": contract_hash,
        "spec_hash": spec_hash,
        "ordered_groups": ordered_rows,
        "hard_rules": hard_rules,
    }
    return snapshot


def write_router_contract_plus_reports() -> Dict[str, Any]:
    """Generate and persist graph + snapshot into reports directory."""
    contract = load_router_contract()
    spec = build_router_spec()
    mermaid = generate_mermaid_graph(contract, spec)
    snapshot = generate_route_order_snapshot(contract, spec)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(mermaid, encoding="utf-8")
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "graph_path": str(GRAPH_PATH),
        "snapshot_path": str(SNAPSHOT_PATH),
        "contract_hash": snapshot["contract_hash"],
        "spec_hash": snapshot["spec_hash"],
    }
