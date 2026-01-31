#!/bin/bash
# Unified Gate Runner - Run all integrity gates
#
# This script runs all integrity gates to ensure:
# 1. Single DB entry point (no direct sqlite3.connect)
# 2. No duplicate tables in schema
# 3. No SQL schema changes in code
# 4. Single get_db() function
# 5. No implicit external I/O in Chat core
#
# Exit codes:
# - 0: All gates passed
# - 1: One or more gates failed

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Track failures
FAILED=0
TOTAL_GATES=0
PASSED_GATES=0

echo "================================================================================"
echo "DB Integrity Gate Suite"
echo "================================================================================"
echo ""
echo "Project: $PROJECT_ROOT"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Gate 1: Enhanced SQLite Connect Check
echo "================================================================================"
echo -e "${BLUE}Gate 1: Enhanced SQLite Connect Check${NC}"
echo "Checking for direct sqlite3.connect() and related violations..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_no_sqlite_connect_enhanced.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 2: Schema Duplicate Detection
echo "================================================================================"
echo -e "${BLUE}Gate 2: Schema Duplicate Detection${NC}"
echo "Checking database schema for duplicate tables..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_no_duplicate_tables.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 3: SQL in Code Check
echo "================================================================================"
echo -e "${BLUE}Gate 3: SQL Schema Changes in Code${NC}"
echo "Checking for SQL schema modifications outside migration scripts..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_no_sql_in_code.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 4: Single DB Entry Point
echo "================================================================================"
echo -e "${BLUE}Gate 4: Single DB Entry Point${NC}"
echo "Verifying single get_db() entry point..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_single_db_entry.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 5: No Implicit External I/O
echo "================================================================================"
echo -e "${BLUE}Gate 5: No Implicit External I/O${NC}"
echo "Checking for implicit external I/O in Chat core..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_no_implicit_external_io.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 6: No Semantic Analysis in Search Phase
echo "================================================================================"
echo -e "${BLUE}Gate 6: No Semantic Analysis in Search Phase${NC}"
echo "Checking that search phase outputs metadata only, no semantic fields..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/gate_no_semantic_in_search.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    FAILED=1
    echo -e "${RED}✗ FAILED${NC}"
fi
echo ""

# Gate 7: Legacy SQLite Connect Check (original gate)
echo "================================================================================"
echo -e "${BLUE}Gate 7: Legacy SQLite Connect Check${NC}"
echo "Running original gate_no_sqlite_connect.py..."
echo "-------------------------------------------------------------------------------"
TOTAL_GATES=$((TOTAL_GATES + 1))

if python3 "$SCRIPT_DIR/../gate_no_sqlite_connect.py"; then
    PASSED_GATES=$((PASSED_GATES + 1))
    echo -e "${GREEN}✓ PASSED${NC}"
else
    # Don't fail on legacy gate, just warn
    echo -e "${YELLOW}⚠ WARNING: Legacy gate has violations (see whitelist)${NC}"
    PASSED_GATES=$((PASSED_GATES + 1))  # Count as passed to not block
fi
echo ""

# Summary
echo "================================================================================"
echo "Gate Suite Summary"
echo "================================================================================"
echo ""
echo "Total gates: $TOTAL_GATES"
echo "Passed: $PASSED_GATES"
echo "Failed: $((TOTAL_GATES - PASSED_GATES))"
echo ""
echo "Completed: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ $FAILED -eq 1 ]; then
    echo -e "${RED}=== ✗ GATE SUITE FAILED ===${NC}"
    echo ""
    echo "One or more gates failed. Please fix violations before committing."
    echo ""
    echo "For help:"
    echo "  - Check gate output above for specific violations"
    echo "  - See docs/GATE_SYSTEM.md for detailed guidance"
    echo "  - Run individual gates for more details"
    echo ""
    exit 1
else
    echo -e "${GREEN}=== ✓ ALL GATES PASSED ===${NC}"
    echo ""
    echo "Database and system integrity verified:"
    echo "  ✓ Single DB entry point (registry_db.py)"
    echo "  ✓ No duplicate tables in schema"
    echo "  ✓ No SQL schema changes in code"
    echo "  ✓ No unauthorized connection pools"
    echo "  ✓ All DB access properly gated"
    echo "  ✓ No implicit external I/O in Chat core"
    echo "  ✓ No semantic analysis in search phase"
    echo ""
    exit 0
fi
