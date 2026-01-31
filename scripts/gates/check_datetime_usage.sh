#!/bin/bash
# Datetime Usage Check Script
# Enforces Time & Timestamp Contract - prevents datetime.utcnow() and datetime.now() regression
#
# Part of Task #12: CI Gate for datetime usage prevention

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE_SCRIPT="$SCRIPT_DIR/gate_datetime_usage.py"

# Check if Python gate exists
if [ ! -f "$GATE_SCRIPT" ]; then
    echo "Error: Datetime usage gate script not found at: $GATE_SCRIPT"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

echo "🕐 Running Time & Timestamp Contract Enforcement..."
echo "Checking for forbidden datetime usage patterns..."
echo ""

# Run the Python gate
python3 "$GATE_SCRIPT" "$@"
