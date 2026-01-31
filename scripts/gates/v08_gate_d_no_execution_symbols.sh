#!/bin/bash
# Gate D: 静态扫描 - 禁止执行符号 (v0.8 Commands)
#
# 扫描范围:
#   - docs/content/commands/**/*.yaml
#   - examples/commands/**/*.json (如果存在)
#
# 禁止符号:
#   - execute, run, shell, bash, python, cmd:, powershell, subprocess
#   - exec, invoke, script, command_line
#
# 注意: 只扫描字段值，避免误伤注释

set -e

echo "============================================================"
echo "Gate D: 静态扫描 - 禁止执行符号 (v0.8)"
echo "============================================================"
echo ""

# 定义禁止的执行符号（不包括 "description" 等文档字段）
FORBIDDEN_PATTERNS=(
    'execute:'
    'run:'
    'shell:'
    'bash:'
    'python:'
    'powershell:'
    'subprocess:'
    'exec:'
    'invoke:'
    'script:'
    'command_line:'
    'executable:'
    'cmd:'
)

VIOLATIONS_FOUND=0
TOTAL_FILES=0

# 扫描 YAML 文件
echo "Scanning YAML files in docs/content/commands/..."
if [ -d "docs/content/commands" ]; then
    while IFS= read -r file; do
        TOTAL_FILES=$((TOTAL_FILES + 1))
        
        for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
            # 使用 grep 检查，排除注释行（# 开头）和 description 字段
            if grep -n "$pattern" "$file" | grep -v '^\s*#' | grep -v 'description:' > /dev/null 2>&1; then
                echo "❌ VIOLATION in $file:"
                grep -n "$pattern" "$file" | grep -v '^\s*#' | grep -v 'description:' | head -3
                VIOLATIONS_FOUND=$((VIOLATIONS_FOUND + 1))
            fi
        done
    done < <(find docs/content/commands -type f \( -name "*.yaml" -o -name "*.yml" \))
else
    echo "⚠️  Directory not found: docs/content/commands"
fi

# 扫描 JSON 文件（如果存在）
if [ -d "examples/commands" ]; then
    echo ""
    echo "Scanning JSON files in examples/commands/..."
    while IFS= read -r file; do
        TOTAL_FILES=$((TOTAL_FILES + 1))
        
        for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
            # JSON 中只检查字段名，不检查 description 内容
            field="${pattern%:}"
            if grep -n "\"$field\"" "$file" | grep -v "description" > /dev/null 2>&1; then
                echo "❌ VIOLATION in $file:"
                grep -n "\"$field\"" "$file" | head -3
                VIOLATIONS_FOUND=$((VIOLATIONS_FOUND + 1))
            fi
        done
    done < <(find examples/commands -type f -name "*.json")
fi

echo ""
echo "============================================================"
echo "Scan Results:"
echo "  Total files scanned: $TOTAL_FILES"
echo "  Violations found: $VIOLATIONS_FOUND"
echo "============================================================"

if [ $VIOLATIONS_FOUND -gt 0 ]; then
    echo ""
    echo "❌ Gate D: FAIL - Found execution symbols in command definitions"
    echo ""
    echo "🚨 RED LINE C1 VIOLATION: Commands must not contain executable payload"
    echo ""
    exit 1
else
    echo ""
    echo "✅ Gate D: PASS - No execution symbols found"
    echo ""
    exit 0
fi
