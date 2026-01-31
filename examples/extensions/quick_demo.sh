#!/bin/bash
# Quick Demo Script for Extension System
#
# This script demonstrates the complete extension system workflow:
# 1. Create extension packages
# 2. Start the server
# 3. Run acceptance tests
# 4. Show results
#
# Usage:
#   ./quick_demo.sh

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    if ! command -v python3 &> /dev/null; then
        print_error "python3 is not installed"
        exit 1
    fi
    print_success "python3 found: $(python3 --version)"

    if ! command -v sqlite3 &> /dev/null; then
        print_error "sqlite3 is not installed"
        exit 1
    fi
    print_success "sqlite3 found: $(sqlite3 --version)"

    # Check if requests module is available
    if ! python3 -c "import requests" 2>/dev/null; then
        print_error "Python 'requests' module not found"
        print_info "Install it with: pip3 install requests"
        exit 1
    fi
    print_success "Python requests module found"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

print_header "AgentOS Extension System - Quick Demo"
echo "Project: $PROJECT_ROOT"
echo "Examples: $SCRIPT_DIR"

# Step 1: Check prerequisites
check_prerequisites

# Step 2: Create extension packages
print_header "Step 1: Creating Extension Packages"
cd "$SCRIPT_DIR"

if [ ! -f "hello-extension.zip" ] || [ ! -f "postman-extension.zip" ]; then
    print_info "Generating extension packages..."
    python3 create_extensions.py
    print_success "Extension packages created"
else
    print_info "Extension packages already exist"
    print_success "Using existing packages"
fi

# List created packages
echo ""
echo "Created packages:"
ls -lh *.zip | awk '{print "  - " $9 " (" $5 ")"}'

# Step 3: Initialize database (if needed)
print_header "Step 2: Initializing Database"
cd "$PROJECT_ROOT"

if [ ! -f "store/registry.sqlite" ]; then
    print_info "Creating database..."
    python3 -c "from agentos.store import init_db; init_db()"
    print_success "Database initialized"
else
    print_info "Database already exists"
    print_success "Using existing database"
fi

# Step 4: Start server in background
print_header "Step 3: Starting AgentOS Server"

# Check if server is already running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_info "Server is already running"
    print_success "Server is healthy"
    SERVER_STARTED=false
else
    print_info "Starting server in background..."
    python3 -m agentos.webui.server > /tmp/agentos_demo.log 2>&1 &
    SERVER_PID=$!
    SERVER_STARTED=true

    # Wait for server to be ready
    print_info "Waiting for server to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "Server is ready (PID: $SERVER_PID)"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            print_error "Server failed to start"
            cat /tmp/agentos_demo.log
            exit 1
        fi
    done
fi

# Step 5: Run acceptance tests
print_header "Step 4: Running Acceptance Tests"
cd "$SCRIPT_DIR"

print_info "Running end-to-end tests..."
echo ""

if python3 e2e_acceptance_test.py --verbose; then
    print_success "All tests passed!"
else
    print_error "Some tests failed"

    # Cleanup
    if [ "$SERVER_STARTED" = true ]; then
        print_info "Stopping server..."
        kill $SERVER_PID 2>/dev/null || true
    fi

    exit 1
fi

# Step 6: Show results
print_header "Step 5: Verification"

print_info "Checking installed extensions..."
EXTENSIONS=$(curl -s http://localhost:8000/api/extensions | python3 -c "
import sys, json
data = json.load(sys.stdin)
extensions = data.get('extensions', [])
for ext in extensions:
    print(f'  - {ext[\"id\"]} (v{ext[\"version\"]}) - {ext[\"status\"]}')
")

if [ -z "$EXTENSIONS" ]; then
    print_info "No extensions currently installed (this is expected after cleanup)"
else
    echo "$EXTENSIONS"
fi

# Step 7: Show manual testing instructions
print_header "Step 6: Manual Testing"

echo "You can now manually test the extensions:"
echo ""
echo "1. Open the WebUI:"
echo "   ${GREEN}http://localhost:8000/extensions${NC}"
echo ""
echo "2. Install an extension:"
echo "   - Click 'Install Extension'"
echo "   - Select ${YELLOW}hello-extension.zip${NC}"
echo "   - Watch the installation progress"
echo ""
echo "3. Test slash commands in chat:"
echo "   ${GREEN}http://localhost:8000/chat${NC}"
echo "   - Type: ${YELLOW}/hello${NC}"
echo "   - Type: ${YELLOW}/hello AgentOS${NC}"
echo ""
echo "4. View extension details:"
echo "   - Click on the installed extension"
echo "   - View capabilities and documentation"
echo ""
echo "5. Test API endpoints:"
echo "   ${YELLOW}curl http://localhost:8000/api/extensions | jq${NC}"
echo ""

# Cleanup option
print_header "Cleanup"

if [ "$SERVER_STARTED" = true ]; then
    echo "Server is running in background (PID: $SERVER_PID)"
    echo ""
    echo "To stop the server:"
    echo "  ${YELLOW}kill $SERVER_PID${NC}"
    echo ""
    echo "Or press Ctrl+C to stop now..."
    echo ""

    # Wait for user interrupt
    trap "echo ''; print_info 'Stopping server...'; kill $SERVER_PID 2>/dev/null || true; print_success 'Server stopped'; exit 0" INT

    # Keep script running
    wait $SERVER_PID 2>/dev/null || true
else
    echo "Server was already running before the demo started."
    echo "You may want to restart it to apply any changes."
fi

print_header "Demo Complete!"
echo "Thank you for trying the AgentOS Extension System!"
echo ""
