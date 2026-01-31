#!/bin/bash
# Test the datetime usage gate

set -e

echo "Testing datetime usage gate..."
echo ""

# Create temporary test directory
TEST_DIR="/tmp/datetime_gate_test_$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# Create a minimal agentos structure for testing
mkdir -p agentos/core

echo "Creating test cases..."

# Test case 1: Should fail - datetime.utcnow()
cat > agentos/core/bad_utcnow.py <<'EOF'
from datetime import datetime

def get_timestamp():
    # This should be flagged
    timestamp = datetime.utcnow()
    return timestamp
EOF

# Test case 2: Should fail - datetime.now() without tz
cat > agentos/core/bad_now.py <<'EOF'
from datetime import datetime

def get_timestamp():
    # This should be flagged
    timestamp = datetime.now()
    return timestamp
EOF

# Test case 3: Should pass - clock.utc_now()
cat > agentos/core/good_clock.py <<'EOF'
from agentos.core.time import utc_now

def get_timestamp():
    # This is correct
    timestamp = utc_now()
    return timestamp
EOF

# Test case 4: Should pass - datetime.now(timezone.utc)
cat > agentos/core/good_now_tz.py <<'EOF'
from datetime import datetime, timezone

def get_timestamp():
    # This is allowed (but clock.utc_now() is preferred)
    timestamp = datetime.now(timezone.utc)
    return timestamp
EOF

# Test case 5: Should pass - datetime.now(tz=...)
cat > agentos/core/good_now_tz_kwarg.py <<'EOF'
from datetime import datetime, timezone

def get_timestamp():
    # This is allowed
    timestamp = datetime.now(tz=timezone.utc)
    return timestamp
EOF

echo ""
echo "Test 1: Detect datetime.utcnow()..."
if grep -q "datetime\.utcnow()" agentos/core/bad_utcnow.py; then
    echo "✅ Pattern detected correctly"
else
    echo "❌ Failed to detect pattern"
fi

echo ""
echo "Test 2: Detect datetime.now() without tz..."
if grep "datetime\.now()" agentos/core/bad_now.py | grep -qv "timezone"; then
    echo "✅ Pattern detected correctly"
else
    echo "❌ Failed to detect pattern"
fi

echo ""
echo "Test 3: Allow clock.utc_now()..."
if ! grep -q "datetime\.utcnow()" agentos/core/good_clock.py; then
    echo "✅ Correctly allowed"
else
    echo "❌ False positive"
fi

echo ""
echo "Test 4: Allow datetime.now(timezone.utc)..."
if grep "datetime\.now" agentos/core/good_now_tz.py | grep -q "timezone"; then
    echo "✅ Correctly allowed"
else
    echo "❌ False positive"
fi

echo ""
echo "Test 5: Allow datetime.now(tz=...)..."
if grep "datetime\.now" agentos/core/good_now_tz_kwarg.py | grep -q "tz="; then
    echo "✅ Correctly allowed"
else
    echo "❌ False positive"
fi

# Cleanup
cd /
rm -rf "$TEST_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Gate testing complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
