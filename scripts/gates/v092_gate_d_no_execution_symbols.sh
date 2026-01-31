#!/bin/bash
# v0.9.2 Gate D: Static Scan for Execution Symbols
#
# Scans Coordinator implementation code for forbidden execution symbols
# RED LINE enforcement: Coordinator must NOT execute, only plan

set -e

echo "======================================================================"
echo "v0.9.2 Gate D: Static Scan for Execution Symbols"
echo "======================================================================"

COORDINATOR_DIR="agentos/core/coordinator"
FORBIDDEN_PATTERNS=(
    "subprocess"
    "shell"
    "execute"
    "run_command"
    "git commit"
    "git push"
    "os.system"
    "eval("
    "exec("
)

if [ ! -d "$COORDINATOR_DIR" ]; then
    echo "⚠️  Coordinator directory not found: $COORDINATOR_DIR"
    echo "   (This is expected if implementation not started yet)"
    exit 0
fi

ALL_CLEAN=true

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    echo ""
    echo "Scanning for: $pattern"
    
    # Use grep with context
    if grep -r -n --include="*.py" "$pattern" "$COORDINATOR_DIR" 2>/dev/null; then
        echo "  ❌ FOUND forbidden pattern: $pattern"
        ALL_CLEAN=false
    else
        echo "  ✅ Pattern not found"
    fi
done

echo ""
echo "======================================================================"
if [ "$ALL_CLEAN" = true ]; then
    echo "✅ Gate D: PASSED - No execution symbols found"
    echo "======================================================================"
    exit 0
else
    echo "❌ Gate D: FAILED - Execution symbols detected"
    echo "======================================================================"
    exit 1
fi
