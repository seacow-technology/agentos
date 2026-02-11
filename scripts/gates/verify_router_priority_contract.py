#!/usr/bin/env python3
"""Static gate: validate router priority contract and implementation mapping."""

from __future__ import annotations

import sys

from octopusos.core.chat.router_priority_contract import (
    ENGINE_ROUTER_SPEC,
    load_router_priority_contract,
    load_router_priority_schema,
    validate_router_implementation_against_contract,
    validate_router_priority_contract,
)


def main() -> int:
    contract = load_router_priority_contract()
    schema = load_router_priority_schema()
    validate_router_priority_contract(contract, schema)
    validate_router_implementation_against_contract(ENGINE_ROUTER_SPEC, contract)
    print("router-priority-contract: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"router-priority-contract: FAIL - {exc}")
        raise
