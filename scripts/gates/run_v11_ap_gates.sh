#!/bin/bash
# Run all Phase 1 AnswerPack Gates

set -e

echo "================================================================"
echo "Running All v11 AnswerPack Gates (Phase 1)"
echo "================================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXIT_CODE=0

# Gate A: Existence
echo "--- Running AP Gate A: Existence ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_a_existence.py"; then
    echo "✓ Gate A PASSED"
else
    echo "✗ Gate A FAILED"
    EXIT_CODE=1
fi
echo ""

# Gate B: Schema Validation
echo "--- Running AP Gate B: Schema Validation ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_b_schema_validation.py"; then
    echo "✓ Gate B PASSED"
else
    echo "✗ Gate B FAILED"
    EXIT_CODE=1
fi
echo ""

# Gate C: Negative Fixtures
echo "--- Running AP Gate C: Negative Fixtures ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_c_negative_fixtures.py"; then
    echo "✓ Gate C PASSED"
else
    echo "✗ Gate C FAILED"
    EXIT_CODE=1
fi
echo ""

# Gate D: No Execution Symbols
echo "--- Running AP Gate D: No Execution ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_d_no_execution.py"; then
    echo "✓ Gate D PASSED"
else
    echo "✗ Gate D FAILED"
    EXIT_CODE=1
fi
echo ""

# Gate E: Isolation
echo "--- Running AP Gate E: Isolation ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_e_isolation.py"; then
    echo "✓ Gate E PASSED"
else
    echo "✗ Gate E FAILED"
    EXIT_CODE=1
fi
echo ""

# Gate F: Snapshot
echo "--- Running AP Gate F: Snapshot ---"
if python3 "$SCRIPT_DIR/v11_ap_gate_f_snapshot.py"; then
    echo "✓ Gate F PASSED"
else
    echo "✗ Gate F FAILED"
    EXIT_CODE=1
fi
echo ""

# Summary
echo "================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ ALL ANSWERPACK GATES PASSED"
else
    echo "✗ SOME ANSWERPACK GATES FAILED"
fi
echo "================================================================"

exit $EXIT_CODE
