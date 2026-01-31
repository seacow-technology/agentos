#!/usr/bin/env bash
#
# v0.9.1 Gate D: Static Scan for Execution Symbols
#
# Scans intent JSON files for forbidden execution-related keywords.
# Excludes documentation files.

set -e

echo "============================================================"
echo "v0.9.1 Gate D: Static Scan for Execution Symbols"
echo "============================================================"

# Forbidden symbols (execution-related)
FORBIDDEN=(
    "subprocess"
    "command_line"
    "shell.*execute"
    "bash.*-c"
    "python.*-c"
    "powershell.*-Command"
    "os\\.system"
    "exec\\("
    "eval\\("
)

# Files to scan
SCAN_PATHS=(
    "examples/intents/*.json"
    "fixtures/intents/invalid/*.json"
)

# Exclusions (documentation)
EXCLUDE_DOCS=(
    "docs/execution/intent-authoring-guide.md"
    "docs/execution/intent-catalog.md"
    "README.md"
)

violations=0

for pattern in "${SCAN_PATHS[@]}"; do
    files=$(find $(dirname $pattern) -name "$(basename $pattern)" 2>/dev/null || true)
    
    if [ -z "$files" ]; then
        continue
    fi
    
    for file in $files; do
        echo ""
        echo "Scanning: $file"
        
        for symbol in "${FORBIDDEN[@]}"; do
            if grep -qE "$symbol" "$file"; then
                # Check if it's in a description/documentation field (allowed)
                if grep -E "\"(description|title|goal|reason)\".*$symbol" "$file" > /dev/null; then
                    echo "  ⚠️  Found '$symbol' in documentation field (allowed)"
                else
                    echo "  ❌ Found forbidden symbol: $symbol"
                    violations=$((violations + 1))
                fi
            fi
        done
        
        # Check for "execute" field (not in string values)
        if grep -qE '"execute"\s*:' "$file"; then
            echo "  ❌ Found forbidden field: \"execute\""
            violations=$((violations + 1))
        fi
        
        if [ $violations -eq 0 ]; then
            echo "  ✅ No execution symbols found"
        fi
    done
done

echo ""
echo "============================================================"
if [ $violations -eq 0 ]; then
    echo "✅ Gate D: PASSED (no execution symbols found)"
    echo "============================================================"
    exit 0
else
    echo "❌ Gate D: FAILED ($violations violation(s) found)"
    echo "============================================================"
    exit 1
fi
