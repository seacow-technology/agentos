#!/bin/bash
# Verify Gate System Installation
#
# This script verifies that all gate system components are properly installed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0

echo "================================================================================"
echo -e "${BLUE}Gate System Installation Verification${NC}"
echo "================================================================================"
echo ""
echo "Project: $PROJECT_ROOT"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Function to check file exists
check_file() {
    local file="$1"
    local description="$2"
    local required="${3:-true}"

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        if [ "$required" = "true" ]; then
            echo -e "${RED}✗${NC} $description (missing: $file)"
            CHECKS_FAILED=$((CHECKS_FAILED + 1))
        else
            echo -e "${YELLOW}⚠${NC} $description (optional: $file)"
            CHECKS_WARNED=$((CHECKS_WARNED + 1))
        fi
        return 1
    fi
}

# Function to check file is executable
check_executable() {
    local file="$1"
    local description="$2"

    if [ -x "$file" ]; then
        echo -e "${GREEN}✓${NC} $description is executable"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $description is not executable"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        return 1
    fi
}

# Function to check Python script syntax
check_python_syntax() {
    local file="$1"
    local description="$2"

    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $description syntax OK"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $description has syntax errors"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        return 1
    fi
}

echo "=== Core Gate Scripts ==="
echo ""

check_file "$SCRIPT_DIR/gate_no_sqlite_connect_enhanced.py" "Enhanced SQLite Connect Gate"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/gate_no_sqlite_connect_enhanced.py" "gate_no_sqlite_connect_enhanced.py"
    check_python_syntax "$SCRIPT_DIR/gate_no_sqlite_connect_enhanced.py" "gate_no_sqlite_connect_enhanced.py"
fi
echo ""

check_file "$SCRIPT_DIR/gate_no_duplicate_tables.py" "Schema Duplicate Detection Gate"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/gate_no_duplicate_tables.py" "gate_no_duplicate_tables.py"
    check_python_syntax "$SCRIPT_DIR/gate_no_duplicate_tables.py" "gate_no_duplicate_tables.py"
fi
echo ""

check_file "$SCRIPT_DIR/gate_no_sql_in_code.py" "SQL in Code Detection Gate"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/gate_no_sql_in_code.py" "gate_no_sql_in_code.py"
    check_python_syntax "$SCRIPT_DIR/gate_no_sql_in_code.py" "gate_no_sql_in_code.py"
fi
echo ""

check_file "$SCRIPT_DIR/gate_single_db_entry.py" "Single DB Entry Point Gate"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/gate_single_db_entry.py" "gate_single_db_entry.py"
    check_python_syntax "$SCRIPT_DIR/gate_single_db_entry.py" "gate_single_db_entry.py"
fi
echo ""

echo "=== Infrastructure Scripts ==="
echo ""

check_file "$SCRIPT_DIR/run_all_gates.sh" "Unified Gate Runner"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/run_all_gates.sh" "run_all_gates.sh"
fi
echo ""

check_file "$SCRIPT_DIR/install_pre_commit_hook.sh" "Pre-commit Hook Installer"
if [ $? -eq 0 ]; then
    check_executable "$SCRIPT_DIR/install_pre_commit_hook.sh" "install_pre_commit_hook.sh"
fi
echo ""

echo "=== CI/CD Configuration ==="
echo ""

check_file "$PROJECT_ROOT/.github/workflows/gate-db-integrity.yml" "GitHub Actions Workflow"
echo ""

echo "=== Documentation ==="
echo ""

check_file "$PROJECT_ROOT/docs/GATE_SYSTEM.md" "Comprehensive Gate System Documentation"
check_file "$SCRIPT_DIR/README.md" "Quick Start Guide"
check_file "$PROJECT_ROOT/GATE_SYSTEM_IMPLEMENTATION_REPORT.md" "Implementation Report"
check_file "$PROJECT_ROOT/GATE_QUICK_REFERENCE.md" "Quick Reference Card"
echo ""

echo "=== Legacy Components ==="
echo ""

check_file "$PROJECT_ROOT/scripts/gate_no_sqlite_connect.py" "Legacy SQLite Connect Gate" "false"
echo ""

echo "=== Optional Components ==="
echo ""

check_file "$PROJECT_ROOT/.git/hooks/pre-commit" "Pre-commit Hook (installed)" "false"
if [ $? -eq 0 ]; then
    check_executable "$PROJECT_ROOT/.git/hooks/pre-commit" "pre-commit hook"
else
    echo -e "${YELLOW}  Note: Run './scripts/gates/install_pre_commit_hook.sh' to install${NC}"
fi
echo ""

echo "=== Functional Tests ==="
echo ""

# Test gate runner can be invoked
if [ -x "$SCRIPT_DIR/run_all_gates.sh" ]; then
    echo -n "Testing gate runner invocation... "
    if "$SCRIPT_DIR/run_all_gates.sh" --help >/dev/null 2>&1 || [ $? -eq 1 ]; then
        # Exit code 1 is expected if gates find violations
        echo -e "${GREEN}✓${NC} Can invoke run_all_gates.sh"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠${NC} Gate runner script exists but may have issues"
        CHECKS_WARNED=$((CHECKS_WARNED + 1))
    fi
else
    echo -e "${RED}✗${NC} Cannot invoke gate runner"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
fi
echo ""

# Test individual gates can be imported
for gate in gate_no_sqlite_connect_enhanced gate_no_duplicate_tables gate_no_sql_in_code gate_single_db_entry; do
    echo -n "Testing $gate.py import... "
    if python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); import $gate" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Can import $gate"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} Cannot import $gate"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
done
echo ""

echo "=== Summary ==="
echo ""
echo "Checks passed:  $CHECKS_PASSED"
echo "Checks warned:  $CHECKS_WARNED"
echo "Checks failed:  $CHECKS_FAILED"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}================================================================================"
    echo -e "Gate System Installation: VERIFIED ✓"
    echo -e "================================================================================${NC}"
    echo ""
    echo "All components are installed correctly."
    echo ""
    echo "Next steps:"
    echo "  1. Run gates: ./scripts/gates/run_all_gates.sh"
    echo "  2. Install hook: ./scripts/gates/install_pre_commit_hook.sh"
    echo "  3. Read docs: docs/GATE_SYSTEM.md"
    echo ""
    exit 0
else
    echo -e "${RED}================================================================================"
    echo -e "Gate System Installation: INCOMPLETE ✗"
    echo -e "================================================================================${NC}"
    echo ""
    echo "Some components are missing or have errors."
    echo "Please review the output above and fix the issues."
    echo ""
    exit 1
fi
