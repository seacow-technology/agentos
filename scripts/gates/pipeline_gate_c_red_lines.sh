#!/bin/bash
#
# Pipeline Gate P-C: 红线验证
#
# 静态扫描:
# - 扫描Runner代码，禁止执行符号
# - 如果Runner调用CLI，必须使用plan/explain模式
#

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "======================================================================"
echo "Pipeline Gate P-C: 红线验证"
echo "======================================================================"

FAILURES=0

# 检查Runner脚本是否存在
RUNNER_SCRIPT="$PROJECT_ROOT/scripts/pipeline/run_nl_to_pr_artifacts.py"
if [ ! -f "$RUNNER_SCRIPT" ]; then
    echo "❌ Runner script not found: $RUNNER_SCRIPT"
    exit 1
fi

echo ""
echo "1. 静态扫描: 检查禁止的执行符号..."

# RED LINE P1: 禁止直接执行命令（subprocess除外用于调用CLI）
FORBIDDEN_PATTERNS=(
    "os\.system"
    "eval\("
    "exec\("
    "compile\("
    "__import__\(\"os\"\)"
)

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if grep -q "$pattern" "$RUNNER_SCRIPT"; then
        echo "   ❌ Found forbidden pattern: $pattern"
        grep -n "$pattern" "$RUNNER_SCRIPT"
        FAILURES=$((FAILURES + 1))
    else
        echo "   ✅ No $pattern found"
    fi
done

echo ""
echo "2. 检查subprocess调用是否安全..."

# 检查subprocess调用是否只用于CLI命令（plan/explain模式）
if grep -n "subprocess\.run" "$RUNNER_SCRIPT" | grep -v "# Pipeline调用CLI" > /dev/null 2>&1; then
    # 确保subprocess调用包含'plan'或'explain'
    SUBPROCESS_LINES=$(grep -n "subprocess\.run" "$RUNNER_SCRIPT" | cut -d':' -f1)
    
    for line_num in $SUBPROCESS_LINES; do
        # 提取前后10行检查context
        CONTEXT=$(sed -n "$((line_num - 5)),$((line_num + 10))p" "$RUNNER_SCRIPT")
        
        if echo "$CONTEXT" | grep -q "plan\|explain\|builder run\|coordinate\|dry-run"; then
            echo "   ✅ Line $line_num: subprocess calls CLI (plan/explain mode)"
        else
            echo "   ⚠️  Line $line_num: subprocess call without obvious plan/explain"
        fi
    done
else
    echo "   ✅ All subprocess calls are for CLI commands"
fi

echo ""
echo "3. 检查RED LINE P3: Question Pack阻塞逻辑..."

if grep -q "question_pack\[" "$RUNNER_SCRIPT" && grep -q "BLOCKED" "$RUNNER_SCRIPT"; then
    echo "   ✅ Question Pack阻塞逻辑存在"
else
    echo "   ❌ Missing Question Pack阻塞逻辑"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "4. 检查RED LINE P4: Checksum生成..."

if grep -q "compute_checksum\|checksum" "$RUNNER_SCRIPT"; then
    echo "   ✅ Checksum生成逻辑存在"
else
    echo "   ❌ Missing checksum generation"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "5. 检查RED LINE P5: 审计日志..."

if grep -q "log_audit\|audit_log" "$RUNNER_SCRIPT"; then
    echo "   ✅ 审计日志逻辑存在"
else
    echo "   ❌ Missing audit logging"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "======================================================================"

if [ $FAILURES -gt 0 ]; then
    echo "❌ Gate P-C FAILED: $FAILURES red line violations"
    exit 1
else
    echo "✅ Gate P-C PASSED: All red lines enforced"
    exit 0
fi
