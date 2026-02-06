#!/bin/bash
# Quick test runner for Gate Tests
# Usage: ./run_gate_tests.sh [options]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default options
VERBOSE="-v"
COVERAGE=""
CATEGORY=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE="--cov=agentos.core.chat.comm_commands --cov=agentos.core.chat.communication_adapter --cov=agentos.core.chat.guards --cov-report=term-missing"
            shift
            ;;
        --quiet)
            VERBOSE=""
            shift
            ;;
        --phase-gate)
            CATEGORY="::TestPhaseGate"
            shift
            ;;
        --ssrf)
            CATEGORY="::TestSSRFProtection"
            shift
            ;;
        --trust-tier)
            CATEGORY="::TestTrustTier"
            shift
            ;;
        --attribution)
            CATEGORY="::TestAttribution"
            shift
            ;;
        --content-fence)
            CATEGORY="::TestContentFence"
            shift
            ;;
        --audit)
            CATEGORY="::TestAudit"
            shift
            ;;
        --integration)
            CATEGORY="::TestIntegration"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --coverage         Run with coverage report"
            echo "  --quiet            Minimal output"
            echo "  --phase-gate       Run only Phase Gate tests"
            echo "  --ssrf             Run only SSRF Protection tests"
            echo "  --trust-tier       Run only Trust Tier tests"
            echo "  --attribution      Run only Attribution tests"
            echo "  --content-fence    Run only Content Fence tests"
            echo "  --audit            Run only Audit tests"
            echo "  --integration      Run only Integration tests"
            echo "  --help             Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                          # Run all tests"
            echo "  $0 --coverage               # Run with coverage"
            echo "  $0 --phase-gate             # Run only Phase Gate tests"
            echo "  $0 --coverage --attribution # Run Attribution tests with coverage"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate up to project root: tests -> chat -> core -> agentos -> root
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found at .venv/${NC}"
    exit 1
fi

# Print header
echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Running Gate Tests - Chat ↔ CommunicationOS Integration${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo ""

if [ -n "$CATEGORY" ]; then
    echo -e "${YELLOW}Category: $(echo $CATEGORY | sed 's/::Test//')${NC}"
fi

if [ -n "$COVERAGE" ]; then
    echo -e "${YELLOW}Coverage: Enabled${NC}"
fi

echo ""

# Run tests
TEST_FILE="agentos/core/chat/tests/test_comm_integration_gates.py${CATEGORY}"

if python -m pytest "$TEST_FILE" $VERBOSE $COVERAGE --tb=short; then
    echo ""
    echo -e "${GREEN}==================================================================${NC}"
    echo -e "${GREEN}✅ All tests passed successfully!${NC}"
    echo -e "${GREEN}==================================================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}==================================================================${NC}"
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo -e "${RED}==================================================================${NC}"
    exit 1
fi
