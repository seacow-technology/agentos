#!/bin/bash
# Gate D: 静态扫描 - 禁止执行符号 (v0.9 Rules)
#
# 验证:
# 1. 扫描所有 YAML 文件（docs/content/rules/**/*.yaml）
# 2. 扫描所有 JSON 文件（examples/rules/**/*.json，如果存在）
# 3. 禁止字段：execute, run, shell, bash, python, powershell, subprocess, exec, invoke, script, command_line
# 4. 排除注释和 description 字段中的合法使用
#
# 用法:
#     bash scripts/gates/v09_gate_d_no_execution_symbols.sh

set -e

echo "============================================================"
echo "Gate D: 静态扫描 - 禁止执行符号 (v0.9)"
echo "============================================================"
echo

# Forbidden keywords (execution-related)
FORBIDDEN_KEYWORDS=(
    "execute:"
    "run:"
    "shell:"
    "bash:"
    "python:"
    "powershell:"
    "subprocess:"
    "command_line:"
    "script:"
    "exec:"
)

VIOLATIONS_FOUND=0

# Scan YAML files
echo "Scanning YAML files..."
YAML_DIR="docs/content/rules"

if [ ! -d "$YAML_DIR" ]; then
    echo "❌ Rules directory not found: $YAML_DIR"
    exit 1
fi

# Exclude README, catalog, and authoring-guide (they may mention keywords in documentation)
YAML_FILES=$(find "$YAML_DIR" -name "*.yaml" -o -name "*.yml" | grep -v README | grep -v catalog | grep -v authoring-guide)

for keyword in "${FORBIDDEN_KEYWORDS[@]}"; do
    echo "  Checking for forbidden keyword: $keyword"
    
    # Search in YAML files
    if echo "$YAML_FILES" | xargs grep -n "$keyword" 2>/dev/null; then
        echo "    ❌ Found forbidden keyword '$keyword' in YAML files"
        VIOLATIONS_FOUND=$((VIOLATIONS_FOUND + 1))
    fi
done

# Scan JSON files (if they exist)
JSON_DIR="examples/rules"

if [ -d "$JSON_DIR" ]; then
    echo
    echo "Scanning JSON files..."
    
    JSON_FILES=$(find "$JSON_DIR" -name "*.json" 2>/dev/null || true)
    
    if [ -n "$JSON_FILES" ]; then
        for keyword in "${FORBIDDEN_KEYWORDS[@]}"; do
            echo "  Checking for forbidden keyword: $keyword"
            
            # Search in JSON files
            if echo "$JSON_FILES" | xargs grep -n "$keyword" 2>/dev/null; then
                echo "    ❌ Found forbidden keyword '$keyword' in JSON files"
                VIOLATIONS_FOUND=$((VIOLATIONS_FOUND + 1))
            fi
        done
    else
        echo "  (No JSON files found - OK, they are optional)"
    fi
else
    echo "  (No JSON directory found - OK, JSON files are optional)"
fi

echo
echo "============================================================"

if [ $VIOLATIONS_FOUND -eq 0 ]; then
    echo "✅ Gate D: PASS - No forbidden execution symbols found"
    echo "============================================================"
    exit 0
else
    echo "❌ Gate D: FAIL - Found $VIOLATIONS_FOUND violation(s)"
    echo "============================================================"
    exit 1
fi
