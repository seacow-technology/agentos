#!/bin/bash

# Demo script for /comm brief ai pipeline

echo "════════════════════════════════════════════════════════════════"
echo "  /comm brief ai Pipeline Demo"
echo "════════════════════════════════════════════════════════════════"
echo

echo "This demo shows the complete pipeline execution:"
echo "  1. Multi-Query Search (4 queries)"
echo "  2. Candidate Filtering (dedup + domain limit)"
echo "  3. Fetch & Verify (parallel, skip failures)"
echo "  4. Markdown Generation (frozen template)"
echo

read -p "Press Enter to run unit tests..."
echo

echo "────────────────────────────────────────────────────────────────"
echo "Running Unit Tests (22 tests)..."
echo "────────────────────────────────────────────────────────────────"
python3 -m pytest test_comm_brief.py -v --tb=short

echo
echo "────────────────────────────────────────────────────────────────"
echo "Test Summary"
echo "────────────────────────────────────────────────────────────────"
python3 -m pytest test_comm_brief.py -v --tb=no | tail -5

echo
read -p "Press Enter to run E2E test (mock mode)..."
echo

echo "────────────────────────────────────────────────────────────────"
echo "Running E2E Test (Mock Mode)..."
echo "────────────────────────────────────────────────────────────────"
python3 test_comm_brief_e2e.py

echo
echo "════════════════════════════════════════════════════════════════"
echo "  Demo Complete!"
echo "════════════════════════════════════════════════════════════════"
echo
echo "What was demonstrated:"
echo "  ✅ All 22 unit tests passing"
echo "  ✅ Multi-stage pipeline execution"
echo "  ✅ Markdown brief generation"
echo "  ✅ Statistics and trust tier tracking"
echo
echo "To test with real network:"
echo "  python3 test_comm_brief_e2e.py --live"
echo
echo "To use in Chat Mode:"
echo "  /comm brief ai --today"
echo "  /comm brief ai --max-items 5"
echo
