#!/usr/bin/env bash
# Run all Phase 2 Executor Gates (v0.12)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔒 Running Phase 2 Executor Gates (v0.12)"
echo "=========================================="

# G-EX-DAG: DAG Scheduler
echo ""
python3 "$SCRIPT_DIR/v12_ex_gate_dag.py"

# G-EX-SANDBOX: Container Sandbox
echo ""
python3 "$SCRIPT_DIR/v12_ex_gate_sandbox.py"

# G-EX-ALLOWLIST: Allowlist Extensions
echo ""
python3 "$SCRIPT_DIR/v12_ex_gate_allowlist.py"

echo ""
echo "=========================================="
echo "✅ All Phase 2 Gates PASSED"
