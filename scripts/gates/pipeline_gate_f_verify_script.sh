#!/bin/bash
#
# Pipeline Gate P-F: 一键可复现验证
#
# 检查scripts/verify_pipeline.sh是否存在且可执行
#

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "======================================================================"
echo "Pipeline Gate P-F: 一键可复现验证"
echo "======================================================================"

VERIFY_SCRIPT="$PROJECT_ROOT/scripts/verify_pipeline.sh"

echo ""
echo "Checking verify_pipeline.sh..."

if [ ! -f "$VERIFY_SCRIPT" ]; then
    echo "❌ verify_pipeline.sh not found: $VERIFY_SCRIPT"
    exit 1
fi

if [ ! -x "$VERIFY_SCRIPT" ]; then
    echo "❌ verify_pipeline.sh is not executable"
    echo "   Run: chmod +x $VERIFY_SCRIPT"
    exit 1
fi

echo "✅ verify_pipeline.sh exists and is executable"

# 检查脚本内容是否正确
echo ""
echo "Checking verify_pipeline.sh content..."

REQUIRED_GATES=(
    "pipeline_gate_a_existence.py"
    "pipeline_gate_c_red_lines.sh"
    "pipeline_gate_e_snapshot.py"
)

MISSING=0

for gate in "${REQUIRED_GATES[@]}"; do
    if grep -q "$gate" "$VERIFY_SCRIPT"; then
        echo "   ✅ Calls $gate"
    else
        echo "   ❌ Missing call to $gate"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
echo "======================================================================"

if [ $MISSING -gt 0 ]; then
    echo "❌ Gate P-F FAILED: verify_pipeline.sh is incomplete"
    exit 1
else
    echo "✅ Gate P-F PASSED: verify_pipeline.sh is ready"
    exit 0
fi
