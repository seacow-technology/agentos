#!/bin/bash
# Gate D: Registry 不拥有执行权 - 静态扫描

set -e

echo "============================================================"
echo "Gate D: Registry 不拥有执行权 - 静态扫描"
echo "============================================================"
echo

FAILED=0

# 扫描路径
SCAN_PATHS=(
    "agentos/core/content/registry.py"
    "agentos/core/content/facade.py"
    "agentos/core/content/activation.py"
)

# 禁止的关键词（作为方法名）
# 排除注释行（以 # 开头的行）
FORBIDDEN_METHODS=(
    "def execute("
    "def run("
    "def apply("
    "def dispatch("
    "def invoke("
)

# 检查每个文件
for file in "${SCAN_PATHS[@]}"; do
    if [ ! -f "$file" ]; then
        echo "⚠️  File not found: $file (skipped)"
        continue
    fi
    
    echo "Scanning: $file"
    
    for method in "${FORBIDDEN_METHODS[@]}"; do
        # 使用 grep 查找，排除注释行
        if grep -v "^\s*#" "$file" | grep -q "$method"; then
            echo "  ❌ Found forbidden method: $method"
            FAILED=1
        fi
    done
    
    if [ $FAILED -eq 0 ]; then
        echo "  ✅ No forbidden methods found"
    fi
    echo
done

# 检查 RED LINE 注释是否存在
echo "Checking for RED LINE comments..."
if grep -q "RED LINE.*does NOT execute" agentos/core/content/registry.py; then
    echo "  ✅ RED LINE comment found in registry.py"
else
    echo "  ❌ RED LINE comment missing in registry.py"
    FAILED=1
fi
echo

if [ $FAILED -eq 0 ]; then
    echo "============================================================"
    echo "✅ Gate D: PASS - No execution methods found"
    echo "============================================================"
    exit 0
else
    echo "============================================================"
    echo "❌ Gate D: FAIL - Found forbidden execution methods"
    echo "============================================================"
    exit 1
fi
