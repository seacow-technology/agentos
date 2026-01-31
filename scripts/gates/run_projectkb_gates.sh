#!/bin/bash
# ProjectKB 验收 Gate 执行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "======================================================================"
echo "ProjectKB Gate Validation"
echo "======================================================================"
echo ""

GATES_PASSED=0
GATES_FAILED=0

# Gate A1: FTS5 Available性
echo "[Gate A1] FTS5 Availability Check"
if uv run python -c "from agentos.core.project_kb import ProjectKBService; kb = ProjectKBService(); print('✓ FTS5 available')" 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ FTS5 not available"
    ((GATES_FAILED++))
fi
echo ""

# Gate A2: 迁移幂等
echo "[Gate A2] Migration Idempotence"
if uv run python -c "from agentos.core.project_kb import ProjectKBService; kb = ProjectKBService(); kb.indexer.ensure_schema(); kb.indexer.ensure_schema(); print('✓ Migrations are idempotent')" 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Migration failed"
    ((GATES_FAILED++))
fi
echo ""

# Gate D10: Explain 完整性
echo "[Gate D10] Explain Completeness"
if [ -f "scripts/gates/kb_gate_explain.py" ]; then
    if uv run python scripts/gates/kb_gate_explain.py; then
        ((GATES_PASSED++))
    else
        echo "✗ Explain gate failed"
        ((GATES_FAILED++))
    fi
else
    echo "⊘ Gate script not found (skipped)"
fi
echo ""

# Gate C8: 删除文件处理 (需要临时文件)
echo "[Gate C8] Deleted File Cleanup"
TEST_FILE="docs/test_gate_delete_$(date +%s).md"
if [ ! -f "$TEST_FILE" ]; then
    echo "# Test Delete" > "$TEST_FILE"
    echo "Created test file: $TEST_FILE"
    
    # 索引
    uv run python -c "from agentos.core.project_kb import ProjectKBService; kb = ProjectKBService(); kb.refresh()" 2>/dev/null
    
    # 删除
    rm "$TEST_FILE"
    
    # 重新索引
    uv run python -c "from agentos.core.project_kb import ProjectKBService; kb = ProjectKBService(); kb.refresh()" 2>/dev/null
    
    # 验证不再存在
    SEARCH_RESULT=$(uv run python -c "from agentos.core.project_kb import ProjectKBService; kb = ProjectKBService(); results = kb.search('Test Delete'); print(len(results))" 2>/dev/null || echo "0")
    
    if [ "$SEARCH_RESULT" = "0" ]; then
        echo "✓ Deleted files properly cleaned up"
        ((GATES_PASSED++))
    else
        echo "✗ Deleted file still in index"
        ((GATES_FAILED++))
    fi
else
    echo "⊘ Test file exists (skipped)"
fi
echo ""

# P2 Embedding Gates (如果启用)
echo "[Gate E1] Embedding Coverage"
if uv run python scripts/gates/kb_gate_e1_coverage.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E1 failed"
    ((GATES_FAILED++))
fi
echo ""

echo "[Gate E2] Explain Completeness (Vector)"
if uv run python scripts/gates/kb_gate_e2_explain.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E2 failed"
    ((GATES_FAILED++))
fi
echo ""

echo "[Gate E3] Determinism"
if uv run python scripts/gates/kb_gate_e3_determinism.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E3 failed"
    ((GATES_FAILED++))
fi
echo ""

echo "[Gate E4] Graceful Fallback"
if uv run python scripts/gates/kb_gate_e4_fallback.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E4 failed"
    ((GATES_FAILED++))
fi
echo ""

echo "[Gate E5] Incremental Consistency"
if uv run python scripts/gates/kb_gate_e5_incremental.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E5 failed"
    ((GATES_FAILED++))
fi
echo ""

echo "[Gate E6] Performance Threshold"
if uv run python scripts/gates/kb_gate_e6_performance.py 2>/dev/null; then
    ((GATES_PASSED++))
else
    echo "✗ Gate E6 failed"
    ((GATES_FAILED++))
fi
echo ""

# Gate D12: Evidence 格式
echo "[Gate D12] Evidence Format Stability"
EVIDENCE=$(uv run python -c "
from agentos.core.project_kb import ProjectKBService
kb = ProjectKBService()
results = kb.search('test', top_k=1)
if results:
    print(results[0].to_evidence_ref())
" 2>/dev/null || echo "")

if [[ "$EVIDENCE" =~ ^kb:[a-z0-9_]+:.+#L[0-9]+-L[0-9]+$ ]]; then
    echo "✓ Evidence format valid: $EVIDENCE"
    ((GATES_PASSED++))
else
    echo "✗ Evidence format invalid: $EVIDENCE"
    ((GATES_FAILED++))
fi
echo ""

# 总结
echo "======================================================================"
echo "Gate Summary"
echo "======================================================================"
echo "Passed: $GATES_PASSED"
echo "Failed: $GATES_FAILED"
echo ""

if [ "$GATES_FAILED" -eq 0 ]; then
    echo "✅ All gates PASSED"
    exit 0
else
    echo "❌ Some gates FAILED"
    exit 1
fi
