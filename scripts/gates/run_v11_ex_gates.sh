#!/bin/bash
# 运行所有 Phase 2 Executor Gates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "========================================"
echo "Running All Phase 2 Executor Gates"
echo "========================================"
echo ""

TOTAL_GATES=8
PASSED_GATES=0

# Gate A
echo "[1/8] Running EX Gate A - Existence..."
if uv run python scripts/gates/v11_ex_gate_a_existence.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate B
echo "[2/8] Running EX Gate B - Schema Validation..."
if uv run python scripts/gates/v11_ex_gate_b_schema_validation.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate C
echo "[3/8] Running EX Gate C - Negative Tests..."
if uv run python scripts/gates/v11_ex_gate_c_negative_tests.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate D
echo "[4/8] Running EX Gate D - Static Scan..."
if uv run python scripts/gates/v11_ex_gate_d_static_scan.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate E
echo "[5/8] Running EX Gate E - Isolation..."
if uv run python scripts/gates/v11_ex_gate_e_isolation.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate F
echo "[6/8] Running EX Gate F - Snapshot..."
if uv run python scripts/gates/v11_ex_gate_f_snapshot.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate G
echo "[7/8] Running EX Gate G - Lock..."
if uv run python scripts/gates/v11_ex_gate_g_lock.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# Gate H
echo "[8/8] Running EX Gate H - Approval..."
if uv run python scripts/gates/v11_ex_gate_h_approval.py; then
    PASSED_GATES=$((PASSED_GATES + 1))
fi
echo ""

# 总结
echo "========================================"
echo "Phase 2 Executor Gates Summary"
echo "========================================"
echo "Passed: $PASSED_GATES / $TOTAL_GATES"

if [ $PASSED_GATES -eq $TOTAL_GATES ]; then
    echo "✅ ALL GATES PASSED"
    exit 0
else
    echo "❌ SOME GATES FAILED"
    exit 1
fi
