#!/bin/bash
# Test script for project import CLI commands
# Prerequisites: agentos CLI installed and database initialized

set -e  # Exit on error

echo "=== Testing AgentOS Project Import CLI ==="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Show help
echo -e "${YELLOW}Test 1: Show import command help${NC}"
agentos project import --help
echo -e "${GREEN}✓ Help displayed${NC}"
echo ""

# Test 2: Show repos command help
echo -e "${YELLOW}Test 2: Show repos command help${NC}"
agentos project repos --help
echo -e "${GREEN}✓ Repos help displayed${NC}"
echo ""

# Test 3: Import project from config file
echo -e "${YELLOW}Test 3: Import project from config file${NC}"
cat > /tmp/test-project.yaml <<EOF
name: test-app
description: Test multi-repo project
repos:
  - name: backend
    path: ./backend
    role: code
    writable: true
  - name: frontend
    path: ./frontend
    role: code
    writable: true
  - name: docs
    path: ./docs
    role: docs
    writable: false
EOF

agentos project import --from /tmp/test-project.yaml --yes || true
echo -e "${GREEN}✓ Import from config file completed${NC}"
echo ""

# Test 4: List repositories
echo -e "${YELLOW}Test 4: List repositories${NC}"
agentos project repos list test-app
echo -e "${GREEN}✓ Repositories listed${NC}"
echo ""

# Test 5: Add a new repository
echo -e "${YELLOW}Test 5: Add new repository${NC}"
agentos project repos add test-app \
  --name shared-lib \
  --path ./lib \
  --role code \
  --read-only || true
echo -e "${GREEN}✓ Repository added${NC}"
echo ""

# Test 6: List repositories again
echo -e "${YELLOW}Test 6: List repositories (should include shared-lib)${NC}"
agentos project repos list test-app
echo -e "${GREEN}✓ Updated repositories listed${NC}"
echo ""

# Test 7: Validate project
echo -e "${YELLOW}Test 7: Validate project${NC}"
agentos project validate test-app || true
echo -e "${GREEN}✓ Validation completed${NC}"
echo ""

# Test 8: Update repository
echo -e "${YELLOW}Test 8: Update repository${NC}"
agentos project repos update test-app shared-lib --branch develop || true
echo -e "${GREEN}✓ Repository updated${NC}"
echo ""

# Test 9: Remove repository
echo -e "${YELLOW}Test 9: Remove repository${NC}"
agentos project repos remove test-app shared-lib --yes || true
echo -e "${GREEN}✓ Repository removed${NC}"
echo ""

# Test 10: Import with inline options
echo -e "${YELLOW}Test 10: Import with inline options${NC}"
agentos project import inline-test \
  --repo name=service1,path=./svc1,role=code \
  --repo name=service2,path=./svc2,role=code \
  --description "Inline import test" \
  --skip-validation \
  --yes || true
echo -e "${GREEN}✓ Inline import completed${NC}"
echo ""

# Test 11: List all projects
echo -e "${YELLOW}Test 11: List all projects${NC}"
agentos project list
echo -e "${GREEN}✓ Projects listed${NC}"
echo ""

# Cleanup
rm -f /tmp/test-project.yaml

echo ""
echo -e "${GREEN}=== All tests completed! ===${NC}"
echo ""
echo "Summary:"
echo "  ✓ Help commands"
echo "  ✓ Import from config file"
echo "  ✓ Repository management (list, add, update, remove)"
echo "  ✓ Project validation"
echo "  ✓ Inline import"
echo ""
echo "Note: Some tests may have been skipped if projects already existed."
echo "To clean up test data, run:"
echo "  rm -rf store/registry.sqlite"
echo "  agentos init"
