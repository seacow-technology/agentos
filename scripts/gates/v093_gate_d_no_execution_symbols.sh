#!/bin/bash
# v0.9.3 Gate D: No Execution Symbols

echo "======================================================================"
echo "v0.9.3 Gate D: No Execution Symbols"
echo "======================================================================"
echo ""

SCHEMA_DIR="agentos/schemas/evaluator"
EXAMPLES_DIR="examples/intents/evaluations"
CORE_DIR="agentos/core/evaluator"

PROHIBITED_PATTERNS=(
  "subprocess"
  "os\.system"
  "eval\("
  "exec\("
  "import subprocess"
  "shell=True"
  "\.run\("
  "Popen"
)

failed=0

for pattern in "${PROHIBITED_PATTERNS[@]}"; do
  echo "Scanning for pattern: $pattern"
  
  matches=$(grep -r "$pattern" "$SCHEMA_DIR" "$EXAMPLES_DIR" 2>/dev/null || true)
  
  if [ -n "$matches" ]; then
    echo "❌ FAILED: Found prohibited pattern: $pattern"
    echo "$matches"
    failed=1
  else
    echo "  ✓ Not found"
  fi
done

echo ""

if [ $failed -eq 0 ]; then
  echo "======================================================================"
  echo "✅ Gate D: PASSED"
  echo "======================================================================"
  exit 0
else
  echo "======================================================================"
  echo "❌ Gate D: FAILED"
  echo "======================================================================"
  exit 1
fi
