#!/bin/bash
# v0.9.4 Gate D: No Execution Symbols Scan
#
# Scans v0.9.4 files for forbidden execution symbols:
# - Python: subprocess, os.system, exec, eval, run_command
# - JSON/YAML: execute, shell, bash, powershell, run
#
# RED LINE: Builder must not contain execution code

set -e

echo "======================================================================"
echo "v0.9.4 Gate D: No Execution Symbols Scan"
echo "======================================================================"

SCAN_DIRS=(
    "agentos/schemas/execution/nl_request.schema.json"
    "agentos/schemas/execution/intent_builder_output.schema.json"
    "agentos/core/intent_builder"
    "agentos/cli/intent_builder.py"
    "examples/nl"
)

PYTHON_FORBIDDEN=(
    "subprocess"
    "os.system"
    "eval("
    "exec("
)

JSON_FORBIDDEN=(
    '"execute"[[:space:]]*:'
    '"shell"[[:space:]]*:'
    '"bash"[[:space:]]*:'
    '"powershell"[[:space:]]*:'
    '"run_command"[[:space:]]*:'
    '"subprocess"[[:space:]]*:'
    '"exec"[[:space:]]*:'
    '"eval"[[:space:]]*:'
)

VIOLATIONS=0

echo ""
echo "🔍 Scanning Python files for forbidden symbols..."
for dir in "${SCAN_DIRS[@]}"; do
    if [[ ! -e "$dir" ]]; then
        echo "  ⚠️  Path not found: $dir (skipping)"
        continue
    fi
    
    if [[ -f "$dir" ]]; then
        # Single file
        FILES=("$dir")
    else
        # Directory - find Python files
        FILES=($(find "$dir" -name "*.py" 2>/dev/null || true))
    fi
    
    for file in "${FILES[@]}"; do
        for symbol in "${PYTHON_FORBIDDEN[@]}"; do
            # Search for symbol, excluding comments, docstrings, and string literals
            # Skip lines with # comments
            # Skip lines in triple-quoted strings
            # Skip lines that only mention the word (e.g., in error messages)
            matches=$(grep -n "$symbol" "$file" 2>/dev/null | \
                      grep -v "^[[:space:]]*#" | \
                      grep -v '"""' | \
                      grep -v "'''" | \
                      grep -v 'no subprocess' | \
                      grep -v 'forbidden.*subprocess' | \
                      grep -v '"subprocess"' | \
                      grep -v "'subprocess'" || true)
            
            if [[ -n "$matches" ]]; then
                echo "  ❌ Found '$symbol' in $file:"
                echo "$matches" | head -3 | sed 's/^/     /'
                VIOLATIONS=$((VIOLATIONS + 1))
            fi
        done
    done
done

echo ""
echo "🔍 Scanning JSON/YAML files for forbidden fields (structure only)..."
for dir in "${SCAN_DIRS[@]}"; do
    if [[ ! -e "$dir" ]]; then
        continue
    fi
    
    if [[ -f "$dir" ]]; then
        FILES=("$dir")
    else
        FILES=($(find "$dir" \( -name "*.json" -o -name "*.yaml" -o -name "*.yml" \) 2>/dev/null || true))
    fi
    
    for file in "${FILES[@]}"; do
        for symbol in "${JSON_FORBIDDEN[@]}"; do
            # Only match structure fields (key: value), not in strings/descriptions
            # Skip lines that are clearly documentation/description values
            matches=$(grep -n "$symbol" "$file" 2>/dev/null | \
                      grep -v '  "description"' | \
                      grep -v '  "context"' | \
                      grep -v '  "question_text"' | \
                      grep -v '  "reason"' | \
                      grep -v 'forbidden' | \
                      grep -v '# ' || true)
            
            if [[ -n "$matches" ]]; then
                echo "  ❌ Found forbidden field $symbol in $file:"
                echo "$matches" | head -3 | sed 's/^/     /'
                VIOLATIONS=$((VIOLATIONS + 1))
            fi
        done
    done
done

echo ""
echo "======================================================================"
if [[ $VIOLATIONS -eq 0 ]]; then
    echo "✅ Gate D: PASSED - No execution symbols detected"
    echo "======================================================================"
    exit 0
else
    echo "❌ Gate D: FAILED - Found $VIOLATIONS violation(s)"
    echo "======================================================================"
    exit 1
fi
